---
type: Value
title: "Carb value"
description: "Grams of carbohydrate for a portion: round(grams × carbsPer100g / 100)."
tags: [domain, safety]
timestamp: 2026-10-26
status: draft
links:
  derived_from: [domain/portion.md, domain/nutrition-source.md]
  governed_by: [rules/provenance-required.md, rules/whole-gram-rounding.md]
---
# Carb value
Computed by the server when a portion is saved, stored, and shown in whole grams.
Changing a food's carbs/100 g recomputes its portions but never past log entries
(see [snapshot rule](../rules/snapshot-log-values.md)).
