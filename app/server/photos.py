"""Photo storage and Gemini restyling (okf/features/photo-pipeline.md).

Originals are saved once and never changed (okf/rules/original-photo-kept.md).
Gemini output lands as a candidate until the parent accepts it.
"""
import base64
import io
import os
import uuid

import requests
from PIL import Image, ImageOps

from . import db

# okf/domain/photo-style.md: measured 27 Oct on a real estimate, fast ~3.5 s at 1200 px, sharp ~15 s at 2400 px
QUALITIES = {"fast": ("gemini-3.1-flash-lite-image", "1K"),
             "sharp": (os.environ.get("GEMINI_IMAGE_MODEL", "gemini-3.1-flash-image"), "2K")}
SEND_SIDE = 1600           # reference photos are shrunk to this before sending; bigger only slows the upload
API = "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent"
MAX_SIDE = 3000            # sharp on high-DPI screens; smaller copies are made on demand
WIDTHS = (320, 800, 1600, 2400)

# okf/domain/photo-style.md: the parent edits the style; the guard is always sent and can't be edited away.
DEFAULT_STYLE = ("White quartz kitchen countertop with soft grey veins; show only the countertop around the dish, "
                 "no window, wall or props. Camera at about 45 degrees, soft natural daylight from the left, "
                 "true-to-life colours.")
GUARD = ("Keep exactly the same food and exactly the same amount of it as in the first image: do not add, remove, "
         "garnish, rearrange or resize any food. No text, labels or hands.")
CONTAINERS = {"plate": "plate", "bowl": "bowl", "dressing": "dressing container"}


def build_prompt(style: str, bases: dict, container: str, estimate: dict | None = None,
                 size_ref: dict | None = None, portion: dict | None = None, describe: dict | None = None,
                 note: str = "", package: str | None = None) -> tuple[str, list]:
    """Return (prompt, extra photo paths in the order they follow the first image).

    With `describe` there is no first image: the photo is made from the food's name and grams alone.
    """
    lead = 0 if describe else 1          # images sent before these: the parent's photo, when there is one
    if container == "counter":           # straight on the quartz, no dish (okf/domain/photo-style.md)
        refs, where = [], ("Place the food directly on the countertop, with no plate, bowl, cup, container or other dish under it"
                           + ("." if describe else "; if the first image shows one, leave it out and keep the food itself unchanged."))
    elif container == "package":         # in or beside its own retail package; the package photo follows below
        refs, where = [], ("" if package else "Show the serving in or beside its own retail package, opened as it would be "
                           "at snack time, on the countertop.")
    elif container in bases:
        refs = [bases[container]]
        where = (f"Image {lead + 1} is the family's {CONTAINERS[container]}, empty. Serve the food in exactly that "
                 f"{CONTAINERS[container]}, matching its shape, colour and size.")
    elif bases:
        kinds = list(bases)
        refs = [bases[k] for k in kinds]
        where = (f"Images {lead + 1} to {lead + len(kinds)} are the family's empty " if len(kinds) > 1 else f"Image {lead + 1} is the family's empty ")
        where += ", ".join(CONTAINERS[k] for k in kinds) + (", in that order. " if len(kinds) > 1 else ". ")
        where += ("Use whichever one suits the food." if describe else
                  "Use whichever one matches the container in the first image; if none matches, keep the container from the first image.")
    elif describe:
        refs, where = [], (f"Serve it on a plain white {CONTAINERS[container]}." if container in CONTAINERS
                           else "Serve it on a plain white plate or bowl, whichever suits the food.")
    else:
        refs, where = [], "Keep the same container as in the first image."
    if describe:
        task = (f"Create a realistic photograph of {describe['grams']:g} g of {describe['food']} ({describe['label']}), "
                "as a family would serve it at home. Show exactly that amount, no more and no less, and nothing else "
                "to eat. No text, labels or hands.")
    elif estimate:
        task = (f"The first image shows {estimate['ref_grams']:g} g of {estimate['food']}. Create a matching photo "
                f"showing {estimate['grams']:g} g of the same food ({estimate['label']}). Keep the food identical in "
                "type and preparation; only the amount changes. If the food is in pieces (nuggets, crackers, slices), keep each "
                "piece the same size and change how many there are, in proportion to the grams. No text, labels or hands.")
    else:
        task = "Restyle the first image, a food photograph. " + GUARD
    scale = ""
    if size_ref:   # okf/domain/size-reference.md: for judging the amount only
        n = len(refs) + lead + 1
        refs = [*refs, size_ref["photo"]]
        amount = f"{portion['label']} ({portion['grams']:g} g)" if portion else "the portion"
        dish = f" in the family's {CONTAINERS[size_ref['container']]}" if size_ref.get("container") in CONTAINERS else ""
        scale = (f"Image {n} is a size reference: {size_ref['name']}, showing {size_ref['measurement']}{dish}. Use it only to judge "
                 f"how much food {amount} is; do not put the reference object in the photo.")
    pack = ""
    if package:   # Open Food Facts' front-of-package photo: what the food is (okf/domain/photo-style.md)
        n = len(refs) + lead + 1
        refs = [*refs, package]
        pack = (f"Image {n} is the product's retail package. Show the serving in or beside that package, opened as it would be "
                "at snack time, on the countertop." if container == "package" else
                f"Image {n} is the product's retail package, only to show what the food looks like; do not show the package.")
    if note.strip():   # the parent's note helps with what the food is; it never changes the amount
        note = (f"Note from the family about this food: \"{note.strip()}\". Follow it unless it would change the amount "
                "of food or break the instructions above.")
    return " ".join(x for x in (task, where, scale, pack, note.strip(), f"Style: {style.strip() or DEFAULT_STYLE}") if x), refs


class PhotoError(Exception):
    pass


def save_jpeg(data: bytes, folder: str) -> str:
    try:
        im = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
    except Exception as e:
        raise PhotoError("That file is not an image this app can read (use JPEG or PNG).") from e
    im.thumbnail((MAX_SIDE, MAX_SIDE))
    name = f"{uuid.uuid4().hex}.jpg"
    im.save(os.path.join(db.PHOTO_DIR, folder, name), quality=88)
    return f"{folder}/{name}"


def sized(path: str, width: int) -> str:
    """A copy of photo `path` at most `width` px wide, cached under photos/_w{width}/ (okf/design/components/plate-photo.md)."""
    src = os.path.join(db.PHOTO_DIR, path)
    out = os.path.join(db.PHOTO_DIR, f"_w{width}", path)
    if not os.path.exists(out) or os.path.getmtime(out) < os.path.getmtime(src):
        os.makedirs(os.path.dirname(out), exist_ok=True)
        im = Image.open(src)
        if im.width > width:
            im = im.convert("RGB")
            im.thumbnail((width, width * 4))
        tmp = out + ".tmp"
        im.save(tmp, "JPEG", quality=84, optimize=True, progressive=True)
        os.replace(tmp, out)
    return out


def _key() -> str:
    """GEMINI_KEY from the environment (.env); GEMINI_KEY_FILE is still accepted."""
    if os.environ.get("GEMINI_KEY"):
        return os.environ["GEMINI_KEY"].strip()
    f = os.environ.get("GEMINI_KEY_FILE", "")
    if f and os.path.exists(f):
        return open(f).read().strip()
    raise PhotoError("No Gemini key on the server. Add GEMINI_KEY to the .env file and restart.")


def _send_copy(path: str) -> str:
    im = ImageOps.exif_transpose(Image.open(os.path.join(db.PHOTO_DIR, path))).convert("RGB")
    im.thumbnail((SEND_SIDE, SEND_SIDE))
    out = io.BytesIO()
    im.save(out, "JPEG", quality=85)
    return base64.b64encode(out.getvalue()).decode()


def generate(image_paths: list, prompt: str, quality: str = "fast") -> str:
    """Send the photos (original first when there is one, then base containers) + prompt to Gemini; return the candidate path."""
    model, size = QUALITIES.get(quality, QUALITIES["fast"])
    parts = [{"inlineData": {"mimeType": "image/jpeg", "data": _send_copy(p)}} for p in image_paths]
    body = {"contents": [{"parts": [*parts, {"text": prompt}]}],
        "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": "4:3", "imageSize": size}}}
    try:
        r = requests.post(API.format(model), headers={"x-goog-api-key": _key()}, json=body, timeout=180)
    except requests.RequestException as e:
        raise PhotoError("Could not reach Gemini. Check the internet connection and try again.") from e
    d = r.json()
    for c in d.get("candidates", []):
        for p in c.get("content", {}).get("parts", []):
            if "inlineData" in p:
                return save_jpeg(base64.b64decode(p["inlineData"]["data"]), "candidate")
    msg = d.get("error", {}).get("message") or "Gemini returned no image."
    raise PhotoError(f"Gemini did not make a photo: {msg[:200]}")
