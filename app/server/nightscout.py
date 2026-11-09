"""Nightscout reader (okf/architecture/nightscout-client.md): glucose, IOB and targets, with GET requests only.
Sending treatments, when a parent switches it on, is nightscout_send.py (okf/rules/nightscout-sends-what-was-logged.md).
The token stays here on the server.
"""
import logging
import threading
import time
from datetime import datetime, timezone

import requests

from . import db

log = logging.getLogger("nightscout")
BACKFILL_DAYS = 90
CHUNK_MS = 3 * 86_400_000          # 3 days ≈ 864 readings, under the 1000 page size
SYNC_EVERY_S = 300


class NightscoutError(Exception):
    pass


def _get(url: str, token: str, path: str, params: dict):
    try:
        r = requests.get(url.rstrip("/") + path, params={**params, "token": token}, timeout=20,
                         headers={"Accept": "application/json"})
    except requests.RequestException as e:
        raise NightscoutError(f"Could not reach Nightscout: {e.__class__.__name__}") from e
    if r.status_code in (401, 403):
        raise NightscoutError("Nightscout refused the token. Use a token with the 'readable' role.")
    if r.status_code != 200:
        raise NightscoutError(f"Nightscout answered {r.status_code}.")
    return r.json()


def latest(url: str, token: str):
    """The newest reading, or None when the site has none yet (no CGM uploading); the token is checked either way."""
    rows = _get(url, token, "/api/v1/entries/sgv.json", {"count": 1})
    if not rows:
        return None
    return {"date_ms": rows[0]["date"], "sgv": rows[0]["sgv"], "direction": rows[0].get("direction")}


def _ms(v):
    """Nightscout times come as epoch ms or ISO strings."""
    if isinstance(v, (int, float)):
        return int(v)
    if isinstance(v, str):
        try:
            return int(datetime.fromisoformat(v.replace("Z", "+00:00")).timestamp() * 1000)
        except ValueError:
            return None
    return None


def iob(url: str, token: str):
    """Insulin on board for the meal summary (okf/architecture/nightscout-client.md): the IOB plugin first,
    then the newest device status. Returns {units, mills, source} or None; never guesses."""
    try:
        p = _get(url, token, "/api/v2/properties/iob", {})
        x = p.get("iob") if isinstance(p, dict) else None
        # 'Care Portal' is worked out from the bolus treatments at the moment it's asked, so it comes without a time
        care = isinstance(x, dict) and x.get("source") == "Care Portal"
        t = isinstance(x, dict) and (_ms(x.get("mills")) or (care and int(time.time() * 1000)))
        if isinstance(x, dict) and isinstance(x.get("iob"), (int, float)) and t:
            return {"units": float(x["iob"]), "mills": t, "source": "Nightscout, from logged boluses" if care else x.get("source") or "Nightscout"}
    except NightscoutError:
        pass
    rows = _get(url, token, "/api/v1/devicestatus.json", {"count": 3})
    for r in rows if isinstance(rows, list) else []:
        if not isinstance(r, dict):
            continue
        when = _ms(r.get("created_at")) or _ms(r.get("mills"))
        o = r.get("openaps", {}).get("iob") if isinstance(r.get("openaps"), dict) else None
        o = o[0] if isinstance(o, list) and o else o
        for src, d, keys in (("Loop", (r.get("loop") or {}).get("iob"), ("iob",)),
                             ("OpenAPS", o, ("iob",)),
                             ("Pump", (r.get("pump") or {}).get("iob"), ("bolusiob", "iob"))):
            if isinstance(d, dict):
                v = next((d[k] for k in keys if isinstance(d.get(k), (int, float))), None)
                t = _ms(d.get("timestamp")) or _ms(d.get("time")) or when
                if v is not None and t:
                    return {"units": float(v), "mills": t, "source": src}
    return None


_live = {"at": 0, "key": None, "val": None}


def live(url: str, token: str, max_age_s: int = 60):
    """Latest reading and IOB, read when the meal summary opens; cached for a minute."""
    now = time.time()
    if _live["key"] == url and now - _live["at"] < max_age_s:
        return _live["val"]
    out = {"bg": None, "iob": None, "error": None}
    try:
        out["bg"] = latest(url, token)
    except NightscoutError as e:
        out["error"] = str(e)
    try:
        out["iob"] = iob(url, token)
    except NightscoutError as e:
        out["error"] = out["error"] or str(e)
    _live.update(at=now, key=url, val=out)
    return out


def targets(url: str, token: str):
    """Target range from Nightscout status thresholds, if set."""
    try:
        th = _get(url, token, "/api/v1/status.json", {}).get("settings", {}).get("thresholds", {})
        return th.get("bgTargetBottom"), th.get("bgTargetTop")
    except NightscoutError:
        return None, None


def sync_once(now_ms: int | None = None) -> int:
    con = db.connect()
    url, token = db.get_setting(con, "ns_url"), db.get_setting(con, "ns_token")
    if not url or not token:
        return 0
    now_ms = now_ms or int(time.time() * 1000)
    row = con.execute("SELECT MAX(date_ms) AS m FROM glucose").fetchone()
    since = row["m"] or now_ms - BACKFILL_DAYS * 86_400_000
    added = 0
    while since < now_ms:
        until = min(since + CHUNK_MS, now_ms + 60_000)
        rows = _get(url, token, "/api/v1/entries/sgv.json",
                    {"find[date][$gt]": since, "find[date][$lte]": until, "count": 1000})
        with con:
            for e in rows:
                if isinstance(e.get("sgv"), (int, float)) and e.get("date"):
                    cur = con.execute("INSERT OR IGNORE INTO glucose(date_ms, sgv, direction) VALUES (?, ?, ?)",
                                      (int(e["date"]), int(e["sgv"]), e.get("direction")))
                    added += cur.rowcount
        since = until
    try:   # boluses are extra: a failure here never stops the glucose
        sync_insulin(con, url, token, now_ms)
    except NightscoutError as e:
        log.warning("nightscout insulin sync failed: %s", e)
    with con:
        db.set_setting(con, "ns_last_sync", now_ms)
        db.set_setting(con, "ns_last_error", None)
    return added


def _iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def sync_insulin(con, url: str, token: str, now_ms: int):
    """Boluses from Nightscout treatments into ns_insulin (okf/architecture/nightscout-client.md). The last 24 hours
    are read again and replaced each time, so edits and deletions in Nightscout follow; the first sync goes back 90
    days. Kitchen Carbs' own treatments are skipped: the log has them."""
    last = db.get_setting(con, "ns_insulin_sync")
    since = max(int(last) - 86_400_000, now_ms - BACKFILL_DAYS * 86_400_000) if last else now_ms - BACKFILL_DAYS * 86_400_000
    while since < now_ms:
        until = min(since + CHUNK_MS, now_ms + 60_000)
        rows = _get(url, token, "/api/v1/treatments.json",
                    {"find[created_at][$gte]": _iso(since), "find[created_at][$lt]": _iso(until), "count": 1000})
        with con:
            con.execute("DELETE FROM ns_insulin WHERE date_ms >= ? AND date_ms < ?", (since, until))
            for t in rows if isinstance(rows, list) else []:
                u, ms = t.get("insulin"), _ms(t.get("date") or t.get("mills") or t.get("created_at"))
                if not isinstance(u, (int, float)) or not 0 < u <= 100 or not ms or not t.get("_id"):
                    continue
                if t.get("enteredBy") == "Kitchen Carbs" or t.get("app") == "kitchen-carbs":
                    continue
                con.execute("INSERT OR REPLACE INTO ns_insulin(id, date_ms, units, event_type, entered_by) VALUES (?, ?, ?, ?, ?)",
                            (str(t["_id"]), ms, round(float(u), 2), t.get("eventType"), t.get("enteredBy")))
        since = until
    with con:
        db.set_setting(con, "ns_insulin_sync", now_ms)


def _loop():
    while True:
        try:
            n = sync_once()
            if n:
                log.info("nightscout: %d new readings", n)
        except Exception as e:  # keep the loop alive; show the error in the app
            log.warning("nightscout sync failed: %s", e)
            with db.connect() as con:
                db.set_setting(con, "ns_last_error", str(e))
        time.sleep(SYNC_EVERY_S)


def start_background_sync():
    threading.Thread(target=_loop, name="nightscout-sync", daemon=True).start()
