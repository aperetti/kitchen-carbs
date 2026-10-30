"""Read-only nutrition lookups (okf/architecture/nutrition-apis.md).

USDA FoodData Central for generic foods (carbs per 100 g), Open Food Facts for
packaged products (per serving + per 100 g). Results are suggestions: the parent
confirms them before saving (okf/rules/label-reading-needs-check.md).
"""
import io
import os
import re
import time

import requests
from PIL import Image

FDC = "https://api.nal.usda.gov/fdc/v1"
OFF = "https://world.openfoodfacts.org"
OFF_SEARCH = "https://search.openfoodfacts.org/search"   # their newer search service; the old cgi search is often down
DEFAULT_CONTACT = "owner@example.com"   # owner's choice (27 Oct); editable in Manage → Settings
CARBS_ID = 1005
FIBER_ID = 1079                                                    # "Fiber, total dietary"
# Open Food Facts country tags for the region setting (okf/features/food-lookup.md); "" = all countries
COUNTRIES = {"en:united-states": "United States", "en:canada": "Canada", "en:mexico": "Mexico", "en:united-kingdom": "United Kingdom",
             "en:ireland": "Ireland", "en:australia": "Australia", "en:new-zealand": "New Zealand", "en:france": "France",
             "en:germany": "Germany", "en:spain": "Spain", "en:italy": "Italy", "": "All countries"}
DEFAULT_COUNTRY = "en:united-states"                               # "Carbohydrate, by difference"
OFF_FIELDS = ("code,product_name,brands,serving_size,serving_quantity,serving_quantity_unit,nutriments,"
              "image_nutrition_url,image_front_url,image_front_small_url")


class LookupError(Exception):
    pass


def _get(url, params=None, headers=None, what="the nutrition database"):
    try:
        r = requests.get(url, params=params, headers=headers, timeout=20)
    except requests.RequestException as e:
        raise LookupError(f"Could not reach {what}. Check the internet connection.") from e
    if r.status_code == 404:
        return None
    if r.status_code == 429:
        raise LookupError(f"{what} is limiting requests right now. Wait a minute and try again.")
    if r.status_code != 200:
        raise LookupError(f"{what} answered {r.status_code}.")
    return r.json()


# ---------- USDA ----------
def _fdc_key():
    return os.environ.get("FDC_API_KEY") or "DEMO_KEY"


def usda_search(q: str, n: int = 10):
    d = _get(f"{FDC}/foods/search", {"api_key": _fdc_key(), "query": q, "dataType": "Foundation,SR Legacy",
                                     "pageSize": 40}, what="USDA FoodData Central") or {}
    out = []
    for f in d.get("foods", []):
        carbs = next((x.get("value") for x in f.get("foodNutrients", []) if x.get("nutrientId") == CARBS_ID), None)
        if carbs is not None:
            out.append({"source": "usda", "id": str(f["fdcId"]), "name": f["description"], "carbs_per_100g": round(carbs, 1)})
    return sorted(out, key=lambda r: usda_rank(q, r["name"]))[:n]


def usda_rank(q: str, name: str):
    """'rice cooked' should find 'Rice, white, ... cooked' before 'Rice noodles' or 'Wild rice'."""
    words = re.findall(r"[a-z]+", q.lower())
    head = name.lower().split(",")[0].strip()
    same = lambda a, b: a == b or a in (b + "s", b + "es") or b in (a + "s", a + "es")   # apple ~ apples, tomato ~ tomatoes
    return (not words or not same(head, words[0]),                     # the food itself is the first word
            not all(w.rstrip("s") in name.lower() for w in words),     # every word typed appears
            len(re.findall(r"[a-z]+", name.lower())))                  # plainer descriptions first


def usda_food(fdc_id: str):
    if not fdc_id.isdigit():
        raise LookupError("That isn't a USDA food number.")
    d = _get(f"{FDC}/food/{fdc_id}", {"api_key": _fdc_key()}, what="USDA FoodData Central")
    if not d:
        raise LookupError("USDA has no food with that number.")
    amount = lambda nid: next((n.get("amount") for n in d.get("foodNutrients", []) if n.get("nutrient", {}).get("id") == nid), None)
    carbs, fiber = amount(CARBS_ID), amount(FIBER_ID)
    portions = []
    for p in d.get("foodPortions", [])[:6]:
        desc = " ".join(str(x) for x in (p.get("amount") and f"{p['amount']:g}", p.get("modifier") or p.get("portionDescription")) if x)
        if p.get("gramWeight") and desc:
            portions.append(f"{desc} = {p['gramWeight']:g} g")
    return {"id": fdc_id, "name": d.get("description", ""), "carbs_per_100g": None if carbs is None else round(carbs, 1),
            "fiber_per_100g": None if fiber is None else round(fiber, 1),
            "typical_portions": portions, "source_ref": f"USDA FDC {fdc_id}"}


# ---------- FatSecret (okf/architecture/nutrition-apis.md) ----------
FS_TOKEN_URL = "https://oauth.fatsecret.com/connect/token"
FS_API = "https://platform.fatsecret.com/rest/server.api"
_fs_token = {"value": None, "until": 0.0}


def fatsecret_ready() -> bool:
    return bool(os.environ.get("FAT_SECRET_CLIENT_ID") and os.environ.get("FAT_SECRET_CLIENT_SECRET"))


def _fs_access_token() -> str:
    """OAuth 2.0 client credentials; the token lasts a day, so it is reused until a few minutes before it expires."""
    if _fs_token["value"] and time.time() < _fs_token["until"]:
        return _fs_token["value"]
    if not fatsecret_ready():
        raise LookupError("FatSecret isn't set up: add FAT_SECRET_CLIENT_ID and FAT_SECRET_CLIENT_SECRET to .env and restart.")
    try:
        r = requests.post(FS_TOKEN_URL, data={"grant_type": "client_credentials", "scope": "basic"}, timeout=20,
                          auth=(os.environ["FAT_SECRET_CLIENT_ID"].strip(), os.environ["FAT_SECRET_CLIENT_SECRET"].strip()))
    except requests.RequestException as e:
        raise LookupError("Could not reach FatSecret. Check the internet connection.") from e
    if r.status_code != 200:
        raise LookupError("FatSecret didn't accept the app's credentials. Check the client ID and secret in .env.")
    d = r.json()
    _fs_token.update(value=d["access_token"], until=time.time() + int(d.get("expires_in", 3600)) - 300)
    return _fs_token["value"]


def _fs_call(method: str, **params) -> dict:
    try:
        r = requests.get(FS_API, params={"method": method, "format": "json", **params}, timeout=20,
                         headers={"Authorization": f"Bearer {_fs_access_token()}"})
    except requests.RequestException as e:
        raise LookupError("Could not reach FatSecret. Check the internet connection.") from e
    try:
        d = r.json()
    except ValueError as e:
        raise LookupError(f"FatSecret answered {r.status_code}.") from e
    err = d.get("error")
    if err:
        if str(err.get("code")) == "21":   # the server's public address isn't on the app's allowlist
            ip = (re.findall(r"'([\d.:a-fA-F]+)'", err.get("message", "")) or ["this server's address"])[0]
            raise LookupError(f"FatSecret refused {ip}. Add it to the IP allowlist for your key in the FatSecret developer portal.")
        if str(err.get("code")) in ("12", "22"):
            raise LookupError("FatSecret is limiting requests right now. Wait a minute and try again.")
        raise LookupError(f"FatSecret: {err.get('message', 'error')[:160]}")
    return d


def _listify(x):
    return x if isinstance(x, list) else [x] if x else []


def fs_search(q: str, n: int = 12):
    d = _fs_call("foods.search", search_expression=q, max_results=n)
    out = []
    for f in _listify((d.get("foods") or {}).get("food")):
        m = re.match(r"Per (.+?) - .*?Carbs: ([\d.]+)g", f.get("food_description", ""))
        per, carbs = (m.group(1), float(m.group(2))) if m else (None, None)
        out.append({"source": "fatsecret", "id": str(f["food_id"]), "name": f.get("food_name", ""),
                    "brand": f.get("brand_name") or "", "kind": f.get("food_type", ""),
                    "carbs_per_100g": round(carbs, 1) if per == "100g" else None,
                    "serving": None if per == "100g" or per is None else f"{carbs:g} g carbs per {per}"})
    return out


def _grams(s):
    return _num(s.get("metric_serving_amount")) if (s.get("metric_serving_unit") or "").lower() == "g" else None


def fs_food(food_id: str):
    """FatSecret food -> the reading shape a label scan produces (labels.check), plus its other servings."""
    if not food_id.isdigit():
        raise LookupError("That isn't a FatSecret food number.")
    f = (_fs_call("food.get.v4", food_id=food_id).get("food")) or {}
    if not f:
        raise LookupError("FatSecret has no food with that number.")
    servings = _listify((f.get("servings") or {}).get("serving"))
    in_grams = [s for s in servings if _grams(s)]
    main = (next((s for s in in_grams if str(s.get("is_default")) == "1"), None)
            or next((s for s in in_grams if not (s.get("serving_description") or "").startswith("100")), None)
            or (in_grams[0] if in_grams else None) or (servings[0] if servings else {}))
    per100 = next((_num(s.get("carbohydrate")) * 100 / _grams(s) for s in in_grams
                   if _num(s.get("carbohydrate")) is not None), None)
    fiber100 = next((_num(s.get("fiber")) * 100 / _grams(s) for s in in_grams if _num(s.get("fiber")) is not None), None)
    brand = f.get("brand_name") or ""
    name = f"{f.get('food_name', '')} – {brand}" if brand and brand.lower() not in f.get("food_name", "").lower() else f.get("food_name", "")
    others = [f"{s.get('serving_description')} = {_grams(s):g} g ({_num(s.get('carbohydrate')) or 0:g} g carbs)"
              for s in in_grams if s is not main][:6]
    reading = {"is_nutrition_label": True, "product_name": name, "serving_size_text": main.get("serving_description"),
               "serving_grams": _grams(main), "servings_per_container": None,
               "total_carbs_g_per_serving": _num(main.get("carbohydrate")), "fiber_g_per_serving": _num(main.get("fiber")),
               "total_sugars_g_per_serving": _num(main.get("sugar")),
               "carbs_g_per_100g": round(per100, 1) if per100 is not None else None,
               "fiber_g_per_100g": round(fiber100, 1) if fiber100 is not None else None}
    return reading, others


# ---------- Open Food Facts ----------
def _off_headers(contact):
    return {"User-Agent": f"KitchenCarbs/1.0 ({contact or DEFAULT_CONTACT})"}


def _num(v):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return v if v >= 0 else None


def off_reading(p: dict) -> dict:
    """Open Food Facts product → the same reading shape a label scan produces (labels.check)."""
    n = p.get("nutriments", {})
    unit = (p.get("serving_quantity_unit") or "").lower()
    grams = _num(p.get("serving_quantity")) if unit in ("", "g") else None
    if grams is not None and not unit and not re.search(r"\d\s*g\b", p.get("serving_size") or "", re.I):
        grams = None   # a serving in mL or pieces has no gram weight
    title, brand = (p.get("product_name") or "").strip(), _brand(p)
    name = f"{title} – {brand}" if brand and brand.lower() not in title.lower() else title
    return {"is_nutrition_label": True, "product_name": name or None, "serving_size_text": p.get("serving_size"),
            "serving_grams": grams, "servings_per_container": None,
            "total_carbs_g_per_serving": _num(n.get("carbohydrates_serving")),
            "fiber_g_per_serving": _num(n.get("fiber_serving")), "total_sugars_g_per_serving": _num(n.get("sugars_serving")),
            "carbs_g_per_100g": _num(n.get("carbohydrates_100g")), "fiber_g_per_100g": _num(n.get("fiber_100g"))}


def off_product(code: str, contact: str):
    code = re.sub(r"\D", "", code)
    if not 8 <= len(code) <= 14:
        raise LookupError("A barcode has 8 to 14 digits.")
    d = _get(f"{OFF}/api/v2/product/{code}.json", {"fields": OFF_FIELDS}, _off_headers(contact), "Open Food Facts")
    if not d or d.get("status") != 1:
        raise LookupError(f"Open Food Facts doesn't have barcode {code}. Scan the nutrition label instead.")
    return code, d["product"]


def off_query(q: str) -> str:
    """Whole words only match whole words there, and "yoshida" isn't "yoshida's": try each word three ways."""
    words = re.findall(r"[\w-]+", q.lower())[:6]
    return " ".join(f"({w} OR {w}* OR {w}'s)" for w in words)


def _brand(p):
    b = p.get("brands") or ""
    return (b[0] if isinstance(b, list) and b else b.split(",")[0] if isinstance(b, str) else "").strip()


def off_search(q: str, contact: str, n: int = 12, country: str = ""):
    where = f' countries_tags:"{country}"' if country in COUNTRIES and country else ""
    try:
        d = _get(OFF_SEARCH, {"q": off_query(q) + where, "page_size": n, "langs": "en", "fields": OFF_FIELDS},
                 _off_headers(contact), "Open Food Facts") or {}
        products = d.get("hits", [])
    except LookupError:   # fall back to the old search when the new one is unavailable
        old = {"search_terms": q, "search_simple": 1, "json": 1, "page_size": n, "fields": OFF_FIELDS}
        if where:
            old.update(tagtype_0="countries", tag_contains_0="contains", tag_0=country)
        d = _get(f"{OFF}/cgi/search.pl", old, _off_headers(contact), "Open Food Facts") or {}
        products = d.get("products", [])
    out = []
    for p in products:
        if not (p.get("code") and p.get("product_name")):
            continue
        carbs = _num((p.get("nutriments") or {}).get("carbohydrates_100g"))
        out.append({"source": "off", "id": p["code"], "name": p["product_name"], "brand": _brand(p),
                    "carbs_per_100g": None if carbs is None else round(carbs, 1),   # shown as "carbs not listed"
                    "serving": p.get("serving_size"), "image": p.get("image_front_small_url")})
    out.sort(key=lambda r: (r["carbs_per_100g"] is None, r["image"] is None))   # complete entries first
    return out


def fetch_image(url: str, contact: str):
    """Download an Open Food Facts photo (only from their image host)."""
    if not url or not re.match(r"^https://images\.openfoodfacts\.org/", url):
        return None
    try:
        r = requests.get(url, headers=_off_headers(contact), timeout=20)
        return r.content if r.status_code == 200 else None
    except requests.RequestException:
        return None


# ---------- barcodes ----------
def read_barcode(data: bytes) -> str:
    import zxingcpp
    try:
        im = Image.open(io.BytesIO(data)).convert("RGB")
    except Exception as e:
        raise LookupError("That file is not an image this app can read.") from e
    im.thumbnail((2000, 2000))
    for r in zxingcpp.read_barcodes(im):
        text = re.sub(r"\D", "", r.text or "")
        if 8 <= len(text) <= 14:
            return text
    raise LookupError("No barcode found in the photo. Try again closer and in good light, or type the digits.")
