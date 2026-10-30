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
