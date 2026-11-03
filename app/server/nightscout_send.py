"""Keeps Kitchen Carbs' treatments in Nightscout in step with the log, for forecasting (okf/features/nightscout-send.md,
okf/architecture/nightscout-client.md). Off until a parent switches it on; only what was logged, never the calculated
dose, never CGM, and long-acting insulin and planned meals only as notes (okf/rules/nightscout-sends-what-was-logged.md)."""
import hashlib
import json
import logging
import os
import threading
import time
import uuid
from datetime import date, datetime, timedelta

import requests

from . import core, db

log = logging.getLogger("nightscout-send")
APP = "kitchen-carbs"
KINDS = ("carbs", "insulin", "bg")
NEEDS = ("api:treatments:create", "api:treatments:update", "api:treatments:delete")
NS_UUID = uuid.UUID(bytes=b"NightscoutRocks!")   # Nightscout's own namespace for v3 identifiers
BASAL_KINDS = {"basal", "long"}
SYNC_EVERY_S, SETTLE_S = 300, 20
ROLE_HELP = ("In Nightscout, Admin tools → Roles → Add new role 'kitchencarbs' with the permission api:treatments:*, "
             "then give that role (and 'readable') to this token's subject.")

_wake = threading.Event()
_lock = threading.Lock()
_jwt = {}   # {"key": (url, token), "jwt": ..., "exp": ..., "groups": [...]}: kept in memory only


class SendError(Exception):
    pass


def enabled() -> bool:
    """Production only: QA's database is a copy of production's, and dev and demo data are made up."""
    return os.environ.get("KC_ENV", "prod") == "prod"


def config(c) -> dict:
    g = lambda k, d=None: db.get_setting(c, "ns_send_" + k, d)
    kinds = json.loads(g("kinds") or '{"carbs": true, "insulin": true, "bg": true}')
    return {"on": g("on") == "on", "from": g("from") or (date.today() - timedelta(days=30)).isoformat(),
            "kinds": {k: bool(kinds.get(k)) for k in KINDS},
            "last_sync": g("last_sync"), "last_error": g("last_error"),
            "sent": c.execute("SELECT COUNT(*) FROM nightscout_sent").fetchone()[0]}


def public(c) -> dict:
    return {**config(c), "available": enabled(), "connected": bool(db.get_setting(c, "ns_url") and db.get_setting(c, "ns_token"))}


# ----- HTTP -----
def _grants(pattern: str, need: str) -> bool:
    """Nightscout's (Shiro) permissions: '*' matches any part, 'a,b' lists parts, missing trailing parts match all."""
    have, want = pattern.split(":"), need.split(":")
    return all(i >= len(have) or have[i] == "*" or w in have[i].split(",") for i, w in enumerate(want))


def missing_permissions(groups) -> list[str]:
    flat = [p for g in groups or [] for p in (g if isinstance(g, list) else [g]) if isinstance(p, str)]
    return [n for n in NEEDS if not any(_grants(p, n) for p in flat)]


def authorize(url: str, token: str, fresh: bool = False) -> dict:
    """A JWT for the v3 API from the access token, and what the token may do."""
    key = (url, token)
    if not fresh and _jwt.get("key") == key and _jwt["exp"] - time.time() > 300:
        return _jwt
    try:
        r = requests.get(f"{url.rstrip('/')}/api/v2/authorization/request/{token}", timeout=20, headers={"Accept": "application/json"})
    except requests.RequestException as e:
        raise SendError(f"Could not reach Nightscout: {e.__class__.__name__}") from e
    if r.status_code in (401, 403):
        raise SendError("Nightscout didn't recognise the token.")
    if r.status_code != 200:
        raise SendError(f"Nightscout answered {r.status_code} when asked for a sign-in.")
    try:
        d = r.json()
        d["token"]
    except (ValueError, TypeError, KeyError) as e:   # an old Nightscout, or not Nightscout at all
        raise SendError("This Nightscout didn't hand out a sign-in for the token. Sending needs Nightscout 14 or newer.") from e
    _jwt.clear()
    _jwt.update(key=key, jwt=d["token"], exp=d.get("exp") or time.time() + 3600, groups=d.get("permissionGroups") or [])
    return _jwt


def check(url: str, token: str) -> None:
    """Raises unless the token may create, update and delete treatments."""
    gone = missing_permissions(authorize(url, token, fresh=True)["groups"])
    if gone:
        raise SendError(f"This token can't {', '.join(n.rsplit(':', 1)[1] for n in gone)} treatments. {ROLE_HELP}")


def _call(url, token, method, path, body=None, retry=True):
    auth = authorize(url, token)
    try:
        r = requests.request(method, url.rstrip("/") + path, json=body, timeout=30,
                             headers={"Authorization": f"Bearer {auth['jwt']}", "Accept": "application/json"})
    except requests.RequestException as e:
        raise SendError(f"Could not reach Nightscout: {e.__class__.__name__}") from e
    if r.status_code == 401 and retry:   # the JWT ran out: ask for a new one once
        _jwt.clear()
        return _call(url, token, method, path, body, retry=False)
    if method == "DELETE" and r.status_code == 404:   # already gone
        return None
    if r.status_code in (401, 403):
        raise SendError(f"Nightscout refused to {method} a treatment ({r.status_code}). {ROLE_HELP}")
    if r.status_code >= 300:
        raise SendError(f"Nightscout answered {r.status_code} to {method} {path.split('?')[0]}: {r.text[:300]}")
    return r.json() if r.content and "json" in r.headers.get("content-type", "") else None


# ----- the treatments wanted -----
def identifier(doc: dict) -> str:
    """The identifier Nightscout computes itself from device, date and eventType, so the two always agree."""
    return str(uuid.uuid5(NS_UUID, f"{doc['device']}_{doc['date']}_{doc['eventType']}"))


def _doc(oid: str, day: str, hhmm: str, event: str, minus_min: int = 0, **fields) -> dict:
    local = (datetime.fromisoformat(f"{day}T{hhmm}") - timedelta(minutes=minus_min)).astimezone()
    # 1-999 ms from the origin: Nightscout also merges treatments with the same created_at and eventType, and
    # another app's treatment could be logged in the same minute
    ms = int(local.timestamp()) * 1000 + 1 + int(hashlib.sha256(oid.encode()).hexdigest()[:8], 16) % 999
    doc = {"date": ms, "utcOffset": int(local.utcoffset().total_seconds() // 60), "app": APP, "enteredBy": "Kitchen Carbs",
           "device": f"{APP}://{oid}", "eventType": event, **fields}
    doc["identifier"] = identifier(doc)
    return doc


def _insulin(oid, day, hhmm, units, kind, event, minus_min=0, note=""):
    if kind in BASAL_KINDS:   # never in the insulin field: OpenAPS would count it as rapid-acting
        return _doc(oid, day, hhmm, "Note", minus_min, notes=f"Long-acting insulin {units:g} u{f' · {note}' if note else ''}")
    return _doc(oid, day, hhmm, event, minus_min, insulin=units, **({"notes": note} if note else {}))


def _bg(oid, day, hhmm, value):
    return _doc(oid, day, hhmm, "BG Check", glucose=int(value), glucoseType="Finger", units="mg/dl")


def wanted(c, cfg) -> dict:
    """Every treatment that should be in Nightscout now, by origin ID."""
    k, out = cfg["kinds"], {}
    for m in c.execute("SELECT * FROM meals WHERE day >= ? AND deleted_at IS NULL", (cfg["from"],)).fetchall():
        items = c.execute("SELECT food_name, carbs_exact FROM meal_items WHERE meal_id = ? ORDER BY id", (m["id"],)).fetchall()
        foods = ", ".join(i["food_name"] for i in items)[:500]
        if k["carbs"]:
            exact = m["carbs_corrected"] if m["carbs_corrected"] is not None else sum(i["carbs_exact"] for i in items)
            notes = foods + (f" · eaten: {m['eaten']}" if m["eaten"] else "")
            out[f"kc-meal-{m['id']}"] = _doc(f"kc-meal-{m['id']}", m["day"], m["time"], "Meal Bolus",
                                             carbs=core.whole_grams(exact), notes=notes)
        if k["insulin"] and m["insulin"] is not None:
            oid = f"kc-meal-{m['id']}-insulin"
            out[oid] = _insulin(oid, m["day"], m["time"], m["insulin"], m["insulin_kind"], "Meal Bolus",
                                m["insulin_offset_min"] or 0, foods)
        if k["bg"] and m["bg"] is not None and m["bg_source"] != "cgm":
            out[f"kc-meal-{m['id']}-bg"] = _bg(f"kc-meal-{m['id']}-bg", m["day"], m["time"], m["bg"])
    for e in c.execute("SELECT * FROM log_entries WHERE day >= ? AND deleted_at IS NULL", (cfg["from"],)).fetchall():
        if k["carbs"] and e["carbs"] is not None:
            oid = f"kc-entry-{e['id']}-carbs"
            out[oid] = _doc(oid, e["day"], e["time"], "Carb Correction", carbs=e["carbs"],
                            **({"notes": e["note"][:500]} if e["note"] else {}))
        if k["insulin"] and e["insulin"] is not None:
            oid = f"kc-entry-{e['id']}-insulin"
            out[oid] = _insulin(oid, e["day"], e["time"], e["insulin"], e["insulin_kind"], "Correction Bolus", note=e["note"][:500])
        if k["bg"] and e["bg"] is not None:
            out[f"kc-entry-{e['id']}-bg"] = _bg(f"kc-entry-{e['id']}-bg", e["day"], e["time"], e["bg"])
    if k["carbs"]:   # a planned meal: a note only, never in the carbs field, so no forecast counts it (okf/features/plan-meal.md)
        for p in c.execute("SELECT * FROM planned_meals WHERE day >= ?", (cfg["from"],)).fetchall():
            items = json.loads(p["items"])
            carbs, foods = core.whole_grams(core.plan_carbs(items)), ", ".join(i["food_name"] for i in items)
            out[f"kc-plan-{p['id']}"] = _doc(f"kc-plan-{p['id']}", p["day"], p["time"], "Note",
                                             notes=f"Planned meal: {p['name']} · {foods} · {carbs} g carbs, not eaten yet"[:500])
    return out


def _hash(doc) -> str:
    return hashlib.sha256(json.dumps(doc, sort_keys=True).encode()).hexdigest()[:32]


# ----- sending -----
def _forget_row(c, oid):
    with c:
        c.execute("DELETE FROM nightscout_sent WHERE origin_id = ?", (oid,))


def sync_once(resend: bool = False) -> dict:
    """Send what's new or changed (everything, with resend), delete what's gone. Returns {sent, removed} or {} when not set up."""
    if not enabled():
        return {}
    with _lock:
        c = db.connect()
        try:
            cfg = config(c)
            url, token = db.get_setting(c, "ns_url"), db.get_setting(c, "ns_token")
            if not (cfg["on"] and url and token):
                return {}
            stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            try:
                want = wanted(c, cfg)
                sent = {r["origin_id"]: r for r in c.execute("SELECT * FROM nightscout_sent")}
                n_sent = n_removed = 0
                for oid in [o for o in sent if o not in want]:
                    _call(url, token, "DELETE", f"/api/v3/treatments/{sent[oid]['identifier']}?permanent=true")
                    _forget_row(c, oid)
                    n_removed += 1
                for oid, doc in want.items():
                    old, h = sent.get(oid), _hash(doc)
                    if old and old["hash"] == h and not resend:
                        continue
                    if old and old["identifier"] != doc["identifier"]:   # moved or a new kind: delete the old one first, so it never counts twice
                        _call(url, token, "DELETE", f"/api/v3/treatments/{old['identifier']}?permanent=true")
                        _forget_row(c, oid)
                    _call(url, token, "POST", "/api/v3/treatments", doc)
                    with c:
                        c.execute("INSERT INTO nightscout_sent(origin_id, identifier, hash, sent_at) VALUES (?, ?, ?, ?) "
                                  "ON CONFLICT(origin_id) DO UPDATE SET identifier = excluded.identifier, hash = excluded.hash, "
                                  "sent_at = excluded.sent_at", (oid, doc["identifier"], h, stamp))
                    n_sent += 1
                with c:
                    db.set_setting(c, "ns_send_last_sync", stamp)
                    db.set_setting(c, "ns_send_last_error", "")
                return {"sent": n_sent, "removed": n_removed}
            except SendError as e:
                with c:
                    db.set_setting(c, "ns_send_last_error", f"{stamp} {e}")
                raise
        finally:
            c.close()


def remove_all() -> int:
    """Delete every treatment Kitchen Carbs sent, and nothing else; sending turns off."""
    with _lock:
        c = db.connect()
        try:
            url, token = db.get_setting(c, "ns_url"), db.get_setting(c, "ns_token")
            rows = c.execute("SELECT origin_id, identifier FROM nightscout_sent").fetchall()
            with c:
                db.set_setting(c, "ns_send_on", "")
            if rows and not (url and token):
                raise SendError("Connect Nightscout again first, so its treatments can be removed.")
            for r in rows:
                _call(url, token, "DELETE", f"/api/v3/treatments/{r['identifier']}?permanent=true")
                _forget_row(c, r["origin_id"])
            with c:
                db.set_setting(c, "ns_send_last_error", "")
            return len(rows)
        finally:
            c.close()


def forget(c) -> None:
    """A different Nightscout site: stop sending and forget what went to the old one."""
    _jwt.clear()
    c.execute("DELETE FROM nightscout_sent")
    for k in ("on", "last_sync", "last_error"):
        db.set_setting(c, "ns_send_" + k, "")


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
                log.info("nightscout: sent %d, removed %d", r["sent"], r["removed"])
        except Exception as e:   # shown in Manage → Nightscout; the next run tries again
            log.warning("nightscout send failed: %s", e)


def start_background_sync():
    if enabled():
        threading.Thread(target=_loop, name="nightscout-send", daemon=True).start()
