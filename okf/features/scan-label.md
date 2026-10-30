---
type: Feature
title: "Scan a nutrition label"
description: "Photograph a Nutrition Facts panel; Gemini reads it and a pre-filled new food (with a '1 serving' portion) opens beside the label for the parent to check and save."
tags: [feature, admin]
timestamp: 2026-10-27
status: draft
links:
  uses: [domain/nutrition-label.md, domain/food.md, domain/portion.md, domain/nutrition-source.md, domain/carb-value.md]
  constrained_by: [rules/label-reading-needs-check.md, rules/provenance-required.md, rules/whole-gram-rounding.md]
---
# Scan a nutrition label
1. Manage → Foods → Add a food → Look up → 'Photograph the nutrition label' (decided 27 Oct: no separate tab; it sat beside barcode scanning and read as a repeat) → take or choose a photo.
2. Server stores the label photo and asks Gemini for the printed values (structured JSON, nulls when unreadable).
3. Review: label photo left; name, tags, serving grams, carbs per serving, portion name right; carbs/100 g worked out live.
4. Confirm serving size and total carbohydrate (two separate ticks, each showing the value). Save creates the food (source: Package label, with the photo) and its first portion; then add plate photos as usual.
