"""Made-up meals, entries and insulin ratios for the demo reels, for the last two days and this morning.
   seed.py <demo app.db>   (the demo server must be running on 127.0.0.1:8095)"""
import json, sqlite3, sys, urllib.request
from datetime import date, timedelta

B = "http://127.0.0.1:8095"
db = sqlite3.connect(sys.argv[1]); db.row_factory = sqlite3.Row

def call(path, body, method="POST"):
    r = urllib.request.Request(B + path, json.dumps(body).encode(), {"Content-Type": "application/json", "X-Parent-Pin": "1234"}, method=method)
    return json.load(urllib.request.urlopen(r))

def item(fid, label):
    f = db.execute("SELECT * FROM foods WHERE id = ?", (fid,)).fetchone()
    p = f and db.execute("SELECT * FROM portions WHERE food_id = ? AND label = ?", (fid, label)).fetchone()
    if not p:
        sys.exit(f"The demo needs the dev food {fid!r} with a {label!r} portion.")
    return {"food_id": fid, "food_name": f["name"], "portion_label": label, "grams": p["grams"], "carbs_per_100g": f["carbs_per_100g"], "qty": 1}

call("/api/dose-settings", {"carb_ratio": [{"start": "00:00", "value": 15}], "isf": [{"start": "00:00", "value": 50}],
                            "target": [{"start": "00:00", "value": 120}]}, "PUT")
n = 0
def meal(day, time, items, **kw):
    global n; n += 1
    return call("/api/meals", {"client_id": f"demo-meal-{n:04d}", "day": day, "time": time, "items": items, **kw})

for back in (2, 1):
    day = (date.today() - timedelta(days=back)).isoformat()
    meal(day, "07:30", [item("multi-grain-cheerios", "1 serving"), item("honeycrisp-apple-slices", "½ serving")],
         bg=128, bg_source="meter", insulin=3.5, insulin_kind="bolus", insulin_offset_min=15, eat_min=20)
    meal(day, "12:15", [item("100-whole-grain-penne-rigate-whole-wheat-macaroni-product-kr", "1 serving"), item("d-anjou-pears", "1 serving")],
         bg=142, bg_source="cgm", insulin=4, insulin_kind="bolus", insulin_offset_min=10)
    meal(day, "18:00", [item("dino-buddies", "4 Nuggets"), item("marinade-cooking-sauce-mr-yoshida-s", "1 Tbsp"),
                        item("apple-apple-gogo-squeeze-fruitz", "1 serving")], bg=118, bg_source="meter", insulin=4.5, insulin_kind="bolus", insulin_offset_min=15)
    call("/api/entries", {"client_id": f"demo-snack-{back}", "day": day, "time": "15:30", "carbs": 15, "bg": 96, "note": "Juice box after soccer"})
    call("/api/entries", {"client_id": f"demo-basal-{back}", "day": day, "time": "20:30", "insulin": 12, "insulin_kind": "long", "note": "Bedtime long-acting"})
meal(date.today().isoformat(), "07:30", [item("cinnamon-toast-crunch-general-mills", "1 serving"), item("honeycrisp-apple-slices", "½ serving")],
     bg=124, bg_source="cgm", insulin=4, insulin_kind="bolus", insulin_offset_min=15)
with db:   # logged at the time, as a family would: no 'changed later' marks
    db.execute("UPDATE meals SET edited_at = NULL, eaten = 'all'")
    db.execute("UPDATE log_entries SET edited_at = NULL")
print("seeded", n, "meals")
