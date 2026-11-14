---
type: Feature
title: "Manual log entry"
description: "From the Log, add a timed entry with carbs, a BG reading and/or insulin given; entries sit between meals in the day and on the glucose curve."
tags: [feature]
timestamp: 2026-11-13
status: draft
links:
  uses: [domain/manual-entry.md, domain/meal-log.md, domain/insulin-settings.md]
  constrained_by: [rules/no-dosing.md, rules/same-day-edits.md, rules/glucose-units.md, rules/offline-queue.md]
---
# Manual log entry
- Log → 'Add entry', on the day shown: today, or an earlier day while earlier days can be changed
  (okf/rules/same-day-edits.md; marked 'Changed later'). Time defaults to now.
- Correct BG (decided 13 Nov): under the insulin boxes, 'Correct BG' opens a correction worked out from the parent's
  settings, the same way as the meal summary's (okf/features/meal-dose-summary.md, okf/rules/no-dosing.md): BG − target
  ÷ correction factor at the entry's time, insulin on board from Nightscout taken off (if fresh; otherwise it says none
  was), rounded down to the dose step and never below zero, each step on its own line. No carbs are counted, even when
  carbs are typed in the entry. The BG is the one typed in the entry, else a CGM reading under 15 minutes old. It is
  offered only for an entry at about now (within 15 minutes, today), since insulin on board is now's; for another
  time it says so and works nothing out. A correction in the last few hours (the recent-correction window) is named
  with a warning, as in the summary. BG at or under target: nothing to add, and it says so. No settings: it points to
  Manage → Settings. Beside the total, '← Fill in 1.20 u' copies it into 'Insulin given' and picks Rapid-acting on a
  tap; until then the box stays as it was, and once filled it is an ordinary typed amount. The worked-out amount is
  never stored or sent. 'Hide' closes it. The note under the form says the app records what is entered and only
  works out a correction when asked.
- Tapping 'Add entry' brings the new entry's form into view (decided 31 Oct: on a phone it opened below the day's
  list, out of sight), scrolling smoothly unless the device asks for reduced motion.
- Editing an entry (decided 31 Oct): its BG, carbs, insulin (amount and rapid or long-acting) and note are editable
  in place, on any day changes are allowed (okf/rules/same-day-edits.md), so a wrong number can be fixed and
  insulin or carbs added later. Saved with the log's one Save bar together with the date and time
  (okf/features/review-log.md); the same checks as adding apply, and an entry can't be emptied (delete it instead).
  A change after the entry's day is marked ✎. Editing never notifies phones (okf/features/notify-family.md).
- The day shows insulin totals by kind as plain facts. No ratios, no 'insulin on board', no suggestions.
- On a meal's glucose curve, meter BG readings show as squares and insulin as labelled ticks.
- Exported in the CSV with meals.
