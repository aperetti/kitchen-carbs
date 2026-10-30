"""Read a Nutrition Facts photo with Gemini (okf/features/scan-label.md).

Gemini only reads what is printed; the server checks the numbers and the parent
confirms them beside the photo before anything is saved
(okf/rules/label-reading-needs-check.md).
"""
import base64
import json
import os

import requests

from . import db, photos

MODEL = os.environ.get("GEMINI_TEXT_MODEL", "gemini-3.5-flash-lite")

PROMPT = """Read this food package's nutrition label exactly as printed.
Return only values you can see; use null for anything missing or unreadable. Do not estimate.
- serving_grams: the gram weight of one serving only if the label prints it in grams (e.g. "1 cup (55g)" -> 55).
  If the serving is only in mL, cups or pieces, use null.
- total_carbs_g_per_serving: the "Total Carbohydrate" (or "Carbohydrate") amount per serving in grams.
- carbs_g_per_100g: only if the label prints a per-100 g column.
- fiber_g_per_serving: "Dietary Fiber" per serving in grams if printed; fiber_g_per_100g only from a per-100 g column.
- Sugars per serving in grams if printed.
- product_name: the product name if it is visible on the photo, else null."""

SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "is_nutrition_label": {"type": "BOOLEAN"},
        "product_name": {"type": "STRING", "nullable": True},
        "serving_size_text": {"type": "STRING", "nullable": True},
        "serving_grams": {"type": "NUMBER", "nullable": True},
        "servings_per_container": {"type": "NUMBER", "nullable": True},
        "total_carbs_g_per_serving": {"type": "NUMBER", "nullable": True},
        "fiber_g_per_serving": {"type": "NUMBER", "nullable": True},
        "total_sugars_g_per_serving": {"type": "NUMBER", "nullable": True},
        "carbs_g_per_100g": {"type": "NUMBER", "nullable": True},
        "fiber_g_per_100g": {"type": "NUMBER", "nullable": True},
    },
    "required": ["is_nutrition_label"],
}


def ask_gemini(label_path: str) -> dict:
    data = open(os.path.join(db.PHOTO_DIR, label_path), "rb").read()
    body = {"contents": [{"parts": [
        {"inlineData": {"mimeType": "image/jpeg", "data": base64.b64encode(data).decode()}},
        {"text": PROMPT}]}],
        "generationConfig": {"responseMimeType": "application/json", "responseSchema": SCHEMA, "temperature": 0}}
    try:
        r = requests.post(photos.API.format(MODEL), headers={"x-goog-api-key": photos._key()}, json=body, timeout=90)
    except requests.RequestException as e:
        raise photos.PhotoError("Could not reach Gemini. Check the internet connection and try again.") from e
    d = r.json()
    try:
        return json.loads(d["candidates"][0]["content"]["parts"][0]["text"])
    except (KeyError, IndexError, ValueError):
        msg = d.get("error", {}).get("message") or "Gemini returned no reading."
        raise photos.PhotoError(f"Could not read the label: {msg[:200]}")


def _num(v):
    return float(v) if isinstance(v, (int, float)) and v >= 0 else None


def check(raw: dict) -> dict:
    """Normalise Gemini's reading and list everything the parent should look at."""
    r = {k: raw.get(k) for k in SCHEMA["properties"]}
    for k in ("serving_grams", "servings_per_container", "total_carbs_g_per_serving",
              "fiber_g_per_serving", "total_sugars_g_per_serving", "carbs_g_per_100g", "fiber_g_per_100g"):
        r[k] = _num(r[k])
    warnings = []
    if not raw.get("is_nutrition_label"):
        warnings.append("This doesn't look like a nutrition label. Check the photo, or enter the values yourself.")
    carbs, grams, per100 = r["total_carbs_g_per_serving"], r["serving_grams"], r["carbs_g_per_100g"]
    if carbs is None:
        warnings.append("Total carbohydrate couldn't be read. Enter it from the label.")
    if grams is None:
        warnings.append("The serving has no gram weight on the label"
                        + (f" ({r['serving_size_text']})" if r["serving_size_text"] else "")
                        + ". Weigh one serving and enter the grams.")
    if carbs is not None and grams and carbs > grams:
        warnings.append(f"Carbs ({carbs:g} g) are more than the serving weight ({grams:g} g). One of them was misread.")
    computed = round(carbs / grams * 100, 1) if carbs is not None and grams else None
    if computed is not None and per100 is not None and abs(computed - per100) > max(1.0, per100 * 0.05):
        warnings.append(f"The label's per-100 g carbs ({per100:g} g) don't match the per-serving numbers ({computed:g} g). Check both.")
    fiber = r["fiber_g_per_serving"]
    if fiber is not None and grams and fiber > grams:
        warnings.append(f"Fiber ({fiber:g} g) is more than the serving weight ({grams:g} g). It was misread.")
    elif fiber is not None and carbs is not None and fiber > carbs:   # European labels list carbs without fiber
        warnings.append(f"Fiber ({fiber:g} g) is more than the carbs ({carbs:g} g). Check both; some labels list carbs without fiber.")
    r["carbs_per_100g"] = per100 if per100 is not None else computed
    if r["carbs_per_100g"] is not None and r["carbs_per_100g"] > 100:
        warnings.append("Carbs per 100 g came out above 100. A number was misread.")
        r["carbs_per_100g"] = None
    return {"reading": r, "warnings": warnings}


# ---- best-guess container for a generated photo (okf/domain/photo-style.md) ----
CONTAINER_CHOICES = ["package", "plate", "bowl", "dressing", "counter"]
GUESS_PROMPT = """A family is making a photo of one serving of this food for their kitchen carb-counting app.
Food: {name}. Serving: {serving}.
How would one serving most naturally be served to a child at home? Choose exactly one:
- package: eaten from its own retail package (granola bar, juice box, yogurt cup, squeeze pouch, single-serve snack bag)
- plate: on a plate (sandwiches, nuggets, pasta, crackers, fruit slices)
- bowl: in a bowl (cereal, soup, rice, poured-out small snacks)
- dressing: in a small dressing cup (sauces, dips, dressings, syrup, ketchup)
- counter: whole on the counter with no dish (a whole apple, banana or orange)"""


def guess_container(name: str, serving: str, package_path: str | None = None) -> str:
    """Gemini's best guess at what one serving is shown in; the parent can change it on the portion."""
    parts = [{"text": GUESS_PROMPT.format(name=name, serving=serving or "not given")}]
    if package_path:
        data = open(os.path.join(db.PHOTO_DIR, package_path), "rb").read()
        parts.insert(0, {"inlineData": {"mimeType": "image/jpeg", "data": base64.b64encode(data).decode()}})
    body = {"contents": [{"parts": parts}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0, "responseSchema": {
                "type": "OBJECT", "properties": {"container": {"type": "STRING", "enum": CONTAINER_CHOICES}}, "required": ["container"]}}}
    try:
        r = requests.post(photos.API.format(MODEL), headers={"x-goog-api-key": photos._key()}, json=body, timeout=30)
        choice = json.loads(r.json()["candidates"][0]["content"]["parts"][0]["text"])["container"]
    except (requests.RequestException, KeyError, IndexError, ValueError) as e:
        raise photos.PhotoError("Gemini couldn't guess the dish.") from e
    if choice not in CONTAINER_CHOICES:
        raise photos.PhotoError("Gemini couldn't guess the dish.")
    return choice
