---
type: Feature
title: "Annotate meal"
description: "Mark how much of a logged meal was eaten and add comments."
tags: [feature]
timestamp: 2026-10-27
status: draft
links:
  uses: [domain/meal.md, domain/meal-note.md]
  constrained_by: [rules/same-day-edits.md, rules/no-dosing.md]
---
# Annotate meal
From the log, tap a meal: choose an 'eaten' option, add a comment. Comments show with their time.
- Meal details (decided 29 Oct): BG, insulin (Bolus or Basal) and when it was given, and how long the meal took to eat
  (okf/domain/meal.md). Editable in place on the meal and saved with the log's one Save button (okf/features/review-log.md), on earlier days too while
  the setting allows it (okf/rules/same-day-edits.md). All optional.
