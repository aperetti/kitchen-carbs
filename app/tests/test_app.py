"""Tests for the rules in okf/rules/ and the calculations in okf/domain/."""
import importlib
import re
import json
import os
import sqlite3
from datetime import datetime

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("KC_DATA", str(tmp_path))
    monkeypatch.setenv("KC_NIGHTSCOUT_SYNC", "0")
    from server import db, main
    importlib.reload(db)
    importlib.reload(main)
    monkeypatch.setattr(main, "now", lambda: datetime(2026, 10, 27, 18, 30))
    monkeypatch.setattr(main, "RUN_JOBS_IN_BACKGROUND", False)
    with TestClient(main.app) as client:
        client.post("/api/pin", json={"pin": "1234"})
        client.headers["X-Parent-Pin"] = "1234"
        yield client, main


def meal(day="2026-10-27", time="18:05", qty=1, cid="client-0001"):
    return {"client_id": cid, "day": day, "time": time, "items": [
        {"food_id": "pasta-cooked", "food_name": "Pasta, cooked", "portion_label": "1 cup",
         "grams": 140, "carbs_per_100g": 30.9, "qty": qty}]}


# ---- core maths ----
def test_whole_gram_rounding_is_half_up():
    from server.core import whole_grams
    assert whole_grams(42.5) == 43 and whole_grams(43.5) == 44 and whole_grams(42.49) == 42


def test_total_rounds_once():
    from server.core import total_carbs
    # three items of 10.4 g: rounding each gives 30, rounding the sum gives 31
    assert total_carbs([10.4, 10.4, 10.4]) == 31


def test_stats_and_coverage():
    from server.core import glucose_stats
    step = 300_000
    rs = [(i * step, v) for i, v in enumerate([60, 100, 150, 200, 260, 120])]
    s = glucose_stats(rs, 70, 180, 0, 12 * step)
    assert s["count"] == 6 and s["coverage"] == 0.5 and not s["complete"]
    assert s["below"] == pytest.approx(16.7) and s["very_high"] == pytest.approx(16.7)
    assert s["lows"] == 1 and s["gmi"] is None


def test_meal_window_keeps_gaps():
    from server.core import meal_window
    m = 10_000_000
    rs = [(m - 300_000, 118), (m + 3_600_000, 215), (m + 7_200_000, 190)]
    w = meal_window(rs, m, m + 4 * 3_600_000)
    assert w["at_meal"] == 118 and w["peak"]["sgv"] == 215 and w["two_h"] == 190
    assert w["coverage"] < 0.1 and not w["in_progress"]


# ---- foods ----
def test_seeded_foods_are_drafts_with_estimated_photos(app):
    client, _ = app
    foods = client.get("/api/foods").json()
    assert len(foods) == 4
    pasta = next(f for f in foods if f["id"] == "pasta-cooked")
    assert pasta["trust"] == "draft"
    assert [p["carbs"] for p in pasta["portions"]] == [22, 43, 65]
    assert all(p["photo"]["estimated"] for p in pasta["portions"])


def test_food_needs_source_and_pin(app):
    client, _ = app
    body = {"name": "Banana", "carbs_per_100g": 22.8, "source_kind": "usda", "source_ref": ""}
    assert client.post("/api/foods", json=body).status_code == 422
    body["source_ref"] = "USDA banana, raw"
    assert client.post("/api/foods", json=body, headers={"X-Parent-Pin": "9999"}).status_code == 401
    r = client.post("/api/foods", json={**body, "verified": True})
    assert r.status_code == 200 and r.json()["trust"] == "parent-verified"


def test_changing_carbs_unverifies_unless_confirmed(app):
    client, _ = app
    f = client.post("/api/foods", json={"name": "Oats", "carbs_per_100g": 66, "source_kind": "label",
                                        "source_ref": "Bag label", "verified": True}).json()
    r = client.put(f"/api/foods/{f['id']}", json={"name": "Oats", "carbs_per_100g": 60, "source_kind": "label",
                                                  "source_ref": "Bag label", "verified": False}).json()
    assert r["trust"] == "draft" and r["verified_at"] is None



def test_food_confirmations_per_account(app, monkeypatch):
    """okf/features/confirm-food.md: a carbs or cooking-ratio change clears everyone's confirmation but the editor's."""
    client, main = app
    assert client.get("/api/confirmations").json() == {"enabled": False, "foods": []}   # sign-in off: nothing to confirm
    monkeypatch.setattr(main.auth, "enabled", lambda: True)
    monkeypatch.setattr(main.auth, "lookup", lambda c, raw: (raw, False) if raw else None)
    as_ = lambda who: {"Cookie": f"kc_session={who}"}
    mine = lambda who: client.get("/api/confirmations", headers=as_(who)).json()["foods"]
    body = {"name": "Oats", "carbs_per_100g": 66, "source_kind": "label", "source_ref": "Bag label", "verified": True}
    fid = client.post("/api/foods", json=body, headers=as_("mum@x")).json()["id"]
    assert fid in mine("mum@x") and fid not in mine("dad@x")             # the person who added it has checked it
    assert client.post(f"/api/foods/{fid}/confirm", headers=as_("dad@x")).status_code == 200
    assert fid in mine("dad@x") and "pasta-cooked" not in mine("dad@x")
    client.put(f"/api/foods/{fid}", json={**body, "name": "Rolled oats", "notes": "big bag"}, headers=as_("mum@x"))
    assert fid in mine("dad@x")                                          # other edits keep confirmations
    client.put(f"/api/foods/{fid}", json={**body, "carbs_per_100g": 60}, headers=as_("dad@x"))
    assert fid in mine("dad@x") and fid not in mine("mum@x")             # only the editor stays confirmed
    client.post(f"/api/foods/{fid}/confirm", headers=as_("mum@x"))
    client.put(f"/api/foods/{fid}", json={**body, "carbs_per_100g": 60, "basis": "raw", "cook_raw_g": 100, "cook_cooked_g": 240},
               headers=as_("mum@x"))
    assert fid in mine("mum@x") and fid not in mine("dad@x")             # a new cooking ratio counts too
    assert client.post("/api/foods/nope/confirm", headers=as_("dad@x")).status_code == 404
    assert client.post(f"/api/foods/{fid}/confirm").status_code == 401   # signed out



def test_food_barcode(app, monkeypatch):
    """okf/domain/food.md: the barcode is its own field; changing it changes nothing else."""
    client, main = app
    monkeypatch.setattr(main.auth, "enabled", lambda: True)
    monkeypatch.setattr(main.auth, "lookup", lambda c, raw: (raw, False) if raw else None)
    me = {"Cookie": "kc_session=mum@x"}
    body = {"name": "Crackers", "serving_grams": 30, "serving_carbs": 20, "source_kind": "openfoodfacts",
            "source_ref": "Open Food Facts, barcode 0016000275287", "verified": True}
    f = client.post("/api/foods", json=body, headers=me).json()
    assert f["barcode"] == "0016000275287"                          # taken from the source when not sent
    r = client.put(f"/api/foods/{f['id']}", json={**body, "barcode": "5000112637922"}, headers=me).json()
    assert r["barcode"] == "5000112637922" and r["source_ref"] == body["source_ref"]
    assert (r["carbs_per_100g"], r["trust"], r["verified_at"]) == (f["carbs_per_100g"], f["trust"], f["verified_at"])
    assert f["id"] in client.get("/api/confirmations", headers=me).json()["foods"]
    assert client.put(f"/api/foods/{f['id']}", json=body, headers=me).json()["barcode"] == "5000112637922"   # not sent: kept
    assert client.put(f"/api/foods/{f['id']}", json={**body, "barcode": None}, headers=me).json()["barcode"] is None
    assert client.put(f"/api/foods/{f['id']}", json={**body, "barcode": "12ab"}, headers=me).status_code == 422

# ---- meals ----


def test_correct_meal_total(app):
    """okf/domain/meal.md: the total can be corrected with a reason; the items keep their saved carbs."""
    client, _ = app
    mid = client.post("/api/meals", json=meal()).json()["id"]
    assert client.put(f"/api/meals/{mid}/carbs", json={"total": 35}).status_code == 422                 # a reason is required
    assert client.put(f"/api/meals/{mid}/carbs", json={"total": 35, "reason": "  "}).status_code == 422
    assert client.put(f"/api/meals/{mid}/carbs", json={"total": 43, "reason": "same"}).status_code == 400
    r = client.put(f"/api/meals/{mid}/carbs", json={"total": 35, "reason": "Only half the juice was poured"}).json()
    assert r == {"total": 35, "corrected": True}
    log = client.get("/api/log").json()
    m = log["meals"][0]
    assert (m["total"], m["items_total"], m["carbs_corrected"], log["total"]) == (35, 43, 35, 35)
    assert sum(i["carbs"] for i in m["items"]) == 43                                                     # items unchanged
    assert m["comments"][-1]["text"] == "Carbs changed from 43 to 35 g: Only half the juice was poured"
    import csv as csvmod, io as iomod
    row = next(r for r in csvmod.DictReader(iomod.StringIO(client.get("/api/export.csv?start=2026-10-27&end=2026-10-27").text)) if r["type"] == "meal")
    assert (row["meal_total_g"], row["meal_total_from_foods_g"]) == ("35", "43")
    assert client.get("/api/stats?days=1").json()["carbs_total"] == 35
    r = client.put(f"/api/meals/{mid}/carbs", json={"total": 43, "reason": "Recounted, the label was right"}).json()
    assert r == {"total": 43, "corrected": False}
    m = client.get("/api/log").json()["meals"][0]
    assert m["carbs_corrected"] is None and "back to the foods" in m["comments"][-1]["text"]
    old = client.post("/api/meals", json=meal(day="2026-10-26", cid="fix-old-1")).json()["id"]
    client.put(f"/api/meals/{old}/carbs", json={"total": 50, "reason": "Seconds"})
    o = client.get("/api/log?day=2026-10-26").json()["meals"][0]
    assert (o["total"], o["edited_at"], o["comments"][-1]["time"]) == (50, "2026-10-27 18:30", "2026-10-27 18:30")
    client.put("/api/settings/past-edits", json={"allowed": False})
    assert client.put(f"/api/meals/{old}/carbs", json={"total": 40, "reason": "x y z"}).status_code == 409


def test_soft_delete_and_restore(app):
    """okf/domain/meal-log.md: deleting keeps the meal or entry, out of every total, and it can be restored."""
    client, _ = app
    mid = client.post("/api/meals", json=meal()).json()["id"]
    eid = client.post("/api/entries", json={"client_id": "del-entry-1", "day": "2026-10-27", "time": "12:00", "carbs": 15, "insulin": 1, "insulin_kind": "rapid"}).json()["id"]
    assert client.get("/api/log").json()["total"] == 43 + 15
    assert client.delete(f"/api/meals/{mid}").status_code == 200 and client.delete(f"/api/entries/{eid}").status_code == 200
    log = client.get("/api/log").json()
    assert (log["meals"], log["entries"], log["total"], log["insulin"]) == ([], [], 0, {})
    assert {(d["kind"], d["id"], d["deleted_at"]) for d in log["deleted"]} == {("meal", mid, "2026-10-27 18:30"), ("entry", eid, "2026-10-27 18:30")}
    assert next(d for d in log["deleted"] if d["kind"] == "meal")["carbs"] == 43
    assert client.get("/api/stats?days=1").json()["meals"] == 0
    assert "meal" not in client.get("/api/export.csv?start=2026-10-27&end=2026-10-27").text.split("\n", 1)[1]
    assert client.patch(f"/api/meals/{mid}", json={"eaten": "all"}).status_code == 404   # deleted: nothing else changes it
    assert client.delete(f"/api/meals/{mid}").status_code == 404
    assert client.post("/api/meals", json=meal()).json()["duplicate"]                       # a queued copy doesn't bring it back
    assert client.post(f"/api/meals/{mid}/restore").status_code == 200 and client.post(f"/api/entries/{eid}/restore").status_code == 200
    log = client.get("/api/log").json()
    assert log["total"] == 43 + 15 and log["deleted"] == [] and log["meals"][0]["edited_at"] is None
    assert client.post(f"/api/meals/{mid}/restore").status_code == 404
    # an earlier day: restoring follows the setting, and is marked
    old = client.post("/api/meals", json=meal(day="2026-10-26", cid="old-del-1")).json()["id"]
    client.delete(f"/api/meals/{old}")
    client.put("/api/settings/past-edits", json={"allowed": False})
    assert client.post(f"/api/meals/{old}/restore").status_code == 409
    client.put("/api/settings/past-edits", json={"allowed": True})
    assert client.post(f"/api/meals/{old}/restore").status_code == 200
    assert client.get("/api/log?day=2026-10-26").json()["meals"][0]["edited_at"] == "2026-10-27 18:30"


def test_carbs_entered_by_hand(app):
    """okf/domain/plate.md: carbs typed with a description, saved without a weight, counted in the total."""
    client, _ = app
    hand = {"food_name": "Party cake at school", "portion_label": "x", "entered_carbs": 32.5}
    body = {**meal(cid="hand-meal-1", time="18:30"), "items": [*meal()["items"], hand]}
    for bad in ({**hand, "entered_carbs": 0}, {**hand, "entered_carbs": 301}, {**hand, "food_name": "  "},
                {"food_name": "Mystery", "portion_label": "1 serving", "qty": 1}):
        assert client.post("/api/meals", json={**body, "client_id": "hand-bad-" + str(len(str(bad))), "items": [bad]}).status_code == 422, bad
    mid = client.post("/api/meals", json=body).json()["id"]
    m = next(x for x in client.get("/api/log").json()["meals"] if x["id"] == mid)
    weighed, typed = m["items"]
    assert (typed["food_name"], typed["portion_label"], typed["entered_carbs"], typed["food_id"]) == ("Party cake at school", "Carbs entered by hand", 32.5, None)
    assert abs(m["total_exact"] - (weighed["carbs_exact"] + 32.5)) < 1e-9
    csv_text = client.get("/api/export.csv?start=2026-10-27&end=2026-10-27").text
    assert "18:30,meal,Party cake at school,Carbs entered by hand,,,33," in csv_text
    fav = client.post(f"/api/meals/{mid}/favorite", json={"name": "Cake night"}).json()   # pinning leaves the typed carbs out
    assert [i["food_name"] for i in fav["items"]] == [weighed["food_name"]]
    only = client.post("/api/meals", json={**meal(cid="hand-meal-2"), "items": [hand]}).json()["id"]
    assert "nothing to pin" in client.post(f"/api/meals/{only}/favorite", json={"name": "Cake"}).json()["detail"]


def test_meal_details_optional(app):
    """okf/domain/meal.md: BG, insulin (bolus or basal) and timings go with the meal; all optional, editable today."""
    client, _ = app
    assert client.post("/api/meals", json=meal(cid="plain-meal-1")).status_code == 200   # nothing extra is fine
    bad = [{"insulin": 2.5}, {"insulin": 2.52, "insulin_kind": "bolus"}, {"insulin": 1, "insulin_kind": "rapid"},
           {"eat_min": 0}, {"bg": 5}, {"insulin": 1, "insulin_kind": "bolus", "insulin_offset_min": 200}]
    for i, extra in enumerate(bad):
        assert client.post("/api/meals", json={**meal(cid=f"bad-meal-{i}"), **extra}).status_code == 422, extra
    r = client.post("/api/meals", json={**meal(cid="detail-meal-1", time="18:20"), "bg": 180, "bg_source": "cgm", "insulin": 3.45,
                                        "insulin_kind": "bolus", "insulin_offset_min": 15, "eat_min": 25}).json()
    log = client.get("/api/log").json()
    m = next(x for x in log["meals"] if x["id"] == r["id"])
    assert (m["bg"], m["bg_source"], m["insulin"], m["insulin_kind"], m["insulin_offset_min"], m["eat_min"]) == (180, "cgm", 3.45, "bolus", 15, 25)
    assert log["insulin"] == {"bolus": 3.45}
    # changed later: no insulin clears its kind and timing; a BG without a source is a meter reading
    d = client.put(f"/api/meals/{r['id']}/details", json={"bg": 140, "eat_min": 40}).json()
    assert d == {"bg": 140, "bg_source": "meter", "insulin": None, "insulin_kind": None, "insulin_offset_min": None, "eat_min": 40}
    marks = client.get(f"/api/meals/{r['id']}/glucose").json()["entries"]
    assert {"ms": marks[-1]["ms"], "bg": 140}.items() <= marks[-1].items()
    csv_text = client.get("/api/export.csv?start=2026-10-27&end=2026-10-27").text
    assert ",140,,,,,meter,,40" in csv_text
def test_log_snapshots_values(app):
    client, _ = app
    client.post("/api/meals", json=meal(qty=1.5))
    client.put("/api/foods/pasta-cooked", json={"name": "Pasta, cooked", "carbs_per_100g": 25,
                                                "source_kind": "usda", "source_ref": "x"})
    log = client.get("/api/log").json()
    assert log["meals"][0]["items"][0]["carbs"] == 65 and log["total"] == 65


def test_half_steps_only(app):
    client, _ = app
    assert client.post("/api/meals", json=meal(qty=0.3)).status_code == 422
    assert client.post("/api/meals", json=meal(qty=0.5)).status_code == 200


def test_queued_meal_saved_once(app):
    client, _ = app
    a = client.post("/api/meals", json=meal()).json()
    b = client.post("/api/meals", json=meal()).json()
    assert a["id"] == b["id"] and b["duplicate"]
    assert len(client.get("/api/log").json()["meals"]) == 1


def test_same_day_edits(app):
    """okf/rules/same-day-edits.md: earlier days change while the setting allows it, marked; off, they're read-only."""
    client, _ = app
    today = client.post("/api/meals", json=meal()).json()["id"]
    old = client.post("/api/meals", json=meal(day="2026-10-26", cid="client-0002")).json()["id"]
    assert client.patch(f"/api/meals/{today}", json={"eaten": "most"}).status_code == 200
    assert client.post(f"/api/meals/{today}/comments", json={"text": "Left the crusts"}).status_code == 200
    m = client.get("/api/log").json()["meals"][0]
    assert m["eaten"] == "most" and m["comments"][0] == {**m["comments"][0], "time": "18:30", "text": "Left the crusts"}
    assert m["edited_at"] is None                                           # today's changes aren't marked
    # on by default: an earlier day can change, and is marked
    assert client.get("/api/settings").json()["past_edits"] is True
    assert client.get("/api/log?day=2026-10-26").json()["editable"] is True
    assert client.patch(f"/api/meals/{old}", json={"eaten": "half"}).status_code == 200
    assert client.put(f"/api/meals/{old}/details", json={"bg": 150}).status_code == 200
    assert client.post(f"/api/meals/{old}/comments", json={"text": "Felt low later"}).status_code == 200
    o = client.get("/api/log?day=2026-10-26").json()["meals"][0]
    assert (o["eaten"], o["bg"], o["edited_at"], o["comments"][0]["time"]) == ("half", 150, "2026-10-27 18:30", "2026-10-27 18:30")
    e = client.post("/api/entries", json={"client_id": "late-entry-1", "day": "2026-10-26", "time": "21:00", "bg": 99}).json()
    assert client.get("/api/log?day=2026-10-26").json()["entries"][0]["edited_at"] == "2026-10-27 18:30"   # added later: marked
    assert "2026-10-27 18:30" in client.get("/api/export.csv?start=2026-10-26&end=2026-10-26").text.splitlines()[1]
    # the parent turns it off: the server refuses, not just the screen
    assert client.put("/api/settings/past-edits", json={"allowed": False}, headers={"X-Parent-Pin": "0000"}).status_code == 401
    assert client.put("/api/settings/past-edits", json={"allowed": False}).json()["past_edits"] is False
    assert client.get("/api/log?day=2026-10-26").json()["editable"] is False
    assert client.patch(f"/api/meals/{old}", json={"eaten": "all"}).status_code == 409
    assert client.put(f"/api/meals/{old}/details", json={}).status_code == 409
    assert client.post(f"/api/meals/{old}/comments", json={"text": "x"}).status_code == 409
    assert client.delete(f"/api/meals/{old}").status_code == 409
    assert client.delete(f"/api/entries/{e['id']}").status_code == 409
    assert client.post("/api/entries", json={"client_id": "late-entry-2", "day": "2026-10-26", "time": "21:30", "bg": 99}).status_code == 409
    assert client.patch(f"/api/meals/{today}", json={"eaten": "all"}).status_code == 200   # today is always editable
    client.put("/api/settings/past-edits", json={"allowed": True})
    assert client.delete(f"/api/meals/{old}").status_code == 200


def test_stats_periods(app):
    client, _ = app
    client.post("/api/meals", json=meal())
    r = client.get("/api/stats?days=7").json()
    assert r["days"] == 7 and r["carbs_total"] == 43 and r["glucose"] is None
    assert client.get("/api/stats?days=5").status_code == 400


def test_no_future_meals(app):
    client, _ = app
    assert client.post("/api/meals", json=meal(day="2026-10-28")).status_code == 400


def test_export_has_eaten_and_comments(app):
    client, _ = app
    mid = client.post("/api/meals", json=meal()).json()["id"]
    client.patch(f"/api/meals/{mid}", json={"eaten": "most"})
    client.post(f"/api/meals/{mid}/comments", json={"text": "Left the crusts"})
    csv = client.get("/api/export.csv?start=2026-10-27&end=2026-10-27").text
    assert '"Pasta, cooked",1 cup,140,1,43,43,most,,,,18:30 Left the crusts' in csv


# ---- nightscout ----
def test_nightscout_is_read_only_and_token_hidden(app, monkeypatch):
    client, main = app
    calls = []

    class R:
        status_code = 200
        def __init__(self, data): self._d = data
        def json(self): return self._d

    def fake_get(url, params=None, **kw):
        calls.append(("GET", url, params))
        if url.endswith("status.json"):
            return R({"settings": {"thresholds": {"bgTargetBottom": 80, "bgTargetTop": 170}}})
        base = int(datetime(2026, 10, 27, 17, 30).timestamp() * 1000)
        if params.get("count") == 1:
            return R([{"date": base, "sgv": 118, "direction": "Flat"}])
        lo, hi = params["find[date][$gt]"], params["find[date][$lte]"]
        return R([{"date": base + i * 300_000, "sgv": 118 + i} for i in range(40) if lo < base + i * 300_000 <= hi])

    def fail_write(*a, **k):
        raise AssertionError("Nightscout must never be written to")

    monkeypatch.setattr(main.nightscout.requests, "get", fake_get)
    for verb in ("post", "put", "delete", "patch"):
        monkeypatch.setattr(main.nightscout.requests, verb, fail_write)
    monkeypatch.setattr(main.threading, "Thread", lambda target, daemon: type("T", (), {"start": lambda s: None})())
    r = client.post("/api/nightscout", json={"url": "https://ns.example.org/", "token": "kitchen-abc123"})
    assert r.status_code == 200
    monkeypatch.setattr(main.nightscout.time, "time", lambda: datetime(2026, 10, 27, 21, 0).timestamp())
    assert main.nightscout.sync_once() == 40
    status = client.get("/api/nightscout").json()
    assert "kitchen-abc123" not in str(status) and status["low"] == 80 and status["readings"] == 40
    mid = client.post("/api/meals", json=meal()).json()["id"]
    w = client.get(f"/api/meals/{mid}/glucose").json()
    assert w["at_meal"] == 125 and w["in_progress"]


# ---- tags and favorites ----
def test_default_tags_and_multiple_tags(app):
    client, _ = app
    tags = {t["name"]: t["id"] for t in client.get("/api/tags").json()}
    assert list(tags)[:3] == ["Breakfast", "Lunch", "Dinner"]
    apple = next(f for f in client.get("/api/foods").json() if f["id"] == "apple-sliced")
    assert set(apple["tags"]) == {tags["Breakfast"], tags["Lunch"]}
    body = {"name": "Yogurt", "carbs_per_100g": 4.7, "source_kind": "label", "source_ref": "Tub", "tags": [tags["Breakfast"], tags["Dinner"]]}
    f = client.post("/api/foods", json=body).json()
    assert f["tags"] == [tags["Breakfast"], tags["Dinner"]] and "category" not in f
    assert client.post("/api/tags", json={"name": "Favorites"}).status_code == 400
    snacks = client.post("/api/tags", json={"name": "Snacks"}).json()
    assert [t["name"] for t in snacks][-1] == "Snacks"
    assert client.post("/api/tags", json={"name": "snacks"}).status_code == 409


def test_favorites_use_current_values(app):
    client, _ = app
    foods = {f["id"]: f for f in client.get("/api/foods").json()}
    toast, apple = foods["toast-whole-wheat"]["portions"][0], foods["apple-sliced"]["portions"][1]
    fav = client.post("/api/favorites", json={"name": "Usual breakfast", "items": [
        {"portion_id": toast["id"], "qty": 2}, {"portion_id": apple["id"], "qty": 0.5}]}).json()
    assert fav["total"] == 37 and fav["missing"] == 0   # 2×13.216 + 0.5×20.7 = 36.78
    client.put("/api/foods/toast-whole-wheat", json={"name": "Toast, whole-wheat", "carbs_per_100g": 45,
                                                     "source_kind": "label", "source_ref": "Bread bag"})
    assert client.get("/api/favorites").json()[0]["total"] == 39   # 2×14.4 + 10.35
    client.delete(f"/api/portions/{toast['id']}")
    fav = client.get("/api/favorites").json()[0]
    assert fav["missing"] == 1 and fav["items"][0]["missing"] and fav["items"][0]["food_name"] == "Toast, whole-wheat"


def test_pin_meal_as_favorite(app):
    client, _ = app
    pasta = next(f for f in client.get("/api/foods").json() if f["id"] == "pasta-cooked")["portions"][1]
    body = meal(qty=1.5)
    body["items"][0]["portion_id"] = pasta["id"]
    mid = client.post("/api/meals", json=body).json()["id"]
    fav = client.post(f"/api/meals/{mid}/favorite", json={"name": "Pasta night"}).json()
    assert fav["name"] == "Pasta night" and fav["items"][0]["qty"] == 1.5 and fav["total"] == 65
    old = client.post("/api/meals", json=meal(cid="client-0009")).json()["id"]   # no portion_id: matched by name
    assert client.post(f"/api/meals/{old}/favorite", json={"name": "Old"}).json()["items"][0]["portion_id"] == pasta["id"]
    # amounts come from the weight slider, so any multiple of the portion is kept (to 2 places), within 0-10
    for bad in (0, 10.5):
        assert client.post("/api/favorites", json={"name": "x", "items": [{"portion_id": pasta["id"], "qty": bad}]}).status_code == 422
    odd = client.post("/api/favorites", json={"name": "Weighed", "items": [{"portion_id": pasta["id"], "qty": 1.234}]}).json()
    assert odd["items"][0]["qty"] == 1.23
    client.delete(f"/api/favorites/{odd['id']}")
    client.delete(f"/api/favorites/{fav['id']}")
    assert [f["name"] for f in client.get("/api/favorites").json()] == ["Old"]



def test_favorite_plate_photo(app, monkeypatch):
    """okf/features/favorite-plates.md: Gemini combines the foods' photos; nothing changes until the parent accepts."""
    client, main = app
    sent = {}

    def fake_generate(paths, prompt, quality="fast"):
        sent["paths"], sent["prompt"] = paths, prompt
        return "candidate/" + "a" * 32 + ".jpg"

    monkeypatch.setattr(main.photos, "generate", fake_generate)
    foods = {f["id"]: f for f in client.get("/api/foods").json()}
    toast, apple = foods["toast-whole-wheat"]["portions"][0], foods["apple-sliced"]["portions"][1]
    fav = client.post("/api/favorites", json={"name": "Usual breakfast", "items": [
        {"portion_id": toast["id"], "qty": 2}, {"portion_id": apple["id"], "qty": 1}]}).json()
    assert fav["photo"] is None and fav["photo_candidate"] is None
    assert client.post(f"/api/favorites/{fav['id']}/photo", headers={"X-Parent-Pin": "0000"}).status_code == 401
    out = client.post(f"/api/favorites/{fav['id']}/photo").json()
    assert sent["paths"] == [i["photo"] for i in fav["items"]]           # every food's photo, in order
    assert f"the meal has {toast['grams'] * 2:g} g" in sent["prompt"] and "the same amount" in sent["prompt"]
    assert out["photo_candidate"] and out["photo"] is None              # waits for the check
    out = client.post(f"/api/favorites/{fav['id']}/photo/review", json={"action": "accept"}).json()
    assert out["photo"] == "candidate/" + "a" * 32 + ".jpg" and out["photo_candidate"] is None
    assert client.post(f"/api/favorites/{fav['id']}/photo/review", json={"action": "accept"}).status_code == 400
    assert client.post(f"/api/favorites/{fav['id']}/photo/review", json={"action": "remove"}).json()["photo"] is None
    client.post(f"/api/favorites/{fav['id']}/photo"); client.post(f"/api/favorites/{fav['id']}/photo/review", json={"action": "accept"})
    client.delete(f"/api/portions/{toast['id']}")
    client.post(f"/api/favorites/{fav['id']}/drop-missing")                # a photo of foods that are gone goes too
    assert client.get("/api/favorites").json()[0]["photo"] is None
    assert client.post("/api/favorites/999/photo").status_code == 404


def test_plate_prompt_names_foods_without_photos():
    from server import photos
    foods = [{"food": "Toast", "label": "1 slice", "photo_grams": 32, "grams": 32, "photo": "styled/a.jpg"},
             {"food": "Milk", "label": "1 cup", "photo_grams": 240, "grams": 120, "photo": None}]
    prompt, refs = photos.build_plate_prompt("", foods)
    assert refs == ["styled/a.jpg"] and "120 g of Milk (1 cup)" in prompt and photos.DEFAULT_STYLE in prompt
    many = [{**foods[0], "food": f"F{n}"} for n in range(12)]
    prompt, refs = photos.build_plate_prompt("", many)
    assert len(refs) == photos.PLATE_PHOTOS and "32 g of F11" in prompt   # past the limit, described by name


# ---- nutrition label scanning ----
def jpeg_bytes():
    import io
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (40, 30), "white").save(buf, "JPEG")
    return buf.getvalue()


def test_label_check_maths_and_warnings():
    from server.labels import check
    ok = check({"is_nutrition_label": True, "product_name": "Oat Rings", "serving_size_text": "1 cup (28g)",
                "serving_grams": 28, "total_carbs_g_per_serving": 20, "fiber_g_per_serving": 3})
    assert ok["reading"]["carbs_per_100g"] == 71.4 and ok["warnings"] == []
    cups = check({"is_nutrition_label": True, "serving_size_text": "1 cup (240 mL)", "total_carbs_g_per_serving": 12})
    assert cups["reading"]["carbs_per_100g"] is None and "no gram weight" in cups["warnings"][0]
    bad = check({"is_nutrition_label": True, "serving_grams": 20, "total_carbs_g_per_serving": 27})
    assert any("more than the serving weight" in w for w in bad["warnings"]) and bad["reading"]["carbs_per_100g"] is None
    clash = check({"is_nutrition_label": True, "serving_grams": 30, "total_carbs_g_per_serving": 21, "carbs_g_per_100g": 50})
    assert any("don't match" in w for w in clash["warnings"])
    assert check({"is_nutrition_label": False})["warnings"][0].startswith("This doesn't look like")
    assert check({"is_nutrition_label": True, "serving_grams": -5})["reading"]["serving_grams"] is None


def test_scan_label_flow(app, monkeypatch):
    client, main = app
    monkeypatch.setattr(main.labels, "ask_gemini", lambda path: {
        "is_nutrition_label": True, "product_name": "Oat Rings", "serving_size_text": "1 cup (28g)",
        "serving_grams": 28, "total_carbs_g_per_serving": 20})
    files = {"file": ("label.jpg", jpeg_bytes(), "image/jpeg")}
    assert client.post("/api/labels/read", files=files, headers={"X-Parent-Pin": "0000"}).status_code == 401
    r = client.post("/api/labels/read", files=files).json()
    assert r["label_photo"].startswith("labels/") and r["reading"]["carbs_per_100g"] == 71.4
    body = {"name": "Oat Rings", "carbs_per_100g": 71.4, "source_kind": "label",
            "source_ref": "Nutrition label photo", "label_photo": r["label_photo"]}
    unconfirmed = client.post("/api/foods", json=body)
    assert unconfirmed.status_code == 400 and "serving size and total carbohydrate" in unconfirmed.json()["detail"]
    f = client.post("/api/foods", json={**body, "verified": True}).json()
    assert f["label_photo"] == r["label_photo"] and f["trust"] == "parent-verified"
    p = client.post(f"/api/foods/{f['id']}/portions", json={"label": "1 serving", "grams": 28}).json()["portions"][0]
    assert p["carbs"] == 20
    assert client.post("/api/foods", json={"name": "x", "carbs_per_100g": 1, "source_kind": "label", "source_ref": "x",
                                           "label_photo": "../app.db"}).status_code == 422
    assert client.post("/api/labels/read", files={"file": ("x.txt", b"not an image", "text/plain")}).status_code == 400


# ---- photo style ----
def test_style_prompt_always_keeps_the_guard():
    from server.photos import GUARD, build_prompt
    prompt, refs = build_prompt("Make it a bigger portion on a marble table", {}, "auto")
    assert GUARD in prompt and refs == [] and "marble table" in prompt
    bases = {"plate": "base/p.jpg", "bowl": "base/b.jpg"}
    prompt, refs = build_prompt("", bases, "auto")
    assert refs == ["base/p.jpg", "base/b.jpg"] and "plate, bowl, in that order" in prompt and "white quartz" in prompt.lower()
    prompt, refs = build_prompt("x", bases, "bowl")
    assert refs == ["base/b.jpg"] and "exactly that bowl" in prompt
    prompt, refs = build_prompt("x", bases, "dressing")      # no dressing base photo yet: fall back to all
    assert refs == ["base/p.jpg", "base/b.jpg"]
    prompt, _ = build_prompt("x", {}, "auto", {"ref_grams": 140, "food": "Pasta", "grams": 70, "label": "½ cup"})
    assert "showing 70 g of the same food" in prompt


def test_style_setup_and_generation_inputs(app, monkeypatch):
    client, main = app
    sent = {}

    def fake_generate(paths, prompt, quality="fast"):
        sent["paths"], sent["prompt"] = paths, prompt
        return "candidate/x.jpg"

    monkeypatch.setattr(main.photos, "generate", fake_generate)
    files = {"file": ("bowl.jpg", jpeg_bytes(), "image/jpeg")}
    assert client.get("/api/style", headers={"X-Parent-Pin": "0000"}).status_code == 401
    s = client.post("/api/style/base/bowl", files=files).json()
    assert s["bases"]["bowl"].startswith("base/") and s["bases"]["plate"] is None
    assert client.post("/api/style/base/cup", files=files).status_code == 422
    client.put("/api/style", json={"prompt": "Dark walnut table, evening lamp light"})
    pasta = next(f for f in client.get("/api/foods").json() if f["id"] == "pasta-cooked")["portions"][1]
    client.post(f"/api/portions/{pasta['id']}/original", files={"file": ("p.jpg", jpeg_bytes(), "image/jpeg")})
    food = client.put(f"/api/portions/{pasta['id']}", json={"label": "1 cup", "grams": 140, "container": "bowl"}).json()
    assert next(p for p in food["portions"] if p["id"] == pasta["id"])["container"] == "bowl"
    client.post(f"/api/portions/{pasta['id']}/style")
    assert sent["paths"][0].startswith("original/") and sent["paths"][1] == s["bases"]["bowl"]
    assert "walnut" in sent["prompt"] and main.photos.GUARD in sent["prompt"]
    assert client.put("/api/style", json={"prompt": ""}).json()["prompt"] == main.photos.DEFAULT_STYLE
    assert client.delete("/api/style/base/bowl").json()["bases"]["bowl"] is None


def test_sized_photos(app):
    import io
    from PIL import Image
    client, main = app
    buf = io.BytesIO(); Image.new("RGB", (3200, 2400), "white").save(buf, "JPEG")
    pasta = next(f for f in client.get("/api/foods").json() if f["id"] == "pasta-cooked")["portions"][0]
    food = client.post(f"/api/portions/{pasta['id']}/original", files={"file": ("p.jpg", buf.getvalue(), "image/jpeg")}).json()
    path = next(p for p in food["portions"] if p["id"] == pasta["id"])["photo"]["original"]
    assert Image.open(io.BytesIO(client.get(f"/photos/{path}").content)).size == (3000, 2250)   # master capped at 3000
    r = client.get(f"/img/800/{path}")
    assert r.status_code == 200 and Image.open(io.BytesIO(r.content)).width == 800 and "immutable" in r.headers["cache-control"]
    assert client.get(f"/img/801/{path}").status_code == 404
    assert client.get("/img/800/original/..%2Fapp.db").status_code == 404
    small = next(f for f in client.get("/api/foods").json() if f["id"] == "toast-whole-wheat")["portions"][0]["photo"]["styled"]
    assert Image.open(io.BytesIO(client.get(f"/img/2400/{small}").content)).width <= 2400       # never upscaled


# ---- manual entries (okf/features/manual-log.md) ----
def entry(**kw):
    return {"client_id": kw.pop("cid", "entry-0001"), "day": "2026-10-27", "time": "18:00", **kw}


def test_manual_entries(app):
    client, _ = app
    assert client.post("/api/entries", json=entry()).status_code == 422                       # nothing recorded
    assert client.post("/api/entries", json=entry(insulin=2.5)).status_code == 422            # kind missing
    assert client.post("/api/entries", json=entry(insulin=2.53, insulin_kind="rapid")).status_code == 422
    assert client.post("/api/entries", json=entry(bg=15)).status_code == 422
    e = client.post("/api/entries", json=entry(bg=142, insulin=2.5, insulin_kind="rapid", carbs=15, note="juice")).json()
    assert client.post("/api/entries", json=entry(bg=142, insulin=2.5, insulin_kind="rapid")).json()["duplicate"]
    client.post("/api/entries", json=entry(cid="entry-0002", time="21:00", insulin=8, insulin_kind="long"))
    client.post("/api/meals", json=meal())
    log = client.get("/api/log").json()
    assert log["total"] == 43 + 15 and log["insulin"] == {"rapid": 2.5, "long": 8}
    assert [x["time"] for x in log["entries"]] == ["18:00", "21:00"]
    csv = client.get("/api/export.csv?start=2026-10-27&end=2026-10-27").text.splitlines()
    assert csv[1] == "2026-10-27,18:00,entry,,,,,15,,,142,2.5,rapid,juice,,meter,,,," and csv[2].startswith("2026-10-27,18:05,meal")
    assert client.delete(f"/api/entries/{e['id']}").status_code == 200
    assert client.get("/api/log").json()["insulin"] == {"long": 8}


def test_no_dose_is_ever_computed(app):
    """okf/rules/no-dosing.md: the log and stats only ever return insulin that was typed in; only /api/dose calculates."""
    client, _ = app
    client.post("/api/meals", json=meal(qty=2))
    body = json.dumps([client.get("/api/log").json(), client.get("/api/stats?days=7").json(),
                       client.get("/api/meals/1/glucose").json()])
    assert '"insulin": {}' in body
    for word in ("ratio", "dose", "bolus", "iob", "on_board", "suggest"):
        assert word not in body.lower()


# ---- food lookup (okf/features/food-lookup.md) ----
CHEERIOS = {"product_name": "Cheerios", "brands": "General Mills, Cheerios", "serving_size": "1.5 cup (39g)",
            "serving_quantity": 39, "serving_quantity_unit": "g",
            "nutriments": {"carbohydrates_100g": 74.36, "carbohydrates_serving": 29, "fiber_serving": 4}}


def test_off_reading_and_checks():
    from server import labels, lookup
    r = labels.check(lookup.off_reading(CHEERIOS))
    assert r["reading"]["product_name"] == "Cheerios – General Mills" and r["reading"]["carbs_per_100g"] == 74.36
    assert lookup.off_reading({**CHEERIOS, "brands": "Cheerios, General Mills"})["product_name"] == "Cheerios"
    assert r["warnings"] == []
    ml = labels.check(lookup.off_reading({**CHEERIOS, "serving_quantity": 240, "serving_quantity_unit": "ml"}))
    assert ml["reading"]["serving_grams"] is None and any("no gram weight" in w for w in ml["warnings"])


def test_lookup_endpoints(app, monkeypatch):
    client, main = app
    seen = {}
    monkeypatch.setattr(main.lookup, "off_product", lambda code, contact: (seen.update(contact=contact) or ("0016000275287", CHEERIOS)))
    monkeypatch.setattr(main.lookup, "fetch_image", lambda url, contact: None)
    monkeypatch.setattr(main.lookup, "fs_search", lambda q: [{"source": "fatsecret", "id": "4501", "name": "Pasta, cooked", "carbs_per_100g": 30.9}])
    def off_down(q, contact, *a): raise main.lookup.LookupError("Open Food Facts is limiting requests right now.")
    monkeypatch.setattr(main.lookup, "off_search", off_down)
    assert client.get("/api/lookup/search?q=pasta", headers={"X-Parent-Pin": "0000"}).status_code == 401
    s = client.get("/api/lookup/search?q=pasta").json()
    assert s["fatsecret"][0]["id"] == "4501" and s["off"] == [] and "limiting" in s["errors"][0]   # one source down, other still shown
    r = client.get("/api/lookup/off/0016000275287").json()
    assert r["mode"] == "serving" and r["source_ref"] == "Open Food Facts, barcode 0016000275287"
    chk = client.get("/api/lookup/off/0016000275287?check=true").json()   # comparing a new barcode: the numbers only
    assert chk["code"] == "0016000275287" and chk["reading"] == r["reading"] and "label_photo" not in chk
    assert seen["contact"] == "owner@example.com"                       # default contact
    client.put("/api/settings", json={"off_contact": "kitchen@example.org"})
    client.get("/api/lookup/off/0016000275287")
    assert seen["contact"] == "kitchen@example.org"
    assert client.put("/api/settings", json={"off_contact": "not an email"}).status_code == 422
    body = {"name": "Cheerios", "carbs_per_100g": 74.4, "source_kind": "openfoodfacts", "source_ref": r["source_ref"]}
    assert client.post("/api/foods", json=body).status_code == 400            # must be confirmed
    assert client.post("/api/foods", json={**body, "verified": True}).status_code == 200


def test_barcode_photo():
    import io
    import zxingcpp
    from PIL import Image
    from server import lookup
    img = zxingcpp.write_barcode(zxingcpp.BarcodeFormat.EAN13, "0016000275287", width=400, height=160) \
        if hasattr(zxingcpp, "write_barcode") else None
    if img is None:
        pytest.skip("zxing-cpp build without writer")
    buf = io.BytesIO(); Image.fromarray(img.__array__() if hasattr(img, "__array__") else img).convert("RGB").save(buf, "PNG")
    assert lookup.read_barcode(buf.getvalue()) == "0016000275287"
    with pytest.raises(lookup.LookupError, match="No barcode"):
        b = io.BytesIO(); Image.new("RGB", (200, 200), "white").save(b, "PNG"); lookup.read_barcode(b.getvalue())


def test_usda_ranking():
    from server.lookup import usda_rank
    names = ["Rice noodles, cooked", "Wild rice, cooked", "Rice, white, long-grain, regular, enriched, cooked",
             "Cereals, CREAM OF RICE, cooked with water", "Rice, brown, long-grain, cooked"]
    ranked = sorted(names, key=lambda n: usda_rank("rice cooked", n))
    assert ranked[:2] == ["Rice, brown, long-grain, cooked", "Rice, white, long-grain, regular, enriched, cooked"]
    apples = sorted(["Rose-apples, raw", "Mammy-apple, (mamey), raw", "Apples, raw, with skin"], key=lambda n: usda_rank("apple raw", n))
    assert apples[0] == "Apples, raw, with skin"


def test_off_search_query_and_results(monkeypatch):
    from server import lookup
    assert lookup.off_query("Yoshida sauce") == "(yoshida OR yoshida* OR yoshida's) (sauce OR sauce* OR sauce's)"
    hits = [{"code": "1", "product_name": "Gourmet sauce", "brands": ["Mr. Yoshida's"], "nutriments": {}},
            {"code": "2", "product_name": "Yoshida's Gourmet Sauce", "brands": "Mr. Yoshida's, Kikkoman",
             "nutriments": {"carbohydrates_100g": 33.3}, "image_front_small_url": "https://images.openfoodfacts.org/x.jpg"}]
    monkeypatch.setattr(lookup, "_get", lambda url, params=None, headers=None, what="": {"hits": hits})
    r = lookup.off_search("yoshida", "a@b.co")
    assert [x["id"] for x in r] == ["2", "1"] and r[1]["carbs_per_100g"] is None and r[0]["brand"] == "Mr. Yoshida's"
    calls = []
    def flaky(url, params=None, headers=None, what=""):
        calls.append(url)
        if "search.openfoodfacts" in url:
            raise lookup.LookupError("Open Food Facts answered 503.")
        return {"products": hits[1:]}
    monkeypatch.setattr(lookup, "_get", flaky)
    assert [x["id"] for x in lookup.off_search("yoshida", "a@b.co")] == ["2"] and "cgi/search.pl" in calls[1]


def test_photo_job_lifecycle(app, monkeypatch):
    client, main = app
    pasta = next(f for f in client.get("/api/foods").json() if f["id"] == "pasta-cooked")["portions"][1]
    client.post(f"/api/portions/{pasta['id']}/original", files={"file": ("p.jpg", jpeg_bytes(), "image/jpeg")})
    def boom(paths, prompt, quality="fast"): raise main.photos.PhotoError("Gemini did not make a photo: quota")
    monkeypatch.setattr(main.photos, "generate", boom)
    client.post(f"/api/portions/{pasta['id']}/style")
    p = next(x for x in client.get("/api/foods").json() if x["id"] == "pasta-cooked")["portions"][1]
    assert p["job"] is None and "quota" in p["job_error"]
    # a job in progress refuses a second start and shows in the food list
    main.RUN_JOBS_IN_BACKGROUND = True
    import threading
    gate = threading.Event()
    def slow(paths, prompt, quality="fast"):
        gate.wait(5)
        return "candidate/x.jpg"
    monkeypatch.setattr(main.photos, "generate", slow)
    assert client.post(f"/api/portions/{pasta['id']}/style").status_code == 200
    p = next(x for x in client.get("/api/foods").json() if x["id"] == "pasta-cooked")["portions"][1]
    assert p["job"]["kind"] == "style" and p["job_error"] is None
    assert client.post(f"/api/portions/{pasta['id']}/style").status_code == 409
    gate.set()
    for _ in range(50):
        p = next(x for x in client.get("/api/foods").json() if x["id"] == "pasta-cooked")["portions"][1]
        if not p["job"]:
            break
        import time; time.sleep(0.05)
    assert p["job"] is None and p["photo"]["candidate"] == "candidate/x.jpg"


# ---- size references (okf/domain/size-reference.md) ----
def test_size_reference_in_prompt():
    from server.photos import GUARD, build_prompt
    ref = {"name": "Measuring cup", "measurement": "1 cup, filled", "photo": "base/cup.jpg"}
    prompt, refs = build_prompt("", {"plate": "base/p.jpg"}, "plate", None, ref, {"label": "½ cup", "grams": 70})
    assert refs == ["base/p.jpg", "base/cup.jpg"] and "Image 3 is a size reference: Measuring cup, showing 1 cup, filled" in prompt
    assert "½ cup (70 g)" in prompt and "do not put the reference object in the photo" in prompt and GUARD in prompt
    prompt, refs = build_prompt("", {}, "auto", None, ref, {"label": "1 cup", "grams": 140})
    assert refs == ["base/cup.jpg"] and "Image 2 is a size reference" in prompt


def test_size_reference_crud_and_generation(app, monkeypatch):
    client, main = app
    sent = {}
    monkeypatch.setattr(main.photos, "generate", lambda paths, prompt, quality="fast": sent.update(paths=paths, prompt=prompt) or "candidate/x.jpg")
    files = {"file": ("cup.jpg", jpeg_bytes(), "image/jpeg")}
    assert client.post("/api/size-refs", data={"name": "Cup", "measurement": "1 cup"}, files=files, headers={"X-Parent-Pin": "0"}).status_code == 401
    s = client.post("/api/size-refs", data={"name": "Measuring cup", "measurement": "1 cup, filled"}, files=files).json()
    ref = s["size_refs"][0]
    assert ref["name"] == "Measuring cup" and ref["photo"].startswith("base/")
    pasta = next(f for f in client.get("/api/foods").json() if f["id"] == "pasta-cooked")["portions"][1]
    client.post(f"/api/portions/{pasta['id']}/original", files={"file": ("p.jpg", jpeg_bytes(), "image/jpeg")})
    assert client.put(f"/api/portions/{pasta['id']}", json={"label": "1 cup", "grams": 140, "size_ref_id": 999}).status_code == 400
    food = client.put(f"/api/portions/{pasta['id']}", json={"label": "1 cup", "grams": 140, "size_ref_id": ref["id"]}).json()
    assert next(p for p in food["portions"] if p["id"] == pasta["id"])["size_ref_id"] == ref["id"]
    client.post(f"/api/portions/{pasta['id']}/style")
    assert sent["paths"][-1] == ref["photo"] and "1 cup (140 g)" in sent["prompt"]
    client.put(f"/api/size-refs/{ref['id']}", json={"name": "Big cup", "measurement": "2 cups"})
    assert client.get("/api/size-refs").json()[0]["measurement"] == "2 cups"
    client.delete(f"/api/size-refs/{ref['id']}")
    p = next(f for f in client.get("/api/foods").json() if f["id"] == "pasta-cooked")["portions"][1]
    assert p["size_ref_id"] is None and client.get("/api/size-refs").json() == []


# ---- photo with no reference photo (okf/features/photo-pipeline.md step 6) ----
def test_generate_photo_from_name_alone(app, monkeypatch):
    client, main = app
    from server.photos import GUARD, build_prompt
    prompt, refs = build_prompt("", {}, "bowl", describe={"food": "Oat cereal", "grams": 30, "label": "1 cup"})
    assert refs == [] and "30 g of Oat cereal (1 cup)" in prompt and "plain white bowl" in prompt and GUARD not in prompt
    ref = {"name": "Cup", "measurement": "1 cup", "photo": "base/cup.jpg"}
    prompt, refs = build_prompt("", {"plate": "base/p.jpg"}, "plate", None, ref, {"label": "1 cup", "grams": 30},
                                {"food": "Oat cereal", "grams": 30, "label": "1 cup"})
    assert refs == ["base/p.jpg", "base/cup.jpg"] and "Image 1 is the family's plate" in prompt and "Image 2 is a size reference" in prompt

    sent = {}
    monkeypatch.setattr(main.photos, "generate", lambda paths, prompt, quality="fast": sent.update(paths=paths, prompt=prompt) or "candidate/g.jpg")
    food = client.post("/api/foods", json={"name": "Plain rice", "carbs_per_100g": 28, "source_kind": "usda",
                                           "source_ref": "USDA FDC 1", "tags": []}).json()
    p = client.post(f"/api/foods/{food['id']}/portions", json={"label": "½ cup", "grams": 80}).json()["portions"][0]
    out = client.post(f"/api/portions/{p['id']}/generate").json()
    assert sent["paths"] == [] and "80 g of Plain rice (½ cup)" in sent["prompt"]
    ph = out["portions"][0]["photo"]
    assert ph["candidate"] == "candidate/g.jpg" and ph["candidate_estimated"] and ph["candidate_kind"] == "generated"
    out = client.post(f"/api/portions/{p['id']}/review", json={"action": "accept"}).json()
    assert out["portions"][0]["photo"]["estimated"] is True and out["portions"][0]["photo"]["styled"] == "candidate/g.jpg"
    client.post(f"/api/portions/{p['id']}/original", files={"file": ("r.jpg", jpeg_bytes(), "image/jpeg")})
    assert client.post(f"/api/portions/{p['id']}/generate").status_code == 400


def test_size_reference_goes_with_a_dish(app):
    client, main = app
    from server.photos import build_prompt
    files = {"file": ("bowl.jpg", jpeg_bytes(), "image/jpeg")}
    s = client.post("/api/size-refs", data={"name": "Cereal bowl, to the line", "measurement": "1 cup", "container": "bowl"}, files=files).json()
    ref = s["size_refs"][0]
    assert ref["container"] == "bowl"
    assert client.post("/api/size-refs", data={"name": "x", "measurement": "1", "container": "cup"}, files=files).status_code == 422
    any_dish = client.post("/api/size-refs", data={"name": "Spoon", "measurement": "15 mL"}, files=files).json()["size_refs"][1]
    assert any_dish["container"] is None
    s = client.put(f"/api/size-refs/{ref['id']}", json={"name": "Cereal bowl", "measurement": "1 cup", "container": "plate"}).json()
    assert s["size_refs"][0]["container"] == "plate"
    prompt, _ = build_prompt("", {}, "bowl", None, {**ref, "container": "bowl"}, {"label": "1 cup", "grams": 30})
    assert "showing 1 cup in the family's bowl" in prompt


def test_photo_note_goes_to_gemini_and_survives_other_edits(app, monkeypatch):
    client, main = app
    from server.photos import GUARD, build_prompt
    prompt, _ = build_prompt("", {}, "auto", note="Rice on the left, ignore the fork")
    assert '"Rice on the left, ignore the fork"' in prompt and "unless it would change the amount" in prompt and GUARD in prompt
    assert "Note from the family" not in build_prompt("", {}, "auto", note="  ")[0]
    sent = {}
    monkeypatch.setattr(main.photos, "generate", lambda paths, prompt, quality="fast": sent.update(prompt=prompt) or "candidate/n.jpg")
    pasta = next(f for f in client.get("/api/foods").json() if f["id"] == "pasta-cooked")["portions"][1]
    body = {"label": pasta["label"], "grams": pasta["grams"]}
    food = client.put(f"/api/portions/{pasta['id']}", json={**body, "photo_note": " Penne with butter, no cheese "}).json()
    assert next(p for p in food["portions"] if p["id"] == pasta["id"])["photo_note"] == "Penne with butter, no cheese"
    food = client.put(f"/api/portions/{pasta['id']}", json={**body, "container": "bowl"}).json()   # no note sent: kept
    assert next(p for p in food["portions"] if p["id"] == pasta["id"])["photo_note"] == "Penne with butter, no cheese"
    client.post(f"/api/portions/{pasta['id']}/generate")
    assert "Penne with butter, no cheese" in sent["prompt"]
    assert client.put(f"/api/portions/{pasta['id']}", json={**body, "photo_note": "x" * 301}).status_code == 422


# ---- a food keeps its serving as typed (okf/domain/food.md) ----
def test_food_keeps_its_serving(app):
    client, main = app
    base = {"name": "Dino nuggets", "source_kind": "label", "source_ref": "box", "tags": []}
    f = client.post("/api/foods", json={**base, "serving_carbs": 17, "serving_grams": 85}).json()
    assert (f["serving_carbs"], f["serving_grams"], f["carbs_per_100g"]) == (17, 85, 20.0)
    f = client.post("/api/foods", json={**base, "serving_carbs": 22, "serving_grams": 30, "carbs_per_100g": 99}).json()
    assert f["carbs_per_100g"] == 73.33 and f["serving_carbs"] == 22   # worked out from the serving, never trusted from the client
    assert client.post("/api/foods", json={**base, "serving_carbs": 40, "serving_grams": 30}).status_code == 422
    assert client.post("/api/foods", json={**base, "serving_grams": 30}).status_code == 422
    assert client.post("/api/foods", json=base).status_code == 422
    usda = client.post("/api/foods", json={**base, "carbs_per_100g": 28}).json()
    assert usda["serving_grams"] is None and usda["carbs_per_100g"] == 28
    f = client.put(f"/api/foods/{f['id']}", json={**base, "serving_carbs": 24, "serving_grams": 30}).json()
    assert (f["serving_carbs"], f["carbs_per_100g"]) == (24, 80.0)


def test_estimate_from_a_serving_with_only_an_accepted_photo(app, monkeypatch):
    client, main = app
    sent = {}
    monkeypatch.setattr(main.photos, "generate", lambda paths, prompt, quality="fast": sent.update(paths=paths, prompt=prompt) or "candidate/e.jpg")
    f = client.post("/api/foods", json={"name": "Nuggets", "source_kind": "label", "source_ref": "box", "tags": [],
                                        "serving_carbs": 17, "serving_grams": 85}).json()
    serving = client.post(f"/api/foods/{f['id']}/portions", json={"label": "4 nuggets", "grams": 85}).json()["portions"][0]
    double = client.post(f"/api/foods/{f['id']}/portions", json={"label": "8 nuggets", "grams": 170}).json()["portions"][1]
    assert client.post(f"/api/portions/{double['id']}/estimate", json={"from_portion_id": serving["id"]}).status_code == 400  # no photo yet
    client.post(f"/api/portions/{serving['id']}/generate")
    client.post(f"/api/portions/{serving['id']}/review", json={"action": "accept"})   # generated, accepted: styled only
    out = client.post(f"/api/portions/{double['id']}/estimate", json={"from_portion_id": serving["id"]}).json()
    assert sent["paths"][0] == "candidate/e.jpg" and "shows 85 g of Nuggets" in sent["prompt"] and "showing 170 g" in sent["prompt"]
    assert next(p for p in out["portions"] if p["id"] == double["id"])["photo"]["candidate_kind"] == "estimate"


def test_photo_speed_setting(app, monkeypatch):
    client, main = app
    sent = {}
    monkeypatch.setattr(main.photos, "generate", lambda paths, prompt, quality="fast": sent.update(quality=quality) or "candidate/q.jpg")
    assert client.get("/api/style").json()["quality"] == "fast"
    assert client.put("/api/style/quality", json={"quality": "slow"}).status_code == 422
    assert client.put("/api/style/quality", json={"quality": "sharp"}, headers={"X-Parent-Pin": "0"}).status_code == 401
    pasta = next(f for f in client.get("/api/foods").json() if f["id"] == "pasta-cooked")["portions"][1]
    client.post(f"/api/portions/{pasta['id']}/generate")
    assert sent["quality"] == "fast"
    client.post(f"/api/portions/{pasta['id']}/review", json={"action": "discard"})
    assert client.put("/api/style/quality", json={"quality": "sharp"}).json()["quality"] == "sharp"
    client.post(f"/api/portions/{pasta['id']}/generate")
    assert sent["quality"] == "sharp"
    assert main.photos.QUALITIES["fast"] == ("gemini-3.1-flash-lite-image", "1K")


def test_on_the_counter_sends_no_dish(app, monkeypatch):
    client, main = app
    from server.photos import GUARD, build_prompt
    bases = {"plate": "base/p.jpg", "bowl": "base/b.jpg"}
    prompt, refs = build_prompt("", bases, "counter")
    assert refs == [] and "directly on the countertop" in prompt and "leave it out" in prompt and GUARD in prompt
    prompt, refs = build_prompt("", bases, "counter", describe={"food": "Apple", "grams": 150, "label": "1 apple"})
    assert refs == [] and "directly on the countertop" in prompt and "leave it out" not in prompt
    pasta = next(f for f in client.get("/api/foods").json() if f["id"] == "pasta-cooked")["portions"][1]
    food = client.put(f"/api/portions/{pasta['id']}", json={"label": "1 cup", "grams": 140, "container": "counter"}).json()
    assert next(p for p in food["portions"] if p["id"] == pasta["id"])["container"] == "counter"
    assert client.put(f"/api/portions/{pasta['id']}", json={"label": "1 cup", "grams": 140, "container": "tray"}).status_code == 422


# ---- quick add by barcode: best-guess dish, made in the background (okf/features/food-lookup.md) ----
def test_generate_guesses_the_dish_and_uses_the_package(app, monkeypatch):
    client, main = app
    from server.photos import build_prompt
    prompt, refs = build_prompt("", {"plate": "base/p.jpg"}, "package", describe={"food": "Bar", "grams": 24, "label": "1 bar"},
                                package="labels/" + "a" * 32 + ".jpg")
    assert refs == ["labels/" + "a" * 32 + ".jpg"] and "Image 1 is the product's retail package. Show the serving in or beside" in prompt
    prompt, refs = build_prompt("", {"bowl": "base/b.jpg"}, "bowl", describe={"food": "Cereal", "grams": 30, "label": "1 cup"},
                                package="labels/" + "b" * 32 + ".jpg")
    assert refs == ["base/b.jpg", "labels/" + "b" * 32 + ".jpg"] and "Image 2 is the product's retail package, only to show" in prompt

    pkg = main.photos.save_jpeg(jpeg_bytes(), "labels")
    sent, asked = {}, {}
    monkeypatch.setattr(main.photos, "generate", lambda paths, prompt, quality="fast": sent.update(paths=paths, prompt=prompt) or "candidate/b.jpg")
    monkeypatch.setattr(main.labels, "guess_container", lambda name, serving, package=None: asked.update(name=name, serving=serving, package=package) or "package")
    f = client.post("/api/foods", json={"name": "Granola bar", "source_kind": "openfoodfacts", "source_ref": "Open Food Facts, barcode 1",
                                        "verified": True, "serving_carbs": 16, "serving_grams": 24, "package_photo": pkg, "tags": []}).json()
    assert f["package_photo"] == pkg
    pid = client.post(f"/api/foods/{f['id']}/portions", json={"label": "1 bar", "grams": 24}).json()["portions"][0]["id"]
    out = client.post(f"/api/portions/{pid}/generate").json()
    p = out["portions"][0]
    assert asked == {"name": "Granola bar", "serving": "1 bar, 24 g", "package": pkg}
    assert p["container"] == "package" and p["photo"]["candidate"] == "candidate/b.jpg" and sent["paths"] == [pkg]

    def no_guess(*a, **k): raise main.photos.PhotoError("Gemini couldn't guess the dish.")
    monkeypatch.setattr(main.labels, "guess_container", no_guess)
    pid2 = client.post(f"/api/foods/{f['id']}/portions", json={"label": "2 bars", "grams": 48}).json()["portions"][1]["id"]
    out = client.post(f"/api/portions/{pid2}/generate").json()
    assert next(x for x in out["portions"] if x["id"] == pid2)["container"] == "plate"   # falls back to a plate
    client.put(f"/api/portions/{pid2}", json={"label": "2 bars", "grams": 48, "container": "bowl"})
    asked.clear(); client.post(f"/api/portions/{pid2}/review", json={"action": "discard"}); client.post(f"/api/portions/{pid2}/generate")
    assert asked == {}   # a dish the parent chose is not guessed again


def test_estimate_prefers_the_styled_photo(app, monkeypatch):
    client, main = app
    sent = {}
    monkeypatch.setattr(main.photos, "generate", lambda paths, prompt, quality="fast": sent.update(paths=paths) or "candidate/s.jpg")
    f = client.post("/api/foods", json={"name": "Nuggets", "source_kind": "label", "source_ref": "box", "tags": [],
                                        "serving_carbs": 17, "serving_grams": 85}).json()
    serving = client.post(f"/api/foods/{f['id']}/portions", json={"label": "4 nuggets", "grams": 85}).json()["portions"][0]
    double = client.post(f"/api/foods/{f['id']}/portions", json={"label": "8 nuggets", "grams": 170}).json()["portions"][1]
    client.post(f"/api/portions/{serving['id']}/original", files={"file": ("n.jpg", jpeg_bytes(), "image/jpeg")})
    client.post(f"/api/portions/{double['id']}/estimate", json={"from_portion_id": serving["id"]})
    assert sent["paths"][0].startswith("original/")   # nothing styled yet: your photo
    client.post(f"/api/portions/{double['id']}/review", json={"action": "discard"})
    client.post(f"/api/portions/{serving['id']}/style")
    client.post(f"/api/portions/{serving['id']}/review", json={"action": "accept"})
    client.post(f"/api/portions/{double['id']}/estimate", json={"from_portion_id": serving["id"]})
    assert sent["paths"][0] == "candidate/s.jpg"      # the styled version once there is one


def test_packaged_search_region(app, monkeypatch):
    client, main = app
    from server import lookup
    seen = []
    monkeypatch.setattr(main.lookup, "fs_search", lambda q: [])
    monkeypatch.setattr(main.lookup, "off_search", lambda q, contact, n=12, country="": seen.append(country) or [])
    assert client.get("/api/settings").json()["off_country"] == "en:united-states"
    r = client.get("/api/lookup/search?q=cheerios").json()
    assert seen[-1] == "en:united-states" and r["country_name"] == "United States"
    assert client.get("/api/lookup/search?q=cheerios&everywhere=1").json()["country"] == "" and seen[-1] == ""
    assert client.put("/api/settings/country", json={"country": "en:narnia"}).status_code == 422
    assert client.put("/api/settings/country", json={"country": "en:canada"}).json()["off_country"] == "en:canada"
    client.get("/api/lookup/search?q=cheerios"); assert seen[-1] == "en:canada"
    client.put("/api/settings/country", json={"country": ""})
    client.get("/api/lookup/search?q=cheerios"); assert seen[-1] == ""
    assert 'countries_tags:"en:france"' not in lookup.off_query("cheerios")   # the filter is added in off_search only



# ---- FatSecret (okf/architecture/nutrition-apis.md) ----
class FakeResp:
    def __init__(self, data, status=200): self.data, self.status_code = data, status
    def json(self): return self.data


def test_fatsecret_search_food_and_errors(app, monkeypatch):
    client, main = app
    from server import lookup
    monkeypatch.setenv("FAT_SECRET_CLIENT_ID", "id"); monkeypatch.setenv("FAT_SECRET_CLIENT_SECRET", "secret")
    lookup._fs_token.update(value=None, until=0)
    calls = {"token": 0}

    def post(url, data=None, timeout=None, auth=None):
        calls["token"] += 1
        assert auth == ("id", "secret") and data["grant_type"] == "client_credentials"
        return FakeResp({"access_token": "tok", "expires_in": 86400})

    answers = {
        "foods.search": {"foods": {"food": [
            {"food_id": "4501", "food_name": "White Rice", "food_type": "Generic",
             "food_description": "Per 100g - Calories: 130kcal | Fat: 0.28g | Carbs: 28.17g | Protein: 2.69g"},
            {"food_id": "99", "food_name": "Granola Bar", "brand_name": "Nature Valley", "food_type": "Brand",
             "food_description": "Per 1 bar - Calories: 190kcal | Fat: 7g | Carbs: 29.00g | Protein: 4g"}]}},
        "food.get.v4": {"food": {"food_id": "4501", "food_name": "White Rice", "servings": {"serving": [
            {"serving_description": "100 g", "metric_serving_amount": "100.000", "metric_serving_unit": "g", "carbohydrate": "28.17"},
            {"serving_description": "1 cup", "metric_serving_amount": "158.000", "metric_serving_unit": "g", "carbohydrate": "44.51",
             "fiber": "0.6", "sugar": "0.08", "is_default": "1"},
            {"serving_description": "1 oz", "metric_serving_amount": "28.350", "metric_serving_unit": "g", "carbohydrate": "7.99"}]}}},
    }

    def get(url, params=None, timeout=None, headers=None):
        assert headers["Authorization"] == "Bearer tok"
        return FakeResp(answers[params["method"]])

    monkeypatch.setattr(lookup.requests, "post", post); monkeypatch.setattr(lookup.requests, "get", get)
    monkeypatch.setattr(main.lookup, "off_search", lambda *a, **k: [])
    s = client.get("/api/lookup/search?q=rice").json()
    rice, bar = s["fatsecret"]
    assert rice["carbs_per_100g"] == 28.2 and rice["serving"] is None
    assert bar["carbs_per_100g"] is None and bar["serving"] == "29 g carbs per 1 bar" and bar["brand"] == "Nature Valley"
    r = client.get("/api/lookup/fatsecret/4501").json()
    assert r["source"] == "fatsecret" and r["source_ref"] == "FatSecret food 4501" and r["warnings"] == []
    assert r["reading"]["serving_grams"] == 158 and r["reading"]["total_carbs_g_per_serving"] == 44.51   # the default serving
    assert r["other_servings"] == ["100 g = 100 g (28.17 g carbs)", "1 oz = 28.35 g (7.99 g carbs)"]
    assert calls["token"] == 1   # the token is reused
    assert client.get("/api/lookup/fatsecret/abc").status_code == 400
    # saving needs both confirmations, like a packaged food
    body = {"name": "White Rice", "source_kind": "fatsecret", "source_ref": "FatSecret food 4501", "serving_carbs": 44.51, "serving_grams": 158, "tags": []}
    assert client.post("/api/foods", json=body).status_code == 400
    assert client.post("/api/foods", json={**body, "verified": True}).json()["source_kind"] == "fatsecret"
    # the server's address isn't allowlisted
    answers["foods.search"] = {"error": {"code": 21, "message": "Invalid IP address detected:  '50.34.57.205'"}}
    s = client.get("/api/lookup/search?q=rice").json()
    assert s["fatsecret"] == [] and "FatSecret refused 50.34.57.205" in s["errors"][0] and "allowlist" in s["errors"][0]
    monkeypatch.delenv("FAT_SECRET_CLIENT_ID"); lookup._fs_token.update(value=None, until=0)
    assert "isn't set up" in client.get("/api/lookup/search?q=rice").json()["errors"][0]



# ---- Google sign-in (okf/architecture/auth.md, okf/rules/allowlisted-accounts-only.md) ----
def test_sign_in_gate_sessions_and_allow_list(app, monkeypatch):
    client, main = app
    from server import auth
    tokens = {"tok-mom": ("mom@example.com", True), "tok-kid": ("kid@example.com", True), "tok-stranger": ("x@example.com", True)}

    def verify(id_token):
        if id_token not in tokens:
            raise auth.AuthError("Google sign-in couldn't be checked. Try again.")
        return tokens[id_token][0]

    monkeypatch.setattr(auth, "verify", verify)
    assert client.get("/api/auth/config").json() == {"enabled": False, "firebase": None}
    assert client.get("/api/foods").status_code == 200            # off until a Firebase project is set
    monkeypatch.setenv("FIREBASE_PROJECT_ID", "kitchen-carbs-test"); monkeypatch.setenv("FIREBASE_API_KEY", "AIza-test")
    monkeypatch.setenv("FIREBASE_AUTH_DOMAIN", "kitchen-carbs-test.firebaseapp.com")
    monkeypatch.setenv("KC_ALLOWED_EMAILS", "Mom@Example.com, kid@example.com")
    cfg = client.get("/api/auth/config").json()
    assert cfg["enabled"] and cfg["firebase"]["projectId"] == "kitchen-carbs-test"
    for path in ("/api/foods", "/api/session", "/photos/original/x.jpg", "/img/800/original/x.jpg"):
        r = client.get(path)
        assert r.status_code == 401 and r.json()["signin"] is True, path
    assert client.get("/").status_code == 200 and client.get("/app.js").status_code == 200   # the page can show sign-in
    assert client.post("/api/auth/session", json={"id_token": "tok-stranger-xxxxxxxxxxxx"}).status_code == 401
    r = client.post("/api/auth/session", json={"id_token": "tok-stranger"[:0] + "x" * 30})
    assert r.status_code == 401
    tokens["x" * 30] = ("x@example.com", True)
    r = client.post("/api/auth/session", json={"id_token": "x" * 30})
    assert r.status_code == 403 and "isn't on this family's list" in r.json()["detail"]
    tokens["m" * 30] = ("mom@example.com", True)
    r = client.post("/api/auth/session", json={"id_token": "m" * 30})
    assert r.status_code == 200 and r.json()["email"] == "mom@example.com"
    cookie = r.cookies.get(auth.COOKIE)
    assert cookie and "httponly" in r.headers["set-cookie"].lower() and "max-age=2592000" in r.headers["set-cookie"].lower()
    assert client.get("/api/foods").status_code == 200 and client.get("/api/auth/me").json()["email"] == "mom@example.com"
    stored = sqlite3.connect(os.path.join(os.environ["KC_DATA"], "app.db")).execute("SELECT id_hash FROM sessions").fetchall()
    assert len(stored) == 1 and stored[0][0] != cookie                 # only a hash of the cookie is kept
    acc = client.get("/api/accounts").json()
    assert acc["emails"] == ["kid@example.com", "mom@example.com"] and acc["me"] == "mom@example.com"
    assert client.put("/api/accounts", json={"emails": ["kid@example.com"]}).status_code == 400   # can't drop yourself
    assert client.put("/api/accounts", json={"emails": ["mom@example.com", "nope"]}).status_code == 422
    # the kid's tablet signs in; taking the kid off the list signs that device out at its next request
    kid = TestClient(main.app); tokens["k" * 30] = ("kid@example.com", True)
    assert kid.post("/api/auth/session", json={"id_token": "k" * 30}).status_code == 200 and kid.get("/api/foods").status_code == 200
    assert client.put("/api/accounts", json={"emails": ["mom@example.com", "dad@example.com"]}).json()["emails"] == ["dad@example.com", "mom@example.com"]
    assert kid.get("/api/foods").status_code == 401
    # an expired session is refused; sign out ends this device
    con = sqlite3.connect(os.path.join(os.environ["KC_DATA"], "app.db"))
    with con:
        con.execute("UPDATE sessions SET expires_at = '2000-01-01T00:00:00'")
    assert client.get("/api/foods").status_code == 401
    with con:
        con.execute("UPDATE sessions SET expires_at = '2999-01-01T00:00:00'")
    assert client.get("/api/foods").status_code == 200
    assert client.post("/api/auth/logout").status_code == 200 and client.get("/api/foods").status_code == 401


def test_app_files_are_revalidated(app):
    # Cloudflare would otherwise let browsers keep an old app.js for hours (okf/architecture/https.md)
    client, _ = app
    for path in ("/", "/app.js", "/app.css", "/scale.js"):
        assert client.get(path).headers["cache-control"] == "no-cache"
    page = client.get("/").text   # and the page asks for them by content hash
    assert re.search(r'src="app.js\?v=[0-9a-f]{8}"', page) and re.search(r'href="app.css\?v=[0-9a-f]{8}"', page)


def test_sign_in_with_a_code_and_frames(app, monkeypatch):
    # okf/features/sign-in.md: kiosks and the Home Assistant dashboard
    client, main = app
    from server import auth
    monkeypatch.setenv("FIREBASE_PROJECT_ID", "kitchen-carbs-test"); monkeypatch.setenv("KC_ALLOWED_EMAILS", "mom@example.com")
    monkeypatch.setattr(auth, "verify", lambda tok: "mom@example.com")
    https = {"x-forwarded-proto": "https"}
    r = client.post("/api/auth/session", json={"id_token": "m" * 30}, headers=https)
    c = r.headers["set-cookie"]
    assert "Secure" in c and "SameSite=None" in c and "Partitioned" in c and "HttpOnly" in c   # works inside a frame
    assert "SameSite=Lax" in client.post("/api/auth/session", json={"id_token": "m" * 30}).headers["set-cookie"]   # plain http
    # writes from another site's page are refused; the app's own page and tools with no Origin are fine
    assert client.post("/api/tags", json={"name": "Snack"}, headers={"origin": "https://evil.example"}).status_code == 403
    assert client.post("/api/tags", json={"name": "Snack"}, headers={"origin": "http://testserver"}).status_code == 200
    # a kiosk asks for a code and waits
    kiosk = TestClient(main.app)
    d = kiosk.post("/api/auth/device").json()
    assert re.fullmatch(r"[A-Z2-9]{4}-[A-Z2-9]{4}", d["code"]) and kiosk.get(f"/api/auth/device/{d['poll']}").json() == {"state": "pending"}
    assert kiosk.get("/api/foods").status_code == 401
    # approving needs a signed-in device and the parent PIN; a wrong code is refused
    assert TestClient(main.app).post("/api/accounts/approve-device", json={"code": d["code"]}).status_code == 401
    assert client.post("/api/accounts/approve-device", json={"code": "ZZZZ-ZZZZ"}).status_code == 404
    assert client.post("/api/accounts/approve-device", json={"code": d["code"].lower().replace("-", " ")}).json()["email"] == "mom@example.com"
    assert kiosk.get(f"/api/auth/device/{d['poll']}").json()["state"] == "approved"
    assert kiosk.get("/api/foods").status_code == 200 and kiosk.get("/api/auth/me").json()["email"] == "mom@example.com"
    assert kiosk.get(f"/api/auth/device/{d['poll']}").json() == {"state": "expired"}   # a code works once
    assert client.post("/api/accounts/approve-device", json={"code": d["code"]}).status_code == 404
    # codes run out after 10 minutes
    d2 = kiosk.post("/api/auth/device").json()
    monkeypatch.setattr(auth.time, "time", lambda: 10 ** 12)
    assert kiosk.get(f"/api/auth/device/{d2['poll']}").json() == {"state": "expired"}


def test_http_through_cloudflare_goes_to_https(app):
    client, _ = app
    r = client.get("/api/auth/config?x=1", headers={"x-forwarded-proto": "http", "host": "kitchen.example.com"}, follow_redirects=False)
    assert r.status_code == 301 and r.headers["location"] == "https://kitchen.example.com/api/auth/config?x=1"
    assert client.get("/api/auth/config").status_code == 200                                    # LAN and localhost: no header
    assert client.get("/api/auth/config", headers={"x-forwarded-proto": "https"}).status_code == 200


def test_no_free_snacks_setting(app):
    # okf/features/browse-foods.md: no carb-limit tab; a family makes a 'Free snacks' tag by hand
    client, _ = app
    assert "free_max" not in client.get("/api/session").json()
    assert client.put("/api/settings/free-snacks", json={"grams": 3}).status_code in (404, 405)


def test_installable(app):
    # okf/architecture/install.md: manifest icons exist and the worker is served fresh
    client, _ = app
    m = client.get("/manifest.webmanifest").json()
    for icon in m["icons"]:
        assert client.get("/" + icon["src"]).status_code == 200, icon["src"]
    assert {"192x192", "512x512"} <= {i["sizes"] for i in m["icons"]} and any(i.get("purpose") == "maskable" for i in m["icons"])
    assert client.get("/icon-180.png").status_code == 200   # apple-touch-icon
    r = client.get("/sw.js")
    assert r.status_code == 200 and r.headers["cache-control"] == "no-cache" and "caches." not in r.text   # caches nothing


def test_change_date_and_time_any_day_marked(app):
    # okf/rules/same-day-edits.md: date and time move on any day, and the move is shown
    client, _ = app
    client.put("/api/settings/past-edits", json={"allowed": False})   # moving works even when earlier days are locked
    mid = client.post("/api/meals", json=meal(day="2026-10-26", time="18:05", cid="client-move-1")).json()["id"]
    r = client.put(f"/api/meals/{mid}/when", json={"day": "2026-10-25", "time": "23:40"}).json()
    assert r["moved_from"] == "2026-10-26 18:05"
    log = client.get("/api/log?day=2026-10-25").json()
    assert log["meals"][0]["moved_from"] == "2026-10-26 18:05" and not log["editable"]
    r = client.put(f"/api/meals/{mid}/when", json={"day": "2026-10-27", "time": "07:00"}).json()
    assert r["moved_from"] == "2026-10-26 18:05"                       # still the first logged time
    assert client.put(f"/api/meals/{mid}/when", json={"day": "2026-10-26", "time": "18:05"}).json()["moved_from"] is None
    assert client.put(f"/api/meals/{mid}/when", json={"day": "2026-10-28", "time": "08:00"}).status_code == 400   # future
    assert client.put(f"/api/meals/{mid}/when", json={"day": "2026-02-30", "time": "08:00"}).status_code == 422
    assert client.patch(f"/api/meals/{mid}", json={"eaten": "all"}).status_code == 409   # the rest stays read-only
    eid = client.post("/api/entries", json={"client_id": "entry-move-1", "day": "2026-10-27", "time": "12:00", "bg": 110}).json()["id"]
    assert client.put(f"/api/entries/{eid}/when", json={"day": "2026-10-26", "time": "12:30"}).json()["moved_from"] == "2026-10-27 12:00"
    csv_text = client.get("/api/export.csv?start=2026-10-25&end=2026-10-27").text
    assert csv_text.splitlines()[0].endswith(",moved_from,bg_source,insulin_min_before_eating,eating_min,changed_later,meal_total_from_foods_g") and "2026-10-27 12:00" in csv_text


def test_portion_label_is_amount_then_unit(app):
    # okf/domain/portion.md
    client, _ = app
    fid = client.get("/api/foods").json()[0]["id"]
    for good in ("1 cup", "2 slices", "½ serving", "1 1/3 Cup", "1.5 Tbsp", "¾cup"):
        assert client.post(f"/api/foods/{fid}/portions", json={"label": good, "grams": 50}).status_code == 200, good
    for bad in ("serving", "a cup", "0 cup", "1/0 cup", "½ × 1 serving", "2"):
        r = client.post(f"/api/foods/{fid}/portions", json={"label": bad, "grams": 50})
        assert r.status_code == 422 and "a number, then the unit" in r.text, bad


def test_amount_formatting():
    from server import core
    assert core.portion_amount("1 1/3 Cup") == (4 / 3, "Cup") and core.portion_amount("½ × 1 serving") is None
    assert core.fmt_amount(1.5) == "1½" and core.fmt_amount(2 / 3) == "⅔" and core.fmt_amount(2.4) == "2.4" and core.fmt_amount(3) == "3"
    assert core.unit_for(2, "serving") == "servings" and core.unit_for(0.5, "servings") == "serving" and core.unit_for(3, "Tbsp") == "Tbsp"


def test_remove_orphaned_favorites(app):
    # okf/domain/favorite-plate.md: removed only when asked; partly missing favorites keep their good items
    client, _ = app
    foods = client.get("/api/foods").json()
    a, b = foods[0]["portions"][0]["id"], foods[1]["portions"][0]["id"]
    whole = client.post("/api/favorites", json={"name": "Gone", "items": [{"portion_id": a, "qty": 1}]}).json()["id"]
    part = client.post("/api/favorites", json={"name": "Half", "items": [{"portion_id": a, "qty": 1}, {"portion_id": b, "qty": 1}]}).json()["id"]
    keep = client.post("/api/favorites", json={"name": "Fine", "items": [{"portion_id": b, "qty": 2}]}).json()["id"]
    assert client.delete(f"/api/foods/{foods[0]['id']}").status_code == 200
    favs = {f["id"]: f for f in client.get("/api/favorites").json()}
    assert favs[whole]["missing"] == 1 and favs[part]["missing"] == 1               # shown, not dropped silently
    assert client.post("/api/favorites/remove-orphans").json() == {"removed": 1}
    assert client.post(f"/api/favorites/{part}/drop-missing").json() == {"removed_items": 1, "deleted": False}
    favs = {f["id"]: f for f in client.get("/api/favorites").json()}
    assert set(favs) == {part, keep} and favs[part]["missing"] == 0 and len(favs[part]["items"]) == 1


def test_fiber_kept_with_the_serving(app):
    # okf/domain/food.md: fiber for the same amount as the carbs, reference only; carbs untouched
    client, _ = app
    body = {"name": "Bar", "serving_grams": 40, "serving_carbs": 24, "serving_fiber": 3, "source_kind": "care-team",
            "source_ref": "test", "verified": True}
    f = client.post("/api/foods", json=body).json()
    assert (f["serving_fiber"], f["fiber_per_100g"], f["fiber_checked_at"]) == (3, 7.5, "2026-10-27")
    assert f["carbs_per_100g"] == 60
    assert client.post("/api/foods", json={**body, "name": "Bad", "serving_fiber": 41}).status_code == 422
    assert client.post("/api/foods", json={**body, "name": "Bad", "serving_grams": None, "serving_carbs": None,
                                           "carbs_per_100g": 50}).status_code == 422   # fiber per serving needs a serving
    f = client.put(f"/api/foods/{f['id']}", json={**body, "serving_fiber": None}).json()
    assert f["fiber_per_100g"] is None and f["fiber_checked_at"] is None
    per100 = client.post("/api/foods", json={"name": "Rice", "carbs_per_100g": 28, "fiber_per_100g": 0.4, "source_kind": "care-team",
                                              "source_ref": "test", "verified": True}).json()
    assert per100["fiber_per_100g"] == 0.4 and per100["serving_fiber"] is None


def test_fill_in_fiber_from_own_source(app, monkeypatch):
    # okf/features/fill-in-fiber.md: read again from the food's own barcode, scaled to its serving; saved only when confirmed
    client, main = app
    f = client.post("/api/foods", json={"name": "Crackers", "serving_grams": 30, "serving_carbs": 20, "source_kind": "openfoodfacts",
                                        "source_ref": "Open Food Facts, barcode 0001234567890", "verified": True}).json()
    assert f["fiber_lookup"] is True
    seen = []
    monkeypatch.setattr(main.lookup, "off_product", lambda code, contact: (seen.append(code), (code, {}))[1])
    monkeypatch.setattr(main.lookup, "off_reading", lambda p: {"serving_grams": 15, "fiber_g_per_serving": 0.5,
                                                               "total_carbs_g_per_serving": 12, "carbs_g_per_100g": None})
    r = client.get(f"/api/foods/{f['id']}/fiber-lookup").json()
    assert seen == ["0001234567890"]
    assert r["fiber"] == 1.0 and r["per_grams"] == 30 and "scaled to 30 g" in r["notes"][0]
    assert any("now gives 24.0 g carbs" in w for w in r["warnings"])   # 12 per 15 g vs the saved 20 per 30 g
    assert client.put(f"/api/foods/{f['id']}/fiber", json={"fiber": 1, "confirmed": False}).status_code == 400
    assert client.put(f"/api/foods/{f['id']}/fiber", json={"fiber": 31, "confirmed": True}).status_code == 422
    g = client.put(f"/api/foods/{f['id']}/fiber", json={"fiber": 1, "confirmed": True}).json()
    assert (g["serving_fiber"], g["fiber_per_100g"], g["carbs_per_100g"], g["fiber_lookup"]) == (1, 3.33, f["carbs_per_100g"], False)
    typed = client.post("/api/foods", json={"name": "Typed", "carbs_per_100g": 10, "source_kind": "care-team", "source_ref": "x"}).json()
    assert typed["fiber_lookup"] is False
    assert client.get(f"/api/foods/{typed['id']}/fiber-lookup").status_code == 400


def test_dry_or_cooked_food_needs_its_ratio(app):
    # okf/domain/food.md: a dry / raw or cooked food can't be saved without its measured cooking ratio
    client, _ = app
    body = {"name": "Pasta", "serving_grams": 56, "serving_carbs": 40, "source_kind": "care-team", "source_ref": "box", "basis": "raw"}
    r = client.post("/api/foods", json=body)
    assert r.status_code == 422 and "cooking ratio" in r.text
    f = client.post("/api/foods", json={**body, "cook_raw_g": 100, "cook_cooked_g": 240}).json()
    assert f["cook_ratio"] == 2.4
    assert client.post("/api/foods", json={**body, "name": "Bread", "basis": "as-sold"}).status_code == 200


PHONE = {"endpoint": "https://fcm.googleapis.com/fcm/send/phone-1", "p256dh": "B" * 87, "auth": "a" * 22, "device": "Android · Chrome"}


def test_notify_on_meal_and_entry(app, monkeypatch):
    """okf/features/notify-family.md: every subscribed device but the one that logged it, with the logged numbers only."""
    client, main = app
    sent = []
    monkeypatch.setattr(main.push, "_send_one", lambda vapid, subject, sub, payload: sent.append((sub["endpoint"], payload)))
    monkeypatch.setattr(main.push, "send_later", lambda payload, skip="": main.push.send(payload, skip))
    assert client.get("/api/push").json()["public_key"]
    assert client.post("/api/push/subscribe", json=PHONE, headers={"X-Parent-Pin": "0000"}).status_code == 401
    assert client.post("/api/push/subscribe", json={**PHONE, "endpoint": "https://192.168.0.1/x"}).status_code == 422
    assert client.post("/api/push/subscribe", json={**PHONE, "endpoint": "http://fcm.googleapis.com/x"}).status_code == 422
    client.post("/api/push/subscribe", json=PHONE)
    tablet = {**PHONE, "endpoint": "https://web.push.apple.com/tablet"}
    client.post("/api/push/subscribe", json=tablet)
    body = meal(); body.update(bg=182, bg_source="meter", insulin=2.5, insulin_kind="bolus")
    client.post("/api/meals", json=body, headers={"X-KC-Push": tablet["endpoint"]})
    assert [e for e, _ in sent] == [PHONE["endpoint"]]
    p = sent[0][1]
    assert p["title"].startswith("Meal logged · ") and p["title"].endswith(" g carbs")
    assert p["body"] == "18:05 · Pasta, cooked · BG 182 mg/dL · 2.5 u bolus"
    client.post("/api/meals", json=body, headers={"X-KC-Push": tablet["endpoint"]})   # the same meal again: saved once, told once
    assert len(sent) == 1
    sent.clear()
    client.post("/api/entries", json={"client_id": "entry-0001", "day": "2026-10-26", "time": "15:10", "bg": 95, "carbs": 15, "note": "juice"})
    assert [p for _, p in sent][0] == {"title": "BG 95 mg/dL · 15 g carbs", "body": "Mon 26 Oct, 15:10 · juice", "tag": sent[0][1]["tag"], "url": "/#log"}
    assert len(sent) == 2
    devs = client.get("/api/push/devices", headers={"X-KC-Push": PHONE["endpoint"]}).json()
    assert [d["mine"] for d in devs] == [True, False] and devs[0]["device"] == "Android · Chrome"
    client.post("/api/push/unsubscribe", json={"endpoint": PHONE["endpoint"]}, headers={"X-Parent-Pin": ""})
    assert len(client.get("/api/push/devices").json()) == 1


def test_push_gone_and_qa(app, monkeypatch):
    client, main = app
    client.post("/api/push/subscribe", json=PHONE)
    monkeypatch.setattr(main.push, "_send_one", lambda *a: "gone")
    assert client.post("/api/push/test", json={"endpoint": PHONE["endpoint"]}).status_code == 502
    assert client.get("/api/push/devices").json() == []   # the push service said it's gone
    monkeypatch.setenv("KC_ENV", "qa")
    assert client.get("/api/push").json() == {"enabled": False, "public_key": None}
    assert client.post("/api/push/subscribe", json=PHONE).status_code == 400
    assert main.push.send({"title": "x"}) == {"sent": 0, "failed": 0}


def test_push_payload_is_encrypted_for_the_phone(app, monkeypatch):
    """A real Web Push request (RFC 8291): only the phone's own keys can read it."""
    import base64, http_ece, requests
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    client, main = app
    key, secret = ec.generate_private_key(ec.SECP256R1()), b"0123456789abcdef"
    b64 = lambda b: base64.urlsafe_b64encode(b).decode().rstrip("=")
    pub = key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    client.post("/api/push/subscribe", json={**PHONE, "p256dh": b64(pub), "auth": b64(secret)})
    seen = {}
    def fake_post(url, data=None, headers=None, timeout=None, **kw):
        seen.update(url=url, data=data, headers=headers)
        r = requests.Response(); r.status_code = 201; return r
    monkeypatch.setattr(requests, "post", fake_post)
    assert main.push.send({"title": "Meal logged · 30 g carbs"}) == {"sent": 1, "failed": 0}
    assert seen["url"] == PHONE["endpoint"] and seen["headers"]["Authorization"].startswith("vapid t=")
    assert b"carbs" not in seen["data"]
    plain = http_ece.decrypt(seen["data"], private_key=key, auth_secret=secret, version="aes128gcm")
    assert json.loads(plain) == {"title": "Meal logged · 30 g carbs"}


def test_meal_saved_to_an_earlier_day_is_marked(app):
    """okf/features/meal-dose-summary.md: the summary's date can be earlier; such a meal is marked like a late entry."""
    client, main = app
    client.post("/api/meals", json=meal(day="2026-10-26", time="20:15", cid="late-meal-1"))
    client.post("/api/meals", json=meal(time="12:00", cid="today-meal-1"))
    rows = dict(main.db.connect().execute("SELECT client_id, edited_at FROM meals").fetchall())
    assert rows["late-meal-1"] == "2026-10-27 18:30" and rows["today-meal-1"] is None
    assert client.post("/api/meals", json=meal(day="2026-10-28", cid="future-1")).status_code == 400


def test_edit_entry_values(app, monkeypatch):
    """okf/features/manual-log.md: values fixed or added later, same checks as adding, marked after its day."""
    client, main = app
    sent = []
    monkeypatch.setattr(main.push, "send_later", lambda payload, skip="": sent.append(payload))
    eid = client.post("/api/entries", json=entry(bg=142)).json()["id"]
    r = client.put(f"/api/entries/{eid}", json={"bg": 124, "carbs": 15, "insulin": 1.5, "insulin_kind": "rapid", "note": " juice "})
    assert r.status_code == 200 and (r.json()["bg"], r.json()["carbs"], r.json()["insulin"], r.json()["note"], r.json()["edited_at"]) == (124, 15, 1.5, "juice", None)
    assert client.put(f"/api/entries/{eid}", json={}).status_code == 422                                  # can't be emptied
    assert client.put(f"/api/entries/{eid}", json={"insulin": 2}).status_code == 422                      # kind missing
    assert client.put(f"/api/entries/{eid}", json={"insulin": 2.53, "insulin_kind": "rapid"}).status_code == 422
    assert client.put(f"/api/entries/{eid}", json={"insulin": 2, "insulin_kind": "bolus"}).status_code == 422
    r = client.put(f"/api/entries/{eid}", json={"bg": 124, "insulin_kind": "long"})                      # no insulin: no kind kept
    assert r.json()["insulin"] is None and r.json()["insulin_kind"] is None
    assert len(sent) == 1                                                                                 # editing never notifies
    old = client.post("/api/entries", json=entry(cid="entry-old-1", day="2026-10-26", bg=90)).json()["id"]
    assert client.put(f"/api/entries/{old}", json={"bg": 95}).json()["edited_at"] == "2026-10-27 18:30"
    client.put("/api/settings/past-edits", json={"allowed": False})
    assert client.put(f"/api/entries/{old}", json={"bg": 99}).status_code == 409
    assert client.put("/api/entries/9999", json={"bg": 99}).status_code == 404


def test_export_pdf(app):
    """okf/features/export-log.md: the same range as the CSV, as a PDF file; up to 92 days."""
    client, _ = app
    body = meal(); body.update(bg=65, bg_source="meter", insulin=2.5, insulin_kind="bolus")
    client.post("/api/meals", json=body)
    client.post("/api/entries", json=entry(bg=142, insulin=1.5, insulin_kind="rapid", note="Crème brûlée ✎ → café"))
    r = client.get("/api/export.pdf?start=2026-10-21&end=2026-10-27")
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF") and 'filename="kitchen-carbs_2026-10-21_2026-10-27.pdf"' in r.headers["content-disposition"]
    assert client.get("/api/export.pdf?start=2026-10-27&end=2026-10-21").status_code == 400
    assert client.get("/api/export.pdf?start=2026-01-01&end=2026-10-27").status_code == 400
    assert client.get("/api/export.pdf?start=2026-10-20&end=2026-10-20").status_code == 200   # nothing logged


def test_pdf_text_keeps_only_font_characters():
    from server import report
    assert report.safe("Crème ✎ → café") == "Crème   café"
    assert report.units(2.5) == "2.5" and report.units(3.0) == "3" and report.units(0.05) == "0.05"


class FakeTidepool:
    """Tidepool's login, data sets and delete-by-origin deduplication, as the client uses them."""
    def __init__(self):
        self.records, self.datasets, self.calls, self.fail_next = {}, [], [], None

    def resp(self, status, body=None, headers=None):
        import requests
        r = requests.Response(); r.status_code = status
        r._content = json.dumps(body).encode() if body is not None else b""
        r.headers.update({"content-type": "application/json", **(headers or {})})
        return r

    def post(self, url, auth=None, timeout=None):
        assert url.endswith("/auth/login")
        if auth != ("mom@example.com", "pw-right"):
            return self.resp(401, {})
        return self.resp(200, {"userid": "u1"}, {"x-tidepool-session-token": "tok"})

    def request(self, method, url, json=None, timeout=None, headers=None):
        assert headers["X-Tidepool-Session-Token"] == "tok"
        path = url.split(".org", 1)[1]
        self.calls.append((method, path.split("?")[0]))
        if self.fail_next:
            status, self.fail_next = self.fail_next, None
            return self.resp(status, {"code": "x"})
        if method == "GET" and "/data_sets" in path:
            return self.resp(200, self.datasets)
        if method == "POST" and path == "/v1/users/u1/data_sets":
            assert json["dataSetType"] == "continuous" and json["deduplicator"]["name"].endswith("delete.origin")
            self.datasets.append({"id": "ds1", "dataSetType": "continuous"})
            return self.resp(201, {"data": {"id": "ds1"}})
        if method == "POST" and path == "/v1/data_sets/ds1/data":
            for r in json:
                self.records[r["origin"]["id"]] = r
            return self.resp(200, {})
        if method == "DELETE" and path == "/v1/data_sets/ds1/data":
            for s in json:
                self.records.pop(s["origin"]["id"], None)
            return self.resp(200, {})
        if method == "DELETE" and path == "/v1/data_sets/ds1":
            self.records.clear(); self.datasets.clear()
            return self.resp(200, {})
        return self.resp(404, {})


TP = {"server": "test", "email": "mom@example.com", "password": "pw-right", "send_from": "2026-10-20"}


def test_tidepool_sync(app, monkeypatch):
    """okf/features/tidepool-sync.md: only switched-on kinds, never CGM BG or a dose; edits replace, deletes remove."""
    client, main = app
    tp = FakeTidepool()
    monkeypatch.setattr(main.tidepool.requests, "post", tp.post)
    monkeypatch.setattr(main.tidepool.requests, "request", tp.request)
    monkeypatch.setattr(main.tidepool, "_session", {})
    assert client.put("/api/tidepool", json={**TP, "password": "pw-wrong"}).status_code == 400
    assert client.get("/api/tidepool").json()["on"] is False
    body = meal(); body.update(bg=182, bg_source="cgm", insulin=2.5, insulin_kind="bolus", insulin_offset_min=15)
    mid = client.post("/api/meals", json=body).json()["id"]
    eid = client.post("/api/entries", json=entry(bg=65, carbs=15, insulin=1, insulin_kind="long", note="juice")).json()["id"]
    s = client.put("/api/tidepool", json=TP).json()
    assert s["on"] and s["password_saved"] and "password" not in s and s["kinds"] == {"carbs": True, "bg": False, "insulin": False}
    r = client.post("/api/tidepool/sync").json()
    assert (r["sent"], r["removed"], r["sent"]) == (2, 0, 2)
    food = tp.records[f"kc-meal-{mid}"]
    assert food["type"] == "food" and food["nutrition"]["carbohydrate"] == {"net": main.core.whole_grams(sum(
        i["carbs_exact"] for i in main.db.connect().execute("SELECT carbs_exact FROM meal_items WHERE meal_id = ?", (mid,)))), "units": "grams"}
    assert food["meal"] == "dinner" and food["deviceTime"] == "2026-10-27T18:05:00" and food["name"] == "Pasta, cooked"
    assert tp.records[f"kc-entry-{eid}-carbs"]["nutrition"]["carbohydrate"]["net"] == 15
    assert client.post("/api/tidepool/sync").json()["sent"] == 0                         # nothing changed: nothing sent
    # BG and insulin switched on: meter BG only, insulin as typed at the time given
    client.put("/api/tidepool", json={**TP, "password": "", "bg": True, "insulin": True})
    client.post("/api/tidepool/sync")
    assert f"kc-meal-{mid}-bg" not in tp.records                                         # CGM BG never sent
    assert tp.records[f"kc-entry-{eid}-bg"]["value"] == 65 and tp.records[f"kc-entry-{eid}-bg"]["units"] == "mg/dL"
    ins = tp.records[f"kc-meal-{mid}-insulin"]                                       # bolus as Tidepool's bolus
    assert (ins["type"], ins["subType"], ins["normal"]) == ("bolus", "normal", 2.5)
    assert ins["deviceTime"] == "2026-10-27T17:50:00"                                   # 15 min before eating
    bas = tp.records[f"kc-entry-{eid}-insulin"]                                         # long-acting spread over 24 h
    assert (bas["type"], bas["deliveryType"], bas["duration"]) == ("basal", "scheduled", 24 * 3600 * 1000)
    assert abs(bas["rate"] * 24 - 1) < 0.001
    # a long-acting dose ends at the next one 20 h later; a rapid one in between doesn't cut it
    e2 = client.post("/api/entries", json={**entry(insulin=12, insulin_kind="long", cid="entry-0002"), "day": "2026-10-26", "time": "22:00"}).json()["id"]
    client.post("/api/entries", json={**entry(insulin=1, insulin_kind="rapid", cid="entry-0003"), "time": "08:00"})
    client.post("/api/tidepool/sync")
    assert tp.records[f"kc-entry-{e2}-insulin"]["duration"] == 20 * 3600 * 1000 and tp.records[f"kc-entry-{e2}-insulin"]["rate"] == 0.5
    assert tp.records[f"kc-entry-{eid}-insulin"]["duration"] == 24 * 3600 * 1000
    # a weekly insulin: the parent sets the spread
    assert client.put("/api/tidepool", json={**TP, "password": "", "bg": True, "insulin": True, "basal_hours": 200}).status_code == 422
    client.put("/api/tidepool", json={**TP, "password": "", "bg": True, "insulin": True, "basal_hours": 168})
    assert client.get("/api/tidepool").json()["basal_hours"] == 168
    client.post("/api/tidepool/sync")
    assert tp.records[f"kc-entry-{eid}-insulin"]["duration"] == 168 * 3600 * 1000
    assert tp.records[f"kc-entry-{eid}-insulin"]["rate"] == round(1 / 168, 4)
    client.delete(f"/api/entries/{e2}")
    assert not any("dose" in k for r in tp.records.values() for k in r if k != "dose")
    # an edit replaces, a delete removes, a kind switched off is removed
    client.put(f"/api/entries/{eid}", json={"bg": 70, "carbs": 20, "note": "juice"})
    client.delete(f"/api/meals/{mid}")
    r = client.post("/api/tidepool/sync").json()
    assert tp.records[f"kc-entry-{eid}-carbs"]["nutrition"]["carbohydrate"]["net"] == 20
    assert f"kc-entry-{eid}-insulin" not in tp.records and not any(k.startswith(f"kc-meal-{mid}") for k in tp.records)
    client.put("/api/tidepool", json={**TP, "password": "", "bg": False})
    client.post("/api/tidepool/sync")
    assert sorted(tp.records) == [f"kc-entry-{eid}-carbs"]
    # an error is kept for the screen; removing deletes only our data set
    tp.fail_next = 500
    client.post(f"/api/meals/{mid}/restore")
    assert client.post("/api/tidepool/sync").status_code == 502 and "500" in client.get("/api/tidepool").json()["last_error"]
    assert client.post("/api/tidepool/sync").json()["sent"] == 1
    s = client.delete("/api/tidepool/data").json()
    assert tp.records == {} and s["on"] is False and s["sent"] == 0 and ("DELETE", "/v1/data_sets/ds1") in tp.calls


def test_tidepool_off_in_qa(app, monkeypatch):
    client, main = app
    monkeypatch.setenv("KC_ENV", "qa")
    assert client.put("/api/tidepool", json=TP).status_code == 400
    assert main.tidepool.sync_once() == {}
