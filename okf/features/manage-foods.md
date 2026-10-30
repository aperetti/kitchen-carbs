---
type: Feature
title: "Manage foods"
description: "Parent adds/edits foods and portions: carbs/100 g, source, weighed grams, verify."
tags: [feature, admin]
timestamp: 2026-10-26
status: draft
links:
  uses: [domain/tag.md, domain/food.md, domain/portion.md, domain/nutrition-source.md, domain/carb-value.md]
  constrained_by: [rules/provenance-required.md, rules/whole-gram-rounding.md, rules/cooking-ratio-measured.md]
---
# Manage foods
Carbs are typed for whatever amount the source gives ('17 g per 85 g'), with no default amount. That serving is kept as typed
(the form never rewrites it to per 100 g; carbs per 100 g is worked out behind it) and always becomes the first, default portion.
Label and barcode checks keep their serving the same way. Source defaults to 'Package label' for typed-in foods. Pick any number of tags per food; add, rename and remove tags.
Quick add makes portions as ½×, 1½×, 2× or a typed multiple of the main serving (okf/domain/portion.md).
Behind a simple parent PIN so the child doesn't change data by accident.
- Barcode (decided 29 Oct, for a package whose barcode changed or a food that had none): the food form has a Barcode
  row with the current digits, 'Scan' (the live camera, opened in the form; okf/features/food-lookup.md), 'Photo' and
  typing. A new code is looked up on Open Food Facts and the form shows that product's name and carbs next to the food's
  own, warning when they differ, so a changed recipe isn't missed. Nothing else on the food changes; 'Save food' keeps it.
- Each food says whether its carbs are as sold, dry / raw or cooked, and can keep a measured cooking ratio
  (dry and cooked weight of one batch) so the plate can take either weight (okf/domain/food.md, decided 28 Oct).
