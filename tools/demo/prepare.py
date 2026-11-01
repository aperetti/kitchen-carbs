"""Demo data for the reels: a copy of dev's foods and photos with no log, no accounts and no keys.
   prepare.py <dev data dir> <demo data dir>"""
import hashlib, json, os, secrets, shutil, sqlite3, sys

src, dst = sys.argv[1:3]
shutil.rmtree(dst, ignore_errors=True)
shutil.copytree(os.path.join(src, "photos"), os.path.join(dst, "photos"))
a, b = sqlite3.connect(os.path.join(src, "app.db")), sqlite3.connect(os.path.join(dst, "app.db"))
a.backup(b); a.close()
with b:
    for t in ("glucose", "push_subscriptions", "sessions", "tidepool_sent", "meal_comments", "meal_items", "meals", "log_entries"):
        b.execute(f"DELETE FROM {t}")
    b.execute("DELETE FROM settings WHERE key LIKE 'tp\\_%' ESCAPE '\\' OR key IN ('vapid_private', 'dose_settings', 'dose_updated', 'ns_last_error', 'ns_last_sync')")
    salt = secrets.token_hex(8)
    for k, v in {"allowed_emails": json.dumps(["parent@example.com", "other.parent@example.com"]), "off_contact": "kitchen@example.com",
                 "ns_url": "http://127.0.0.1:8766", "ns_token": "demo-token", "pin_salt": salt,
                 "pin_hash": hashlib.sha256((salt + "1234").encode()).hexdigest()}.items():
        b.execute("INSERT INTO settings(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value", (k, v))
b.close()
print("demo data ready:", dst)
