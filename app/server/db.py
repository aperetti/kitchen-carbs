"""SQLite storage on the Docker volume (okf/architecture/storage.md)."""
import os
import sqlite3
import threading
import time

from . import migrations

DATA_DIR = os.environ.get("KC_DATA", os.path.join(os.path.dirname(__file__), "..", "..", "data"))
DB_PATH = os.path.join(DATA_DIR, "app.db")
PHOTO_DIR = os.path.join(DATA_DIR, "photos")
_lock = threading.Lock()

def connect() -> sqlite3.Connection:
    os.makedirs(DATA_DIR, exist_ok=True)
    con = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA journal_mode = WAL")
    return con


def init():
    for d in ("original", "styled", "candidate", "labels", "base"):
        os.makedirs(os.path.join(PHOTO_DIR, d), exist_ok=True)
    with _lock:
        migrations.run(DB_PATH)


def backup(keep: int = 14):
    """Daily copy of the database into data/backups (okf/architecture/storage.md)."""
    folder = os.path.join(DATA_DIR, "backups")
    os.makedirs(folder, exist_ok=True)
    name = os.path.join(folder, f"app-{time.strftime('%Y-%m-%d')}.db")
    if not os.path.exists(name):
        src, dst = connect(), sqlite3.connect(name)
        with dst:
            src.backup(dst)
        src.close(), dst.close()
    for old in sorted(f for f in os.listdir(folder) if f.startswith("app-"))[:-keep]:
        os.remove(os.path.join(folder, old))


def backup_loop():
    while True:
        try:
            backup()
        except Exception as e:  # a failed backup must not stop the app
            print("backup failed:", e)
        time.sleep(3600)


def get_setting(con, key, default=None):
    row = con.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(con, key, value):
    con.execute("INSERT INTO settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, None if value is None else str(value)))
