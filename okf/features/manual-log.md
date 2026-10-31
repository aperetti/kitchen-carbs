---
type: Feature
title: "Manual log entry"
description: "From the Log, add a timed entry with carbs, a BG reading and/or insulin given; entries sit between meals in the day and on the glucose curve."
tags: [feature]
timestamp: 2026-10-27
status: draft
links:
  uses: [domain/manual-entry.md, domain/meal-log.md]
  constrained_by: [rules/no-dosing.md, rules/same-day-edits.md, rules/glucose-units.md, rules/offline-queue.md]
---
# Manual log entry
- Log → 'Add entry', on the day shown: today, or an earlier day while earlier days can be changed
  (okf/rules/same-day-edits.md; marked 'Changed later'). Time defaults to now.
- Tapping 'Add entry' brings the new entry's form into view (decided 31 Oct: on a phone it opened below the day's
  list, out of sight), scrolling smoothly unless the device asks for reduced motion.
- The day shows insulin totals by kind as plain facts. No ratios, no 'insulin on board', no suggestions.
- On a meal's glucose curve, meter BG readings show as squares and insulin as labelled ticks.
- Exported in the CSV with meals.
