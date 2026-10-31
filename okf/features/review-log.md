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
- One Save for every change (decided 31 Oct, replacing the same day's 'Change' button and 'Not saved yet' line): a
  meal's details are all editable in place: date and time, BG, insulin and its timing, time to eat, how much was
  eaten, the total carbs (with its reason) and a new comment. Nothing is saved as it is typed or tapped. As soon as
  anything differs from what is saved, the changed parts get a warn-coloured border and a bar floats at the bottom of
  the meal: 'Unsaved changes' with 'Save changes' and 'Discard'. Putting everything back by hand hides it.
  An entry works the same way for its date, time, BG, carbs, insulin and note.
- Save changes checks everything first (BG 20–600, insulin in 0.05 u steps, a reason of 3+ characters when the
  carbs changed, no future date) and saves nothing until it all passes; the problem shows in the bar. Then it saves
  the details, eaten, carbs and comment, and the date and time last, and follows the meal to its day.
- While there are unsaved changes, choosing another meal, entry or day, or adding an entry, is held back with
  'Save or discard the changes first', so nothing typed is lost without a choice.
