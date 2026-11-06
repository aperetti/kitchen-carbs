---
type: Entity
title: "Portion"
description: "A named, weighed amount of a food (e.g. '1 cup, 140 g') with its carb value and photos."
tags: [domain]
timestamp: 2026-10-26
status: draft
links:
  part_of: [domain/food.md]
  has: [domain/carb-value.md, domain/photo.md]
---
# Portion
- Fields: label, grams (weighed), carbs (derived), display order, container (auto | plate | bowl | dressing), size reference (optional).
- grams comes from the kitchen scale at photo time, never estimated. It is in the food's own state (decided 28 Oct): for a
  dry / raw food the Portions table heads it 'Grams, dry / raw' and, with a cooking ratio, shows the cooked weight beside it.
- Label = an amount then a unit (decided 28 Oct): '1 cup', '2 slices', '½ serving', '1 1/3 cup', '1.5 Tbsp'. The amount is
  a whole number, a decimal, a fraction (1/3, 1 1/3) or ¼ ½ ¾ ⅓ ⅔ ⅛; the unit starts with a letter. Refused otherwise,
  so every portion can be counted on the plate. Migration 5 rewrote the old '½ × 1 serving' labels as '½ serving';
  logged meals keep their labels (okf/rules/snapshot-log-values.md).
- Multiple of a serving (decided 27 Oct): a portion can be made as ½×, 1½×, 2× or any multiple (0.1 to 10) of a weighed
  portion, by default the food's serving (the first portion). Its grams are that weighed amount times the multiple, its label
  is the multiplied amount in the same unit ('1½ servings', 1.5 × '4 Nuggets' = '6 Nuggets'), and after that it is an ordinary portion: it can be renamed, reweighed or photographed. The new portion shows the
  serving's photo (its styled photo first) straight away, with no call to Gemini (decided 6 Nov, replacing the estimate started
  at once); the serving's note for Gemini, container and size reference are copied.
- Any added portion (decided 6 Nov): a portion added later, as a multiple or by hand, uses its parent portion's photo by
  default: the one it is a multiple of, else the serving, else any portion with a photo. It is labelled 'Same photo as
  another portion' (okf/rules/estimated-photo-label.md) until a photo of that amount is uploaded or estimated.
