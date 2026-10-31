"""okf/architecture/migrations.md and okf/rules/backup-before-change.md"""
import os
import sqlite3

import pytest

from server import migrations

QUIET = dict(log=lambda m: None)


def add_example_migration(monkeypatch, fn):
    """Simulate the first post-deploy schema change."""
    monkeypatch.setattr(migrations, "MIGRATIONS", [*migrations.MIGRATIONS, fn])
    monkeypatch.setattr(migrations, "LATEST", len(migrations.MIGRATIONS))


def deployed_db(tmp_path):
    db = str(tmp_path / "app.db")
    migrations.run(db, **QUIET)
    con = sqlite3.connect(db)
    con.executescript("INSERT INTO foods(id, name, carbs_per_100g, source_kind, source_ref) VALUES ('kiwi', 'Kiwi', 14.7, 'usda', 'x');"
                      "INSERT INTO meals(client_id, day, time) VALUES ('c1', '2026-10-26', '07:30');"
                      "INSERT INTO meal_items(meal_id, food_name, portion_label, grams, carbs_per_100g, qty, carbs_exact) "
                      "VALUES (1, 'Kiwi', '1 kiwi', 75, 14.7, 1, 11.025);")
    con.close()
    return db


def test_new_database_gets_schema_and_default_tags(tmp_path):
    db = str(tmp_path / "app.db")
    assert migrations.run(db, **QUIET) == 0
    con = sqlite3.connect(db)
    assert migrations.version(con) == migrations.LATEST
    assert [r[0] for r in con.execute("SELECT name FROM tags ORDER BY sort")] == ["Breakfast", "Lunch", "Dinner"]
    assert not (tmp_path / "backups").exists()          # nothing to back up on a fresh install


def test_new_migration_backs_up_and_keeps_data(tmp_path, monkeypatch):
    db = deployed_db(tmp_path)
    n = migrations.LATEST   # the version production is on now
    add_example_migration(monkeypatch, lambda con: con.execute("ALTER TABLE foods ADD COLUMN brand TEXT"))
    assert migrations.run(db, **QUIET) == n
    con = sqlite3.connect(db)
    assert con.execute("SELECT name, brand FROM foods").fetchall() == [("Kiwi", None)]
    assert con.execute("SELECT COUNT(*) FROM meal_items").fetchone()[0] == 1
    backups = os.listdir(tmp_path / "backups")
    assert len(backups) == 1 and backups[0].startswith(f"pre-migration-v{n}-to-v{n + 1}-")
    old = sqlite3.connect(str(tmp_path / "backups" / backups[0]))
    assert migrations.version(old) == n and old.execute("SELECT name FROM foods").fetchone() == ("Kiwi",)
    assert migrations.run(db, **QUIET) == n + 1 and len(os.listdir(tmp_path / "backups")) == 1   # second run: nothing to do


def test_failed_migration_rolls_back(tmp_path, monkeypatch):
    db = deployed_db(tmp_path)

    def broken(con):
        con.execute("CREATE TABLE half_done (x)")
        raise RuntimeError("boom")

    n = migrations.LATEST
    add_example_migration(monkeypatch, broken)
    with pytest.raises(migrations.MigrationError, match=f"Migration {n + 1} .* rolled back"):
        migrations.run(db, **QUIET)
    con = sqlite3.connect(db)
    assert migrations.version(con) == n
    assert not con.execute("SELECT 1 FROM sqlite_master WHERE name = 'half_done'").fetchone()
    assert con.execute("SELECT COUNT(*) FROM foods").fetchone()[0] == 1


def test_newer_database_is_refused(tmp_path):
    db = str(tmp_path / "app.db")
    con = sqlite3.connect(db)
    con.execute(f"PRAGMA user_version = {migrations.LATEST + 1}")
    con.close()
    with pytest.raises(migrations.MigrationError, match="newer than this app"):
        migrations.run(db, **QUIET)


def test_production_v1_upgrades_to_sessions(tmp_path, monkeypatch):
    """The homelab database was deployed at version 1; version 2 adds sign-in sessions and keeps everything."""
    real = migrations.MIGRATIONS
    monkeypatch.setattr(migrations, "MIGRATIONS", real[:1]); monkeypatch.setattr(migrations, "LATEST", 1)
    db = deployed_db(tmp_path)
    monkeypatch.setattr(migrations, "MIGRATIONS", real); monkeypatch.setattr(migrations, "LATEST", len(real))
    assert migrations.run(db, **QUIET) == 1
    con = sqlite3.connect(db)
    assert migrations.version(con) == migrations.LATEST and con.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 0
    assert con.execute("SELECT name FROM foods").fetchall() == [("Kiwi",)]
    assert os.listdir(tmp_path / "backups")[0].startswith(f"pre-migration-v1-to-v{migrations.LATEST}-")


def test_v2_upgrades_to_cooked_state(tmp_path, monkeypatch):
    """Version 3 (okf/domain/food.md): existing foods become 'as sold' with no cooking ratio, nothing else changes."""
    real = migrations.MIGRATIONS
    monkeypatch.setattr(migrations, "MIGRATIONS", real[:2]); monkeypatch.setattr(migrations, "LATEST", 2)
    db = deployed_db(tmp_path)
    monkeypatch.setattr(migrations, "MIGRATIONS", real); monkeypatch.setattr(migrations, "LATEST", len(real))
    assert migrations.run(db, **QUIET) == 2
    con = sqlite3.connect(db)
    assert con.execute("SELECT name, basis, cook_raw_g, cook_cooked_g FROM foods").fetchall() == [("Kiwi", "as-sold", None, None)]


def test_v3_upgrades_to_moved_from(tmp_path, monkeypatch):
    """Version 4 (okf/rules/same-day-edits.md): nothing logged so far is marked as moved."""
    real = migrations.MIGRATIONS
    monkeypatch.setattr(migrations, "MIGRATIONS", real[:3]); monkeypatch.setattr(migrations, "LATEST", 3)
    db = deployed_db(tmp_path)
    monkeypatch.setattr(migrations, "MIGRATIONS", real); monkeypatch.setattr(migrations, "LATEST", len(real))
    assert migrations.run(db, **QUIET) == 3
    con = sqlite3.connect(db)
    assert con.execute("SELECT day, time, moved_from FROM meals").fetchall() == [("2026-10-26", "07:30", None)]


def test_v4_rewrites_multiplied_portion_labels(tmp_path, monkeypatch):
    """Version 5 (okf/domain/portion.md): '½ × 1 serving' becomes '½ serving'; good labels and the log are untouched."""
    real = migrations.MIGRATIONS
    monkeypatch.setattr(migrations, "MIGRATIONS", real[:4]); monkeypatch.setattr(migrations, "LATEST", 4)
    db = deployed_db(tmp_path)
    con = sqlite3.connect(db)
    con.executescript("INSERT INTO portions(food_id, label, grams) VALUES ('kiwi', '½ × 1 serving', 40), ('kiwi', '1½ × 4 Nuggets', 90),"
                      " ('kiwi', '1 1/3 Cup', 120), ('kiwi', 'a handful', 30);"
                      "UPDATE meal_items SET portion_label = '½ × 1 serving';")
    con.commit(); con.close()
    monkeypatch.setattr(migrations, "MIGRATIONS", real); monkeypatch.setattr(migrations, "LATEST", len(real))
    assert migrations.run(db, **QUIET) == 4
    con = sqlite3.connect(db)
    assert [r[0] for r in con.execute("SELECT label FROM portions ORDER BY id")] == ["½ serving", "6 Nuggets", "1 1/3 Cup", "a handful"]
    assert con.execute("SELECT portion_label FROM meal_items").fetchone()[0] == "½ × 1 serving"   # the log keeps its snapshot


def test_v5_adds_fiber_columns(tmp_path, monkeypatch):
    """Version 6 (okf/domain/food.md): fiber columns, empty for every food already saved; carbs unchanged."""
    real = migrations.MIGRATIONS
    monkeypatch.setattr(migrations, "MIGRATIONS", real[:5]); monkeypatch.setattr(migrations, "LATEST", 5)
    db = deployed_db(tmp_path)
    before = sqlite3.connect(db).execute("SELECT id, carbs_per_100g FROM foods ORDER BY id").fetchall()
    monkeypatch.setattr(migrations, "MIGRATIONS", real); monkeypatch.setattr(migrations, "LATEST", len(real))
    assert migrations.run(db, **QUIET) == 5
    con = sqlite3.connect(db)
    assert con.execute("SELECT id, carbs_per_100g FROM foods ORDER BY id").fetchall() == before
    assert con.execute("SELECT COUNT(*) FROM foods WHERE serving_fiber IS NOT NULL OR fiber_per_100g IS NOT NULL OR fiber_checked_at IS NOT NULL").fetchone()[0] == 0


def test_v8_moves_barcodes_into_their_field(tmp_path, monkeypatch):
    """Version 9 (okf/domain/food.md): a barcode in the source text is copied to its own field; nothing else changes."""
    real = migrations.MIGRATIONS
    monkeypatch.setattr(migrations, "MIGRATIONS", real[:8]); monkeypatch.setattr(migrations, "LATEST", 8)
    db = deployed_db(tmp_path)
    con = sqlite3.connect(db)
    with con:
        con.execute("INSERT INTO foods(id, name, carbs_per_100g, source_kind, source_ref) VALUES "
                    "('crackers', 'Crackers', 66, 'openfoodfacts', 'Open Food Facts, barcode 0016000275287')")
    before = con.execute("SELECT id, carbs_per_100g, source_ref FROM foods ORDER BY id").fetchall()
    con.close()
    monkeypatch.setattr(migrations, "MIGRATIONS", real); monkeypatch.setattr(migrations, "LATEST", len(real))
    assert migrations.run(db, **QUIET) == 8
    con = sqlite3.connect(db)
    assert con.execute("SELECT id, carbs_per_100g, source_ref FROM foods ORDER BY id").fetchall() == before
    assert dict(con.execute("SELECT id, barcode FROM foods WHERE barcode IS NOT NULL").fetchall()) == {"crackers": "0016000275287"}


def test_v13_adds_favorite_photo(tmp_path, monkeypatch):
    """Version 14 (okf/features/favorite-plates.md): favorites keep their items and start with no plate photo."""
    real = migrations.MIGRATIONS
    monkeypatch.setattr(migrations, "MIGRATIONS", real[:13]); monkeypatch.setattr(migrations, "LATEST", 13)
    db = deployed_db(tmp_path)
    con = sqlite3.connect(db)
    with con:
        con.execute("INSERT INTO favorites(name, sort) VALUES ('Breakfast', 1)")
    con.close()
    monkeypatch.setattr(migrations, "MIGRATIONS", real); monkeypatch.setattr(migrations, "LATEST", len(real))
    assert migrations.run(db, **QUIET) == 13
    con = sqlite3.connect(db)
    assert con.execute("SELECT name, photo, photo_candidate FROM favorites").fetchall() == [("Breakfast", None, None)]


def test_v14_adds_push_subscriptions(tmp_path, monkeypatch):
    """Version 15 (okf/architecture/web-push.md): an empty table of phones; nothing else changes."""
    real = migrations.MIGRATIONS
    monkeypatch.setattr(migrations, "MIGRATIONS", real[:14]); monkeypatch.setattr(migrations, "LATEST", 14)
    db = deployed_db(tmp_path)
    monkeypatch.setattr(migrations, "MIGRATIONS", real); monkeypatch.setattr(migrations, "LATEST", len(real))
    assert migrations.run(db, **QUIET) == 14
    con = sqlite3.connect(db)
    assert con.execute("SELECT COUNT(*) FROM push_subscriptions").fetchone() == (0,)
    assert migrations.version(con) == 15
