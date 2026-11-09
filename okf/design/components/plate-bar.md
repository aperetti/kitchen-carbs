---
type: component
title: "Plate bar"
description: "Phones: bottom bar with item count, food weight and total. Tablets and computers: the full plate beside the food grid, with a draggable divider."
tags: [design]
timestamp: 2026-10-26
status: draft
links:
  implements: [features/build-plate.md, features/log-meal.md, features/view-food.md]
  uses_tokens: [design/foundations/color.md, design/foundations/spacing.md]
---
# Plate bar and plate pane
- Phones (under 900 px wide): a bottom bar with the item count, the total food weight and the carb total; 'Open plate'
  goes to the Plate screen.
- Tablets and computers (decided 27 Oct): no separate Plate screen. The Foods screen is split, food grid on the left and
  the whole plate (weight sliders, totals, Save to log) on the right, 50/50 to start. A vertical divider between
  them can be dragged (or moved with the arrow keys) from 30 % to 75 %; the split is remembered on that device.
- Plate rows follow the pane's own width (decided 28 Oct, after names and carbs overlapped in a thin pane): up to
  760 px the slider takes its own line with the weight field and − / + on the next; up to 600 px the photo sits
  beside the name, the portion count and the carbs stacked in one column, with × in the corner.
  The total below: the number, then Time and Save to log side by side, each given a minimum width so the button
  never wraps; 'Clear plate · Pin as favorite' always stay together. Under 360 px the photo shrinks to 64 px and
  the 'Weight' word is dropped so the grams and − / + still share a line.
