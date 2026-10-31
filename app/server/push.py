"""Web Push to parents' phones when a meal or entry is logged (okf/features/notify-family.md, okf/architecture/web-push.md)."""
import base64
import json
import logging
import os
import threading
from datetime import datetime

from cryptography.hazmat.primitives import serialization

from . import db

log = logging.getLogger("push")
TTL = 6 * 3600   # a phone that's off for longer than this doesn't need hours-old meals


def enabled() -> bool:
    """QA's database is a copy of production's, phones included: it never sends (okf/features/notify-family.md)."""
    return os.environ.get("KC_ENV", "prod") != "qa"


def _vapid(c):
    from py_vapid import Vapid
    pem = db.get_setting(c, "vapid_private")
    if not pem:   # made once; the private key never leaves the server
        v = Vapid()
        v.generate_keys()
        pem = v.private_pem().decode()
        with c:
            db.set_setting(c, "vapid_private", pem)
    return Vapid.from_pem(pem.encode())


def public_key(c) -> str:
    """The application server key browsers subscribe with: the raw P-256 point, base64url."""
    raw = _vapid(c).public_key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _send_one(vapid, subject, sub, payload):
    from pywebpush import WebPushException, webpush
    try:
        webpush({"endpoint": sub["endpoint"], "keys": {"p256dh": sub["p256dh"], "auth": sub["auth"]}},
                data=json.dumps(payload), vapid_private_key=vapid, vapid_claims={"sub": subject}, ttl=TTL, timeout=10)
        return None
    except WebPushException as e:
        status = getattr(e.response, "status_code", None)
        return "gone" if status in (404, 410) else f"{status or ''} {str(e)[:200]}".strip()
    except Exception as e:   # network trouble: keep the phone, note why
        return str(e)[:200]


def send(payload: dict, skip: str = "", only: str = "") -> dict:
    """Send to every subscribed device except `skip` (or only to `only`). Returns {sent, failed} for tests and 'Send a test'."""
    out = {"sent": 0, "failed": 0}
    if not enabled():
        return out
    c = db.connect()
    try:
        vapid, subject = _vapid(c), db.get_setting(c, "push_subject") or "https://localhost"
        subs = c.execute("SELECT * FROM push_subscriptions").fetchall()
        for s in subs:
            if s["endpoint"] == skip or (only and s["endpoint"] != only):
                continue
            err = _send_one(vapid, subject, s, payload)
            stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            with c:
                if err == "gone":   # unsubscribed or uninstalled: the push service won't take more
                    c.execute("DELETE FROM push_subscriptions WHERE id = ?", (s["id"],))
                elif err:
                    c.execute("UPDATE push_subscriptions SET last_error = ? WHERE id = ?", (f"{stamp} {err}", s["id"]))
                else:
                    c.execute("UPDATE push_subscriptions SET last_ok = ?, last_error = NULL WHERE id = ?", (stamp, s["id"]))
            out["failed" if err else "sent"] += 1
    except Exception:
        log.exception("push failed")
    finally:
        c.close()
    return out


def send_later(payload: dict, skip: str = ""):
    """A save never waits on Google's or Apple's push service, and a failed push never fails a save."""
    threading.Thread(target=lambda: send(payload, skip), daemon=True).start()
