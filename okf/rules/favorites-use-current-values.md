---
type: Rule
title: "Favorites use current values"
description: "A favorite stores portions and quantities, not carbs; carbs are worked out from today's food values, and a deleted portion is shown as missing, never silently dropped."
tags: [data, safety]
timestamp: 2026-10-27
status: draft
links:
  applies_to: [domain/favorite-plate.md]
  complements: [rules/snapshot-log-values.md]
---
# Favorites use current values
Opposite of the log on purpose: the log records what was served; a favorite is a shortcut for serving it again,
so it must reflect corrected carb values. If a portion was deleted, the favorite shows it as missing and
'Put on plate' adds only the items that still exist, saying which one was left out.
