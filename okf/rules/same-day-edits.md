---
type: Rule
title: "Edits to earlier days"
description: "Earlier days can be changed while a parent setting allows it (on by default); every later change is marked. With the setting off, only today is editable."
tags: [data, safety]
timestamp: 2026-10-27
status: draft
links:
  applies_to: [domain/meal.md, domain/meal-note.md, domain/meal-log.md]
---
# Edits to earlier days
Decided 29 Oct, replacing 'older days are read-only': the parent wants to fix past numbers, and to be able to lock them.
- Manage → Settings → Log: 'Allow changes to earlier days', behind the parent PIN, **on** by default.
- On: a meal or manual entry from an earlier day can be changed like today's: the meal's BG, insulin and timings, how
  much was eaten, comments, adding a forgotten manual entry to that day, and deleting. The weighed foods and their
  carbs in a saved meal are not editable on any day (okf/rules/snapshot-log-values.md).
- Every change made after the record's own day is marked so the history stays trustworthy for the care team:
  the meal or entry shows 'Changed later, Thu 30 Oct, 21:50' (the last such change) in the log, its details and the
  CSV export; a comment added later carries its own date. An entry added to an earlier day is marked the same way.
- Off: earlier days are read-only, as before 29 Oct. The server refuses the change, not just the screen.
- Either way (decided 28 Oct): the date and time of any meal or manual entry, on any day, can be changed (logged after
  midnight, or entered late). The entry keeps where it was first logged and shows 'Moved from Tue 27 Oct, 18:05' in
  the log, its details and the CSV export. Moving it back to that original date and time clears the mark. A move to a
  future day is refused.
