---
type: Feature
title: "Manual log entry"
description: "From the Log, add a timed entry with carbs, a BG reading and/or insulin given; entries sit between meals in the day and on the glucose curve."
tags: [feature]
timestamp: 2026-11-14
status: draft
links:
  uses: [domain/manual-entry.md, domain/meal-log.md, domain/insulin-settings.md]
  constrained_by: [rules/no-dosing.md, rules/same-day-edits.md, rules/glucose-units.md, rules/offline-queue.md]
---
# Manual log entry
- Log → 'Add entry', on the day shown: today, or an earlier day while earlier days can be changed
  (okf/rules/same-day-edits.md; marked 'Changed later'). Time defaults to now.
- Entry types (decided 14 Nov): 'Add entry' first shows a menu, one large button each with a line on what it is
  for: 'Correct BG' (BG and rapid-acting insulin, with the correction worked out), 'Basal' (long-acting insulin),
  'Carbs' (carbs not from the food list, e.g. juice for a low) and 'Something else' (the full form: any mix of BG,
  carbs, insulin of either kind and a note). Tapping one opens a form with only what that type needs, each with the
  time and a note; '‹ Entry types' goes back to the menu, dropping what was typed. The insulin kind is set by the
  type (Correct BG rapid-acting, Basal long-acting), so only 'Something else' asks for it. What is saved is an
  ordinary entry; the type only shapes the form.
- Correct BG (decided 13 Nov; its own entry type since 14 Nov): the form has the BG, the correction worked out from the parent's
  settings, the same way as the meal summary's (okf/features/meal-dose-summary.md, okf/rules/no-dosing.md): BG − target
  ÷ correction factor at the entry's time, insulin on board from Nightscout taken off (if fresh; otherwise it says none
  was), rounded down to the dose step and never below zero, each step on its own line. The form has no carbs box, and no
  carbs are counted. The BG box starts with the latest CGM reading when it is under 15 minutes old and the entry is for about now
  (decided 14 Nov), with a line under it: 'From the CGM: 169 ↗, 3 min ago. Type over it to use a meter reading.' An
  older reading is named with its age ('Latest CGM: 182, 40 min ago, too old to use') and the box left empty. Typed
  over, it is a meter reading; cleared, there is no BG and no correction. Saved as typed or as the CGM's, with its
  source (okf/domain/manual-entry.md). It is
  offered only for an entry at about now (within 15 minutes, today), since insulin on board is now's; for another
  time it says so and works nothing out. A correction in the last few hours (the recent-correction window) is named
  with a warning, as in the summary. BG at or under target: nothing to add, and it says so. No settings: it points to
  Manage → Settings. Under the total, '↓ Fill in 1.20 u' (scrolling the box into view) copies it into 'Rapid-acting insulin given' on a
  tap; until then the box stays as it was, and once filled it is an ordinary typed amount. The worked-out amount is
  never stored or sent. The note under the form says the app records what is entered and only
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
