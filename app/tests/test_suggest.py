"""Suggest a meal (okf/features/suggest-meal.md)."""
from server import suggest
from test_app import app, meal  # noqa: F401  (fixture)

MT = {"breakfast": "07:30", "lunch": "12:00", "dinner": "18:00"}
TODAY = "2026-11-20"


def food(name, cp, grams, label, *tags):
    return {"name": name, "carbs_per_100g": cp, "portions": [{"id": len(name) * 10 + int(cp), "label": label, "grams": grams}], "tags": set(tags)}


FOODS = {"cereal": food("Cereal", 80, 30, "1 cup", "breakfast"),        # 24 g a cup
         "apple": food("Apple", 12, 150, "1 apple", "fruit"),          # 18 g
         "banana": food("Banana", 20, 120, "1 banana", "fruit"),       # 24 g
         "pear": food("Pear", 15, 160, "1 pear", "fruit", "breakfast"),  # never had: tagged for breakfast only
         "toast": food("Toast", 45, 30, "1 slice"),                    # 13.5 g
         "pasta": food("Pasta", 30, 140, "1 cup")}                     # 42 g


def m(day, time, *ids, qty=1, foods=FOODS):
    return {"day": day, "time": time, "items": [{"food_id": f, "portion_id": 1, "carbs": 20} if f not in foods else
            {"food_id": f, "portion_id": foods[f]["portions"][0]["id"],
             "carbs": qty * foods[f]["portions"][0]["grams"] * foods[f]["carbs_per_100g"] / 100} for f in ids]}


HIST = [m(f"2026-11-{d}", "07:40", "cereal", "apple") for d in (16, 17, 18, 19)] + [
    m("2026-11-15", "07:20", "toast", "apple"), m("2026-11-14", "07:35", "cereal", "banana"),
    m("2026-11-19", "18:10", "pasta"), m("2026-11-18", "17:55", "pasta", "gone-food")]


def test_meal_time_is_the_nearest_one():
    assert suggest.slot_of("07:10", MT) == "breakfast" and suggest.slot_of("14:30", MT) == "lunch"
    assert suggest.slot_of("23:50", MT) == "dinner" and suggest.slot_of("03:00", MT) == "breakfast"   # round midnight


def test_starts_from_what_that_meal_usually_is():
    r = suggest.suggest(HIST, FOODS, MT, "breakfast", TODAY)
    assert {i["food_id"] for i in r["items"]} == {"cereal", "apple"}   # the two most had, and had together
    assert r["based_on"] == 6 and not r["all_meals"] and r["default_carbs"] == 42 and r["target"] == 42 and r["total"] == 42


def test_amounts_move_in_half_portions_toward_the_target():
    r = suggest.suggest(HIST, FOODS, MT, "breakfast", TODAY, target=60)
    qty = {i["food_id"]: i["qty"] for i in r["items"]}
    assert all(q * 2 == int(q * 2) and q >= 0.5 for q in qty.values())
    assert abs(r["total"] - 60) <= 6 and r["total"] == round(sum(i["carbs"] for i in r["items"]))
    small = suggest.suggest(HIST, FOODS, MT, "breakfast", TODAY, target=5)
    assert all(i["qty"] == 0.5 for i in small["items"])   # never under half a portion


def test_swap_prefers_the_same_kind_and_what_goes_with_the_rest():
    r = suggest.suggest(HIST, FOODS, MT, "breakfast", TODAY, keep=["cereal"], swap="apple")
    assert [i["food_id"] for i in r["items"]] == ["cereal", "banana"] and r["added"] == "banana"   # fruit, had with cereal
    r = suggest.suggest(HIST, FOODS, MT, "breakfast", TODAY, keep=["cereal"], swap="banana", exclude={"apple"})
    assert r["added"] == "toast"   # had before beats a fruit never had
    r = suggest.suggest(HIST, FOODS, MT, "breakfast", TODAY, keep=["cereal"], swap="toast", exclude={"apple", "banana"})
    assert r["added"] == "pear"    # tagged Breakfast, never had: last in line
    r = suggest.suggest(HIST, FOODS, MT, "breakfast", TODAY, keep=["cereal"], swap="pear", exclude={"apple", "banana", "toast"})
    assert r["added"] is None and [i["food_id"] for i in r["items"]] == ["cereal"]   # nothing left: just removed


def test_too_few_of_that_meal_uses_every_meal_and_gone_foods_are_skipped():
    r = suggest.suggest(HIST, FOODS, MT, "dinner", TODAY)
    assert r["all_meals"] and r["based_on"] == 8 and r["own"] == 2   # 2 dinners < 3
    assert [i["food_id"] for i in r["items"]] == ["pasta"] and r["target"] == 42   # that meal's own foods, size and count
    assert "gone-food" not in [i["food_id"] for i in r["items"]]
    assert suggest.suggest([], FOODS, MT, "lunch", TODAY)["items"] == []


LUNCH = {"nuggets": food("Nuggets", 15, 100, "6 nuggets", "lunch"),   # 15 g
         "ketchup": food("Ketchup", 25, 16, "1 tbsp"),               # 4 g
         "fries": food("Fries", 35, 85, "1 small"),                  # 30 g
         "carrots": food("Carrots", 8, 60, "10 baby"),               # 5 g
         "italian": food("Italian dressing", 10, 30, "2 tbsp"),      # 3 g
         "sandwich": food("Sandwich", 40, 100, "1 sandwich"),        # 40 g
         "grapes": food("Grapes", 17, 90, "1 cup", "fruit")}         # 15 g
LHIST = ([m(f"2026-11-{d}", "12:05", "nuggets", "ketchup", foods=LUNCH) for d in (10, 12, 14, 16, 18)] +
         [m(f"2026-11-{d}", "12:10", "sandwich", foods=LUNCH) for d in (11, 13, 15, 17, 19)] +
         [m(f"2026-11-{d}", "12:00", "carrots", "italian", foods=LUNCH) for d in (12, 15, 18)] +
         [m("2026-11-19", "12:00", "nuggets", "ketchup", "fries", foods=LUNCH), m("2026-11-18", "12:00", "grapes", foods=LUNCH)])


def test_foods_that_go_together_come_together():
    comp = suggest.companions(LHIST)
    assert comp["sides"]["nuggets"] == ["ketchup"] and comp["sides"]["carrots"] == ["italian"]
    assert "fries" not in comp["sides"]["nuggets"] + comp["pairs"].get("nuggets", [])   # once
    r = suggest.suggest(LHIST, LUNCH, MT, "lunch", TODAY, keep=["sandwich"], swap="sandwich")
    ids = [i["food_id"] for i in r["items"]]
    assert ids == ["nuggets", "ketchup"] and r["added"] == "nuggets"   # never nuggets without the ketchup
    r = suggest.suggest(LHIST, LUNCH, MT, "lunch", TODAY, keep=["nuggets", "ketchup", "grapes"], swap="nuggets", exclude={"nuggets"})
    ids = [i["food_id"] for i in r["items"]]
    assert "ketchup" not in ids and ids[0] == r["added"] and ids[-1] == "grapes"   # the ketchup goes with it; the new food takes its place


def test_more_carbs_adds_a_food_rather_than_piling_on():
    base = suggest.suggest(LHIST, LUNCH, MT, "lunch", TODAY, target=40, keep=["sandwich"])
    assert [i["food_id"] for i in base["items"]] == ["sandwich"] and base["items"][0]["qty"] == 1
    big = suggest.suggest(LHIST, LUNCH, MT, "lunch", TODAY, target=70, keep=["sandwich"])
    ids = [i["food_id"] for i in big["items"]]
    assert len(ids) > 1 and ids[0] == "sandwich" and all(i["qty"] <= 1.5 for i in big["items"])
    assert abs(big["total"] - 70) <= 7
    back = suggest.suggest(LHIST, LUNCH, MT, "lunch", TODAY, target=40, keep=ids)
    assert [i["food_id"] for i in back["items"]] == ["sandwich"]   # back down: the added food goes again
    group = suggest.suggest(LHIST, LUNCH, MT, "lunch", TODAY, target=75, keep=["sandwich"])
    gids = [i["food_id"] for i in group["items"]]
    assert ("nuggets" in gids) == ("ketchup" in gids) and ("carrots" in gids) == ("italian" in gids)


def test_endpoint(app):
    client, main = app
    for n, day in enumerate(("2026-10-25", "2026-10-26", "2026-10-27")):
        assert client.post("/api/meals", json=meal(day=day, time="18:00", cid=f"suggest-{n:04d}")).status_code == 200
    r = client.get("/api/suggest").json()   # 18:30 in the tests: dinner
    assert r["meal"] == "dinner" and r["based_on"] == 3 and r["items"][0]["food_id"] == "pasta-cooked"
    assert r["carb_ratio"] is None and r["meal_time"] == "18:00"   # no insulin settings: no Bolus
    one = r["items"][0]["carbs"] / r["items"][0]["qty"]
    r2 = client.get(f"/api/suggest?meal=dinner&carbs={round(one * 2)}&keep=pasta-cooked").json()
    assert r2["items"][0]["qty"] == 2
    client.put("/api/dose-settings", json={"carb_ratio": [{"start": "00:00", "value": 15}], "isf": [{"start": "00:00", "value": 50}],
                                           "target": [{"start": "00:00", "value": 120}]})
    assert client.get("/api/suggest?meal=dinner").json()["carb_ratio"] == 15
    assert client.get("/api/suggest?carbs=500").status_code == 422


def test_locked_foods_keep_their_serving_and_the_rest_fit_around():
    r = suggest.suggest(LHIST, LUNCH, MT, "lunch", TODAY, target=40, keep=["nuggets", "ketchup"], locked={"nuggets": 2})
    by = {i["food_id"]: i for i in r["items"]}
    assert by["nuggets"]["qty"] == 2 and by["nuggets"]["locked"] and not by["ketchup"]["locked"]
    assert abs(r["total"] - 40) <= 4 and len(r["items"]) > 2   # 30 g locked, 4 g ketchup: something else for the rest
    small = suggest.suggest(LHIST, LUNCH, MT, "lunch", TODAY, target=10, keep=[i["food_id"] for i in r["items"]], locked={"nuggets": 2})
    assert {"nuggets"} <= {i["food_id"] for i in small["items"]} and small["items"][0]["qty"] == 2   # never dropped or resized
    same = suggest.suggest(LHIST, LUNCH, MT, "lunch", TODAY, target=40, keep=["nuggets", "ketchup"], swap="nuggets", locked={"nuggets": 2})
    assert same["added"] is None and "nuggets" in [i["food_id"] for i in same["items"]]   # a locked food isn't swapped
    sw = suggest.suggest(LHIST, LUNCH, MT, "lunch", TODAY, target=40, keep=["nuggets", "ketchup"], swap="nuggets", exclude={"nuggets"},
                         locked={"ketchup": 1})
    assert "ketchup" in [i["food_id"] for i in sw["items"]]   # a locked side stays when its food is swapped


def test_endpoint_lock(app):
    client, main = app
    for n, day in enumerate(("2026-10-25", "2026-10-26", "2026-10-27")):
        client.post("/api/meals", json=meal(day=day, time="18:00", cid=f"lock-{n:04d}"))
    r = client.get("/api/suggest?meal=dinner&carbs=20&keep=pasta-cooked&lock=pasta-cooked:3").json()
    assert r["items"][0]["qty"] == 3 and r["items"][0]["locked"]
    assert client.get("/api/suggest?lock=pasta-cooked:0.3").status_code == 422
    assert client.get("/api/suggest?lock=pasta-cooked").status_code == 422
