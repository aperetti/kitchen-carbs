---
type: Rule
title: "Cooking ratio is measured, never assumed"
description: "Dry and cooked weights are converted only with a ratio the parent weighed for that food; the app never supplies a typical ratio."
tags: [safety, data]
timestamp: 2026-10-28
status: draft
links:
  applies_to: [domain/food.md, domain/plate.md]
  extends: [rules/provenance-required.md]
---
# Cooking ratio is measured, never assumed
Pasta can be ×2 or ×2.8 depending on the shape and the cooking time, so a 'typical' ratio could be off by a third.
- The ratio comes from two weights of one batch (dry or raw before, cooked after), entered by a parent, kept with the
  date as its provenance. It is shown wherever it is used ('×2.4'); the date it was weighed is shown on the food, not on the plate (decided 28 Oct).
- A dry / raw or cooked food needs its ratio to be saved (decided 28 Oct). An older food without one can only be
  weighed in the state its carbs are for until it's edited; the plate says which.
- The plate states which weight was entered (dry or cooked), and the log keeps that in the item's label and the carbs
  per 100 g actually used (okf/rules/snapshot-log-values.md).
