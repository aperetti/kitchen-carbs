"""Pure calculations: carbs, rounding, glucose statistics.

Grounded in okf/domain/carb-value.md, okf/rules/whole-gram-rounding.md,
okf/domain/glucose-stats.md and okf/domain/meal-glucose.md.
No insulin maths here: the meal summary's dose lives in dose.py alone (okf/rules/no-dosing.md).
"""
import math
import re
import statistics

READING_MS = 5 * 60 * 1000          # CGM interval used to judge coverage
WINDOW_BEFORE_MS = 30 * 60 * 1000
WINDOW_AFTER_MS = 180 * 60 * 1000   # 3-hour meal window (confirmed 27 Oct)
NEAR_MS = 10 * 60 * 1000            # how close a reading must be to count as "at" a time
VERY_LOW, VERY_HIGH = 54, 250
MIN_COVERAGE = 0.70                 # okf/rules/sensor-coverage.md


# ----- portion labels: an amount, then a unit (okf/domain/portion.md) -----
FRACTIONS = {"¼": 1 / 4, "½": 1 / 2, "¾": 3 / 4, "⅓": 1 / 3, "⅔": 2 / 3, "⅛": 1 / 8}
PORTION_RE = re.compile(r"^(\d+(?:\.\d+)?(?: \d+/\d+)?|\d+/\d+|\d*[¼½¾⅓⅔⅛])\s*([A-Za-z].*)$")
# countable units that take an s after more than one; abbreviations (Tbsp, oz) never do
PLURAL = {"serving", "cup", "slice", "piece", "package", "bowl", "bar", "cookie", "cracker", "nugget", "egg", "scoop",
          "pouch", "stick", "can", "bottle", "glass", "handful", "spoon", "tablespoon", "teaspoon", "bag", "box", "wrap"}


def portion_amount(label: str):
    """'1 1/3 Cup' -> (1.333, 'Cup'); None if it isn't an amount then a unit."""
    m = PORTION_RE.match(label.strip())
    if not m:
        return None
    a, n = m.group(1), 0.0
    for part in a.split(" "):
        if "/" in part:
            top, bottom = part.split("/")
            if int(bottom) == 0:
                return None
            n += int(top) / int(bottom)
        elif part[-1] in FRACTIONS:
            n += (int(part[:-1]) if part[:-1] else 0) + FRACTIONS[part[-1]]
        else:
            n += float(part)
    return (n, m.group(2).strip()) if n > 0 else None


def fmt_amount(n: float) -> str:
    """1.5 -> '1½', 0.333 -> '⅓', 2.4 -> '2.4'."""
    whole = int(n + 1e-9)
    for ch, v in FRACTIONS.items():
        if abs(n - whole - v) < 0.01:
            return f"{whole or ''}{ch}"
    return str(whole) if abs(n - whole) < 0.01 else f"{n:.2f}".rstrip("0").rstrip(".")


def unit_for(n: float, unit: str) -> str:
    """'serving' after 2 -> 'servings'; 'servings' after ½ -> 'serving'; 'Tbsp' stays."""
    first, rest = (unit.split(" ", 1) + [""])[:2]
    single = first[:-1] if first.lower().endswith("s") and first[:-1].lower() in PLURAL else first
    word = single + ("s" if n > 1 + 1e-9 and single.lower() in PLURAL else "")
    return (word + (" " + rest if rest else "")).strip()


def whole_grams(x: float) -> int:
    """Round half up to a whole gram (Python's round() is banker's rounding)."""
    return int(math.floor(x + 0.5))


def carbs_exact(grams: float, carbs_per_100g: float, qty: float = 1.0) -> float:
    return grams * carbs_per_100g / 100.0 * qty


def total_carbs(exact_values) -> int:
    """Totals add the unrounded values, then round once."""
    return whole_grams(sum(exact_values))


def glucose_stats(readings, low: int, high: int, start_ms: int, end_ms: int) -> dict:
    """Descriptive statistics for readings [(date_ms, sgv)] between start and end."""
    vals = [v for t, v in readings if start_ms <= t < end_ms]
    expected = max(1, (end_ms - start_ms) // READING_MS)
    coverage = min(1.0, len(vals) / expected)
    if not vals:
        return {"count": 0, "coverage": 0.0, "complete": False}
    n = len(vals)
    pct = lambda k: round(100.0 * k / n, 1)
    mean = statistics.fmean(vals)
    sd = statistics.pstdev(vals) if n > 1 else 0.0
    days = (end_ms - start_ms) / 86_400_000
    return {
        "count": n,
        "coverage": round(coverage, 3),
        "complete": coverage >= MIN_COVERAGE,
        "in_range": pct(sum(low <= v <= high for v in vals)),
        "below": pct(sum(v < low for v in vals)),
        "very_low": pct(sum(v < VERY_LOW for v in vals)),
        "above": pct(sum(v > high for v in vals)),
        "very_high": pct(sum(v > VERY_HIGH for v in vals)),
        "mean": whole_grams(mean),
        "cv": round(100.0 * sd / mean, 1) if mean else None,
        # GMI is only meaningful over ~14 days of data; report it with that caveat.
        "gmi": round(3.31 + 0.02392 * mean, 1) if days >= 14 else None,
        "lows": count_low_events(readings, low, start_ms, end_ms),
    }


def count_low_events(readings, low: int, start_ms: int, end_ms: int) -> int:
    """Separate spells below range (a gap of 30+ minutes or a return to range ends one)."""
    events, in_low, last_t = 0, False, None
    for t, v in readings:
        if not start_ms <= t < end_ms:
            continue
        if last_t is not None and t - last_t > 30 * 60 * 1000:
            in_low = False
        if v < low and not in_low:
            events += 1
        in_low = v < low
        last_t = t
    return events


def _nearest(points, target_ms):
    best = min(points, key=lambda p: abs(p[0] - target_ms), default=None)
    return best if best and abs(best[0] - target_ms) <= NEAR_MS else None


def meal_window(readings, meal_ms: int, now_ms: int, other_meals_ms=()) -> dict:
    """Glucose from 30 min before to 3 h after a meal. Gaps stay gaps."""
    start, end = meal_ms - WINDOW_BEFORE_MS, meal_ms + WINDOW_AFTER_MS
    pts = [(t, v) for t, v in readings if start <= t <= end]
    after = [p for p in pts if p[0] > meal_ms]
    at_meal, two_h = _nearest(pts, meal_ms), _nearest(pts, meal_ms + 120 * 60 * 1000)
    peak = max(after, key=lambda p: p[1], default=None)
    lowest = min(after, key=lambda p: p[1], default=None)
    span_end = min(end, now_ms)
    expected = max(1, (span_end - start) // READING_MS)
    return {
        "start_ms": start, "end_ms": end, "meal_ms": meal_ms,
        "points": pts,
        "at_meal": at_meal and at_meal[1],
        "peak": peak and {"ms": peak[0], "sgv": peak[1]},
        "lowest": lowest and {"ms": lowest[0], "sgv": lowest[1]},
        "two_h": two_h and two_h[1],
        "coverage": round(min(1.0, len(pts) / expected), 3),
        "in_progress": now_ms < end,
        "overlapping_meals": [m for m in other_meals_ms if start < m <= end and m != meal_ms],
    }
