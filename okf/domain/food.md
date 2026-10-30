---
type: Entity
title: "Food"
description: "A single food as served, e.g. 'Pasta, cooked'. Has a carb density and one or more portions."
tags: [domain]
timestamp: 2026-10-26
status: draft
links:
  has: [domain/portion.md]
  sourced_from: [domain/nutrition-source.md]
  labelled_by: [domain/tag.md]
---
# Food
- Fields: name, tags (several), carbs per 100 g, serving (carbs and grams exactly as the source gives them, e.g.
  17 g per 85 g; empty for per-100 g sources such as USDA), source, trust (draft | parent-verified), notes.
- Barcode (decided 29 Oct), optional: the package's EAN / UPC digits (8 to 14), its own field. It identifies the
  package; it is not the source of the carbs, so changing it never changes the carbs, the source or the confirmations.
  Foods added from a barcode get it filled in; foods from before 29 Oct took it from their source text.
- The serving is kept as entered and shown again when editing; carbs per 100 g is worked out from it (decided 27 Oct).
- Variants that differ in carbs (whole-wheat vs white pasta) are **separate foods**, not notes.
- State of the carb values (decided 28 Oct): **as sold** (default: ready to eat, nothing changes its weight),
  **dry / raw** (pasta, rice, oats, raw meat: what most packets give) or **cooked**. The portions are weights in that
  same state. The form says it in the carbs sentence ('42 g carbs per 56 g of [dry / raw food]', decided 28 Oct, replacing
  separate radio buttons that were unclear) and then explains what to put on the scale ('Weigh it dry / raw, before
  cooking: 56 g on the scale = 42 g carbs').
- Cooking ratio, **required** for dry / raw or cooked foods (decided 28 Oct, was optional): one batch the parent weighed
  both ways, e.g. 100 g dry → 240 g cooked, kept as those two weights with the date (okf/rules/cooking-ratio-measured.md).
  Ratio = cooked ÷ dry. The form asks for it right under the carbs line, as soon as dry / raw or cooked is chosen, and a
  dry / raw or cooked food can't be saved without it. Foods saved earlier without one ask for it the next time they're edited.
  With it the plate can take either weight: carbs per 100 g cooked = carbs per 100 g dry ÷ ratio.
- Fiber (decided 28 Oct), optional: grams of dietary fiber for the same amount as the carbs ('22 g carbs per 30 g,
  including 3 g fiber'), kept as typed beside the serving, with fiber per 100 g worked out from it, and the date it was
  checked. It comes from the same source as the carbs. It is shown for reference only: the plate, the log and every
  carb number stay total carbohydrate, and nothing subtracts it (okf/rules/no-dosing.md; whether to count fiber is the
  care team's call). Fiber can't be more than the amount of food; more fiber than carbs gets a warning, not a refusal
  (European labels list carbs without fiber).
