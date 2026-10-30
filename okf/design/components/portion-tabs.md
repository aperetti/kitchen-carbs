---
type: component
title: "Portion tabs"
description: "Portion choices: listed in the food card details; the plate slider sets the weight."
tags: [design]
timestamp: 2026-10-30
status: draft
links:
  implements: [features/view-food.md]
  uses_tokens: [design/foundations/color.md, design/foundations/spacing.md]
---
# Portion choices
No longer buttons on the card (27 Oct). The card adds the serving; other portions show in the ⓘ details with their weight and carbs, and the plate's slider covers any amount.

Since 30 Oct a food with several portions opens a portion chooser when its card is tapped (okf/features/browse-foods.md):
a list of rows, each 56 px or taller with the portion's photo, name, weight and carbs. On a phone it is a sheet at the
bottom of the screen; on the tablet a small dialog.
