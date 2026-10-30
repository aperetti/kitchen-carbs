---
type: Entity
title: "Nutrition label"
description: "A photo of a package's Nutrition Facts panel and the values read from it: product name, serving size, grams per serving, total carbohydrate, fiber, sugars."
tags: [domain, safety]
timestamp: 2026-10-27
status: draft
links:
  supports: [domain/nutrition-source.md, domain/food.md]
  governed_by: [rules/label-reading-needs-check.md]
---
# Nutrition label
- The photo is kept with the food as its source, so anyone can look at the label later.
- Carbs per 100 g = total carbohydrate per serving ÷ grams per serving × 100 (or the per-100 g column when printed).
- **Total** carbohydrate is used. Fiber is shown for information only; whether to subtract it is a care-team decision, not the app's.
- A serving given only as a volume ("1 cup (240 mL)") has no gram weight; the parent weighs or enters it.
