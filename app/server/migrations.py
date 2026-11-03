"""Forward-only database migrations (okf/architecture/migrations.md).

Version 1 is the schema as first deployed. To change the schema for a new feature
after that, append a function to MIGRATIONS. Never edit, remove or reorder one that
has shipped: databases in the kitchen have already run it.
"""
import os
import sqlite3
import time

DEFAULT_TAGS = ("Breakfast", "Lunch", "Dinner")


class MigrationError(Exception):
    pass


def m001_schema(con):
    """The schema as first deployed."""
    for stmt in """
    CREATE TABLE foods (
      id TEXT PRIMARY KEY, name TEXT NOT NULL, carbs_per_100g REAL NOT NULL,
      serving_grams REAL, serving_carbs REAL, -- as the source gives them, kept as typed (okf/domain/food.md)
      source_kind TEXT NOT NULL,              -- usda | label | care-team
      source_ref TEXT NOT NULL,               -- okf/rules/provenance-required.md
      trust TEXT NOT NULL DEFAULT 'draft',    -- draft | parent-verified
      verified_at TEXT, notes TEXT NOT NULL DEFAULT '',
      label_photo TEXT,                       -- okf/domain/nutrition-label.md
      package_photo TEXT,                     -- front of package from Open Food Facts, for photo requests only
      updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime')));
    CREATE TABLE portions (
      id INTEGER PRIMARY KEY, food_id TEXT NOT NULL REFERENCES foods(id) ON DELETE CASCADE,
      label TEXT NOT NULL, grams REAL NOT NULL, sort INTEGER NOT NULL DEFAULT 0,
      container TEXT NOT NULL DEFAULT 'auto', -- auto, plate, bowl, dressing or counter (okf/domain/photo-style.md)
      photo_original TEXT,                    -- never modified (okf/rules/original-photo-kept.md)
      photo_styled TEXT, photo_candidate TEXT,
      photo_estimated INTEGER NOT NULL DEFAULT 0,
      candidate_estimated INTEGER NOT NULL DEFAULT 0,   -- 0 styled from your photo, 1 from another portion, 2 from the name alone
      photo_job TEXT,                         -- style | estimate while Gemini is working (okf/features/photo-pipeline.md)
      photo_job_started TEXT, photo_job_error TEXT,
      photo_note TEXT NOT NULL DEFAULT '',     -- the parent's note for Gemini (okf/domain/photo-style.md)
      size_ref_id INTEGER REFERENCES size_refs(id) ON DELETE SET NULL);   -- okf/domain/size-reference.md
    CREATE TABLE size_refs (
      id INTEGER PRIMARY KEY, name TEXT NOT NULL, measurement TEXT NOT NULL, photo TEXT NOT NULL,
      container TEXT,                         -- plate | bowl | dressing, or NULL for any dish
      sort INTEGER NOT NULL DEFAULT 0);
    CREATE TABLE tags (
      id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE COLLATE NOCASE, sort INTEGER NOT NULL DEFAULT 0);
    CREATE TABLE food_tags (
      food_id TEXT NOT NULL REFERENCES foods(id) ON DELETE CASCADE,
      tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE, PRIMARY KEY (food_id, tag_id));
    CREATE TABLE meals (
      id INTEGER PRIMARY KEY, client_id TEXT UNIQUE,  -- lets a queued meal sync once
      day TEXT NOT NULL, time TEXT NOT NULL, eaten TEXT,
      created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')));
    CREATE TABLE meal_items (
      id INTEGER PRIMARY KEY, meal_id INTEGER NOT NULL REFERENCES meals(id) ON DELETE CASCADE,
      food_id TEXT, portion_id INTEGER,
      food_name TEXT NOT NULL, portion_label TEXT NOT NULL,   -- snapshot (okf/rules/snapshot-log-values.md)
      grams REAL NOT NULL, carbs_per_100g REAL NOT NULL, qty REAL NOT NULL, carbs_exact REAL NOT NULL);
    CREATE TABLE meal_comments (
      id INTEGER PRIMARY KEY, meal_id INTEGER NOT NULL REFERENCES meals(id) ON DELETE CASCADE,
      time TEXT NOT NULL, text TEXT NOT NULL);
    CREATE TABLE log_entries (                       -- okf/domain/manual-entry.md
      id INTEGER PRIMARY KEY, client_id TEXT UNIQUE, day TEXT NOT NULL, time TEXT NOT NULL,
      carbs REAL, bg INTEGER, insulin REAL, insulin_kind TEXT, note TEXT NOT NULL DEFAULT '',
      created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')));
    CREATE TABLE favorites (
      id INTEGER PRIMARY KEY, name TEXT NOT NULL, sort INTEGER NOT NULL DEFAULT 0,
      created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')));
    CREATE TABLE favorite_items (
      id INTEGER PRIMARY KEY, favorite_id INTEGER NOT NULL REFERENCES favorites(id) ON DELETE CASCADE,
      portion_id INTEGER REFERENCES portions(id) ON DELETE SET NULL,
      food_name TEXT NOT NULL, portion_label TEXT NOT NULL,   -- names a portion that was later deleted
      qty REAL NOT NULL);
    CREATE TABLE glucose (date_ms INTEGER PRIMARY KEY, sgv INTEGER NOT NULL, direction TEXT);  -- mg/dL
    CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT);
    CREATE INDEX meals_day ON meals(day);
    CREATE INDEX log_entries_day ON log_entries(day)
    """.split(";"):
        con.execute(stmt)
    for n, name in enumerate(DEFAULT_TAGS):
        con.execute("INSERT INTO tags(name, sort) VALUES (?, ?)", (name, n))


def m002_sessions(con):
    """Google sign-in: one row per signed-in device (okf/architecture/auth.md)."""
    for stmt in """
    CREATE TABLE sessions (
      id_hash TEXT PRIMARY KEY,               -- sha256 of the cookie value (the value itself is never stored)
      email TEXT NOT NULL, user_agent TEXT NOT NULL DEFAULT '',
      created_at TEXT NOT NULL, last_seen TEXT NOT NULL, expires_at TEXT NOT NULL);
    CREATE INDEX sessions_email ON sessions(email)
    """.split(";"):
        con.execute(stmt)


def m003_cooked_state(con):
    """Dry, raw or cooked carbs, and a measured cooking ratio (okf/domain/food.md, okf/rules/cooking-ratio-measured.md)."""
    for stmt in (
        "ALTER TABLE foods ADD COLUMN basis TEXT NOT NULL DEFAULT 'as-sold'",   # as-sold, raw or cooked
        "ALTER TABLE foods ADD COLUMN cook_raw_g REAL",                         # one batch weighed dry or raw
        "ALTER TABLE foods ADD COLUMN cook_cooked_g REAL",                      # and the same batch cooked
        "ALTER TABLE foods ADD COLUMN cook_measured_at TEXT",
    ):
        con.execute(stmt)


def m004_moved_from(con):
    """Date and time can be changed on any day; the first logged date and time is kept (okf/rules/same-day-edits.md)."""
    con.execute("ALTER TABLE meals ADD COLUMN moved_from TEXT")         # 'YYYY-MM-DD HH:MM', NULL if never moved
    con.execute("ALTER TABLE log_entries ADD COLUMN moved_from TEXT")


def m005_portion_labels(con):
    """Portion labels are an amount then a unit (okf/domain/portion.md): '½ × 1 serving' becomes '½ serving'.
    Logged meals keep their own labels."""
    from .core import fmt_amount, portion_amount, unit_for
    for pid, label in con.execute("SELECT id, label FROM portions").fetchall():
        if portion_amount(label):
            continue
        mult, _, base = label.partition(" × ")
        m, b = portion_amount(mult + " x"), portion_amount(base)
        if m and b:
            n = m[0] * b[0]
            con.execute("UPDATE portions SET label = ? WHERE id = ?", (f"{fmt_amount(n)} {unit_for(n, b[1])}"[:40], pid))


def m006_fiber(con):
    """Fiber beside the carbs, for reference only (okf/domain/food.md, okf/features/fill-in-fiber.md)."""
    for stmt in (
        "ALTER TABLE foods ADD COLUMN serving_fiber REAL",      # for serving_grams, kept as typed
        "ALTER TABLE foods ADD COLUMN fiber_per_100g REAL",     # worked out from it, or as the source gives it
        "ALTER TABLE foods ADD COLUMN fiber_checked_at TEXT",
    ):
        con.execute(stmt)


def m007_food_confirmations(con):
    """Each account confirms each food's carbs once (okf/features/confirm-food.md)."""
    con.execute("""CREATE TABLE food_confirmations (
      food_id TEXT NOT NULL REFERENCES foods(id) ON DELETE CASCADE,
      email TEXT NOT NULL, confirmed_at TEXT NOT NULL, PRIMARY KEY (food_id, email))""")


def m008_meal_details(con):
    """Optional BG, insulin and timings that go with a meal (okf/domain/meal.md)."""
    for stmt in (
        "ALTER TABLE meals ADD COLUMN bg INTEGER",                 # mg/dL at the meal
        "ALTER TABLE meals ADD COLUMN bg_source TEXT",             # cgm | meter
        "ALTER TABLE meals ADD COLUMN insulin REAL",               # units given, as typed (okf/rules/no-dosing.md)
        "ALTER TABLE meals ADD COLUMN insulin_kind TEXT",          # bolus | basal
        "ALTER TABLE meals ADD COLUMN insulin_offset_min INTEGER", # minutes given before starting to eat; negative = after
        "ALTER TABLE meals ADD COLUMN eat_min INTEGER",            # how long the meal took to eat
    ):
        con.execute(stmt)


def m009_barcode(con):
    """A food's package barcode in its own field (okf/domain/food.md), taken from the source text where it was kept."""
    import re
    con.execute("ALTER TABLE foods ADD COLUMN barcode TEXT")
    for fid, ref in con.execute("SELECT id, source_ref FROM foods").fetchall():
        m = re.search(r"barcode (\d{8,14})", ref or "")
        if m:
            con.execute("UPDATE foods SET barcode = ? WHERE id = ?", (m.group(1), fid))


def m010_entered_carbs(con):
    """Carbs entered by hand on the plate, with no weight (okf/domain/plate.md, okf/domain/meal.md)."""
    con.execute("ALTER TABLE meal_items ADD COLUMN entered_carbs REAL")   # NULL for a weighed food


def m011_edited_later(con):
    """When a meal or entry was last changed after its own day (okf/rules/same-day-edits.md)."""
    con.execute("ALTER TABLE meals ADD COLUMN edited_at TEXT")         # 'YYYY-MM-DD HH:MM', NULL if never
    con.execute("ALTER TABLE log_entries ADD COLUMN edited_at TEXT")


def m012_soft_delete(con):
    """Deleting keeps the row, so a meal or entry can be restored (okf/domain/meal-log.md)."""
    con.execute("ALTER TABLE meals ADD COLUMN deleted_at TEXT")          # 'YYYY-MM-DD HH:MM', NULL while in the log
    con.execute("ALTER TABLE log_entries ADD COLUMN deleted_at TEXT")


def m013_carbs_corrected(con):
    """A meal's total carbs corrected later, with a reason; the items keep their saved carbs (okf/domain/meal.md)."""
    con.execute("ALTER TABLE meals ADD COLUMN carbs_corrected REAL")     # NULL: the items' own total


def m014_favorite_photo(con):
    """A favorite's own photo of the whole meal, combined by Gemini (okf/features/favorite-plates.md)."""
    con.execute("ALTER TABLE favorites ADD COLUMN photo TEXT")             # accepted; NULL: the first food's photo
    con.execute("ALTER TABLE favorites ADD COLUMN photo_candidate TEXT")   # waiting for the parent's check


def m015_push_subscriptions(con):
    """Phones that get a notification when a meal or entry is logged (okf/architecture/web-push.md)."""
    con.execute("""CREATE TABLE push_subscriptions (
      id INTEGER PRIMARY KEY, endpoint TEXT NOT NULL UNIQUE, p256dh TEXT NOT NULL, auth TEXT NOT NULL,
      email TEXT, device TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, last_ok TEXT, last_error TEXT)""")


def m016_tidepool_sent(con):
    """What has been sent to Tidepool, by origin ID, so changes are re-sent and removals deleted (okf/architecture/tidepool-client.md)."""
    con.execute("CREATE TABLE tidepool_sent (origin_id TEXT PRIMARY KEY, hash TEXT NOT NULL, sent_at TEXT NOT NULL)")


def m017_nightscout_sent(con):
    """What has been sent to Nightscout, by origin ID, with its v3 identifier (okf/architecture/nightscout-client.md)."""
    con.execute("CREATE TABLE nightscout_sent (origin_id TEXT PRIMARY KEY, identifier TEXT NOT NULL, hash TEXT NOT NULL, sent_at TEXT NOT NULL)")


def m018_meal_rating(con):
    """A parent's rating of how fast glucose rose after a meal (okf/domain/meal-rating.md)."""
    con.execute("ALTER TABLE meals ADD COLUMN rise TEXT")   # fast, medium, slow


def m019_meal_fiber(con):
    """Each weighed item keeps its food's fiber, in the item's own cooked or dry state (okf/domain/meal.md).
    Meals saved before this get it once from the food as it is now."""
    con.execute("ALTER TABLE meal_items ADD COLUMN fiber_per_100g REAL")   # NULL: the food had none, or entered by hand
    con.execute("""UPDATE meal_items SET fiber_per_100g = (
                     SELECT CASE WHEN f.carbs_per_100g > 0 THEN f.fiber_per_100g * meal_items.carbs_per_100g / f.carbs_per_100g
                                 ELSE f.fiber_per_100g END FROM foods f WHERE f.id = meal_items.food_id)
                   WHERE entered_carbs IS NULL AND food_id IS NOT NULL""")


def m020_planned_meals(con):
    """Plates built ahead for a date and time, kept apart from the log so nothing counts them (okf/domain/planned-meal.md).
    items is the plate's rows as JSON."""
    con.execute("""CREATE TABLE planned_meals (
      id INTEGER PRIMARY KEY, client_id TEXT NOT NULL UNIQUE, name TEXT NOT NULL, day TEXT NOT NULL, time TEXT NOT NULL,
      items TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")


MIGRATIONS = [m001_schema, m002_sessions, m003_cooked_state, m004_moved_from, m005_portion_labels, m006_fiber,
              m007_food_confirmations, m008_meal_details, m009_barcode,
              m010_entered_carbs, m011_edited_later,
              m012_soft_delete, m013_carbs_corrected, m014_favorite_photo,
              m015_push_subscriptions, m016_tidepool_sent, m017_nightscout_sent, m018_meal_rating, m019_meal_fiber,
              m020_planned_meals]
LATEST = len(MIGRATIONS)


def version(con) -> int:
    return con.execute("PRAGMA user_version").fetchone()[0]


def backup_file(db_path: str, label: str) -> str:
    folder = os.path.join(os.path.dirname(db_path), "backups")
    os.makedirs(folder, exist_ok=True)
    dest = os.path.join(folder, f"{label}-{time.strftime('%Y%m%d-%H%M%S')}.db")
    src, dst = sqlite3.connect(db_path), sqlite3.connect(dest)
    with dst:
        src.backup(dst)
    src.close()
    dst.close()
    return dest


def run(db_path: str, log=print) -> int:
    """Bring the database at db_path up to LATEST. Returns the version it started at."""
    con = sqlite3.connect(db_path, isolation_level=None)   # explicit BEGIN/COMMIT below
    try:
        con.execute("PRAGMA foreign_keys = OFF")              # table changes must not cascade
        start = version(con)
        if start > LATEST:
            raise MigrationError(f"The database is at version {start}, newer than this app ({LATEST}). "
                                 "Deploy the newer app, or restore a backup made for this version.")
        if start == LATEST:
            return start
        if start > 0:   # okf/rules/backup-before-change.md
            log(f"backup before migrating: {backup_file(db_path, f'pre-migration-v{start}-to-v{LATEST}')}")
        for n in range(start + 1, LATEST + 1):
            fn = MIGRATIONS[n - 1]
            con.execute("BEGIN IMMEDIATE")
            try:
                fn(con)
                con.execute(f"PRAGMA user_version = {n}")
                con.execute("COMMIT")
            except Exception as e:
                con.execute("ROLLBACK")
                raise MigrationError(f"Migration {n} ({fn.__name__}) failed and was rolled back: {e}") from e
            log(f"migrated to version {n}: {fn.__name__}")
        return start
    finally:
        con.close()
