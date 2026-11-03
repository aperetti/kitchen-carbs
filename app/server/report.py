"""The log as a formatted PDF for the family and care team (okf/features/export-log.md).
Values as logged; nothing is graded or advised (okf/rules/descriptive-stats-only.md, okf/rules/no-dosing.md)."""
import os
import unicodedata
from datetime import date, datetime

from fontTools.ttLib import TTFont
from fpdf import FPDF
from fpdf.fonts import FontFace

FONT_DIR = os.path.join(os.path.dirname(__file__), "fonts")
REGULAR, BOLD = (os.path.join(FONT_DIR, f"kitchen-sans-{w}.ttf") for w in ("Regular", "SemiBold"))
_CMAP = set(TTFont(REGULAR).getBestCmap())

# The app's own colours (okf/design/foundations/color.md)
INK, VEIN, ACCENT, WARN, LINE, SUNK, BAND = (0x2B, 0x2E, 0x30), (0x6F, 0x75, 0x79), (0x1F, 0x3A, 0x5F), (0x8A, 0x5A, 0x00), \
    (0xD9, 0xDB, 0xD7), (0xEE, 0xEF, 0xEC), (0xE6, 0xE8, 0xE4)
KIND = {"rapid": "rapid-acting", "long": "long-acting", "bolus": "bolus", "basal": "basal"}
FOOT = "Values as logged in Kitchen Carbs. Doses are what was recorded, not advice."


def safe(s) -> str:
    """Only characters the bundled font has: accents fold to their letter, anything else drops out."""
    out = []
    for ch in str(s):
        if ord(ch) in _CMAP or ch in "\n":
            out.append(ch)
        else:
            out.extend(c for c in unicodedata.normalize("NFKD", ch) if ord(c) in _CMAP)
    return "".join(out)


def day_label(d: str, year=False) -> str:
    x = date.fromisoformat(d)
    return x.strftime("%a, %b %-d" + (", %Y" if year else ""))


def clock(hhmm: str, h12: bool) -> str:
    """18:30, or 6:30 PM with the log's 12-hour setting (okf/features/review-log.md)."""
    if not h12:
        return hhmm
    h, m = int(hhmm[:2]), int(hhmm[3:5])
    return f"{(h - 1) % 12 + 1}:{m:02d} {'AM' if h < 12 else 'PM'}"


def units(u) -> str:
    return f"{u:.2f}".rstrip("0").rstrip(".") if u % 1 else f"{u:.0f}"


def insulin_text(totals: dict) -> str:
    return " · ".join(f"{units(v)} u {KIND.get(k, k)}" for k, v in totals.items()) or "none recorded"


class Report(FPDF):
    def __init__(self, title_range: str, h12: bool = False):
        super().__init__(format="Letter", unit="pt")
        self.title_range = title_range
        self.h12 = h12
        self.add_font("Sans", "", REGULAR)
        self.add_font("Sans", "B", BOLD)
        self.set_margins(48, 54, 48)
        self.set_auto_page_break(True, 60)
        self.alias_nb_pages()
        self.set_title(f"Kitchen Carbs meal log, {title_range}")
        self.set_creator("Kitchen Carbs")

    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("Sans", "", 8.5)
        self.set_text_color(*VEIN)
        self.cell(0, 12, safe(f"Kitchen Carbs · Meal log · {self.title_range}"), new_x="LMARGIN", new_y="NEXT")
        self.ln(10)

    def footer(self):
        self.set_y(-40)
        self.set_draw_color(*LINE)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.set_font("Sans", "", 8)
        self.set_text_color(*VEIN)
        self.cell(0, 18, FOOT)
        self.set_x(self.l_margin)
        self.cell(0, 18, f"Page {self.page_no()} of {{nb}}", align="R")

    # ----- building blocks -----
    def label(self, text):
        self.set_font("Sans", "B", 7.5)
        self.set_text_color(*VEIN)
        self.set_char_spacing(0.8)
        self.cell(0, 12, safe(text.upper()), new_x="LMARGIN", new_y="NEXT")
        self.set_char_spacing(0)

    def fact(self, name, value, color=INK, width=None):
        """'Avg 156 mg/dL'-style pair, name in grey, value in ink."""
        self.set_font("Sans", "", 9.5)
        self.set_text_color(*VEIN)
        self.cell(self.get_string_width(safe(name)) + 3, 14, safe(name))
        self.set_font("Sans", "B", 9.5)
        self.set_text_color(*color)
        self.cell(width or self.get_string_width(safe(value)) + 16, 14, safe(value))

    def tir_bar(self, g, w=None, h=7):
        """Below / in / above the target as one bar, the way the Log shows it."""
        x, y, w = self.l_margin, self.get_y() + 2, w or (self.w - self.l_margin - self.r_margin)
        below, inside = g["below"] / 100 * w, g["in_range"] / 100 * w
        self.set_fill_color(*BAND)
        self.rect(x, y, w, h, "F")
        self.set_fill_color(*WARN)
        if below:
            self.rect(x, y, below, h, "F")
        self.set_fill_color(*INK)
        self.rect(x + below, y, inside, h, "F")
        self.set_y(y + h + 5)

    def glucose_stats(self, g, low, high):
        self.tir_bar(g)
        self.fact("In range ", f"{g['in_range']:g}%")
        self.fact("Below ", f"{g['below']:g}%", WARN if g["below"] else INK)
        self.fact("Above ", f"{g['above']:g}%")
        self.fact("Avg ", f"{g['mean']} mg/dL")
        if g.get("cv") is not None:
            self.fact("CV ", f"{g['cv']:g}%")
        if g.get("gmi") is not None:
            self.fact("GMI ", f"{g['gmi']:g}%")
        self.fact("Sensor ", f"{round(g['coverage'] * 100)}%" + ("" if g["complete"] else ", incomplete"), INK if g["complete"] else WARN)
        self.ln(16)
        self.set_font("Sans", "", 8)
        self.set_text_color(*VEIN)
        self.cell(0, 10, f"Target {low}-{high} mg/dL", new_x="LMARGIN", new_y="NEXT")

    def trace(self, points, start_ms, low, high, meal_ms, h=86):
        """The day's CGM trace: 0 to 24 h across, 40 to 300 mg/dL up, target band shaded, meals as ticks."""
        x0, y0, w = self.l_margin + 26, self.get_y() + 4, self.w - self.l_margin - self.r_margin - 26
        lo, hi = 40, 300
        Y = lambda v: y0 + h - (min(max(v, lo), hi) - lo) / (hi - lo) * h
        X = lambda ms: x0 + (ms - start_ms) / 86_400_000 * w
        self.set_fill_color(*BAND)
        self.rect(x0, Y(high), w, Y(low) - Y(high), "F")
        self.set_font("Sans", "", 7)
        self.set_text_color(*VEIN)
        for v in (low, high, 250):
            self.set_xy(x0 - 26, Y(v) - 4)
            self.cell(22, 8, str(v), align="R")
        for hr in range(0, 25, 3):
            self.set_xy(X(start_ms + hr * 3_600_000) - 12, y0 + h + 2)
            self.cell(24, 8, ("" if hr == 24 else f"{(hr - 1) % 12 + 1} {'AM' if hr < 12 else 'PM'}" if self.h12 else f"{hr:02d}:00"), align="C")
        self.set_draw_color(*ACCENT)   # meals: thin dashed lines with a small mark at the foot
        self.set_line_width(0.5)
        self.set_dash_pattern(dash=2, gap=2)
        for ms in meal_ms:
            self.line(X(ms), y0 + 6, X(ms), y0 + h)
        self.set_dash_pattern()
        self.set_fill_color(*ACCENT)
        for ms in meal_ms:
            self.polygon([(X(ms) - 3, y0), (X(ms) + 3, y0), (X(ms), y0 + 5)], style="F")
        self.set_draw_color(*INK)
        self.set_line_width(1.1)
        run = []
        for i, (ms, v) in enumerate(points):   # a gap of 15+ minutes breaks the line
            if run and ms - points[i - 1][0] > 15 * 60_000:
                if len(run) > 1:
                    self.polyline(run)
                run = []
            run.append((X(ms), Y(v)))
        if len(run) > 1:
            self.polyline(run)
        self.set_draw_color(*WARN)
        self.set_fill_color(*WARN)
        for ms, v in points:
            if v < low:
                self.circle(X(ms), Y(v), 1.6, "F")
        self.set_line_width(0.2)
        self.set_fill_color(255, 255, 255)
        self.set_font("Sans", "", 7)
        self.set_text_color(*VEIN)
        self.set_xy(self.l_margin, y0 + h + 12)
        self.cell(0, 9, "Triangles mark meals. Dots below the band are readings under the target.", new_x="LMARGIN", new_y="NEXT")
        self.ln(4)


def build(first: str, last: str, days: list[dict], overview: dict, low: int, high: int, made: datetime, h12: bool = False) -> bytes:
    """days: [{day, meals, entries, carbs, fiber, fiber_unknown, insulin, glucose, points, start_ms}] for days with anything logged."""
    rng = day_label(first, True) if first == last else f"{day_label(first)} – {day_label(last, True)}"
    pdf = Report(rng, h12)
    pdf.add_page()
    pdf.set_font("Sans", "B", 20)
    pdf.set_text_color(*INK)
    pdf.cell(0, 26, "Meal log", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Sans", "", 11)
    pdf.set_text_color(*VEIN)
    pdf.cell(0, 16, safe(f"Kitchen Carbs · {rng}"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Sans", "", 8.5)
    pdf.cell(0, 14, f"Made {made.strftime('%b %-d, %Y')} at {clock(made.strftime('%H:%M'), h12)}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(12)

    o = overview
    pdf.label(f"At a glance · {o['days']} day{'s' if o['days'] != 1 else ''}, {o['logged_days']} with something logged")
    pdf.fact("Carbs per day ", f"{o['carbs_per_day']} g")
    pdf.fact("Meals ", str(o["meals"]))
    pdf.fact("Entries ", str(o["entries"]))
    pdf.ln(16)
    pdf.fact("Insulin given ", insulin_text(o["insulin"]))
    pdf.ln(18)
    if o["glucose"] and o["glucose"]["count"]:
        pdf.label("Glucose · mg/dL")
        pdf.glucose_stats(o["glucose"], low, high)
    pdf.ln(8)
    if not days:
        pdf.set_font("Sans", "", 11)
        pdf.set_text_color(*VEIN)
        pdf.cell(0, 20, "Nothing was logged in these days.")

    for d in days:
        if pdf.get_y() > pdf.h - 260:   # a day starts where its heading, trace and first rows fit
            pdf.add_page()
        pdf.set_draw_color(*INK)
        pdf.set_line_width(0.8)
        pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
        pdf.set_line_width(0.2)
        pdf.ln(6)
        pdf.set_font("Sans", "B", 13)
        pdf.set_text_color(*INK)
        pdf.cell(0, 18, safe(day_label(d["day"], True)))
        pdf.set_x(pdf.l_margin)
        pdf.set_text_color(*ACCENT)
        pdf.cell(0, 18, f"{d['carbs']} g carbs", align="R", new_x="LMARGIN", new_y="NEXT")
        pdf.fact("Insulin given ", insulin_text(d["insulin"]))
        if d["meals"]:   # reference only, never taken off the carbs (okf/domain/meal.md)
            unknown = d["fiber_unknown"]
            pdf.fact("Fiber ", f"{d['fiber']:g} g" + (f", not known for {unknown} food{'s' if unknown != 1 else ''}" if unknown else ""))
        g = d["glucose"]
        if g and g["count"]:
            pdf.fact("In range ", f"{g['in_range']:g}%")
            pdf.fact("Below ", f"{g['below']:g}%", WARN if g["below"] else INK)
            pdf.fact("Avg ", f"{g['mean']} mg/dL")
            if not g["complete"]:
                pdf.fact("Sensor ", f"{round(g['coverage'] * 100)}%, incomplete", WARN)
        pdf.ln(16)
        if d["points"]:
            pdf.trace(d["points"], d["start_ms"], low, high, [m["ms"] for m in d["meals"]])
        rows(pdf, d)
        pdf.ln(14)
    return bytes(pdf.output())


def rows(pdf: Report, d: dict):
    """Meals and entries in time order, as the Log lists them."""
    items = sorted([("meal", m) for m in d["meals"]] + [("entry", e) for e in d["entries"]], key=lambda r: r[1]["time"])
    if not items:
        return
    head = FontFace(family="Sans", emphasis="B", size_pt=7.5, color=VEIN, fill_color=SUNK)
    pdf.set_font("Sans", "", 9)
    pdf.set_text_color(*INK)
    pdf.set_draw_color(*LINE)
    pdf.set_fill_color(255, 255, 255)
    with pdf.table(cell_fill_mode="NONE", col_widths=(54, 190, 44, 40, 70, 118) if pdf.h12 else (40, 190, 44, 40, 70, 132), text_align=("LEFT", "LEFT", "RIGHT", "RIGHT", "LEFT", "LEFT"),
                   headings_style=head, borders_layout="HORIZONTAL_LINES", line_height=12, padding=(4, 4),
                   first_row_as_headings=True, repeat_headings=1) as t:
        r = t.row()
        for h in ("TIME", "WHAT", "CARBS", "BG", "INSULIN", "NOTES"):
            r.cell(h)
        for kind, x in items:
            r = t.row()
            edited = bool(x.get("moved_from") or x.get("edited_at"))
            r.cell(clock(x["time"], pdf.h12) + ("\nedited" if edited else ""), style=FontFace(color=INK))
            if kind == "meal":
                r.cell(safe("\n".join(f"{i['food_name']}, {i['carbs']} g" + (" (by hand)" if i["entered_carbs"] is not None else "")
                                      for i in x["items"])))
                r.cell(f"{x['total']} g" + ("\nedited" if x["carbs_corrected"] is not None else ""),
                       style=FontFace(emphasis="B", color=ACCENT))
                bg = x["bg"]
                r.cell("" if bg is None else f"{bg}" + (" CGM" if x["bg_source"] == "cgm" else ""),
                       style=FontFace(color=WARN if bg is not None and bg < 70 else INK))
                ins = "" if x["insulin"] is None else f"{units(x['insulin'])} u {x['insulin_kind']}"
                off = x["insulin_offset_min"]
                if ins and off is not None:
                    ins += "\nat the start" if off == 0 else f"\n{off} min before" if off > 0 else f"\n{-off} min after"
                r.cell(ins)
                notes = [f"Eaten: {x['eaten']}" if x["eaten"] else "", f"Ate in {x['eat_min']} min" if x["eat_min"] else ""]
                notes += [f"{x['rise'].capitalize()} rise" if x.get("rise") else ""]
                notes += [c["text"] for c in x["comments"]]
                r.cell(safe("\n".join(n for n in notes if n)), style=FontFace(size_pt=8, color=VEIN))
            else:
                r.cell("Entry", style=FontFace(color=VEIN))
                r.cell("" if x["carbs"] is None else f"{x['carbs']:g} g", style=FontFace(emphasis="B", color=ACCENT))
                r.cell("" if x["bg"] is None else f"{x['bg']} meter", style=FontFace(color=WARN if x["bg"] is not None and x["bg"] < 70 else INK))
                r.cell("" if x["insulin"] is None else f"{units(x['insulin'])} u {KIND.get(x['insulin_kind'], '')}")
                r.cell(safe(x["note"] or ""), style=FontFace(size_pt=8, color=VEIN))
