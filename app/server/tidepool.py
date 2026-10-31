"""Keeps one Tidepool data set in step with the log (okf/features/tidepool-sync.md, okf/architecture/tidepool-client.md).
Only what was logged, each kind only when switched on (okf/rules/tidepool-sends-what-was-logged.md); the login stays
on this server (okf/rules/tidepool-login-server-only.md)."""
import hashlib
import json
import logging
import os
import threading
from datetime import date, datetime, timedelta, timezone

import requests

from . import core, db

log = logging.getLogger("tidepool")
SERVERS = {"test": "https://external.integration.tidepool.org", "tidepool": "https://api.tidepool.org"}
SERVER_NAMES = {"test": "Tidepool's test server", "tidepool": "Tidepool"}
CLIENT, VERSION = "app.kitchencarbs", "1.0.0"
DEDUPLICATOR = "org.tidepool.deduplicator.dataset.delete.origin"
KINDS = ("carbs", "bg", "insulin")
SYNC_EVERY_S, SETTLE_S, BATCH = 300, 20, 1000
BASAL_KINDS = {"basal", "long"}   # everything else typed is a bolus (okf/architecture/tidepool-client.md)
BASAL_HOURS = 24   # default spread of a long-acting dose; a parent sets 1-168 (Tidepool's longest basal is 7 days)

_wake = threading.Event()
_lock = threading.Lock()
_session = {}   # {"key": (server, email), "token": ..., "userid": ...}: kept in memory only


class TidepoolError(Exception):
    pass


def enabled() -> bool:
    """QA's database is a copy of production's, Tidepool login included: it never sends."""
    return os.environ.get("KC_ENV", "prod") != "qa"


def config(c) -> dict:
    g = lambda k, d=None: db.get_setting(c, "tp_" + k, d)
    kinds = json.loads(g("kinds", '{"carbs": true, "bg": false, "insulin": false}'))
    return {"on": g("on") == "on", "server": g("server", "test"), "email": g("email", ""), "password": g("password", ""),
            "target": g("target", ""), "from": g("from") or (date.today() - timedelta(days=30)).isoformat(),
            "kinds": {k: bool(kinds.get(k)) for k in KINDS},
            "basal_hours": int(g("basal_hours") or BASAL_HOURS), "dataset": g("dataset", ""), "userid": g("userid", ""),
            "last_sync": g("last_sync"), "last_error": g("last_error"), "sent": c.execute("SELECT COUNT(*) FROM tidepool_sent").fetchone()[0]}


def public(c) -> dict:
    """For the settings screen: everything but the password."""
    cfg = config(c)
    return {**{k: v for k, v in cfg.items() if k != "password"}, "password_saved": bool(cfg["password"]),
            "available": enabled(), "server_name": SERVER_NAMES.get(cfg["server"], cfg["server"])}


# ----- HTTP -----
def login(server: str, email: str, password: str) -> tuple[str, str]:
    try:
        r = requests.post(SERVERS[server] + "/auth/login", auth=(email, password), timeout=20)
    except requests.RequestException as e:
        raise TidepoolError(f"Couldn't reach {SERVER_NAMES[server]}: {e.__class__.__name__}") from e
    if r.status_code == 401:
        raise TidepoolError(f"{SERVER_NAMES[server]} didn't accept that email and password.")
    if r.status_code != 200 or not r.headers.get("x-tidepool-session-token"):
        raise TidepoolError(f"{SERVER_NAMES[server]} sign-in failed ({r.status_code}).")
    return r.headers["x-tidepool-session-token"], r.json().get("userid", "")


def _call(cfg, method, path, body=None, retry=True):
    key = (cfg["server"], cfg["email"])
    if _session.get("key") != key:
        token, userid = login(cfg["server"], cfg["email"], cfg["password"])
        _session.update(key=key, token=token, userid=userid)
    try:
        r = requests.request(method, SERVERS[cfg["server"]] + path, json=body, timeout=30,
                             headers={"X-Tidepool-Session-Token": _session["token"]})
    except requests.RequestException as e:
        raise TidepoolError(f"Couldn't reach {SERVER_NAMES[cfg['server']]}: {e.__class__.__name__}") from e
    if r.status_code == 401 and retry:   # the session ended: sign in again once
        _session.clear()
        return _call(cfg, method, path, body, retry=False)
    if r.status_code >= 300:
        raise TidepoolError(f"{SERVER_NAMES[cfg['server']]} answered {r.status_code} to {method} {path.split('?')[0]}: {r.text[:300]}")
    return r.json() if r.content and "json" in r.headers.get("content-type", "") else None


def _unwrap(x):
    return x.get("data", x) if isinstance(x, dict) else x


def dataset(c, cfg) -> str:
    """The one continuous data set Kitchen Carbs writes to: kept, found again by client name, or made."""
    if cfg["dataset"]:
        return cfg["dataset"]
    user = cfg["target"] or _session.get("userid") or login(cfg["server"], cfg["email"], cfg["password"])[1]
    found = _unwrap(_call(cfg, "GET", f"/v1/users/{user}/data_sets?client.name={CLIENT}")) or []
    live = [d for d in found if d.get("dataSetType") == "continuous" and not d.get("deletedTime")]
    if live:
        ds = live[0].get("id") or live[0].get("uploadId")
    else:
        made = _unwrap(_call(cfg, "POST", f"/v1/users/{user}/data_sets", {
            "client": {"name": CLIENT, "version": VERSION}, "dataSetType": "continuous",
            "deduplicator": {"name": DEDUPLICATOR}, "deviceManufacturers": ["Kitchen Carbs"], "deviceModel": "Kitchen Carbs"}))
        ds = made.get("id") or made.get("uploadId")
    with c:
        db.set_setting(c, "tp_dataset", ds)
        db.set_setting(c, "tp_userid", user)
    return ds


# ----- the records wanted -----
def _when(day: str, hhmm: str, minus_min: int = 0) -> dict:
    local = (datetime.fromisoformat(f"{day}T{hhmm}") - timedelta(minutes=minus_min)).astimezone()
    return {"time": local.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "timezoneOffset": int(local.utcoffset().total_seconds() // 60), "deviceTime": local.strftime("%Y-%m-%dT%H:%M:%S")}


def _meal_name(hhmm: str) -> str:   # the app's own times for naming a meal
    return "breakfast" if hhmm < "10:30" else "lunch" if hhmm < "15:00" else "dinner"


def _base(origin_id: str, when: dict, device: str) -> dict:
    return {**when, "deviceId": device, "origin": {"id": origin_id, "name": CLIENT, "type": "application", "version": VERSION}}


def _food(oid, when, device, name, carbs, notes=None) -> dict:
    rec = {**_base(oid, when, device), "type": "food", "name": name[:100] or "Carbs", "brand": "Kitchen Carbs", "code": oid,
           "meal": _meal_name(when["deviceTime"][11:16]), "nutrition": {"carbohydrate": {"net": carbs, "units": "grams"}}}
    if notes:
        rec["notes"] = [n[:1000] for n in notes][:100]
    return rec


def _smbg(oid, when, device, value) -> dict:
    return {**_base(oid, when, device), "type": "smbg", "subType": "manual", "units": "mg/dL", "value": int(value)}


def _bolus(oid, when, device, units) -> dict:
    return {**_base(oid, when, device), "type": "bolus", "subType": "normal", "normal": units}


def _basal(oid, when, device, units, hours, duration_ms) -> dict:
    """A long-acting injection as Tidepool's basal: the dose spread evenly over the set hours, or until the next one."""
    return {**_base(oid, when, device), "type": "basal", "deliveryType": "scheduled",
            "rate": round(units / hours, 4), "duration": duration_ms,
            "insulinFormulation": {"simple": {"actingType": "long"}}}


def _insulin(doses: list, device: str, hours: int, out: dict) -> None:
    """doses: (origin ID, when, units, kind). Basal doses end at the next one so they never overlap."""
    basal = sorted((d for d in doses if d[3] in BASAL_KINDS), key=lambda d: d[1]["time"])
    for i, (oid, when, units, _) in enumerate(basal):
        start = datetime.fromisoformat(when["time"].replace("Z", "+00:00"))
        dur = hours * 3600 * 1000
        if i + 1 < len(basal):
            nxt = datetime.fromisoformat(basal[i + 1][1]["time"].replace("Z", "+00:00"))
            dur = max(60000, min(dur, int((nxt - start).total_seconds() * 1000)))
        out[oid] = _basal(oid, when, device, units, hours, dur)
    for oid, when, units, kind in doses:
        if kind not in BASAL_KINDS:
            out[oid] = _bolus(oid, when, device, units)


def wanted(c, cfg) -> dict:
    """Every record that should be in Tidepool now, by origin ID. Never CGM, never a calculated dose."""
    k, out, device, doses = cfg["kinds"], {}, f"KitchenCarbs-{cfg['server']}", []
    for m in c.execute("SELECT * FROM meals WHERE day >= ? AND deleted_at IS NULL", (cfg["from"],)).fetchall():
        when = _when(m["day"], m["time"])
        if k["carbs"]:
            items = c.execute("SELECT food_name, carbs_exact FROM meal_items WHERE meal_id = ? ORDER BY id", (m["id"],)).fetchall()
            exact = m["carbs_corrected"] if m["carbs_corrected"] is not None else sum(i["carbs_exact"] for i in items)
            oid = f"kc-meal-{m['id']}"
            out[oid] = _food(oid, when, device, ", ".join(i["food_name"] for i in items), core.whole_grams(exact),
                             [f"Eaten: {m['eaten']}"] if m["eaten"] else None)
        if k["bg"] and m["bg"] is not None and m["bg_source"] != "cgm":
            oid = f"kc-meal-{m['id']}-bg"
            out[oid] = _smbg(oid, when, device, m["bg"])
        if k["insulin"] and m["insulin"] is not None:
            oid = f"kc-meal-{m['id']}-insulin"
            doses.append((oid, _when(m["day"], m["time"], m["insulin_offset_min"] or 0), m["insulin"], m["insulin_kind"]))
    for e in c.execute("SELECT * FROM log_entries WHERE day >= ? AND deleted_at IS NULL", (cfg["from"],)).fetchall():
        when = _when(e["day"], e["time"])
        if k["carbs"] and e["carbs"] is not None:
            oid = f"kc-entry-{e['id']}-carbs"
            out[oid] = _food(oid, when, device, e["note"] or "Carbs entered by hand", e["carbs"])
        if k["bg"] and e["bg"] is not None:
            oid = f"kc-entry-{e['id']}-bg"
            out[oid] = _smbg(oid, when, device, e["bg"])
        if k["insulin"] and e["insulin"] is not None:
            oid = f"kc-entry-{e['id']}-insulin"
            doses.append((oid, when, e["insulin"], e["insulin_kind"]))
    _insulin(doses, device, cfg["basal_hours"], out)
    return out


def _hash(rec) -> str:
    return hashlib.sha256(json.dumps(rec, sort_keys=True).encode()).hexdigest()[:32]


# ----- sending -----
def sync_once(resend: bool = False) -> dict:
    """Upload what's new or changed (everything, with resend), delete what's gone. Returns {sent, removed} or {} when not set up."""
    if not enabled():
        return {}
    with _lock:
        c = db.connect()
        try:
            cfg = config(c)
            if not (cfg["on"] and cfg["email"] and cfg["password"]):
                return {}
            try:
                ds = dataset(c, cfg)
                want = wanted(c, cfg)
                sent = {r["origin_id"]: "" if resend else r["hash"] for r in c.execute("SELECT origin_id, hash FROM tidepool_sent")}
                changed = [(oid, rec, _hash(rec)) for oid, rec in want.items() if sent.get(oid) != _hash(rec)]
                gone = [oid for oid in sent if oid not in want]
                stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
                for i in range(0, len(changed), BATCH):
                    part = changed[i:i + BATCH]
                    _call(cfg, "POST", f"/v1/data_sets/{ds}/data", [rec for _, rec, _ in part])
                    with c:
                        c.executemany("INSERT INTO tidepool_sent(origin_id, hash, sent_at) VALUES (?, ?, ?) "
                                      "ON CONFLICT(origin_id) DO UPDATE SET hash = excluded.hash, sent_at = excluded.sent_at",
                                      [(oid, h, stamp) for oid, _, h in part])
                for i in range(0, len(gone), BATCH):
                    part = gone[i:i + BATCH]
                    _call(cfg, "DELETE", f"/v1/data_sets/{ds}/data", [{"origin": {"id": oid}} for oid in part])
                    with c:
                        c.executemany("DELETE FROM tidepool_sent WHERE origin_id = ?", [(oid,) for oid in part])
                with c:
                    db.set_setting(c, "tp_last_sync", stamp)
                    db.set_setting(c, "tp_last_error", "")
                return {"sent": len(changed), "removed": len(gone)}
            except TidepoolError as e:
                with c:
                    db.set_setting(c, "tp_last_error", f"{datetime.now().strftime('%Y-%m-%d %H:%M')} {e}")
                raise
        finally:
            c.close()


def remove_all() -> None:
    """Delete Kitchen Carbs' own data set from Tidepool, and nothing else."""
    with _lock:
        c = db.connect()
        try:
            cfg = config(c)
            if cfg["dataset"] and cfg["email"] and cfg["password"]:
                _call(cfg, "DELETE", f"/v1/data_sets/{cfg['dataset']}")
            with c:
                c.execute("DELETE FROM tidepool_sent")
                for k in ("on", "dataset", "last_sync", "last_error"):
                    db.set_setting(c, "tp_" + k, "")
        finally:
            c.close()


def forget(c) -> None:
    """A new server, account or 'send to' account: start a fresh data set and record of what was sent."""
    _session.clear()
    c.execute("DELETE FROM tidepool_sent")
    for k in ("dataset", "userid", "last_sync", "last_error"):
        db.set_setting(c, "tp_" + k, "")


def poke() -> None:
    """Something in the log changed: send soon."""
    _wake.set()


def _loop():
    while True:
        if _wake.wait(SYNC_EVERY_S):   # a change: let a burst of edits settle before sending
            threading.Event().wait(SETTLE_S)
        _wake.clear()
        try:
            r = sync_once()
            if r.get("sent") or r.get("removed"):
                log.info("tidepool: sent %d, removed %d", r["sent"], r["removed"])
        except Exception as e:   # shown in Settings; the next run tries again
            log.warning("tidepool sync failed: %s", e)


def start_background_sync():
    if enabled():
        threading.Thread(target=_loop, name="tidepool-sync", daemon=True).start()
