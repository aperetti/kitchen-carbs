---
type: Rule
title: "Label reading needs a check"
description: "Values read from a label photo are never saved until a parent has seen them next to the label; the parent must confirm the serving size and total carbohydrate before saving."
tags: [safety, data]
timestamp: 2026-10-27
status: draft
links:
  applies_to: [domain/nutrition-label.md, domain/carb-value.md]
  extends: [rules/provenance-required.md]
---
# Label reading needs a check
Applies equally to values looked up in USDA or Open Food Facts (okf/features/food-lookup.md): they arrive as
suggestions and are confirmed against the label or source before saving.
- The review screen always shows the label photo beside the numbers.
- The parent must separately confirm the **serving size** (grams per serving) and the **total carbohydrate** per serving
  against the photo. Save stays disabled until both are confirmed, and changing either number clears its confirmation.
- Warnings are shown when: the photo isn't a nutrition label, carbs or serving grams can't be read,
  carbs exceed the serving weight, or the printed per-100 g value disagrees with the per-serving maths.
- Nothing is guessed: unreadable values are left empty for the parent to fill.
- Fiber (decided 28 Oct) is read with the carbs and confirmed with the same tick ('Total carbohydrate is 24 g per serving,
  including 3 g fiber'); changing the fiber clears that tick. Fiber filled in later for an existing food needs its own
  tick per food (okf/features/fill-in-fiber.md).
