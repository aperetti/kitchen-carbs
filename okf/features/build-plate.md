---
type: Feature
title: "Build plate"
description: "Add portions, tune each to its weighed grams, and see the running carb total and food weight."
tags: [feature]
timestamp: 2026-10-26
status: draft
links:
  uses: [domain/plate.md, domain/portion.md, domain/carb-value.md]
  constrained_by: [rules/no-dosing.md, rules/whole-gram-rounding.md, rules/cooking-ratio-measured.md]
---
# Build plate
On phones a persistent bar shows the item count, total food weight and carb total, and opens the plate. On tablets and computers the plate sits beside the food grid (okf/design/components/plate-bar.md), so tapping a card and tuning its grams happen on one screen.
Weights can come from a connected kitchen scale (okf/features/kitchen-scale.md).
- No time box on the plate (decided 8 Nov): the meal's date and time are set in the meal summary. 'Save to log
  shows the meal summary first… Enter the total in the pump or meter as usual.' is behind an ⓘ beside 'Plate total'.
