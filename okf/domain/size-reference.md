---
type: Entity
title: "Size reference"
description: "A parent-defined photo of an everyday object with a known measurement (e.g. 'our 1-cup measuring cup, filled'), sent to Gemini so a generated photo shows the right amount."
tags: [domain, photos]
timestamp: 2026-10-27
status: draft
links:
  part_of: [domain/photo-style.md]
  guides: [domain/photo.md]
  governed_by: [rules/estimated-photo-label.md, rules/original-photo-kept.md]
---
# Size reference
- Fields: name ('Measuring cup'), measurement ('1 cup' / '240 mL' / '15 mL'), photo, order, and the dish it goes with:
  any dish (default), plate, bowl or dressing container (decided 27 Oct), e.g. 'our cereal bowl, filled to the line = 1 cup' goes with bowl.
- When a portion's 'Served in' is changed to a dish and the portion has no size reference (or one for another dish),
  the first reference for that dish is chosen; the parent can still change it. Gemini is told the measurement is shown in that dish.
- Each portion can choose one (default: none). Gemini gets the photo after the original and base photos, with the
  portion's label and weighed grams, and is told to use it for scale only and leave it out of the picture.
- It changes only how the photo looks. Carbs always come from the weighed grams; an estimated photo stays labelled.
