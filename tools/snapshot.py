"""Copy a Kitchen Carbs data folder (database + photos) consistently, even while the app runs.

Usage: snapshot.py SOURCE_DATA DEST_DATA      e.g. snapshot.py data data-qa
The destination's database and photos are replaced; its backups/ folder is kept.
Standard library only, so it runs on the server without the app's virtualenv.
"""
import os
import shutil
import sqlite3
import sys


def snapshot(src: str, dst: str) -> None:
    src_db = os.path.join(src, "app.db")
    if not os.path.exists(src_db):
        sys.exit(f"No database at {src_db}")
    os.makedirs(dst, exist_ok=True)
    tmp = os.path.join(dst, "app.db.copying")
    if os.path.exists(tmp):
        os.remove(tmp)
    s, d = sqlite3.connect(src_db), sqlite3.connect(tmp)
    with d:
        s.backup(d)          # SQLite's online backup: a consistent copy even mid-write
    s.close()
    d.close()
    for leftover in ("app.db-wal", "app.db-shm"):
        p = os.path.join(dst, leftover)
        if os.path.exists(p):
            os.remove(p)
    os.replace(tmp, os.path.join(dst, "app.db"))
    if os.path.isdir(os.path.join(dst, "photos")):
        shutil.rmtree(os.path.join(dst, "photos"))
    if os.path.isdir(os.path.join(src, "photos")):
        shutil.copytree(os.path.join(src, "photos"), os.path.join(dst, "photos"))
    con = sqlite3.connect(os.path.join(dst, "app.db"))
    meals = con.execute("SELECT COUNT(*) FROM meals").fetchone()[0] if con.execute(
        "SELECT 1 FROM sqlite_master WHERE name = 'meals'").fetchone() else 0
    print(f"copied {src} -> {dst}: schema v{con.execute('PRAGMA user_version').fetchone()[0]}, {meals} meals")
    con.close()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    snapshot(sys.argv[1], sys.argv[2])
