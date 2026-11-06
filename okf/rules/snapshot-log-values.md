---
type: Rule
title: "Snapshot log values"
description: "A logged meal keeps the food, grams and carbs as they were when it was saved."
tags: [data, safety]
timestamp: 2026-11-05
status: draft
links:
  applies_to: [domain/meal.md, domain/meal-log.md]
---
# Snapshot log values
Editing a food later never rewrites history.
- A discrepancy found later (decided 29 Oct) is fixed by correcting the meal's **total** carbs, never its items: the
  foods, grams and carbs saved stay as they were, beside the corrected total (okf/domain/meal.md).
- Changing the foods themselves (decided 5 Nov): in the meal's Edit, a parent can change a food's weight, remove a
  food, or add one from the food list. A reweighed food keeps the carbs per 100 g it was saved with; an added food is
  snapshotted as it is now. Each change is written into the meal's comments ('Foods changed: Pasta 120 → 90 g; added
  Apple 90 g. Carbs 45 → 52 g'), so the history still shows what was first logged. A corrected total is replaced by
  the foods' new total, and the comment says so.
