---
type: Entity
title: "Meal log"
description: "History of meals by day, with daily totals; exportable."
tags: [domain]
timestamp: 2026-10-26
status: draft
links:
  contains: [domain/meal.md, domain/manual-entry.md]
---
# Meal log
Meals can be edited or deleted on the same day, and on earlier days while the parent setting allows it, each later
change marked (see same-day-edits).
Deleting is soft (decided 29 Oct): a deleted meal or manual entry is kept with the time it was deleted and drops out
of the log, totals, glucose graphs, stats and the CSV export. The bottom of its day lists 'Deleted (n)' with each one's
time, what it was and when it was deleted, and 'Restore' puts it back as it was. Deleting and restoring follow the
same rule as other changes (okf/rules/same-day-edits.md): on an earlier day they need the setting on, and a restore
there is marked 'Changed later'. Nothing is ever erased for good from the app.
