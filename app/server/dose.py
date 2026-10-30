"""The one place insulin is worked out: the meal summary (okf/features/meal-dose-summary.md).

Bounded by okf/rules/no-dosing.md: only from the parent's own settings (okf/domain/insulin-settings.md),
every step returned for the screen, rounded down to 0.05 u, never below zero. Nothing here is stored or sent.
"""
import math
import re

FRESH_MIN = 15          # a CGM reading or IOB older than this is not used
STEP_U = 0.05           # pump precision; always rounded down
LIMITS = {"carb_ratio": (1, 150), "isf": (5, 500), "target": (70, 200)}
HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def check_settings(s: dict) -> dict:
    """Each setting is a list of {start 'HH:MM', value}; the first starts at 00:00. Raises ValueError in plain words."""
    names = {"carb_ratio": "Carb ratio", "isf": "Correction factor", "target": "Target BG"}
    out = {}
    for k, (lo, hi) in LIMITS.items():
        blocks = s.get(k) or []
        if not blocks:
            raise ValueError(f"{names[k]} needs at least one value.")
        seen, clean = set(), []
        for b in blocks:
            start, v = str(b.get("start", "")), b.get("value")
            if not HHMM.match(start):
                raise ValueError(f"{names[k]}: '{start}' isn't a time like 06:30.")
            if start in seen:
                raise ValueError(f"{names[k]} has two blocks starting at {start}.")
            if not isinstance(v, (int, float)) or not lo <= v <= hi:
                raise ValueError(f"{names[k]} at {start} must be between {lo} and {hi}.")
            seen.add(start)
            clean.append({"start": start, "value": round(float(v), 2)})
        clean.sort(key=lambda b: b["start"])
        if clean[0]["start"] != "00:00":
            raise ValueError(f"{names[k]}: the first block must start at 00:00.")
        out[k] = clean
    return out


def block_at(blocks: list, at: str) -> float:
    return [b for b in blocks if b["start"] <= at][-1]["value"]


def round_down(u: float) -> float:
    return round(math.floor(u / STEP_U + 1e-9) * STEP_U, 2)


def calc(carbs: float, bg: float | None, iob: float | None, settings: dict, at: str) -> dict:
    """Carbs ÷ ratio, plus (BG − target) ÷ factor; IOB comes off a positive correction only."""
    icr, isf, target = (block_at(settings[k], at) for k in ("carb_ratio", "isf", "target"))
    carb_u = carbs / icr
    corr = None if bg is None else (bg - target) / isf
    iob_off = 0.0
    if corr is not None and corr > 0 and iob:
        iob_off = min(max(iob, 0.0), corr)
    total = max(0.0, carb_u + (corr or 0.0) - iob_off)
    return {"carb_ratio": icr, "isf": isf, "target": target, "carbs": carbs, "bg": bg,
            "carb_u": round(carb_u, 2), "correction_u": None if corr is None else round(corr, 2),
            "iob": iob, "iob_off": round(iob_off, 2), "iob_used": corr is not None and corr > 0,
            "total_exact": round(total, 3), "dose": round_down(total)}
