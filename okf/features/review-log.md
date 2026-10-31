---
type: Feature
title: "Review log"
description: "See today's meals and earlier days with daily totals."
tags: [feature]
timestamp: 2026-10-26
status: draft
links:
  uses: [domain/meal-log.md, domain/meal.md]
  constrained_by: [rules/snapshot-log-values.md, rules/same-day-edits.md]
---
# Review log
Day view; previous/next day.
- Change when: every meal and entry's details have its date and time, editable on any day; a moved entry is marked
  with where it was first logged (okf/rules/same-day-edits.md, decided 28 Oct).
- Unsaved time (decided 31 Oct): as soon as the date or time differs from the saved one, both boxes get a warn-coloured
  border, 'Change' becomes the primary button, and a line under them says 'Not saved yet. Tap Change to save it.' with
  'Undo' to put the saved date and time back. Setting them back by hand clears it.
