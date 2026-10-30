---
type: Feature
title: "View food"
description: "Tapping a food card adds its serving to the plate; the weight is then tuned on the plate."
tags: [feature]
timestamp: 2026-10-26
status: draft
links:
  uses: [domain/food.md, domain/portion.md, domain/photo.md, domain/carb-value.md]
  constrained_by: [rules/provenance-required.md, rules/estimated-photo-label.md, rules/no-dosing.md]
---
# View food
- The card is the food view: photo and name only (decided 27 Oct: the portion buttons were distracting). Tapping the
  card toggles it (decided 27 Oct): the first tap adds the food's serving (its first portion) to the plate, a second tap
  takes that food off the plate again, each with a short notice; the weight is then set on the
  plate with the slider, whose tick shows the serving's weight.
- ⓘ opens the details over the photo: each portion's weight and carbs, carbs per 100 g, source, verified or not,
  notes, the label photo, and 'Estimated photo' when the photo is a stand-in.
- 'Edit in Manage' sits right under the name in the details (decided 29 Oct; at the top so a phone needn't scroll the card), which opens that food in Manage → Foods; the parent PIN is
  asked first if Manage is locked.
