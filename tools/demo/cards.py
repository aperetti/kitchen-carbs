"""Caption strips and title cards for the demo videos, drawn with the app's own font."""
import os, sys
from PIL import Image, ImageDraw, ImageFont
FONT = os.path.join(os.path.dirname(__file__), "..", "..", "app", "server", "fonts", "kitchen-sans-{}.ttf")
BG, INK, ACCENT, MUTED, WARN = (242, 243, 241), (35, 39, 45), (31, 58, 95), (110, 116, 124), (154, 98, 0)

def caption(text, out, w=1280, h=800):
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    f = ImageFont.truetype(FONT.format("SemiBold"), 21)
    tw = d.textlength(text, font=f); bw, bh = tw + 40, 48
    x0, y0 = (w - bw) / 2, h - bh - 22
    d.rounded_rectangle([x0, y0, x0 + bw, y0 + bh], 12, fill=(28, 32, 38, 225))
    d.text((w / 2, y0 + bh / 2), text, font=f, fill="white", anchor="mm")
    im.save(out)

def card(lines, out, w=1280, h=800, pad_to=None):
    """lines: (text, size, weight, colour) top to bottom, centred in the first w pixels (pad_to: the full width)."""
    im = Image.new("RGB", (pad_to or w, h), BG); d = ImageDraw.Draw(im)
    fonts = [ImageFont.truetype(FONT.format(wt), sz) for _, sz, wt, _ in lines]
    gaps = [sz * 0.9 for _, sz, _, _ in lines]
    total = sum(f.size + g for f, g in zip(fonts, gaps)) - gaps[-1]
    y = (h - total) / 2
    for (text, sz, wt, col), f, g in zip(lines, fonts, gaps):
        d.text((w / 2, y + sz / 2), text, font=f, fill=col, anchor="mm"); y += sz + g
    im.save(out)

def main(out):
    caption("Export any date range as a formatted PDF (or CSV) for the care team", f"{out}/cap-export-1.png")
    caption("Daily glucose traces with meals marked, time in range, and every meal and dose as logged", f"{out}/cap-export-2.png")
    card([("Kitchen Carbs", 76, "SemiBold", INK), ("Carb counting and a shared log for a kid with type 1 diabetes", 28, "Regular", MUTED),
          ("Early alpha · built with AI · not a medical device", 24, "SemiBold", WARN)], f"{out}/card-title.png")
    card([("Kitchen Carbs", 60, "SemiBold", INK), ("github.com/aperetti/kitchen-carbs", 30, "Regular", ACCENT),
          ("Early alpha, built with AI. Not a medical device: check every number", 24, "SemiBold", WARN),
          ("against the label and your care team's plan.", 24, "SemiBold", WARN)], f"{out}/card-end.png")
    for key, title, sub in [("plate", "Build a plate", "Photo cards, real weights, carbs added up"),
                            ("summary", "Meal summary", "BG, the parent's own ratios, what was given"),
                            ("log", "The log", "CGM curves, edits, comments, manual entries"),
                            ("after", "After meals", "Every meal's glucose, side by side"),
                            ("manage", "Foods and photos", "Checked carbs, portions, styled photos"),
                            ("export", "Reports", "A PDF for the care team"),
                            ("settings", "Settings and sync", "Notifications and Tidepool"),
                            ("phone", "On a phone", "The same app, in your pocket")]:
        card([(title, 54, "SemiBold", INK), (sub, 26, "Regular", MUTED)], f"{out}/card-{key}.png")
    card([("On a phone", 54, "SemiBold", INK), ("The same app, in your pocket", 26, "Regular", MUTED)], f"{out}/phone-bg.png", w=760, pad_to=1280)


if __name__ == "__main__":
    main(sys.argv[1])
