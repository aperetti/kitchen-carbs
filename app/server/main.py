"""Kitchen Carbs server: API, photos and the tablet web app (okf/architecture/docker-server.md)."""
import csv
import hashlib
import io
import json
import os
import re
import secrets
import threading
import time
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from typing import Literal

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator, model_validator

from concurrent.futures import ThreadPoolExecutor

from . import auth, core, db, dose, labels, lookup, migrations, nightscout, nightscout_send, photos, push, report, tidepool

WEB_DIR = os.path.join(os.path.dirname(__file__), "..", "web")
SEED_DIR = os.path.join(os.path.dirname(__file__), "..", "seed")
EATEN = ("all", "most", "half", "little", "none")


def now() -> datetime:
    """Server local time (set TZ in docker-compose). Replaced in tests."""
    return datetime.now()


def today() -> str:
    return now().date().isoformat()


def con():
    c = db.connect()
    try:
        yield c
    finally:
        c.close()


def fail(status: int, msg: str):
    raise HTTPException(status_code=status, detail=msg)


# ---------- parent PIN ----------
def _hash(pin: str, salt: str) -> str:
    return hashlib.sha256((salt + pin).encode()).hexdigest()


PIN_TRIES, PIN_WINDOW_S = 10, 600   # then the PIN is locked for the rest of the window (okf/architecture/auth.md)
_pin_misses: list[float] = []
_pin_lock = threading.Lock()


def pin_ok(pin: str, salt: str, h: str) -> bool:
    """A 4-digit PIN can't hold out against unlimited guesses, so wrong ones are counted."""
    with _pin_lock:
        cutoff = time.time() - PIN_WINDOW_S
        _pin_misses[:] = [t for t in _pin_misses if t > cutoff]
        if len(_pin_misses) >= PIN_TRIES:
            fail(429, "Too many wrong PINs. Try again in 10 minutes.")
        if pin and secrets.compare_digest(_hash(pin, salt), h):
            return True
        _pin_misses.append(time.time())
        return False


def parent(x_parent_pin: str = Header(default=""), c=Depends(con)):
    h, salt = db.get_setting(c, "pin_hash"), db.get_setting(c, "pin_salt")
    if not h:
        fail(403, "Set a parent PIN first.")
    if not pin_ok(x_parent_pin, salt, h):
        fail(401, "Wrong PIN.")


# ---------- models ----------
class FoodIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    tags: list[int] = Field(default_factory=list, max_length=20)
    carbs_per_100g: float | None = Field(default=None, ge=0, le=100)
    serving_grams: float | None = Field(default=None, gt=0, le=2000)   # '17 g carbs per 85 g', kept as typed
    serving_carbs: float | None = Field(default=None, ge=0, le=2000)
    serving_fiber: float | None = Field(default=None, ge=0, le=2000)   # fiber for serving_grams, reference only
    fiber_per_100g: float | None = Field(default=None, ge=0, le=100)   # for a per-100 g food (okf/domain/food.md)
    source_kind: Literal["fatsecret", "usda", "label", "care-team", "openfoodfacts"]
    source_ref: str = Field(min_length=1, max_length=200)   # okf/rules/provenance-required.md
    notes: str = Field(default="", max_length=1000)
    barcode: str | None = Field(default=None, pattern=r"^\d{8,14}$")   # identifies the package, not the carbs (okf/domain/food.md)
    verified: bool = False
    label_photo: str | None = Field(default=None, pattern=r"^labels/[0-9a-f]{32}\.jpg$")
    package_photo: str | None = Field(default=None, pattern=r"^labels/[0-9a-f]{32}\.jpg$")
    basis: Literal["as-sold", "raw", "cooked"] = "as-sold"   # the state the carbs are for (okf/domain/food.md)
    cook_raw_g: float | None = Field(default=None, gt=0, le=5000)      # one batch weighed dry or raw ...
    cook_cooked_g: float | None = Field(default=None, gt=0, le=5000)   # ... and cooked (okf/rules/cooking-ratio-measured.md)

    @model_validator(mode="after")
    def cooking_ratio(self):
        if (self.cook_raw_g is None) != (self.cook_cooked_g is None):
            raise ValueError("Give both weights of the batch: dry or raw, and cooked.")
        if self.basis != "as-sold" and self.cook_raw_g is None:   # okf/domain/food.md: required since 28 Oct
            raise ValueError("A dry / raw or cooked food needs its cooking ratio: weigh one batch before and after cooking.")
        if self.cook_raw_g is not None:
            if self.basis == "as-sold":
                raise ValueError("A cooking ratio needs the carbs to be for dry / raw or cooked food.")
            if not 0.2 <= self.cook_cooked_g / self.cook_raw_g <= 6:
                raise ValueError("Those weights give a cooking ratio outside ×0.2 to ×6. Check them.")
        return self

    @model_validator(mode="after")
    def per_100g_from_serving(self):   # okf/domain/food.md: carbs per 100 g is worked out from the serving
        if (self.serving_grams is None) != (self.serving_carbs is None):
            raise ValueError("Give both the serving's grams and its carbs.")
        if self.serving_grams is not None:
            if self.serving_carbs > self.serving_grams:
                raise ValueError("Carbs can't be more than the serving weight.")
            self.carbs_per_100g = round(self.serving_carbs / self.serving_grams * 100, 2)
            if self.serving_fiber is not None:
                if self.serving_fiber > self.serving_grams:
                    raise ValueError("Fiber can't be more than the serving weight.")
                self.fiber_per_100g = round(self.serving_fiber / self.serving_grams * 100, 2)
            else:
                self.fiber_per_100g = None
        elif self.serving_fiber is not None:
            raise ValueError("Give fiber per 100 g for a food without a serving.")
        if self.carbs_per_100g is None:
            raise ValueError("Give carbs per 100 g or a serving.")
        return self


class PortionIn(BaseModel):
    label: str = Field(min_length=1, max_length=40)

    @field_validator("label")
    @classmethod
    def amount_then_unit(cls, v):   # okf/domain/portion.md
        if not core.portion_amount(v):
            raise ValueError("Name a portion with a number, then the unit: 1 cup, 2 slices, ½ serving.")
        return v.strip()
    grams: float = Field(gt=0, le=2000)
    sort: int = 0
    container: Literal["auto", "plate", "bowl", "dressing", "counter", "package"] = "auto"   # counter: no dish
    size_ref_id: int | None = None
    photo_note: str | None = Field(None, max_length=300)   # None keeps the current note


class SizeRefIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    measurement: str = Field(min_length=1, max_length=40)
    container: Literal["plate", "bowl", "dressing"] | None = None   # the dish it goes with; None = any


class StyleIn(BaseModel):
    prompt: str = Field(max_length=2000)


class QualityIn(BaseModel):
    quality: Literal["fast", "sharp"]


def half_steps(v: float) -> float:
    if v <= 0 or v > 10 or (v * 2) != int(v * 2):
        raise ValueError("Quantity must be a half step between 0.5 and 10.")
    return v


ENTERED = "Carbs entered by hand"


class ItemIn(BaseModel):
    food_id: str | None = None
    portion_id: int | None = None
    food_name: str = Field(min_length=1, max_length=80)
    portion_label: str = Field(min_length=1, max_length=40)
    grams: float | None = Field(default=None, gt=0, le=2000)
    carbs_per_100g: float | None = Field(default=None, ge=0, le=100)
    qty: float = 1
    entered_carbs: float | None = Field(default=None, ge=0.5, le=300)   # typed on the plate, no weight (okf/domain/plate.md)

    _qty = field_validator("qty")(half_steps)

    @model_validator(mode="after")
    def weighed_or_entered(self):
        if self.entered_carbs is not None:
            if not self.food_name.strip():
                raise ValueError("Describe the carbs entered by hand.")
            self.food_id = self.portion_id = None
            self.grams, self.carbs_per_100g, self.qty, self.portion_label = 0, 0, 1, ENTERED
        elif self.grams is None or self.carbs_per_100g is None:
            raise ValueError("A food needs its weight and carbs per 100 g.")
        return self


TIME_RE = r"^([01]\d|2[0-3]):[0-5]\d$"


DETAILS = ("bg", "bg_source", "insulin", "insulin_kind", "insulin_offset_min", "eat_min")


class MealDetails(BaseModel):
    """Optional details that go with a meal (okf/domain/meal.md). Insulin is only what was typed (okf/rules/no-dosing.md)."""
    bg: int | None = Field(default=None, ge=20, le=600)                       # mg/dL
    bg_source: Literal["cgm", "meter"] | None = None
    insulin: float | None = Field(default=None, gt=0, le=100)                 # units given
    insulin_kind: Literal["bolus", "basal"] | None = None
    insulin_offset_min: int | None = Field(default=None, ge=-120, le=120)     # given this long before eating; negative = after
    eat_min: int | None = Field(default=None, ge=1, le=240)

    @model_validator(mode="after")
    def consistent(self):
        if self.insulin is not None:
            if self.insulin_kind is None:
                raise ValueError("Choose bolus or basal for the insulin.")
            if abs(self.insulin * 20 - round(self.insulin * 20)) > 1e-6:
                raise ValueError("Insulin is recorded in steps of 0.05 units.")
        else:
            self.insulin_kind = self.insulin_offset_min = None
        self.bg_source = (self.bg_source or "meter") if self.bg is not None else None
        return self


class MealIn(MealDetails):
    client_id: str = Field(min_length=8, max_length=64)
    day: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    time: str = Field(pattern=TIME_RE)
    items: list[ItemIn] = Field(min_length=1, max_length=30)
    plan_id: int | None = None   # saved from a planned meal: the meal replaces it (okf/features/plan-meal.md)


class MealPatch(BaseModel):
    eaten: Literal["all", "most", "half", "little", "none", ""] | None = None
    time: str | None = Field(default=None, pattern=TIME_RE)


class EntryValues(BaseModel):
    """okf/domain/manual-entry.md: a record of what happened. Nothing here is calculated (okf/rules/no-dosing.md)."""
    carbs: float | None = Field(default=None, ge=0, le=500)
    bg: int | None = Field(default=None, ge=20, le=600)          # mg/dL, meter
    insulin: float | None = Field(default=None, gt=0, le=100)    # units given
    insulin_kind: Literal["rapid", "long"] | None = None
    note: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def something_recorded(self):
        if self.carbs is None and self.bg is None and self.insulin is None and not self.note.strip():
            raise ValueError("Enter carbs, a BG reading, insulin or a note.")
        if self.insulin is not None:
            if self.insulin_kind is None:
                raise ValueError("Choose rapid or long-acting for the insulin.")
            if abs(self.insulin * 20 - round(self.insulin * 20)) > 1e-6:
                raise ValueError("Insulin is recorded in steps of 0.05 units.")
        return self


class EntryIn(EntryValues):
    client_id: str = Field(min_length=8, max_length=64)
    day: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    time: str = Field(pattern=TIME_RE)


class CommentIn(BaseModel):
    text: str = Field(min_length=1, max_length=500)


class PinIn(BaseModel):
    pin: str = Field(pattern=r"^\d{4,8}$")
    old_pin: str = ""


class NightscoutIn(BaseModel):
    url: str = Field(pattern=r"^https?://.+")
    token: str = Field(min_length=4, max_length=200)


class TargetsIn(BaseModel):
    low: int = Field(ge=54, le=120)
    high: int = Field(ge=120, le=300)


class ReviewIn(BaseModel):
    action: Literal["accept", "discard", "use_original"]


class EstimateIn(BaseModel):
    from_portion_id: int


class TagIn(BaseModel):
    name: str = Field(min_length=1, max_length=30)


class FavItemIn(BaseModel):
    portion_id: int
    qty: float = Field(gt=0, le=10)   # weighed grams ÷ the portion's grams (okf/domain/favorite-plate.md)

    @field_validator("qty")
    @classmethod
    def two_places(cls, v):
        return round(v, 2)


class FavoriteIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    items: list[FavItemIn] = Field(min_length=1, max_length=30)


class FavoriteRename(BaseModel):
    name: str = Field(min_length=1, max_length=60)


class FavPhotoReview(BaseModel):
    action: Literal["accept", "discard", "remove"]


# ---------- helpers ----------
def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:60] or "food"


def portion_out(p, cp100):
    exact = core.carbs_exact(p["grams"], cp100)
    return {"id": p["id"], "label": p["label"], "grams": p["grams"], "sort": p["sort"], "container": p["container"],
            "size_ref_id": p["size_ref_id"], "photo_note": p["photo_note"],
            "carbs": core.whole_grams(exact), "carbs_exact": exact,
            "job": p["photo_job"] and {"kind": p["photo_job"], "started": p["photo_job_started"]},
            "job_error": p["photo_job_error"],
            "photo": {"styled": p["photo_styled"], "original": p["photo_original"],
                      "candidate": p["photo_candidate"], "estimated": bool(p["photo_estimated"]),
                      "candidate_estimated": bool(p["candidate_estimated"]),
                      "candidate_kind": ("styled", "estimate", "generated")[p["candidate_estimated"] or 0]}}


def food_out(c, f):
    ps = [portion_out(p, f["carbs_per_100g"]) for p in
          c.execute("SELECT * FROM portions WHERE food_id = ? ORDER BY sort, grams", (f["id"],))]
    carbs = [p["carbs"] for p in ps]
    tags = [r["tag_id"] for r in c.execute(
        "SELECT ft.tag_id FROM food_tags ft JOIN tags t ON t.id = ft.tag_id WHERE ft.food_id = ? ORDER BY t.sort, t.name", (f["id"],))]
    ratio = round(f["cook_cooked_g"] / f["cook_raw_g"], 3) if f["cook_raw_g"] and f["cook_cooked_g"] else None
    return {**dict(f), "tags": tags, "portions": ps, "range": [min(carbs), max(carbs)] if carbs else None, "cook_ratio": ratio,
            "fiber_lookup": f["fiber_per_100g"] is None and fiber_source(f) is not None}


def barcode_in(ref):
    m = re.search(r"barcode (\d{8,14})", ref or "")
    return m and m.group(1)


def fiber_source(f):
    """Where a food's fiber can be read again: its own source only (okf/features/fill-in-fiber.md)."""
    ref = f["source_ref"] or ""
    m = (f["source_kind"] == "openfoodfacts" and re.search(r"barcode (\d{8,14})", ref)) \
        or (f["source_kind"] == "fatsecret" and re.search(r"FatSecret food (\d+)", ref)) \
        or (f["source_kind"] == "usda" and re.search(r"FDC (\d+)", ref))
    if m:
        return f["source_kind"], m.group(1)
    if f["label_photo"] and f["source_kind"] == "label":
        return "label", f["label_photo"]
    return None


def check_label_photo(path):
    if path and not os.path.exists(os.path.join(db.PHOTO_DIR, path)):
        fail(400, "The label photo is missing. Scan the label again.")
    return path


def set_food_tags(c, food_id, tag_ids):
    known = {r["id"] for r in c.execute("SELECT id FROM tags")}
    if set(tag_ids) - known:
        fail(400, "One of the tags no longer exists. Reload and try again.")
    c.execute("DELETE FROM food_tags WHERE food_id = ?", (food_id,))
    c.executemany("INSERT INTO food_tags(food_id, tag_id) VALUES (?, ?)", [(food_id, t) for t in dict.fromkeys(tag_ids)])


def get_food(c, food_id):
    f = c.execute("SELECT * FROM foods WHERE id = ?", (food_id,)).fetchone()
    if not f:
        fail(404, "That food no longer exists.")
    return f


def get_portion(c, pid):
    p = c.execute("SELECT * FROM portions WHERE id = ?", (pid,)).fetchone()
    if not p:
        fail(404, "That portion no longer exists.")
    return p


def get_meal(c, mid, deleted=False):
    m = c.execute(f"SELECT * FROM meals WHERE id = ? AND deleted_at IS {'NOT ' if deleted else ''}NULL", (mid,)).fetchone()
    if not m:
        fail(404, "That meal is no longer in the log." if not deleted else "That meal isn't among the deleted ones.")
    return m


def get_entry(c, eid, deleted=False):
    e = c.execute(f"SELECT * FROM log_entries WHERE id = ? AND deleted_at IS {'NOT ' if deleted else ''}NULL", (eid,)).fetchone()
    if not e:
        fail(404, "That entry is no longer in the log." if not deleted else "That entry isn't among the deleted ones.")
    return e


def past_edits(c) -> bool:
    """Earlier days can be changed unless a parent turned it off (okf/rules/same-day-edits.md)."""
    return db.get_setting(c, "past_edits", "on") != "off"


def clock_12h(c) -> bool:
    """The log's times as 6:30 PM instead of 18:30, one setting for the family (okf/features/review-log.md)."""
    return db.get_setting(c, "clock") == "12h"


def require_editable(c, row):
    if row["day"] != today() and not past_edits(c):
        fail(409, "Earlier days are read-only. A parent can allow changes in Manage → Settings.")


def mark_later(c, table, row):
    """A change after the record's own day is marked, so the history stays trustworthy for the care team."""
    if row["day"] < today():
        c.execute(f"UPDATE {table} SET edited_at = ? WHERE id = ?", (now().strftime("%Y-%m-%d %H:%M"), row["id"]))


def meal_ms(day: str, hhmm: str) -> int:
    return int(datetime.fromisoformat(f"{day}T{hhmm}").timestamp() * 1000)


def day_bounds_ms(day: str, days: int = 1):
    start = datetime.fromisoformat(day + "T00:00")
    return int(start.timestamp() * 1000), int((start + timedelta(days=days)).timestamp() * 1000)


def readings(c, start_ms, end_ms):
    return [(r["date_ms"], r["sgv"]) for r in
            c.execute("SELECT date_ms, sgv FROM glucose WHERE date_ms >= ? AND date_ms < ? ORDER BY date_ms",
                      (start_ms, end_ms))]


def targets(c):
    return int(db.get_setting(c, "target_low", 70)), int(db.get_setting(c, "target_high", 180))


def item_fiber(c, i) -> float | None:
    """The food's fiber per 100 g in the item's own state: the cooked or dry factor is the same one its carbs got."""
    if i.entered_carbs is not None or not i.food_id:
        return None
    f = c.execute("SELECT carbs_per_100g, fiber_per_100g FROM foods WHERE id = ?", (i.food_id,)).fetchone()
    if not f or f["fiber_per_100g"] is None:
        return None
    return f["fiber_per_100g"] * i.carbs_per_100g / f["carbs_per_100g"] if f["carbs_per_100g"] else f["fiber_per_100g"]


def fill_meal_fiber(c, food_id: str):
    """Logged items of this food with no fiber get it, in their own state; fiber a meal already has stays (okf/domain/meal.md)."""
    c.execute("""UPDATE meal_items SET fiber_per_100g = (
                   SELECT CASE WHEN f.carbs_per_100g > 0 THEN f.fiber_per_100g * meal_items.carbs_per_100g / f.carbs_per_100g
                               ELSE f.fiber_per_100g END FROM foods f WHERE f.id = meal_items.food_id)
                 WHERE food_id = ? AND fiber_per_100g IS NULL AND entered_carbs IS NULL""", (food_id,))


def meal_fiber(items) -> dict:
    """A meal's fiber, for reference only: never subtracted, and a corrected carb total doesn't change it (okf/domain/meal.md)."""
    known = [i for i in items if i["fiber_per_100g"] is not None]
    return {"fiber": round(sum(core.carbs_exact(i["grams"], i["fiber_per_100g"], i["qty"]) for i in known), 1),
            "fiber_unknown": [i["food_name"] for i in items if i["fiber_per_100g"] is None]}


def meals_for_days(c, first: str, last: str):
    out = []
    for m in c.execute("SELECT * FROM meals WHERE day BETWEEN ? AND ? AND deleted_at IS NULL ORDER BY day, time", (first, last)).fetchall():
        items = [dict(i) for i in c.execute("SELECT * FROM meal_items WHERE meal_id = ? ORDER BY id", (m["id"],))]
        for i in items:
            i["carbs"] = core.whole_grams(i["carbs_exact"])
        comments = [dict(x) for x in c.execute("SELECT id, time, text FROM meal_comments WHERE meal_id = ? ORDER BY id", (m["id"],))]
        own = sum(i["carbs_exact"] for i in items)
        exact = own if m["carbs_corrected"] is None else m["carbs_corrected"]   # a corrected total wins (okf/domain/meal.md)
        out.append({**dict(m), "items": items, "comments": comments, "total": core.whole_grams(exact), "total_exact": exact,
                    "items_total": core.whole_grams(own), **meal_fiber(items)})
    return out


def entries_for_days(c, first: str, last: str):
    return [dict(e) for e in c.execute("SELECT id, client_id, day, time, carbs, bg, insulin, insulin_kind, note, moved_from, edited_at "
                                       "FROM log_entries WHERE day BETWEEN ? AND ? AND deleted_at IS NULL ORDER BY day, time, id", (first, last))]


def insulin_totals(entries):
    out = {}
    for e in entries:
        if e["insulin"] is not None:
            out[e["insulin_kind"]] = round(out.get(e["insulin_kind"], 0) + e["insulin"], 2)
    return out


def has_glucose(c):
    return c.execute("SELECT 1 FROM glucose LIMIT 1").fetchone() is not None


# ---------- app ----------
@asynccontextmanager
async def lifespan(_app):
    if os.environ.get("KC_ENV") in ("prod", "qa") and not auth.enabled():   # never open by accident (okf/rules/allowlisted-accounts-only.md)
        raise RuntimeError("FIREBASE_PROJECT_ID isn't set: production and QA won't start without Google sign-in.")
    db.init()
    with db.connect() as c:   # a job can't survive a restart: say so instead of spinning for ever
        c.execute("UPDATE portions SET photo_job = NULL, photo_job_error = 'Interrupted by a server restart. Try again.' "
                  "WHERE photo_job IS NOT NULL")
    if os.environ.get("KC_SEED", "1") == "1":
        seed()
    if os.environ.get("KC_NIGHTSCOUT_SYNC", "1") == "1":
        nightscout.start_background_sync()
        tidepool.start_background_sync()
        nightscout_send.start_background_sync()
        threading.Thread(target=db.backup_loop, name="backup", daemon=True).start()
    yield


app = FastAPI(title="Kitchen Carbs", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)

# ---------- Google sign-in (okf/architecture/auth.md, okf/rules/allowlisted-accounts-only.md) ----------
OPEN_PATHS = ("/api/auth/",)                      # the page and its scripts load too, to show the sign-in screen
GUARDED = ("/api/", "/photos/", "/img/")


def _https(request: Request) -> bool:
    return request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"


def _set_cookie(response, request: Request, raw: str, max_age: int = auth.DAYS * 86400):
    """Over HTTPS the cookie also works inside another site's frame, such as the Home Assistant dashboard
    (SameSite=None, Partitioned); writes from other sites are refused by same_origin_writes below."""
    attrs = f"{auth.COOKIE}={raw}; Max-Age={max_age}; Path=/; HttpOnly"
    attrs += "; Secure; SameSite=None; Partitioned" if _https(request) else "; SameSite=Lax"
    response.headers.append("set-cookie", attrs)


def _host(value: str) -> str:
    return re.sub(r"^[a-z]+://", "", value.strip().lower()).split("/")[0]


@app.middleware("http")
async def https_only_through_cloudflare(request: Request, call_next):
    """Through the Cloudflare Tunnel, plain http goes to https: the sign-in cookie only works there inside a frame
    (okf/architecture/https.md). Direct LAN and localhost requests have no X-Forwarded-Proto and are left alone."""
    if request.headers.get("x-forwarded-proto") == "http" and request.method in ("GET", "HEAD"):
        from fastapi.responses import RedirectResponse
        return RedirectResponse(str(request.url.replace(scheme="https", port=None)), status_code=301)
    return await call_next(request)


@app.middleware("http")
async def same_origin_writes(request: Request, call_next):
    """The session cookie is sent from other sites' frames too, so anything that changes data must come from this
    app's own pages (okf/architecture/auth.md)."""
    origin = request.headers.get("origin")
    if request.method not in ("GET", "HEAD", "OPTIONS") and origin and request.url.path.startswith("/api/"):
        hosts = {_host(request.headers.get(h, "")) for h in ("host", "x-forwarded-host")} - {""}
        if _host(origin) not in hosts:
            return JSONResponse({"detail": "Changes must come from the app's own page."}, status_code=403)
    return await call_next(request)


@app.middleware("http")
async def syncs_follow_the_log(request: Request, call_next):
    """A saved, changed or deleted meal or entry is sent to Tidepool and Nightscout soon
    (okf/features/tidepool-sync.md, okf/features/nightscout-send.md)."""
    response = await call_next(request)
    if request.method != "GET" and response.status_code < 300 and request.url.path.startswith(("/api/meals", "/api/entries", "/api/plans")):
        tidepool.poke()
        nightscout_send.poke()
    return response


def no_shared_cache(response, path: str):
    """Cloudflare caches .pdf, .csv and .jpg by default; a stored copy would be served without sign-in."""
    if path.startswith(("/photos/", "/img/")):
        response.headers["Cache-Control"] = "private, max-age=31536000, immutable"
    else:
        response.headers["Cache-Control"] = "private, no-store"
    return response


@app.middleware("http")
async def signed_in_only(request: Request, call_next):
    # The path the router uses, not request.url.path: that one is rebuilt from the Host header, and a Host such as
    # 'x/y' made /api/log look like /y/api/log here while the router still served /api/log (okf/architecture/auth.md).
    path = request.scope["path"]
    if not path.startswith(GUARDED) or path.startswith(OPEN_PATHS):
        return await call_next(request)
    if not auth.enabled():
        return no_shared_cache(await call_next(request), path)
    raw = request.cookies.get(auth.COOKIE)
    c = db.connect()
    try:
        with c:
            found = auth.lookup(c, raw)
    finally:
        c.close()
    if not found:
        return JSONResponse({"detail": "Sign in with Google first.", "signin": True}, status_code=401)
    request.state.email = found[0]
    response = no_shared_cache(await call_next(request), path)
    if found[1]:   # the 30 days were renewed: send the cookie again with the new expiry
        _set_cookie(response, request, raw)
    return response


# Only the app and the dashboards named in .env may frame it (okf/architecture/auth.md)
FRAME_ANCESTORS = " ".join(["'self'", *os.environ.get("KC_FRAME_ANCESTORS", "").split()])
HOST_OK = re.compile(r"^(?:[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?|\[[0-9A-Fa-f:.]+\])(?::\d{1,5})?$")


@app.middleware("http")
async def plain_host_and_headers(request: Request, call_next):
    """Outermost: a Host that isn't a host name ('x/y', 'a#') is refused before anything reads the URL."""
    if not HOST_OK.match(request.headers.get("host", "")):
        return JSONResponse({"detail": "Bad Host header."}, status_code=400)
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    response.headers.setdefault("Content-Security-Policy", f"frame-ancestors {FRAME_ANCESTORS}")
    return response


class TokenIn(BaseModel):
    id_token: str = Field(min_length=20, max_length=5000)


class AccountsIn(BaseModel):
    emails: list[str] = Field(max_length=30)


@app.get("/api/auth/config")
def auth_config():
    return {"enabled": auth.enabled(), "firebase": auth.web_config() if auth.enabled() else None}


@app.post("/api/auth/session")
def sign_in(body: TokenIn, request: Request, response: Response, c=Depends(con)):
    if not auth.enabled():
        fail(400, "Sign-in isn't turned on for this server.")
    try:
        email = auth.verify(body.id_token)
    except auth.AuthError as e:
        fail(401, str(e))
    if email not in auth.allowed(c):
        fail(403, f"{email} isn't on this family's list. Ask a parent to add it in Manage → Settings.")
    with c:
        raw = auth.create(c, email, request.headers.get("user-agent", ""))
    _set_cookie(response, request, raw)
    return {"email": email}


@app.get("/api/auth/me")
def who_am_i(request: Request, c=Depends(con)):
    if not auth.enabled():
        return {"enabled": False, "email": None}
    with c:
        found = auth.lookup(c, request.cookies.get(auth.COOKIE))
    return {"enabled": True, "email": found[0] if found else None}


@app.post("/api/auth/logout")
def sign_out(request: Request, response: Response, c=Depends(con)):
    with c:
        auth.end(c, request.cookies.get(auth.COOKIE))
    _set_cookie(response, request, "", max_age=0)
    return {"ok": True}


class CodeIn(BaseModel):
    code: str = Field(min_length=4, max_length=20)


@app.post("/api/auth/device")
def device_start():
    """A kiosk or dashboard asks for a code to show; a parent approves it on a signed-in device."""
    if not auth.enabled():
        fail(400, "Sign-in isn't turned on for this server.")
    try:
        return auth.start_device()
    except auth.AuthError as e:
        fail(429, str(e))


@app.get("/api/auth/device/{poll}")
def device_poll(poll: str, request: Request, response: Response, c=Depends(con)):
    state, email = auth.poll_device(poll)
    if state == "approved":
        if email not in auth.allowed(c):   # taken off the list while the code waited
            return {"state": "expired"}
        with c:
            raw = auth.create(c, email, request.headers.get("user-agent", ""))
        _set_cookie(response, request, raw)
        return {"state": "approved", "email": email}
    return {"state": state}


@app.post("/api/accounts/approve-device", dependencies=[Depends(parent)])
def device_approve(body: CodeIn, request: Request):
    email = getattr(request.state, "email", None)
    if not email:
        fail(400, "Sign in on this device first.")
    if not auth.approve_device(body.code, email):
        fail(404, "No device is waiting with that code. Codes last 10 minutes; start again on the other device.")
    return {"ok": True, "email": email}


@app.get("/api/accounts", dependencies=[Depends(parent)])
def get_accounts(request: Request, c=Depends(con)):
    devices = c.execute("SELECT email, COUNT(*) AS n FROM sessions GROUP BY email").fetchall()
    return {"enabled": auth.enabled(), "emails": auth.allowed(c), "me": getattr(request.state, "email", None),
            "devices": {r["email"]: r["n"] for r in devices}}


@app.put("/api/accounts", dependencies=[Depends(parent)])
def put_accounts(body: AccountsIn, request: Request, c=Depends(con)):
    bad = [e for e in body.emails if e.strip() and not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", e.strip())]
    if bad:
        fail(422, f"Not an email address: {bad[0]}")
    me = getattr(request.state, "email", None)
    if me and me not in [e.strip().lower() for e in body.emails]:
        fail(400, "Keep your own account on the list, or you'd be signed out straight away.")
    with c:
        auth.set_allowed(c, body.emails)
    return get_accounts(request, c)


@app.post("/api/accounts/sign-out-others", dependencies=[Depends(parent)])
def sign_out_others(request: Request, c=Depends(con)):
    with c:
        n = auth.end_others(c, request.cookies.get(auth.COOKIE))
    return {"signed_out": n}



@app.get("/api/session")
def session(c=Depends(con)):
    return {"env": os.environ.get("KC_ENV", "prod"), "schema": migrations.version(c),
            "pin_set": bool(db.get_setting(c, "pin_hash")), "today": today(), "now": now().strftime("%H:%M"),
            "glucose": has_glucose(c), "targets": targets(c)}


@app.post("/api/pin")
def set_pin(body: PinIn, c=Depends(con)):
    h, salt = db.get_setting(c, "pin_hash"), db.get_setting(c, "pin_salt")
    if h and not pin_ok(body.old_pin, salt, h):
        fail(401, "The current PIN is wrong.")
    salt = secrets.token_hex(8)
    with c:
        db.set_setting(c, "pin_salt", salt)
        db.set_setting(c, "pin_hash", _hash(body.pin, salt))
    return {"ok": True}


@app.post("/api/pin/check", dependencies=[Depends(parent)])
def check_pin():
    return {"ok": True}


# ----- foods -----
def food_ratings(c) -> dict:
    """How fast glucose rose in the meals each food was in (okf/domain/meal-rating.md): {food_id: {"fast": 2, "medium": 1}}."""
    out = {}
    for r in c.execute("SELECT DISTINCT i.food_id, m.id, m.rise FROM meal_items i JOIN meals m ON m.id = i.meal_id "
                       "WHERE i.food_id IS NOT NULL AND m.deleted_at IS NULL AND m.rise IS NOT NULL"):
        f = out.setdefault(r["food_id"], {})
        f[r["rise"]] = f.get(r["rise"], 0) + 1
    return out


@app.get("/api/foods")
def list_foods(c=Depends(con)):
    ratings = food_ratings(c)
    return [{**food_out(c, f), "ratings": ratings.get(f["id"])} for f in c.execute("SELECT * FROM foods ORDER BY name COLLATE NOCASE")]


# ----- each account confirms each food's carbs once (okf/features/confirm-food.md) -----
def confirm(c, food_id, email):
    if email:
        c.execute("INSERT INTO food_confirmations(food_id, email, confirmed_at) VALUES (?, ?, datetime('now','localtime')) "
                  "ON CONFLICT(food_id, email) DO UPDATE SET confirmed_at = excluded.confirmed_at", (food_id, email))


@app.get("/api/confirmations")
def my_confirmations(request: Request, c=Depends(con)):
    email = getattr(request.state, "email", None)
    return {"enabled": bool(email), "foods": [r["food_id"] for r in c.execute(
        "SELECT food_id FROM food_confirmations WHERE email = ?", (email,))] if email else []}


@app.post("/api/foods/{food_id}/confirm")
def confirm_food(food_id: str, request: Request, c=Depends(con)):
    email = getattr(request.state, "email", None)
    if not email:
        fail(400, "Sign in to confirm a food.")
    get_food(c, food_id)
    with c:
        confirm(c, food_id, email)
    return {"ok": True}


@app.post("/api/foods", dependencies=[Depends(parent)])
def create_food(body: FoodIn, request: Request, c=Depends(con)):
    if (body.label_photo or body.source_kind in ("openfoodfacts", "fatsecret")) and not body.verified:
        fail(400, "Confirm the serving size and total carbohydrate against the label before saving.")
    base = fid = slugify(body.name)
    n = 2
    while c.execute("SELECT 1 FROM foods WHERE id = ?", (fid,)).fetchone():
        fid, n = f"{base}-{n}", n + 1
    with c:
        c.execute("INSERT INTO foods(id, name, carbs_per_100g, serving_grams, serving_carbs, source_kind, source_ref, trust, "
                  "verified_at, notes, label_photo, package_photo, basis, cook_raw_g, cook_cooked_g, cook_measured_at, "
                  "serving_fiber, fiber_per_100g, fiber_checked_at, barcode) "
                  "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                  (fid, body.name.strip(), body.carbs_per_100g, body.serving_grams, body.serving_carbs, body.source_kind,
                   body.source_ref.strip(), "parent-verified" if body.verified else "draft",
                   today() if body.verified else None, body.notes.strip(), check_label_photo(body.label_photo),
                   check_label_photo(body.package_photo), body.basis, body.cook_raw_g, body.cook_cooked_g,
                   today() if body.cook_raw_g else None, body.serving_fiber, body.fiber_per_100g,
                   today() if body.verified and body.fiber_per_100g is not None else None, body.barcode or barcode_in(body.source_ref)))
        set_food_tags(c, fid, body.tags)
        confirm(c, fid, getattr(request.state, "email", None))   # whoever adds a food has checked it
    return food_out(c, get_food(c, fid))


@app.put("/api/foods/{food_id}", dependencies=[Depends(parent)])
def update_food(food_id: str, body: FoodIn, request: Request, c=Depends(con)):
    f = get_food(c, food_id)
    changed = (f["carbs_per_100g"] != body.carbs_per_100g or f["source_ref"] != body.source_ref.strip()
               or f["source_kind"] != body.source_kind)
    verified_at = (f["verified_at"] if f["trust"] == "parent-verified" and not changed else today()) if body.verified else None
    same_batch = (f["cook_raw_g"], f["cook_cooked_g"]) == (body.cook_raw_g, body.cook_cooked_g)
    measured_at = None if body.cook_raw_g is None else f["cook_measured_at"] if same_batch else today()
    same_fiber = (f["serving_fiber"], f["fiber_per_100g"]) == (body.serving_fiber, body.fiber_per_100g)
    fiber_at = None if body.fiber_per_100g is None or not body.verified else f["fiber_checked_at"] if same_fiber else today()
    with c:
        c.execute("UPDATE foods SET name=?, carbs_per_100g=?, serving_grams=?, serving_carbs=?, source_kind=?, source_ref=?, "
                  "trust=?, verified_at=?, notes=?, basis=?, cook_raw_g=?, cook_cooked_g=?, cook_measured_at=?, "
                  "serving_fiber=?, fiber_per_100g=?, fiber_checked_at=?, updated_at=datetime('now','localtime') WHERE id=?",
                  (body.name.strip(), body.carbs_per_100g, body.serving_grams, body.serving_carbs, body.source_kind,
                   body.source_ref.strip(), "parent-verified" if body.verified else "draft", verified_at,
                   body.notes.strip(), body.basis, body.cook_raw_g, body.cook_cooked_g, measured_at,
                   body.serving_fiber, body.fiber_per_100g, fiber_at, food_id))
        set_food_tags(c, food_id, body.tags)
        if body.fiber_per_100g is not None:
            fill_meal_fiber(c, food_id)
        if "barcode" in body.model_fields_set:   # a form that doesn't send it keeps the one there
            c.execute("UPDATE foods SET barcode = ? WHERE id = ?", (body.barcode, food_id))
        if f["carbs_per_100g"] != body.carbs_per_100g or not same_batch:   # the carbs-to-weight changed: everyone checks again
            email = getattr(request.state, "email", None)
            c.execute("DELETE FROM food_confirmations WHERE food_id = ? AND email IS NOT ?", (food_id, email))
            confirm(c, food_id, email)
    return food_out(c, get_food(c, food_id))


# ----- fill in fiber from each food's own source (okf/features/fill-in-fiber.md) -----
@app.get("/api/foods/{food_id}/fiber-lookup", dependencies=[Depends(parent)])
def fiber_lookup(food_id: str, c=Depends(con)):
    """The source's fiber for this food's own serving (or per 100 g). A suggestion: nothing is saved here."""
    f = get_food(c, food_id)
    src = fiber_source(f)
    if not src:
        fail(400, "This food's source can't be read again. Type the fiber on the food instead.")
    kind, ref = src
    try:
        if kind == "openfoodfacts":
            r = lookup.off_reading(lookup.off_product(ref, off_contact(c))[1])
        elif kind == "fatsecret":
            r = lookup.fs_food(ref)[0]
        elif kind == "usda":
            u = lookup.usda_food(ref)
            r = {"serving_grams": None, "fiber_g_per_serving": None, "total_carbs_g_per_serving": None,
                 "fiber_g_per_100g": u["fiber_per_100g"], "carbs_g_per_100g": u["carbs_per_100g"], "serving_size_text": None}
        else:
            r = labels.check(labels.ask_gemini(ref))["reading"]
    except (lookup.LookupError, photos.PhotoError) as e:
        fail(502, str(e))
    return fiber_suggestion(f, r)


def fiber_suggestion(f, r):
    base = f["serving_grams"] or 100                       # the amount the food's carbs are typed for
    sg, sf, sc = r.get("serving_grams"), r.get("fiber_g_per_serving"), r.get("total_carbs_g_per_serving")
    per100 = r.get("fiber_g_per_100g")
    if per100 is None and sf is not None and sg:
        per100 = sf * 100 / sg
    notes, warnings = [], []
    if sf is not None and sg and abs(sg - base) < 0.05:
        fiber = sf
        notes.append(f"{sf:g} g fiber per {sg:g} g serving")
    elif per100 is not None:
        fiber = round(per100 * base / 100, 1)
        notes.append(f"{sf:g} g fiber per {sg:g} g serving, scaled to {base:g} g" if sf is not None and sg
                     else f"{per100:.1f} g fiber per 100 g" + (f", scaled to {base:g} g" if base != 100 else ""))
    else:
        fiber = None
        warnings.append("The source lists no fiber. Type it from the package, or leave this food without fiber.")
    carbs100 = r.get("carbs_g_per_100g") or (sc * 100 / sg if sc is not None and sg else None)
    if carbs100 is not None and abs(carbs100 - f["carbs_per_100g"]) > max(0.5, f["carbs_per_100g"] * 0.05):
        warnings.append(f"The source now gives {carbs100 * base / 100:.1f} g carbs per {base:g} g; this food has "
                        f"{f['carbs_per_100g'] * base / 100:.1f} g. Only the fiber is filled in here; check the carbs on the food.")
    if fiber is not None and fiber > f["carbs_per_100g"] * base / 100:
        warnings.append("More fiber than carbs. Check both; some labels list carbs without fiber.")
    return {"fiber": fiber, "per_grams": base, "per_serving": f["serving_grams"] is not None, "notes": notes,
            "warnings": warnings, "label_photo": f["label_photo"], "serving_text": r.get("serving_size_text")}


class FiberIn(BaseModel):
    fiber: float = Field(ge=0, le=2000)   # grams of fiber for the food's own serving, or per 100 g
    confirmed: bool


@app.put("/api/foods/{food_id}/fiber", dependencies=[Depends(parent)])
def set_fiber(food_id: str, body: FiberIn, c=Depends(con)):
    """Fiber only: carbs, portions and the log are left as they are (okf/features/fill-in-fiber.md)."""
    f = get_food(c, food_id)
    if not body.confirmed:
        fail(400, "Confirm the fiber against the label or source first.")
    base = f["serving_grams"] or 100
    if body.fiber > base:
        fail(422, f"Fiber can't be more than {base:g} g of food.")
    with c:
        c.execute("UPDATE foods SET serving_fiber=?, fiber_per_100g=?, fiber_checked_at=?, updated_at=datetime('now','localtime') "
                  "WHERE id=?", (body.fiber if f["serving_grams"] else None, round(body.fiber * 100 / base, 2), today(), food_id))
        fill_meal_fiber(c, food_id)
    return food_out(c, get_food(c, food_id))


@app.delete("/api/foods/{food_id}", dependencies=[Depends(parent)])
def delete_food(food_id: str, c=Depends(con)):
    get_food(c, food_id)
    with c:  # logged meals keep their snapshot; only the link is lost
        c.execute("UPDATE meal_items SET food_id = NULL WHERE food_id = ?", (food_id,))
        c.execute("DELETE FROM foods WHERE id = ?", (food_id,))
    return {"ok": True}


@app.post("/api/foods/{food_id}/portions", dependencies=[Depends(parent)])
def add_portion(food_id: str, body: PortionIn, c=Depends(con)):
    get_food(c, food_id)
    with c:
        c.execute("INSERT INTO portions(food_id, label, grams, sort, container, size_ref_id, photo_note) VALUES (?, ?, ?, ?, ?, ?, ?)",
                  (food_id, body.label.strip(), body.grams, body.sort, body.container, check_size_ref(c, body.size_ref_id),
                   (body.photo_note or "").strip()))
    return food_out(c, get_food(c, food_id))


@app.put("/api/portions/{pid}", dependencies=[Depends(parent)])
def update_portion(pid: int, body: PortionIn, c=Depends(con)):
    p = get_portion(c, pid)
    with c:
        note = p["photo_note"] if body.photo_note is None else body.photo_note.strip()
        c.execute("UPDATE portions SET label=?, grams=?, sort=?, container=?, size_ref_id=?, photo_note=? WHERE id=?",
                  (body.label.strip(), body.grams, body.sort, body.container, check_size_ref(c, body.size_ref_id), note, pid))
    return food_out(c, get_food(c, p["food_id"]))


@app.delete("/api/portions/{pid}", dependencies=[Depends(parent)])
def delete_portion(pid: int, c=Depends(con)):
    p = get_portion(c, pid)
    with c:
        c.execute("DELETE FROM portions WHERE id = ?", (pid,))
    return food_out(c, get_food(c, p["food_id"]))


# ----- tags (okf/domain/tag.md) -----
def list_tags_rows(c):
    return [{"id": r["id"], "name": r["name"], "sort": r["sort"],
             "foods": c.execute("SELECT COUNT(*) AS n FROM food_tags WHERE tag_id = ?", (r["id"],)).fetchone()["n"]}
            for r in c.execute("SELECT * FROM tags ORDER BY sort, name COLLATE NOCASE")]


@app.get("/api/tags")
def list_tags(c=Depends(con)):
    return list_tags_rows(c)


@app.post("/api/tags", dependencies=[Depends(parent)])
def add_tag(body: TagIn, c=Depends(con)):
    if c.execute("SELECT 1 FROM tags WHERE name = ?", (body.name.strip(),)).fetchone():
        fail(409, "That tag already exists.")
    if body.name.strip().lower() in ("favorites", "favourites", "all"):
        fail(400, "That name is used by the food list already.")
    with c:
        top = c.execute("SELECT COALESCE(MAX(sort), 0) + 1 AS n FROM tags").fetchone()["n"]
        c.execute("INSERT INTO tags(name, sort) VALUES (?, ?)", (body.name.strip(), top))
    return list_tags_rows(c)


@app.put("/api/tags/{tid}", dependencies=[Depends(parent)])
def rename_tag(tid: int, body: TagIn, c=Depends(con)):
    clash = c.execute("SELECT id FROM tags WHERE name = ?", (body.name.strip(),)).fetchone()
    if clash and clash["id"] != tid:
        fail(409, "That tag already exists.")
    with c:
        c.execute("UPDATE tags SET name = ? WHERE id = ?", (body.name.strip(), tid))
    return list_tags_rows(c)


@app.delete("/api/tags/{tid}", dependencies=[Depends(parent)])
def delete_tag(tid: int, c=Depends(con)):
    with c:  # foods keep their other tags
        c.execute("DELETE FROM tags WHERE id = ?", (tid,))
    return list_tags_rows(c)


# ----- planned meals (okf/features/plan-meal.md, okf/domain/planned-meal.md) -----
PLAN_DAYS = 60


class PlanItem(BaseModel):
    """A plate row as the plate keeps it: a weighed food, or carbs typed by hand."""
    food_id: str | None = Field(default=None, max_length=80)
    portion_id: int | None = None
    food_name: str = Field(min_length=1, max_length=80)
    portion_label: str = Field(default="", max_length=60)
    grams: float | None = Field(default=None, gt=0, le=2000)
    carbs_per_100g: float | None = Field(default=None, ge=0, le=100)
    qty: float = Field(default=1, gt=0, le=10)
    entered: float | None = Field(default=None, ge=0.5, le=300)
    base: float | None = Field(default=None, gt=0, le=2000)
    basis: str | None = Field(default=None, max_length=20)
    state: str | None = Field(default=None, max_length=20)
    cp_basis: float | None = Field(default=None, ge=0, le=100)
    ratio: float | None = Field(default=None, gt=0, le=20)
    ratio_day: str | None = Field(default=None, max_length=40)
    locked: bool = False

    @model_validator(mode="after")
    def weighed_or_typed(self):
        if self.entered is None and (self.food_id is None or self.portion_id is None or self.grams is None or self.carbs_per_100g is None):
            raise ValueError("Each planned food needs its weight, or its carbs typed by hand.")
        return self


class PlanWhen(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    day: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    time: str = Field(pattern=TIME_RE)


class PlanIn(PlanWhen):
    client_id: str = Field(min_length=8, max_length=64)
    items: list[PlanItem] = Field(min_length=1, max_length=30)


class PlanUpdate(PlanWhen):
    items: list[PlanItem] | None = Field(default=None, min_length=1, max_length=30)   # None: only the name, date and time


def plan_out(p) -> dict:
    items = json.loads(p["items"])
    return {"id": p["id"], "client_id": p["client_id"], "name": p["name"], "day": p["day"], "time": p["time"], "items": items,
            "carbs": core.whole_grams(core.plan_carbs(items)), "foods": ", ".join(i["food_name"] for i in items)}


def check_plan_day(day: str):
    try:
        d = date.fromisoformat(day)
    except ValueError:
        fail(400, "Use a date like 2026-10-27.")
    if day < today():
        fail(400, "A plan is for today or later.")
    if d > now().date() + timedelta(days=PLAN_DAYS):
        fail(400, f"A plan can be up to {PLAN_DAYS} days ahead.")


def get_plan(c, pid):
    p = c.execute("SELECT * FROM planned_meals WHERE id = ?", (pid,)).fetchone()
    if not p:
        fail(404, "That plan is no longer there. It may have been eaten or deleted on another device.")
    return p


@app.get("/api/plans")
def list_plans(c=Depends(con)):
    """Every plan, earliest first; ones whose day has passed are overdue until eaten or deleted."""
    return [plan_out(p) for p in c.execute("SELECT * FROM planned_meals ORDER BY day, time, id")]


@app.post("/api/plans")
def create_plan(body: PlanIn, c=Depends(con)):
    check_plan_day(body.day)
    existing = c.execute("SELECT * FROM planned_meals WHERE client_id = ?", (body.client_id,)).fetchone()
    if existing:   # sent twice: kept once
        return plan_out(existing)
    stamp = now().strftime("%Y-%m-%d %H:%M")
    with c:
        pid = c.execute("INSERT INTO planned_meals(client_id, name, day, time, items, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (body.client_id, body.name.strip(), body.day, body.time,
                         json.dumps([i.model_dump() for i in body.items]), stamp, stamp)).lastrowid
    return plan_out(get_plan(c, pid))


@app.put("/api/plans/{pid}")
def update_plan(pid: int, body: PlanUpdate, c=Depends(con)):
    p = get_plan(c, pid)
    if body.day != p["day"]:   # an overdue plan can keep its day, but not move into the past
        check_plan_day(body.day)
    items = json.dumps([i.model_dump() for i in body.items]) if body.items is not None else p["items"]
    with c:
        c.execute("UPDATE planned_meals SET name = ?, day = ?, time = ?, items = ?, updated_at = ? WHERE id = ?",
                  (body.name.strip(), body.day, body.time, items, now().strftime("%Y-%m-%d %H:%M"), pid))
    return plan_out(get_plan(c, pid))


@app.delete("/api/plans/{pid}")
def delete_plan(pid: int, c=Depends(con)):
    get_plan(c, pid)
    with c:
        c.execute("DELETE FROM planned_meals WHERE id = ?", (pid,))
    return {"ok": True}


# ----- favorite plates (okf/features/favorite-plates.md) -----
def favorite_out(c, fav):
    items, exact_sum = [], 0.0
    for i in c.execute("SELECT * FROM favorite_items WHERE favorite_id = ? ORDER BY id", (fav["id"],)):
        row = i["portion_id"] and c.execute(
            "SELECT p.*, f.name AS food_name, f.carbs_per_100g, f.trust FROM portions p JOIN foods f ON f.id = p.food_id "
            "WHERE p.id = ?", (i["portion_id"],)).fetchone()
        if not row:  # okf/rules/favorites-use-current-values.md: shown as missing, never dropped silently
            items.append({"missing": True, "food_name": i["food_name"], "portion_label": i["portion_label"], "qty": i["qty"]})
            continue
        e = core.carbs_exact(row["grams"], row["carbs_per_100g"], i["qty"])
        exact_sum += e
        items.append({"missing": False, "portion_id": row["id"], "food_id": row["food_id"], "food_name": row["food_name"],
                      "portion_label": row["label"], "grams": row["grams"], "carbs_per_100g": row["carbs_per_100g"],
                      "qty": i["qty"], "carbs": core.whole_grams(e), "trust": row["trust"],
                      "photo": row["photo_styled"] or row["photo_original"]})
    return {"id": fav["id"], "name": fav["name"], "sort": fav["sort"], "items": items,
            "total": core.whole_grams(exact_sum), "missing": sum(i["missing"] for i in items),
            "photo": fav["photo"], "photo_candidate": fav["photo_candidate"]}


@app.get("/api/favorites")
def list_favorites(c=Depends(con)):
    return [favorite_out(c, f) for f in c.execute("SELECT * FROM favorites ORDER BY sort, id")]


@app.post("/api/favorites")
def add_favorite(body: FavoriteIn, c=Depends(con)):
    rows = []
    for it in body.items:
        p = c.execute("SELECT p.label, f.name FROM portions p JOIN foods f ON f.id = p.food_id WHERE p.id = ?",
                      (it.portion_id,)).fetchone()
        if not p:
            fail(400, "One of the foods on this plate no longer exists, so it can't be pinned.")
        rows.append((it.portion_id, p["name"], p["label"], it.qty))
    with c:
        top = c.execute("SELECT COALESCE(MAX(sort), 0) + 1 AS n FROM favorites").fetchone()["n"]
        fid = c.execute("INSERT INTO favorites(name, sort) VALUES (?, ?)", (body.name.strip(), top)).lastrowid
        c.executemany("INSERT INTO favorite_items(favorite_id, portion_id, food_name, portion_label, qty) VALUES (?, ?, ?, ?, ?)",
                      [(fid, *r) for r in rows])
    return favorite_out(c, c.execute("SELECT * FROM favorites WHERE id = ?", (fid,)).fetchone())


@app.post("/api/meals/{mid}/favorite")
def favorite_from_meal(mid: int, body: FavoriteRename, c=Depends(con)):
    get_meal(c, mid)
    items = []
    for i in c.execute("SELECT * FROM meal_items WHERE meal_id = ? AND entered_carbs IS NULL ORDER BY id", (mid,)).fetchall():
        pid = i["portion_id"]
        if not pid or not c.execute("SELECT 1 FROM portions WHERE id = ?", (pid,)).fetchone():
            # meals logged before portion ids were kept: match the same food and portion name
            row = c.execute("SELECT id FROM portions WHERE food_id = ? AND label = ?", (i["food_id"], i["portion_label"])).fetchone()
            pid = row and row["id"]
        if not pid:
            fail(400, f"{i['food_name']}, {i['portion_label']} is no longer in the food list, so this meal can't be pinned.")
        items.append(FavItemIn(portion_id=pid, qty=i["qty"]))
    if not items:
        fail(400, "This meal only has carbs entered by hand, so there's nothing to pin.")
    return add_favorite(FavoriteIn(name=body.name, items=items), c)


@app.put("/api/favorites/{fid}")
def rename_favorite(fid: int, body: FavoriteRename, c=Depends(con)):
    with c:
        if not c.execute("UPDATE favorites SET name = ? WHERE id = ?", (body.name.strip(), fid)).rowcount:
            fail(404, "That favorite no longer exists.")
    return {"ok": True}


def get_favorite(c, fid):
    fav = c.execute("SELECT * FROM favorites WHERE id = ?", (fid,)).fetchone()
    if not fav:
        fail(404, "That favorite no longer exists.")
    return fav


@app.post("/api/favorites/{fid}/photo", dependencies=[Depends(parent)])
def favorite_photo(fid: int, c=Depends(con)):
    """Gemini combines the foods' photos into one plate photo, kept as a candidate until checked
    (okf/features/favorite-plates.md). The parent waits on the check screen, so this runs in the request."""
    fav = favorite_out(c, get_favorite(c, fid))
    foods = [{"food": i["food_name"], "label": i["portion_label"], "photo_grams": i["grams"],
              "grams": round(i["grams"] * i["qty"], 1), "photo": i["photo"]} for i in fav["items"] if not i["missing"]]
    if not foods:
        fail(400, "This favorite has no foods left to photograph.")
    style, _ = style_settings(c)
    prompt, refs = photos.build_plate_prompt(style, foods)
    try:
        path = photos.generate(refs, prompt, db.get_setting(c, "photo_quality") or "fast")
    except photos.PhotoError as e:
        fail(502, str(e))
    with c:
        c.execute("UPDATE favorites SET photo_candidate = ? WHERE id = ?", (path, fid))
    return favorite_out(c, get_favorite(c, fid))


@app.post("/api/favorites/{fid}/photo/review", dependencies=[Depends(parent)])
def review_favorite_photo(fid: int, body: FavPhotoReview, c=Depends(con)):
    fav = get_favorite(c, fid)
    with c:
        if body.action == "accept":
            if not fav["photo_candidate"]:
                fail(400, "There is no new photo to use.")
            c.execute("UPDATE favorites SET photo = photo_candidate, photo_candidate = NULL WHERE id = ?", (fid,))
        elif body.action == "discard":
            c.execute("UPDATE favorites SET photo_candidate = NULL WHERE id = ?", (fid,))
        else:   # back to the first food's photo
            c.execute("UPDATE favorites SET photo = NULL WHERE id = ?", (fid,))
    return favorite_out(c, get_favorite(c, fid))


def missing_item_ids(c, fid):   # items whose portion (or its food) is gone
    return [r["id"] for r in c.execute(
        "SELECT i.id FROM favorite_items i LEFT JOIN portions p ON p.id = i.portion_id "
        "WHERE i.favorite_id = ? AND p.id IS NULL", (fid,))]


@app.post("/api/favorites/remove-orphans")
def remove_orphan_favorites(c=Depends(con)):
    """Favorites with no foods left, removed on a parent's tap (okf/domain/favorite-plate.md)."""
    gone = [f["id"] for f in c.execute("SELECT id FROM favorites")
            if len(missing_item_ids(c, f["id"])) == c.execute("SELECT COUNT(*) FROM favorite_items WHERE favorite_id = ?",
                                                                (f["id"],)).fetchone()[0]]
    with c:
        c.executemany("DELETE FROM favorites WHERE id = ?", [(i,) for i in gone])
    return {"removed": len(gone)}


@app.post("/api/favorites/{fid}/drop-missing")
def drop_missing_items(fid: int, c=Depends(con)):
    if not c.execute("SELECT 1 FROM favorites WHERE id = ?", (fid,)).fetchone():
        fail(404, "That favorite no longer exists.")
    ids = missing_item_ids(c, fid)
    with c:
        c.executemany("DELETE FROM favorite_items WHERE id = ?", [(i,) for i in ids])
        if ids:   # the plate photo shows foods that are gone (okf/features/favorite-plates.md)
            c.execute("UPDATE favorites SET photo = NULL, photo_candidate = NULL WHERE id = ?", (fid,))
        left = c.execute("SELECT COUNT(*) FROM favorite_items WHERE favorite_id = ?", (fid,)).fetchone()[0]
        if not left:
            c.execute("DELETE FROM favorites WHERE id = ?", (fid,))
    return {"removed_items": len(ids), "deleted": not left}


@app.delete("/api/favorites/{fid}")
def delete_favorite(fid: int, c=Depends(con)):
    with c:
        c.execute("DELETE FROM favorites WHERE id = ?", (fid,))
    return {"ok": True}


# ----- photo style (okf/features/photo-style-setup.md) -----
@app.get("/api/style", dependencies=[Depends(parent)])
def get_style(c=Depends(con)):
    style, bases = style_settings(c)
    return {"prompt": style, "default_prompt": photos.DEFAULT_STYLE, "guard": photos.GUARD,
            "quality": db.get_setting(c, "photo_quality") or "fast",
            "bases": {k: bases.get(k) for k in photos.CONTAINERS}, "size_refs": size_refs(c)}


@app.get("/api/size-refs")
def list_size_refs(c=Depends(con)):
    return size_refs(c)


@app.post("/api/size-refs", dependencies=[Depends(parent)])
async def add_size_ref(name: str = Form(...), measurement: str = Form(...), container: str = Form(""),
                       file: UploadFile = File(...), c=Depends(con)):
    try:
        body = SizeRefIn(name=name, measurement=measurement, container=container or None)
    except ValueError:
        fail(422, "Choose plate, bowl, dressing container or any dish.")
    try:
        path = photos.save_jpeg(await file.read(), "base")
    except photos.PhotoError as e:
        fail(400, str(e))
    with c:
        top = c.execute("SELECT COALESCE(MAX(sort), 0) + 1 AS n FROM size_refs").fetchone()["n"]
        c.execute("INSERT INTO size_refs(name, measurement, photo, container, sort) VALUES (?, ?, ?, ?, ?)",
                  (body.name.strip(), body.measurement.strip(), path, body.container, top))
    return get_style(c)


@app.put("/api/size-refs/{rid}", dependencies=[Depends(parent)])
def edit_size_ref(rid: int, body: SizeRefIn, c=Depends(con)):
    check_size_ref(c, rid)
    with c:
        c.execute("UPDATE size_refs SET name = ?, measurement = ?, container = ? WHERE id = ?",
                  (body.name.strip(), body.measurement.strip(), body.container, rid))
    return get_style(c)


@app.delete("/api/size-refs/{rid}", dependencies=[Depends(parent)])
def delete_size_ref(rid: int, c=Depends(con)):
    with c:   # portions using it go back to no size reference
        c.execute("UPDATE portions SET size_ref_id = NULL WHERE size_ref_id = ?", (rid,))
        c.execute("DELETE FROM size_refs WHERE id = ?", (rid,))
    return get_style(c)


@app.put("/api/style", dependencies=[Depends(parent)])
def set_style(body: StyleIn, c=Depends(con)):
    with c:
        db.set_setting(c, "style_prompt", body.prompt.strip() or None)
    return get_style(c)


@app.put("/api/style/quality", dependencies=[Depends(parent)])
def set_quality(body: QualityIn, c=Depends(con)):   # okf/domain/photo-style.md: fast or sharp
    with c:
        db.set_setting(c, "photo_quality", body.quality)
    return get_style(c)


@app.post("/api/style/base/{kind}", dependencies=[Depends(parent)])
async def set_base(kind: Literal["plate", "bowl", "dressing"], file: UploadFile = File(...), c=Depends(con)):
    data = await file.read()
    if len(data) > 25 * 1024 * 1024:
        fail(413, "That photo is over 25 MB.")
    try:
        path = photos.save_jpeg(data, "base")
    except photos.PhotoError as e:
        fail(400, str(e))
    with c:
        db.set_setting(c, f"style_base_{kind}", path)
    return get_style(c)


@app.delete("/api/style/base/{kind}", dependencies=[Depends(parent)])
def clear_base(kind: Literal["plate", "bowl", "dressing"], c=Depends(con)):
    with c:
        db.set_setting(c, f"style_base_{kind}", None)
    return get_style(c)


# ----- food lookup (okf/features/food-lookup.md) -----
class SettingsIn(BaseModel):
    off_contact: str = Field(pattern=r"^[^\s()]+@[^\s()]+\.[^\s()]+$", max_length=120)


def default_contact(c):   # KC_OFF_CONTACT, else the first allowed account (okf/architecture/nutrition-apis.md)
    return lookup.DEFAULT_CONTACT or next(iter(auth.allowed(c)), "")


def off_contact(c):
    return db.get_setting(c, "off_contact") or default_contact(c)


def off_country(c):   # "" = all countries
    v = db.get_setting(c, "off_country")
    return lookup.DEFAULT_COUNTRY if v is None or v not in lookup.COUNTRIES else v


class CountryIn(BaseModel):
    country: str = Field(max_length=40)


@app.get("/api/settings", dependencies=[Depends(parent)])
def get_settings(c=Depends(con)):
    return {"off_contact": off_contact(c), "off_contact_default": default_contact(c),
            "off_country": off_country(c), "countries": lookup.COUNTRIES,
            "fatsecret": "set up" if lookup.fatsecret_ready() else "not set up", "past_edits": past_edits(c),
            "clock_12h": clock_12h(c)}


@app.put("/api/settings", dependencies=[Depends(parent)])
def put_settings(body: SettingsIn, c=Depends(con)):
    with c:
        db.set_setting(c, "off_contact", body.off_contact.strip())
    return get_settings(c)


class PastEditsIn(BaseModel):
    allowed: bool


@app.put("/api/settings/past-edits", dependencies=[Depends(parent)])
def set_past_edits(body: PastEditsIn, c=Depends(con)):
    """okf/rules/same-day-edits.md"""
    with c:
        db.set_setting(c, "past_edits", "on" if body.allowed else "off")
    return get_settings(c)


class ClockIn(BaseModel):
    h12: bool


@app.put("/api/settings/clock", dependencies=[Depends(parent)])
def set_clock(body: ClockIn, c=Depends(con)):
    """okf/features/review-log.md"""
    with c:
        db.set_setting(c, "clock", "12h" if body.h12 else "24h")
    return get_settings(c)


@app.put("/api/settings/country", dependencies=[Depends(parent)])
def set_country(body: CountryIn, c=Depends(con)):
    if body.country not in lookup.COUNTRIES:
        fail(422, "Choose a country from the list.")
    with c:
        db.set_setting(c, "off_country", body.country)
    return get_settings(c)


@app.get("/api/lookup/search", dependencies=[Depends(parent)])
def lookup_search(q: str, everywhere: bool = False, c=Depends(con)):
    q = q.strip()
    country = "" if everywhere else off_country(c)
    if len(q) < 2:
        return {"fatsecret": [], "off": [], "errors": [], "country": country}
    contact = off_contact(c)
    with ThreadPoolExecutor(2) as ex:   # both sources at once; one failing doesn't hide the other
        jobs = {"fatsecret": ex.submit(lookup.fs_search, q),
                "off": ex.submit(lookup.off_search, q, contact, 12, country)}
    out, errors = {}, []
    for k, job in jobs.items():
        try:
            out[k] = job.result()
        except lookup.LookupError as e:
            out[k] = []
            errors.append(str(e))
    return {**out, "errors": errors, "country": country, "country_name": lookup.COUNTRIES[country]}


@app.get("/api/lookup/fatsecret/{food_id}", dependencies=[Depends(parent)])
def lookup_fatsecret(food_id: str):
    """Same check screen as a packaged food: serving grams and carbs, each confirmed (okf/features/food-lookup.md)."""
    try:
        reading, others = lookup.fs_food(food_id)
    except lookup.LookupError as e:
        fail(404 if "no food" in str(e) else 400 if "number" in str(e) else 502, str(e))
    return {"mode": "serving", "source": "fatsecret", "code": None, "label_photo": None, "package_photo": None,
            "product_image": None, "source_ref": f"FatSecret food {food_id}", "other_servings": others,
            **labels.check(reading)}


@app.get("/api/lookup/usda/{fdc_id}", dependencies=[Depends(parent)])
def lookup_usda(fdc_id: str):
    try:
        f = lookup.usda_food(fdc_id)
    except lookup.LookupError as e:
        fail(502, str(e))
    return {"mode": "per100", **f}


@app.get("/api/lookup/off/{code}", dependencies=[Depends(parent)])
def lookup_off(code: str, check: bool = False, c=Depends(con)):
    contact = off_contact(c)
    try:
        code, product = lookup.off_product(code, contact)
    except lookup.LookupError as e:
        fail(404 if "doesn't have" in str(e) else 400 if "digits" in str(e) else 502, str(e))
    if check:   # only comparing a new barcode with a food (okf/features/manage-foods.md): no photos kept
        return {"code": code, **labels.check(lookup.off_reading(product))}
    label_photo = None
    img = lookup.fetch_image(product.get("image_nutrition_url"), contact)
    if img:
        try:   # keep Open Food Facts' photo of the nutrition panel as the evidence (okf/domain/nutrition-label.md)
            label_photo = photos.save_jpeg(img, "labels")
        except photos.PhotoError:
            pass
    front = product.get("image_front_url")
    package_photo = None
    pimg = lookup.fetch_image(front, contact)
    if pimg:
        try:   # helps Gemini draw the right food later (okf/domain/photo-style.md)
            package_photo = photos.save_jpeg(pimg, "labels")
        except photos.PhotoError:
            pass
    return {"mode": "serving", "code": code, "label_photo": label_photo, "package_photo": package_photo,
            "product_image": front if front and front.startswith("https://images.openfoodfacts.org/") else None,
            "source_ref": f"Open Food Facts, barcode {code}", **labels.check(lookup.off_reading(product))}


@app.post("/api/lookup/barcode", dependencies=[Depends(parent)])
async def lookup_barcode(file: UploadFile = File(...)):
    try:
        return {"code": lookup.read_barcode(await file.read())}
    except lookup.LookupError as e:
        fail(400, str(e))


# ----- nutrition labels (okf/features/scan-label.md) -----
@app.post("/api/labels/read", dependencies=[Depends(parent)])
async def read_label(file: UploadFile = File(...)):
    data = await file.read()
    if len(data) > 25 * 1024 * 1024:
        fail(413, "That photo is over 25 MB.")
    try:
        path = photos.save_jpeg(data, "labels")
    except photos.PhotoError as e:
        fail(400, str(e))
    try:
        raw = labels.ask_gemini(path)
    except photos.PhotoError as e:
        fail(502, str(e))
    return {"label_photo": path, **labels.check(raw)}


# ----- photos -----
@app.post("/api/portions/{pid}/original", dependencies=[Depends(parent)])
async def upload_original(pid: int, file: UploadFile = File(...), c=Depends(con)):
    p = get_portion(c, pid)
    data = await file.read()
    if len(data) > 25 * 1024 * 1024:
        fail(413, "That photo is over 25 MB.")
    try:
        path = photos.save_jpeg(data, "original")
    except photos.PhotoError as e:
        fail(400, str(e))
    with c:
        # A real photo replaces an estimated stand-in (okf/rules/estimated-photo-label.md).
        if p["photo_estimated"]:
            c.execute("UPDATE portions SET photo_styled = NULL, photo_estimated = 0 WHERE id = ?", (pid,))
        c.execute("UPDATE portions SET photo_original = ?, photo_job_error = NULL WHERE id = ?", (path, pid))
    return food_out(c, get_food(c, p["food_id"]))


def check_size_ref(c, rid):
    if rid is not None and not c.execute("SELECT 1 FROM size_refs WHERE id = ?", (rid,)).fetchone():
        fail(400, "That size reference no longer exists.")
    return rid


def size_refs(c):
    return [dict(r) for r in c.execute("SELECT id, name, measurement, photo, container, sort FROM size_refs ORDER BY sort, id")]


def style_settings(c):
    bases = {k: db.get_setting(c, f"style_base_{k}") for k in photos.CONTAINERS}
    return db.get_setting(c, "style_prompt") or photos.DEFAULT_STYLE, {k: v for k, v in bases.items() if v}


RUN_JOBS_IN_BACKGROUND = True   # tests run them inline


ESTIMATE, GENERATED = 1, 2   # candidate_estimated: 0 = your photo styled, 1 = from another portion, 2 = from the name alone


def _generate(c, pid, ref_path, container, estimated, estimate=None, describe=None, guess=False, queued=False):
    """Start a Gemini job for a portion; it runs in the background and the Manage screen polls for it.

    With guess, the dish is picked first (okf/domain/photo-style.md), also in the background.
    With queued, the portion is claimed with no start time ('Waiting its turn') and the job is returned for a queue to run.
    """
    with c:   # claim the portion; a second press while one runs is refused
        claimed = c.execute("UPDATE portions SET photo_job = ?, photo_job_started = ?, photo_job_error = NULL "
                            "WHERE id = ? AND photo_job IS NULL",
                            (("style", "estimate", "generate")[estimated], None if queued else now().isoformat(timespec="seconds"), pid)).rowcount
    if not claimed:
        fail(409, "A photo for this portion is already being made.")

    def job():
        jc = db.connect()
        try:
            if queued:
                with jc:
                    jc.execute("UPDATE portions SET photo_job_started = ? WHERE id = ?", (now().isoformat(timespec="seconds"), pid))
            p = jc.execute("SELECT * FROM portions WHERE id = ?", (pid,)).fetchone()
            f = jc.execute("SELECT * FROM foods WHERE id = ?", (p["food_id"],)).fetchone()
            dish = container
            if guess:
                serving = f"{p['label']}, {p['grams']:g} g"
                try:
                    dish = labels.guess_container(f["name"], serving, f["package_photo"])
                except photos.PhotoError:
                    dish = "plate"
                with jc:   # saved on the portion so the parent sees the guess and can change it
                    jc.execute("UPDATE portions SET container = ? WHERE id = ?", (dish, pid))
            sref = p["size_ref_id"] and jc.execute("SELECT * FROM size_refs WHERE id = ?", (p["size_ref_id"],)).fetchone()
            style, bases = style_settings(jc)
            quality = db.get_setting(jc, "photo_quality") or "fast"
            prompt, refs = photos.build_prompt(style, bases, dish, estimate, dict(sref) if sref else None,
                                               {"label": p["label"], "grams": p["grams"]}, describe, p["photo_note"],
                                               f["package_photo"])
            path = photos.generate([ref_path, *refs] if ref_path else refs, prompt, quality)
            with jc:
                jc.execute("UPDATE portions SET photo_candidate = ?, candidate_estimated = ?, photo_job = NULL WHERE id = ?",
                           (path, estimated, pid))
        except Exception as e:   # shown in the portion's row
            msg = str(e) if isinstance(e, photos.PhotoError) else "Something went wrong making the photo."
            with jc:
                jc.execute("UPDATE portions SET photo_job = NULL, photo_job_error = ? WHERE id = ?", (msg, pid))
        finally:
            jc.close()

    if queued:
        return job
    if RUN_JOBS_IN_BACKGROUND:
        threading.Thread(target=job, name=f"photo-{pid}", daemon=True).start()
    else:
        job()


@app.post("/api/portions/{pid}/style", dependencies=[Depends(parent)])
def style_photo(pid: int, c=Depends(con)):
    p = get_portion(c, pid)
    if not p["photo_original"]:
        fail(400, "Upload your photo of this portion first.")
    _generate(c, pid, p["photo_original"], p["container"], 0)
    return food_out(c, get_food(c, p["food_id"]))


@app.post("/api/portions/{pid}/estimate", dependencies=[Depends(parent)])
def estimate_photo(pid: int, body: EstimateIn, c=Depends(con)):
    p, ref = get_portion(c, pid), get_portion(c, body.from_portion_id)
    if p["photo_original"]:
        fail(400, "This portion already has your photo. Use 'Style with Gemini' instead.")
    ref_photo = ref["photo_styled"] or ref["photo_original"]   # the approved look first (okf/features/photo-pipeline.md)
    if ref["food_id"] != p["food_id"] or not ref_photo:
        fail(400, "Pick another portion of the same food that has a photo.")
    f = get_food(c, p["food_id"])
    _generate(c, pid, ref_photo, p["container"], ESTIMATE,
              {"ref_grams": ref["grams"], "food": f["name"], "grams": p["grams"], "label": p["label"]})
    return food_out(c, f)


@app.post("/api/portions/{pid}/generate", dependencies=[Depends(parent)])
def generate_photo(pid: int, c=Depends(con)):
    """No photo to start from: Gemini draws the portion from its name and grams (okf/features/photo-pipeline.md)."""
    p = get_portion(c, pid)
    if p["photo_original"]:
        fail(400, "This portion already has your photo. Use 'Style with Gemini' instead.")
    f = get_food(c, p["food_id"])
    _generate(c, pid, None, p["container"], GENERATED, describe={"food": f["name"], "grams": p["grams"], "label": p["label"]},
              guess=p["container"] == "auto")
    return food_out(c, f)


@app.post("/api/photos/generate-missing", dependencies=[Depends(parent)])
def generate_missing_photos(c=Depends(con)):
    """Every portion with no photo at all, one at a time: estimated from a sibling's photo, else from the name (okf/features/photo-pipeline.md)."""
    missing = c.execute("SELECT p.* FROM portions p JOIN foods f ON f.id = p.food_id WHERE p.photo_original IS NULL AND p.photo_styled IS NULL "
                        "AND p.photo_candidate IS NULL AND p.photo_job IS NULL ORDER BY f.name COLLATE NOCASE, p.sort, p.id").fetchall()
    jobs = []
    for p in missing:
        f = get_food(c, p["food_id"])
        ref = c.execute("SELECT * FROM portions WHERE food_id = ? AND id != ? AND (photo_styled IS NOT NULL OR photo_original IS NOT NULL) "
                        "ORDER BY photo_styled IS NULL, grams = ? DESC, sort", (p["food_id"], p["id"], f["serving_grams"])).fetchone()
        what = {"food": f["name"], "grams": p["grams"], "label": p["label"]}
        if ref:
            jobs.append(_generate(c, p["id"], ref["photo_styled"] or ref["photo_original"], p["container"], ESTIMATE,
                                  {**what, "ref_grams": ref["grams"]}, queued=True))
        else:
            jobs.append(_generate(c, p["id"], None, p["container"], GENERATED, describe=what, guess=p["container"] == "auto", queued=True))

    def run_all():   # one at a time, so Gemini isn't asked for twenty photos at once
        for job in jobs:
            job()

    if RUN_JOBS_IN_BACKGROUND:
        threading.Thread(target=run_all, name="photos-missing", daemon=True).start()
    else:
        run_all()
    return {"queued": len(jobs)}


@app.post("/api/portions/{pid}/review", dependencies=[Depends(parent)])
def review_photo(pid: int, body: ReviewIn, c=Depends(con)):
    p = get_portion(c, pid)
    with c:
        if body.action == "accept":
            if not p["photo_candidate"]:
                fail(400, "There is no new photo to accept.")
            c.execute("UPDATE portions SET photo_styled = photo_candidate, photo_estimated = MIN(candidate_estimated, 1), "
                      "photo_candidate = NULL, candidate_estimated = 0 WHERE id = ?", (pid,))
        elif body.action == "discard":
            c.execute("UPDATE portions SET photo_candidate = NULL, candidate_estimated = 0, photo_job_error = NULL WHERE id = ?", (pid,))
        else:
            if not p["photo_original"]:
                fail(400, "There is no photo of yours for this portion yet.")
            c.execute("UPDATE portions SET photo_styled = NULL, photo_estimated = 0, photo_candidate = NULL, "
                      "candidate_estimated = 0 WHERE id = ?", (pid,))
    return food_out(c, get_food(c, p["food_id"]))


# ----- meals -----
@app.post("/api/meals")
def create_meal(body: MealIn, c=Depends(con), x_kc_push: str = Header(default="")):
    if body.day > today():
        fail(400, "A meal can't be logged for a future day.")
    existing = c.execute("SELECT id FROM meals WHERE client_id = ?", (body.client_id,)).fetchone()
    if existing:  # a queued meal sent twice is saved once
        return {"id": existing["id"], "duplicate": True}
    with c:
        mid = c.execute(f"INSERT INTO meals(client_id, day, time, edited_at, {', '.join(DETAILS)}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (body.client_id, body.day, body.time,   # added to an earlier day: marked (okf/rules/same-day-edits.md)
                         now().strftime("%Y-%m-%d %H:%M") if body.day < today() else None,
                         *(getattr(body, k) for k in DETAILS))).lastrowid
        for i in body.items:
            c.execute("INSERT INTO meal_items(meal_id, food_id, portion_id, food_name, portion_label, grams, carbs_per_100g, qty, carbs_exact, entered_carbs, fiber_per_100g) "
                      "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                      (mid, i.food_id, i.portion_id, i.food_name.strip(), i.portion_label, i.grams, i.carbs_per_100g, i.qty,
                       i.entered_carbs if i.entered_carbs is not None else core.carbs_exact(i.grams, i.carbs_per_100g, i.qty), i.entered_carbs,
                       item_fiber(c, i)))
        if body.plan_id is not None:
            c.execute("DELETE FROM planned_meals WHERE id = ?", (body.plan_id,))
    notify(lambda: meal_notice(c, mid), x_kc_push)
    return {"id": mid, "duplicate": False}


@app.patch("/api/meals/{mid}")
def patch_meal(mid: int, body: MealPatch, c=Depends(con)):
    m = get_meal(c, mid)
    require_editable(c, m)
    with c:
        mark_later(c, "meals", m)
        if body.eaten is not None:
            c.execute("UPDATE meals SET eaten = ? WHERE id = ?", (body.eaten or None, mid))
        if body.time:
            c.execute("UPDATE meals SET time = ? WHERE id = ?", (body.time, mid))
    return {"ok": True}


@app.put("/api/meals/{mid}/details")
def put_meal_details(mid: int, body: MealDetails, c=Depends(con)):
    """BG, insulin and timings, added or changed after the meal (okf/features/annotate-meal.md)."""
    m = get_meal(c, mid)
    require_editable(c, m)
    with c:
        mark_later(c, "meals", m)
        c.execute(f"UPDATE meals SET {', '.join(k + ' = ?' for k in DETAILS)} WHERE id = ?", (*(getattr(body, k) for k in DETAILS), mid))
    return {k: getattr(body, k) for k in DETAILS}


class CarbsFixIn(BaseModel):
    total: float = Field(ge=0, le=1000)
    reason: str = Field(min_length=3, max_length=400)


@app.put("/api/meals/{mid}/carbs")
def correct_carbs(mid: int, body: CarbsFixIn, c=Depends(con)):
    """A discrepancy found later: the total changes, the items don't, and the reason is kept (okf/domain/meal.md)."""
    m = get_meal(c, mid)
    require_editable(c, m)
    reason = body.reason.strip()
    if len(reason) < 3:
        fail(422, "Say why the carbs changed.")
    own = sum(r["carbs_exact"] for r in c.execute("SELECT carbs_exact FROM meal_items WHERE meal_id = ?", (mid,)))
    old = own if m["carbs_corrected"] is None else m["carbs_corrected"]
    new = round(body.total, 1)
    if core.whole_grams(new) == core.whole_grams(old):   # compared as shown, in whole grams
        fail(400, "That's the meal's total already.")
    back = core.whole_grams(new) == core.whole_grams(own)
    with c:
        c.execute("UPDATE meals SET carbs_corrected = ? WHERE id = ?", (None if back else new, mid))
        c.execute("INSERT INTO meal_comments(meal_id, time, text) VALUES (?, ?, ?)",
                  (mid, now().strftime("%H:%M" if m["day"] == today() else "%Y-%m-%d %H:%M"),
                   f"Carbs changed from {core.whole_grams(old)} to {core.whole_grams(new)} g"
                   f"{' (back to the foods’ own total)' if back else ''}: {reason}"[:500]))
        mark_later(c, "meals", m)
    return {"total": core.whole_grams(new), "corrected": not back}


class WhenIn(BaseModel):
    day: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    time: str = Field(pattern=TIME_RE)


def move(c, table: str, row, body: WhenIn):
    """New date and time on any day; the first logged one is kept and shown (okf/rules/same-day-edits.md)."""
    try:
        date.fromisoformat(body.day)
    except ValueError:
        fail(422, "Use a real date.")
    if body.day > today():
        fail(400, "It can't be moved to a future day.")
    first = row["moved_from"] or f"{row['day']} {row['time']}"
    moved_from = None if first == f"{body.day} {body.time}" else first   # moved back: no longer marked
    with c:
        c.execute(f"UPDATE {table} SET day = ?, time = ?, moved_from = ? WHERE id = ?", (body.day, body.time, moved_from, row["id"]))
    return {"ok": True, "day": body.day, "time": body.time, "moved_from": moved_from}


@app.put("/api/meals/{mid}/when")
def move_meal(mid: int, body: WhenIn, c=Depends(con)):
    return move(c, "meals", get_meal(c, mid), body)


@app.put("/api/entries/{eid}/when")
def move_entry(eid: int, body: WhenIn, c=Depends(con)):
    e = get_entry(c, eid)
    return move(c, "log_entries", e, body)


@app.delete("/api/meals/{mid}")
def delete_meal(mid: int, c=Depends(con)):
    """Soft: kept with the time it was deleted, and can be restored (okf/domain/meal-log.md)."""
    require_editable(c, get_meal(c, mid))
    with c:
        c.execute("UPDATE meals SET deleted_at = ? WHERE id = ?", (now().strftime("%Y-%m-%d %H:%M"), mid))
    return {"ok": True}


@app.post("/api/meals/{mid}/restore")
def restore_meal(mid: int, c=Depends(con)):
    m = get_meal(c, mid, deleted=True)
    require_editable(c, m)
    with c:
        c.execute("UPDATE meals SET deleted_at = NULL WHERE id = ?", (mid,))
        mark_later(c, "meals", m)
    return {"ok": True}


class RatingIn(BaseModel):
    rise: Literal["fast", "medium", "slow"] | None = None


@app.put("/api/meals/{mid}/rating")
def rate_meal(mid: int, body: RatingIn, c=Depends(con)):
    """The parent's own rating (okf/features/rate-meal.md): on any day, and it changes nothing else about the meal."""
    get_meal(c, mid)
    with c:
        c.execute("UPDATE meals SET rise = ? WHERE id = ?", (body.rise, mid))
    return {"rise": body.rise}


@app.post("/api/meals/{mid}/comments")
def add_comment(mid: int, body: CommentIn, c=Depends(con)):
    m = get_meal(c, mid)
    require_editable(c, m)
    with c:   # a comment added on a later day carries its own date
        c.execute("INSERT INTO meal_comments(meal_id, time, text) VALUES (?, ?, ?)",
                  (mid, now().strftime("%H:%M" if m["day"] == today() else "%Y-%m-%d %H:%M"), body.text.strip()))
    return {"ok": True}


# ----- notifications (okf/features/notify-family.md) -----
INSULIN_KIND = {"rapid": "rapid-acting", "long": "long-acting", "bolus": "bolus", "basal": "basal"}


def _when(day: str, hhmm: str) -> str:
    return hhmm if day == today() else f"{date.fromisoformat(day).strftime('%a %-d %b')}, {hhmm}"


def _facts(r, carbs=False) -> list[str]:
    """What was typed, in the log's order. Insulin is only ever what was given, never the summary's dose (okf/rules/no-dosing.md)."""
    out = [f"BG {r['bg']} mg/dL"] if r["bg"] is not None else []
    if r["insulin"] is not None:
        out.append(f"{r['insulin']:g} u {INSULIN_KIND.get(r['insulin_kind'], r['insulin_kind'] or '')}".strip())
    if carbs and r["carbs"] is not None:
        out.append(f"{r['carbs']:g} g carbs")
    return out


def meal_notice(c, mid: int) -> dict:
    m = c.execute("SELECT * FROM meals WHERE id = ?", (mid,)).fetchone()
    items = c.execute("SELECT food_name, carbs_exact FROM meal_items WHERE meal_id = ? ORDER BY id", (mid,)).fetchall()
    total = core.whole_grams(sum(i["carbs_exact"] for i in items))
    return {"title": f"Meal logged · {total} g carbs", "tag": f"meal-{mid}", "url": "/#log",
            "body": " · ".join([_when(m["day"], m["time"]), ", ".join(i["food_name"] for i in items), *_facts(m)])}


def entry_notice(e) -> dict:
    return {"title": " · ".join(_facts(e, carbs=True)) or "Note added", "tag": f"entry-{e['id']}", "url": "/#log",
            "body": " · ".join(x for x in (_when(e["day"], e["time"]), e["note"]) if x)}


def notify(notice, skip: str):
    """After the save: a notice that can't be built is logged, never turned into a failed save."""
    try:
        push.send_later(notice(), skip=skip)
    except Exception:
        push.log.exception("notification not sent")


PUSH_HOSTS = ("fcm.googleapis.com", "updates.push.services.mozilla.com", ".push.apple.com", ".notify.windows.com")


class PushSubIn(BaseModel):
    endpoint: str = Field(max_length=1000)
    p256dh: str = Field(min_length=20, max_length=200)
    auth: str = Field(min_length=8, max_length=100)
    device: str = Field(default="", max_length=80)

    @field_validator("endpoint")
    @classmethod
    def push_service(cls, v):
        """The server posts to this address, so only the browsers' own push services are accepted, never the home network."""
        from urllib.parse import urlsplit
        u = urlsplit(v)
        host = (u.hostname or "").lower()
        if u.scheme != "https" or not any(host == h or (h.startswith(".") and host.endswith(h)) for h in PUSH_HOSTS):
            raise ValueError("That isn't a browser push address.")
        return v


class PushEndpointIn(BaseModel):
    endpoint: str = Field(max_length=1000)


@app.get("/api/push")
def push_info(c=Depends(con)):
    return {"enabled": push.enabled(), "public_key": push.public_key(c) if push.enabled() else None}


@app.get("/api/push/devices", dependencies=[Depends(parent)])
def push_devices(c=Depends(con), x_kc_push: str = Header(default="")):
    return [{"id": r["id"], "email": r["email"], "device": r["device"], "created_at": r["created_at"], "last_ok": r["last_ok"],
             "last_error": r["last_error"], "mine": bool(x_kc_push) and r["endpoint"] == x_kc_push}
            for r in c.execute("SELECT * FROM push_subscriptions ORDER BY id")]


@app.post("/api/push/subscribe", dependencies=[Depends(parent)])
def push_subscribe(body: PushSubIn, request: Request, c=Depends(con)):
    if not push.enabled():
        fail(400, "Notifications are off in QA.")
    origin = request.headers.get("origin", "")
    with c:
        if origin.startswith("https://"):   # the VAPID contact: the app's own address
            db.set_setting(c, "push_subject", origin)
        c.execute("INSERT INTO push_subscriptions(endpoint, p256dh, auth, email, device, created_at) VALUES (?, ?, ?, ?, ?, ?) "
                  "ON CONFLICT(endpoint) DO UPDATE SET p256dh = excluded.p256dh, auth = excluded.auth, email = excluded.email, "
                  "device = excluded.device, last_error = NULL",
                  (body.endpoint, body.p256dh, body.auth, getattr(request.state, "email", None), body.device.strip(),
                   now().strftime("%Y-%m-%d %H:%M")))
    return {"ok": True}


@app.post("/api/push/unsubscribe")
def push_unsubscribe(body: PushEndpointIn, c=Depends(con)):
    """Turning notifications off never needs the PIN."""
    with c:
        c.execute("DELETE FROM push_subscriptions WHERE endpoint = ?", (body.endpoint,))
    return {"ok": True}


@app.delete("/api/push/devices/{sid}", dependencies=[Depends(parent)])
def push_remove(sid: int, c=Depends(con)):
    with c:
        c.execute("DELETE FROM push_subscriptions WHERE id = ?", (sid,))
    return {"ok": True}


@app.post("/api/push/test")
def push_test(body: PushEndpointIn, c=Depends(con)):
    if not c.execute("SELECT 1 FROM push_subscriptions WHERE endpoint = ?", (body.endpoint,)).fetchone():
        fail(404, "This device isn't getting notifications.")
    r = push.send({"title": "Kitchen Carbs test", "body": "Notifications work on this device.", "tag": "test", "url": "/#log"},
                  only=body.endpoint)
    if not r["sent"]:
        row = c.execute("SELECT last_error FROM push_subscriptions WHERE endpoint = ?", (body.endpoint,)).fetchone()
        fail(502, "The push service didn't take it" + (f": {row['last_error']}" if row and row["last_error"] else
                                                         ". Turn notifications off and on again on this device."))
    return r


@app.post("/api/entries")
def create_entry(body: EntryIn, c=Depends(con), x_kc_push: str = Header(default="")):
    if body.day > today():
        fail(400, "An entry can't be logged for a future day.")
    if body.day < today() and not past_edits(c):
        fail(409, "Earlier days are read-only. A parent can allow changes in Manage → Settings.")
    existing = c.execute("SELECT id FROM log_entries WHERE client_id = ?", (body.client_id,)).fetchone()
    if existing:
        return {"id": existing["id"], "duplicate": True}
    with c:
        eid = c.execute("INSERT INTO log_entries(client_id, day, time, carbs, bg, insulin, insulin_kind, note, edited_at) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (body.client_id, body.day, body.time, body.carbs, body.bg, body.insulin,
                         body.insulin_kind if body.insulin is not None else None, body.note.strip(),
                         now().strftime("%Y-%m-%d %H:%M") if body.day < today() else None)).lastrowid
    notify(lambda: entry_notice(get_entry(c, eid)), x_kc_push)
    return {"id": eid, "duplicate": False}


@app.put("/api/entries/{eid}")
def edit_entry(eid: int, body: EntryValues, c=Depends(con)):
    """Fix a value or add insulin or carbs later (okf/features/manual-log.md); marked when after its day."""
    e = get_entry(c, eid)
    require_editable(c, e)
    with c:
        c.execute("UPDATE log_entries SET carbs = ?, bg = ?, insulin = ?, insulin_kind = ?, note = ? WHERE id = ?",
                  (body.carbs, body.bg, body.insulin, body.insulin_kind if body.insulin is not None else None,
                   body.note.strip(), eid))
        mark_later(c, "log_entries", e)
    return dict(get_entry(c, eid))


@app.delete("/api/entries/{eid}")
def delete_entry(eid: int, c=Depends(con)):
    e = get_entry(c, eid)
    require_editable(c, e)
    with c:
        c.execute("UPDATE log_entries SET deleted_at = ? WHERE id = ?", (now().strftime("%Y-%m-%d %H:%M"), eid))
    return {"ok": True}


@app.post("/api/entries/{eid}/restore")
def restore_entry(eid: int, c=Depends(con)):
    e = get_entry(c, eid, deleted=True)
    require_editable(c, e)
    with c:
        c.execute("UPDATE log_entries SET deleted_at = NULL WHERE id = ?", (eid,))
        mark_later(c, "log_entries", e)
    return {"ok": True}


def deleted_for_day(c, day):
    """What was deleted from this day, newest first, so it can be restored (okf/domain/meal-log.md)."""
    out = []
    for m in c.execute("SELECT * FROM meals WHERE day = ? AND deleted_at IS NOT NULL", (day,)).fetchall():
        items = c.execute("SELECT food_name, carbs_exact FROM meal_items WHERE meal_id = ? ORDER BY id", (m["id"],)).fetchall()
        out.append({"kind": "meal", "id": m["id"], "time": m["time"], "deleted_at": m["deleted_at"],
                    "what": " · ".join(i["food_name"] for i in items), "carbs": core.total_carbs(i["carbs_exact"] for i in items)})
    for e in c.execute("SELECT * FROM log_entries WHERE day = ? AND deleted_at IS NOT NULL", (day,)).fetchall():
        out.append({"kind": "entry", "id": e["id"], "time": e["time"], "deleted_at": e["deleted_at"], "carbs": e["carbs"],
                    "what": dict(e)})
    return sorted(out, key=lambda x: x["deleted_at"], reverse=True)


@app.get("/api/log")
def get_log(day: str | None = None, c=Depends(con)):
    day = day or today()
    try:
        date.fromisoformat(day)
    except ValueError:
        fail(400, "Use a date like 2026-10-27.")
    meals = meals_for_days(c, day, day)
    glucose = None
    if has_glucose(c):
        low, high = targets(c)
        start, end = day_bounds_ms(day)
        end_now = min(end, int(now().timestamp() * 1000))
        rs = readings(c, start - core.WINDOW_BEFORE_MS, end + core.WINDOW_AFTER_MS)
        glucose = core.glucose_stats(rs, low, high, start, max(start + core.READING_MS, end_now))
        for m in meals:
            ms = meal_ms(m["day"], m["time"])
            two = core._nearest([r for r in rs if r[0] > ms], ms + 120 * 60 * 1000)
            m["two_h"] = two and two[1]
    entries = entries_for_days(c, day, day)
    return {"day": day, "editable": day == today() or (day < today() and past_edits(c)), "clock_12h": clock_12h(c), "meals": meals, "entries": entries, "glucose": glucose,
            "deleted": deleted_for_day(c, day),
            "insulin": insulin_totals([*entries, *meals]),
            "total": core.total_carbs([*(m["total_exact"] for m in meals), *(e["carbs"] or 0 for e in entries)])}


@app.get("/api/meals/{mid}/glucose")
def meal_glucose(mid: int, c=Depends(con)):
    m = get_meal(c, mid)
    ms = meal_ms(m["day"], m["time"])
    rs = readings(c, ms - core.WINDOW_BEFORE_MS, ms + core.WINDOW_AFTER_MS + 1)
    others = [meal_ms(o["day"], o["time"]) for o in
              c.execute("SELECT day, time FROM meals WHERE day BETWEEN ? AND ? AND id != ? AND deleted_at IS NULL",
                        ((date.fromisoformat(m["day"]) - timedelta(days=1)).isoformat(),
                         (date.fromisoformat(m["day"]) + timedelta(days=1)).isoformat(), mid))]
    low, high = targets(c)
    w = core.meal_window(rs, ms, int(now().timestamp() * 1000), others)
    near = entries_for_days(c, (date.fromisoformat(m["day"]) - timedelta(days=1)).isoformat(), m["day"])
    marks = [{"ms": t, "bg": e["bg"], "insulin": e["insulin"], "insulin_kind": e["insulin_kind"]}
             for e in near if (t := meal_ms(e["day"], e["time"])) and w["start_ms"] <= t <= w["end_ms"]
             and (e["bg"] is not None or e["insulin"] is not None)]
    if m["insulin"] is not None:   # the meal's own insulin at the time it was given, and a meter BG
        marks.append({"ms": ms - (m["insulin_offset_min"] or 0) * 60000, "bg": None, "insulin": m["insulin"], "insulin_kind": m["insulin_kind"]})
    if m["bg"] is not None and m["bg_source"] == "meter":
        marks.append({"ms": ms, "bg": m["bg"], "insulin": None, "insulin_kind": None})
    return {**w, "entries": marks, "low": low, "high": high}


@app.get("/api/stats")
def stats(days: int = 7, end: str | None = None, c=Depends(con)):
    if days not in (1, 7, 14):
        fail(400, "Choose 1, 7 or 14 days.")
    last = date.fromisoformat(end or today())
    first = last - timedelta(days=days - 1)
    start, stop = day_bounds_ms(first.isoformat(), days)
    stop = min(stop, int(now().timestamp() * 1000))
    low, high = targets(c)
    meals = meals_for_days(c, first.isoformat(), last.isoformat())
    entries = entries_for_days(c, first.isoformat(), last.isoformat())
    carbs = core.total_carbs([*(m["total_exact"] for m in meals), *(e["carbs"] or 0 for e in entries)])
    return {"from": first.isoformat(), "to": last.isoformat(), "days": days, "low": low, "high": high,
            "glucose": core.glucose_stats(readings(c, start, stop), low, high, start, stop) if has_glucose(c) else None,
            "carbs_total": carbs, "carbs_per_day": core.whole_grams(carbs / days), "meals": len(meals)}


def blank(v):
    return "" if v is None else f"{v:g}"


def cell_text(x):
    """Food names come from Open Food Facts and FatSecret: text a spreadsheet would run as a formula gets a leading '."""
    return "'" + x if isinstance(x, str) and x[:1] in ("=", "+", "-", "@", "\t", "\r") else x


@app.get("/api/export.csv")
def export_csv(start: str, end: str, c=Depends(con)):
    try:
        first, last = date.fromisoformat(start), date.fromisoformat(end)
    except ValueError:
        fail(400, "Use dates like 2026-10-27.")
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["date", "time", "type", "food", "portion", "grams", "qty", "carbs_g", "meal_total_g", "eaten",
                "bg_mg_dl", "insulin_u", "insulin_kind", "comments", "moved_from", "bg_source", "insulin_min_before_eating", "eating_min", "changed_later", "meal_total_from_foods_g", "rise_rating"])
    rows = []
    for m in meals_for_days(c, first.isoformat(), last.isoformat()):
        comments = " | ".join(f"{x['time']} {x['text']}" for x in m["comments"])
        for i in m["items"]:
            hand = i["entered_carbs"] is not None   # no weight (okf/domain/meal.md)
            rows.append([m["day"], m["time"], "meal", i["food_name"], i["portion_label"], "" if hand else f"{i['grams']:g}", "" if hand else f"{i['qty']:g}",
                         i["carbs"], m["total"], m["eaten"] or "", blank(m["bg"]), blank(m["insulin"]), m["insulin_kind"] or "",
                         comments, m["moved_from"] or "", m["bg_source"] or "", blank(m["insulin_offset_min"]), blank(m["eat_min"]), m["edited_at"] or "", m["items_total"],
                         m["rise"] or ""])
    for e in entries_for_days(c, first.isoformat(), last.isoformat()):
        rows.append([e["day"], e["time"], "entry", "", "", "", "", "" if e["carbs"] is None else f"{e['carbs']:g}", "", "",
                     e["bg"] if e["bg"] is not None else "", "" if e["insulin"] is None else f"{e['insulin']:g}",
                     e["insulin_kind"] or "", e["note"], e["moved_from"] or "", "meter" if e["bg"] is not None else "", "", "", e["edited_at"] or "", "", ""])
    for r in sorted(rows, key=lambda r: (r[0], r[1])):   # stable: meal items keep their order
        w.writerow([cell_text(x) for x in r])
    days = (last - first).days + 1
    if has_glucose(c) and days > 0:
        s, e = day_bounds_ms(first.isoformat(), days)
        low, high = targets(c)
        g = core.glucose_stats(readings(c, s, e), low, high, s, e)
        if g["count"]:
            w.writerow([])
            w.writerow(["glucose summary (mg/dL)", f"{first} to {last}", f"target {low}-{high}"])
            for k in ("in_range", "below", "very_low", "above", "very_high", "mean", "cv", "gmi", "coverage"):
                w.writerow([k, g[k]])
    name = f"kitchen-carbs_{first}_{last}.csv"
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


@app.get("/api/export.pdf")
def export_pdf(start: str, end: str, c=Depends(con)):
    """The same values as the CSV, laid out to read and print (okf/features/export-log.md)."""
    try:
        first, last = date.fromisoformat(start), date.fromisoformat(end)
    except ValueError:
        fail(400, "Use dates like 2026-10-27.")
    n = (last - first).days + 1
    if n < 1:
        fail(400, "Choose a start date before the end date.")
    if n > 92:
        fail(400, "A PDF covers up to 92 days. Choose a shorter range.")
    low, high = targets(c)
    meals, entries = meals_for_days(c, first.isoformat(), last.isoformat()), entries_for_days(c, first.isoformat(), last.isoformat())
    glucose = has_glucose(c)
    days, carbs_all = [], 0.0
    for k in range(n):
        day = (first + timedelta(days=k)).isoformat()
        dm, de = [m for m in meals if m["day"] == day], [e for e in entries if e["day"] == day]
        for m in dm:
            m["ms"] = meal_ms(m["day"], m["time"])
        carbs = sum(m["total_exact"] for m in dm) + sum(e["carbs"] or 0 for e in de)
        carbs_all += carbs
        s0, e0 = day_bounds_ms(day)
        pts = readings(c, s0, e0) if glucose else []
        if not (dm or de):
            continue
        days.append({"day": day, "meals": dm, "entries": de, "carbs": core.whole_grams(carbs), "start_ms": s0, "points": pts,
                     "fiber": round(sum(m["fiber"] for m in dm), 1), "fiber_unknown": sum(len(m["fiber_unknown"]) for m in dm),
                     "insulin": insulin_totals(de + dm), "glucose": core.glucose_stats(pts, low, high, s0, e0) if pts else None})
    s0, e0 = day_bounds_ms(first.isoformat(), n)
    overview = {"days": n, "logged_days": len(days), "meals": len(meals), "entries": len(entries),
                "carbs_per_day": core.whole_grams(carbs_all / n), "insulin": insulin_totals(entries + meals),
                "glucose": core.glucose_stats(readings(c, s0, e0), low, high, s0, e0) if glucose else None}
    pdf = report.build(first.isoformat(), last.isoformat(), days, overview, low, high, now(), clock_12h(c))
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="kitchen-carbs_{first}_{last}.pdf"'})


# ----- Tidepool (okf/features/tidepool-sync.md) -----
class TidepoolIn(BaseModel):
    server: Literal["test", "tidepool"]
    email: str = Field(max_length=200)
    password: str = Field(default="", max_length=200)     # empty: keep the saved one
    target: str = Field(default="", max_length=40, pattern=r"^[0-9a-fA-F-]*$")
    send_from: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    carbs: bool = True
    bg: bool = False
    insulin: bool = False
    basal_hours: int = Field(default=tidepool.BASAL_HOURS, ge=1, le=168)


@app.get("/api/tidepool", dependencies=[Depends(parent)])
def tidepool_status(c=Depends(con)):
    return tidepool.public(c)


@app.put("/api/tidepool", dependencies=[Depends(parent)])
def tidepool_save(body: TidepoolIn, c=Depends(con)):
    """Checks the login with Tidepool, then saves and turns sending on (okf/rules/tidepool-login-server-only.md)."""
    if not tidepool.enabled():
        fail(400, "Tidepool is off in QA, so test meals never reach the real record.")
    old = tidepool.config(c)
    password = body.password or old["password"]
    email = body.email.strip()
    if not email or not password:
        fail(422, "Enter the Tidepool email and password.")
    try:
        tidepool.login(body.server, email, password)
    except tidepool.TidepoolError as e:
        fail(400, str(e))
    with c:
        if (body.server, email.lower(), body.target) != (old["server"], old["email"].lower(), old["target"]):
            tidepool.forget(c)
        for k, v in {"server": body.server, "email": email, "password": password, "target": body.target, "from": body.send_from,
                     "kinds": json.dumps({"carbs": body.carbs, "bg": body.bg, "insulin": body.insulin}),
                     "basal_hours": str(body.basal_hours), "on": "on"}.items():
            db.set_setting(c, "tp_" + k, v)
    tidepool.poke()
    return tidepool.public(c)


@app.post("/api/tidepool/sync", dependencies=[Depends(parent)])
def tidepool_sync_now(resend: bool = False, c=Depends(con)):
    """Send now, or with ?resend=1 send every record again (okf/features/tidepool-sync.md)."""
    try:
        r = tidepool.sync_once(resend)
    except tidepool.TidepoolError as e:
        fail(502, str(e))
    if not r:
        fail(400, "Connect Tidepool first.")
    return {**tidepool.public(c), **r}


@app.post("/api/tidepool/off", dependencies=[Depends(parent)])
def tidepool_off(c=Depends(con)):
    """Stops sending; what's in Tidepool stays."""
    with c:
        db.set_setting(c, "tp_on", "")
    return tidepool.public(c)


@app.delete("/api/tidepool/data", dependencies=[Depends(parent)])
def tidepool_remove(c=Depends(con)):
    """Deletes Kitchen Carbs' own data set from Tidepool, and turns sending off."""
    try:
        tidepool.remove_all()
    except tidepool.TidepoolError as e:
        fail(502, str(e))
    return tidepool.public(c)


# ----- meal summary dose (okf/features/meal-dose-summary.md, okf/rules/no-dosing.md) -----
class DoseBlock(BaseModel):
    start: str = Field(max_length=5)
    value: float


class DoseSettingsIn(BaseModel):
    carb_ratio: list[DoseBlock] = Field(max_length=24)
    isf: list[DoseBlock] = Field(max_length=24)
    target: list[DoseBlock] = Field(max_length=24)
    round_to: float = dose.STEP_U


def dose_settings(c):
    raw = db.get_setting(c, "dose_settings")
    return {"settings": json.loads(raw) if raw else None, "updated": db.get_setting(c, "dose_updated")}


@app.get("/api/dose-settings")
def get_dose_settings(c=Depends(con)):
    return dose_settings(c)


@app.put("/api/dose-settings", dependencies=[Depends(parent)])
def put_dose_settings(body: DoseSettingsIn, c=Depends(con)):
    try:
        clean = dose.check_settings(body.model_dump())
    except ValueError as e:
        fail(422, str(e))
    with c:
        db.set_setting(c, "dose_settings", json.dumps(clean))
        db.set_setting(c, "dose_updated", today())
    return dose_settings(c)


@app.delete("/api/dose-settings", dependencies=[Depends(parent)])
def clear_dose_settings(c=Depends(con)):
    with c:
        db.set_setting(c, "dose_settings", None)
        db.set_setting(c, "dose_updated", None)
    return dose_settings(c)


@app.get("/api/dose")
def meal_dose(carbs: float = Query(ge=0, le=1000), at: str = Query(pattern=r"^([01]\d|2[0-3]):[0-5]\d$"),
              bg: float | None = Query(default=None, ge=20, le=600), use_cgm: bool = True, c=Depends(con)):
    """Worked out for the summary only; never stored. bg is a typed meter reading; without it the CGM is used if fresh,
    unless use_cgm is false (the parent cleared the box)."""
    ds = dose_settings(c)
    now_ms = int(now().timestamp() * 1000)
    url, token = db.get_setting(c, "ns_url"), db.get_setting(c, "ns_token")
    live = nightscout.live(url, token) if url and token else {"bg": None, "iob": None, "error": None}
    if not live["bg"]:   # Nightscout unreachable: the newest cached reading, judged by the same age limit
        row = c.execute("SELECT date_ms, sgv, direction FROM glucose ORDER BY date_ms DESC LIMIT 1").fetchone()
        live = {**live, "bg": dict(row) if row else None}
    age = lambda ms: None if ms is None else max(0, round((now_ms - ms) / 60000))
    cgm = live["bg"] and {"sgv": live["bg"]["sgv"], "direction": live["bg"].get("direction"), "age_min": age(live["bg"]["date_ms"])}
    cgm_ok = bool(cgm) and cgm["age_min"] <= dose.FRESH_MIN
    i = live["iob"]
    iob = i and {"units": round(i["units"], 2), "age_min": age(i["mills"]), "source": i["source"]}
    iob_ok = bool(iob) and iob["age_min"] <= dose.FRESH_MIN
    from_cgm = bg is None and use_cgm and cgm_ok
    used_bg = bg if bg is not None else (cgm["sgv"] if from_cgm else None)
    out = {"ready": bool(ds["settings"]), "updated": ds["updated"], "nightscout": bool(url and token),
           "cgm": cgm, "cgm_fresh": cgm_ok, "bg_source": "typed" if bg is not None else ("cgm" if from_cgm else None),
           "iob": iob, "iob_fresh": iob_ok, "ns_error": live["error"]}
    if ds["settings"]:
        out["calc"] = dose.calc(carbs, used_bg, iob["units"] if iob_ok else None, ds["settings"], at)
    return out


# ----- nightscout -----
@app.get("/api/nightscout")
def ns_status(c=Depends(con)):
    last = c.execute("SELECT date_ms, sgv, direction FROM glucose ORDER BY date_ms DESC LIMIT 1").fetchone()
    low, high = targets(c)
    sync = db.get_setting(c, "ns_last_sync")
    return {"configured": bool(db.get_setting(c, "ns_token")), "url": db.get_setting(c, "ns_url"),
            "last_sync_ms": int(sync) if sync else None, "last_error": db.get_setting(c, "ns_last_error"),
            "latest": dict(last) if last else None,
            "readings": c.execute("SELECT COUNT(*) AS n FROM glucose").fetchone()["n"], "low": low, "high": high}


@app.post("/api/nightscout", dependencies=[Depends(parent)])
def ns_connect(body: NightscoutIn, c=Depends(con)):
    url = body.url.rstrip("/")
    try:
        latest = nightscout.latest(url, body.token)
    except nightscout.NightscoutError as e:
        fail(400, str(e))
    lo, hi = nightscout.targets(url, body.token)
    with c:
        if url != (db.get_setting(c, "ns_url") or "").rstrip("/"):   # a different site: stop sending and start afresh
            nightscout_send.forget(c)
        db.set_setting(c, "ns_url", url)
        db.set_setting(c, "ns_token", body.token)
        if lo and hi and db.get_setting(c, "target_low") is None:
            db.set_setting(c, "target_low", int(lo))
            db.set_setting(c, "target_high", int(hi))
    threading.Thread(target=nightscout.sync_once, daemon=True).start()
    return {"ok": True, "latest": latest}


@app.delete("/api/nightscout", dependencies=[Depends(parent)])
def ns_disconnect(c=Depends(con)):
    with c:
        db.set_setting(c, "ns_token", None)
    return {"ok": True}


# ----- sending to Nightscout (okf/features/nightscout-send.md) -----
class NightscoutSendIn(BaseModel):
    send_from: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    carbs: bool = True
    insulin: bool = True
    bg: bool = True


@app.get("/api/nightscout/send", dependencies=[Depends(parent)])
def ns_send_status(c=Depends(con)):
    return nightscout_send.public(c)


@app.put("/api/nightscout/send", dependencies=[Depends(parent)])
def ns_send_save(body: NightscoutSendIn, c=Depends(con)):
    """Checks with Nightscout that the token may write treatments, then saves and turns sending on."""
    if not nightscout_send.enabled():
        fail(400, "Sending to Nightscout only works in production: this copy's meals are test data.")
    url, token = db.get_setting(c, "ns_url"), db.get_setting(c, "ns_token")
    if not (url and token):
        fail(400, "Connect Nightscout first.")
    try:
        nightscout_send.check(url, token)
    except nightscout_send.SendError as e:
        fail(400, str(e))
    with c:
        db.set_setting(c, "ns_send_from", body.send_from)
        db.set_setting(c, "ns_send_kinds", json.dumps({"carbs": body.carbs, "insulin": body.insulin, "bg": body.bg}))
        db.set_setting(c, "ns_send_on", "on")
    nightscout_send.poke()
    return nightscout_send.public(c)


@app.post("/api/nightscout/send/sync", dependencies=[Depends(parent)])
def ns_send_now(resend: bool = False, c=Depends(con)):
    """Send now, or with ?resend=1 send every treatment again (Nightscout replaces each by its identifier)."""
    try:
        r = nightscout_send.sync_once(resend)
    except nightscout_send.SendError as e:
        fail(502, str(e))
    if not r:
        fail(400, "Turn on sending first.")
    return {**nightscout_send.public(c), **r}


@app.post("/api/nightscout/send/off", dependencies=[Depends(parent)])
def ns_send_off(c=Depends(con)):
    """Stops sending; what's in Nightscout stays."""
    with c:
        db.set_setting(c, "ns_send_on", "")
    return nightscout_send.public(c)


@app.delete("/api/nightscout/send/data", dependencies=[Depends(parent)])
def ns_send_remove(c=Depends(con)):
    """Deletes every treatment Kitchen Carbs sent, and turns sending off."""
    try:
        n = nightscout_send.remove_all()
    except nightscout_send.SendError as e:
        fail(502, str(e))
    return {**nightscout_send.public(c), "removed": n}


@app.put("/api/targets", dependencies=[Depends(parent)])
def set_targets(body: TargetsIn, c=Depends(con)):
    if body.low >= body.high:
        fail(400, "The low end must be below the high end.")
    with c:
        db.set_setting(c, "target_low", body.low)
        db.set_setting(c, "target_high", body.high)
    return {"ok": True}


# ---------- sample data ----------
SAMPLES = [
    ("Pasta, cooked", ("Lunch", "Dinner"), 30.9, "pasta.jpg", [("½ cup", 70), ("1 cup", 140), ("1½ cups", 210)],
     "Weigh after cooking. Whole-wheat pasta should be its own food."),
    ("Apple, sliced", ("Breakfast", "Lunch"), 13.8, "apple.jpg", [("½ small apple", 75), ("Small apple", 150)], ""),
    ("Rice, white, cooked", ("Lunch", "Dinner"), 28.2, "rice.jpg", [("½ cup", 79), ("1 cup", 158)], "Weigh after cooking."),
    ("Toast, whole-wheat", ("Breakfast",), 41.3, "toast.jpg", [("1 slice", 32)], "Check the bread label; brands vary."),
]


def seed():
    c = db.connect()
    if c.execute("SELECT 1 FROM foods LIMIT 1").fetchone() or db.get_setting(c, "seeded"):
        return
    with c:
        for name, tags, cp, img, portions, notes in SAMPLES:
            fid = slugify(name)
            c.execute("INSERT INTO foods(id, name, carbs_per_100g, source_kind, source_ref, trust, notes) "
                      "VALUES (?, ?, ?, 'usda', ?, 'draft', ?)",
                      (fid, name, cp, "Sample value: check against USDA FoodData Central or the label", notes))
            c.execute(f"INSERT INTO food_tags(food_id, tag_id) SELECT ?, id FROM tags WHERE name IN ({','.join('?' * len(tags))})",
                      (fid, *tags))
            path = photos.save_jpeg(open(os.path.join(SEED_DIR, img), "rb").read(), "styled")
            for n, (label, grams) in enumerate(portions):
                # Sample photos are AI placeholders, not photos of these weighed portions.
                c.execute("INSERT INTO portions(food_id, label, grams, sort, photo_styled, photo_estimated) VALUES (?, ?, ?, ?, ?, 1)",
                          (fid, label, grams, n, path))
        db.set_setting(c, "seeded", "1")


PHOTO_PATH = re.compile(r"^(original|styled|candidate|labels|base)/[0-9a-f]{32}\.jpg$")


@app.get("/img/{width}/{folder}/{name}")
def photo_sized(width: int, folder: str, name: str):
    """Resized copy for srcset; photos never change once written, so they can be cached for good."""
    path = f"{folder}/{name}"
    if width not in photos.WIDTHS or not PHOTO_PATH.match(path) or not os.path.exists(os.path.join(db.PHOTO_DIR, path)):
        fail(404, "No such photo.")
    return FileResponse(photos.sized(path, width), media_type="image/jpeg",
                        headers={"Cache-Control": "private, max-age=31536000, immutable"})


app.mount("/photos", StaticFiles(directory=db.PHOTO_DIR, check_dir=False), name="photos")
@app.get("/", include_in_schema=False)
@app.get("/index.html", include_in_schema=False)
def index_page():
    """The page names its scripts and styles with a hash of their contents (app.js?v=1a2b3c4d), so a browser never runs
    an old copy after a deploy: Cloudflare tells browsers to keep .js and .css for hours, whatever the app says."""
    html = open(os.path.join(WEB_DIR, "index.html")).read()
    for name in ("app.css", "scale.js", "app.js"):
        v = hashlib.sha256(open(os.path.join(WEB_DIR, name), "rb").read()).hexdigest()[:8]
        html = html.replace(f'"{name}"', f'"{name}?v={v}"')
    return Response(html, media_type="text/html", headers={"Cache-Control": "no-cache"})


class WebFiles(StaticFiles):
    """The app's own pages, scripts and styles: browsers and Cloudflare check for a newer copy on every load
    (a quick 304 when nothing changed), so a deploy shows up at once (okf/architecture/https.md)."""
    def file_response(self, *args, **kwargs):
        r = super().file_response(*args, **kwargs)
        r.headers["Cache-Control"] = "no-cache"
        return r


app.mount("/", WebFiles(directory=WEB_DIR, html=True), name="web")
