---
type: Entity
title: "Meal note"
description: "How much of a meal was actually eaten (all / most / half / little / none) plus free-text comments."
tags: [domain]
timestamp: 2026-10-27
status: draft
links:
  part_of: [domain/meal.md]
  governed_by: [rules/same-day-edits.md]
---
# Meal note
- eaten: all | most | half | little | none (default: not set)
- comments: list of {time, text}, so you can add "left the crusts" or "had seconds 20 min later"
- Carb values are never adjusted automatically from 'eaten'; it is a record, not a calculation.
