"""Google sign-in through Firebase, with the server's own sessions (okf/architecture/auth.md).

Firebase proves who someone is; this server checks the ID token itself, checks the family's allow list
(okf/rules/allowlisted-accounts-only.md) and then keeps the device signed in with its own cookie.
"""
import hashlib
import json
import os
import secrets
import threading
import time
from datetime import datetime, timedelta

from . import db

COOKIE = "kc_session"
DAYS = 30


class AuthError(Exception):
    pass


def enabled() -> bool:
    return bool(os.environ.get("FIREBASE_PROJECT_ID", "").strip())


def web_config() -> dict:   # the Firebase web config is public by design; it goes into the page
    return {"apiKey": os.environ.get("FIREBASE_API_KEY", "").strip(),
            "authDomain": os.environ.get("FIREBASE_AUTH_DOMAIN", "").strip(),
            "projectId": os.environ.get("FIREBASE_PROJECT_ID", "").strip()}


_google_request = None


def verify(id_token: str) -> str:
    """Firebase ID token -> verified email address, or AuthError."""
    global _google_request
    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token as google_id_token
    _google_request = _google_request or google_requests.Request()   # caches Google's public keys
    try:
        claims = google_id_token.verify_firebase_token(id_token, _google_request, audience=web_config()["projectId"])
    except Exception as e:   # bad signature, wrong project, expired, malformed
        raise AuthError("Google sign-in couldn't be checked. Try again.") from e
    email = (claims or {}).get("email", "").strip().lower()
    if not email or not claims.get("email_verified"):
        raise AuthError("That Google account has no verified email address.")
    return email


def allowed(c) -> list[str]:
    saved = db.get_setting(c, "allowed_emails")
    if saved is not None:
        return json.loads(saved)
    return sorted({e.strip().lower() for e in os.environ.get("KC_ALLOWED_EMAILS", "").split(",") if e.strip()})


def set_allowed(c, emails: list[str]) -> list[str]:
    clean = sorted({e.strip().lower() for e in emails if e.strip()})
    db.set_setting(c, "allowed_emails", json.dumps(clean))
    if clean:   # anyone taken off the list is signed out everywhere
        c.execute(f"DELETE FROM sessions WHERE email NOT IN ({','.join('?' * len(clean))})", clean)
    else:
        c.execute("DELETE FROM sessions")
    return clean


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _stamp(t: datetime) -> str:
    return t.isoformat(timespec="seconds")


def create(c, email: str, user_agent: str) -> str:
    raw, now = secrets.token_urlsafe(32), datetime.now()
    c.execute("INSERT INTO sessions(id_hash, email, user_agent, created_at, last_seen, expires_at) VALUES (?, ?, ?, ?, ?, ?)",
              (_hash(raw), email, user_agent[:200], _stamp(now), _stamp(now), _stamp(now + timedelta(days=DAYS))))
    return raw


def lookup(c, raw: str | None) -> tuple[str, bool] | None:
    """(email, renewed) for a live session on the allow list; renewed when the 30 days were pushed forward."""
    if not raw:
        return None
    row = c.execute("SELECT * FROM sessions WHERE id_hash = ?", (_hash(raw),)).fetchone()
    now = datetime.now()
    if not row or row["expires_at"] < _stamp(now) or row["email"] not in allowed(c):
        return None
    renew = row["last_seen"] < _stamp(now - timedelta(days=1))   # at most one write a day per device
    if renew:
        c.execute("UPDATE sessions SET last_seen = ?, expires_at = ? WHERE id_hash = ?",
                  (_stamp(now), _stamp(now + timedelta(days=DAYS)), row["id_hash"]))
    return row["email"], renew


def end(c, raw: str | None):
    if raw:
        c.execute("DELETE FROM sessions WHERE id_hash = ?", (_hash(raw),))


def end_others(c, raw: str | None) -> int:
    return c.execute("DELETE FROM sessions WHERE id_hash != ?", (_hash(raw or ""),)).rowcount


# ---------- sign in with a code, for kiosks and web views where Google won't sign in (okf/features/sign-in.md) ----------
CODE_SECONDS = 600
CODE_LETTERS = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"   # no 0/O or 1/I/L to misread
MAX_WAITING = 20
_codes: dict[str, dict] = {}   # poll id -> {code, started, email}; in memory: a restart drops waiting codes
_codes_lock = threading.Lock()


def _drop_old():
    for k in [k for k, v in _codes.items() if time.time() - v["started"] > CODE_SECONDS]:
        del _codes[k]


def _clean_code(code: str) -> str:
    return "".join(ch for ch in code.upper() if ch.isalnum())


def start_device() -> dict:
    with _codes_lock:
        _drop_old()
        if len(_codes) >= MAX_WAITING:
            raise AuthError("Too many devices are waiting to sign in. Try again in a few minutes.")
        code = "".join(secrets.choice(CODE_LETTERS) for _ in range(8))
        poll = secrets.token_urlsafe(32)
        _codes[poll] = {"code": code, "started": time.time(), "email": None}
    return {"code": f"{code[:4]}-{code[4:]}", "poll": poll, "expires_in": CODE_SECONDS}


def approve_device(code: str, email: str) -> bool:
    code = _clean_code(code)
    with _codes_lock:
        _drop_old()
        for v in _codes.values():
            if v["email"] is None and secrets.compare_digest(v["code"], code):
                v["email"] = email
                return True
    return False


def poll_device(poll: str) -> tuple[str, str | None]:
    """('pending', None), ('approved', email) once (the code is then used up), or ('expired', None)."""
    with _codes_lock:
        _drop_old()
        v = _codes.get(poll)
        if not v:
            return "expired", None
        if v["email"] is None:
            return "pending", None
        del _codes[poll]
        return "approved", v["email"]
