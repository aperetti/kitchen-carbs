---
type: Feature
title: "Meal summary and dose"
description: "Tapping 'Save to log' opens a summary of the plate with the insulin worked out from the parent's ratios, the BG and insulin on board, step by step."
tags: [feature, safety]
timestamp: 2026-11-05
status: draft
links:
  uses: [domain/plate.md, domain/insulin-settings.md, domain/glucose-reading.md]
  constrained_by: [rules/no-dosing.md, rules/glucose-units.md, rules/nightscout-sends-what-was-logged.md, rules/whole-gram-rounding.md]
  depends_on: [architecture/nightscout-client.md]
---
# Meal summary and dose
Decided 29 Oct. 'Save to log' on the plate opens a modal before anything is saved.
- The meal: each food with its weight and carbs, the time, and the carb total.
- BG: the latest CGM reading with its trend arrow and age, filled in only if it is under 15 minutes old. Otherwise
  the box is empty and says why. It can always be overwritten with a meter reading; the numbers update as it is typed.
  When the box holds a fresh CGM reading, where it came from ('From the CGM: 217 mg/dL ↑, just now. Type over it to
  use a meter reading.') is behind an ⓘ beside the BG label, shown in a small popover when tapped (decided 8 Nov, to
  keep the summary short). The other BG lines (too old, the meal set away from now, typed in, no CGM) stay in view,
  because they say why the box isn't the CGM's.
- Insulin on board from Nightscout, with its age. Shown even when it isn't used (BG at or below target).
- The dose, large, right under the meal (decided 29 Oct: on a phone it was below the fold), then 'How it's worked out', one line each.
  The BG box is one of those lines, just above Insulin on board, the same size as the text around it (decided 8 Nov;
  it was a large box above the dose):
  - Carbs: 62 g ÷ 15 = 4.13 u
  - Correction: (210 − 120) ÷ 50 = 1.80 u
  - Insulin on board: −0.60 u (off the correction only, never below zero)
  - Total 5.33 u → **5.30 u** (rounded down to 0.05 u, or the step set in the insulin settings: 5.00 u at 0.5 u)
- BG below target: the negative correction lowers the carb dose, never below zero. Below 70 mg/dL the BG shows as low.
- 'Add a BG correction' (decided 5 Nov): a switch beside the Correction step, shown when there is a BG above target.
  Off, the correction (and the insulin on board taken off it) is left out and the dose is the carbs' only; the
  Correction line says it was left out. A BG under target still lowers the dose either way. On to start with, unless a
  correction was given within the recent-correction window (okf/domain/insulin-settings.md, 3 hours until changed):
  then it starts off with a line naming it ('1.5 u correction at 2:10 PM, 1 h 20 min ago, from Nightscout'), and
  turning it on shows a warning that a correction was given recently and insulin may still be acting, to check
  against the pump and the care team's plan. A recent correction is a Nightscout 'Correction Bolus', or a rapid-acting
  insulin entry in the log with no carbs. The switch isn't saved; it resets each time the summary opens.
- No BG: carbs only, and it says no correction was added. No settings: the summary shows the meal, says the ratios
  aren't set up, and links to Manage → Settings.
- 'What was given (optional)', under the steps (decided 29 Oct): insulin given (empty, never filled in from the dose),
  Bolus or Basal, how many minutes before the meal's time it was given (0 = at the meal time; starts at BG ÷ 10, 0
  under 80 mg/dL, 15 with no BG, see okf/domain/meal.md). How long the meal took to eat was asked here until 8 Nov;
  it was removed as not useful.
  The BG in the box is saved with the meal as its BG, marked CGM or meter.
- Eat time estimated from the BG (decided 4 Nov): a new plate's time isn't just the moment the first food goes on.
  It is now plus the same wait the insulin box starts at (okf/domain/meal.md): BG ÷ 10 minutes, none under 80 mg/dL,
  and 15 minutes when there is no BG (no CGM reading under 15 minutes old). When the summary opens, the time is worked
  out again from that moment, and it follows the BG box (CGM or typed) until someone changes the time in the summary
  (the plate's own time box was removed 8 Nov: the time is set here); after that it stays as set. A wait that would cross midnight leaves the time at now.
  A meal set up to 120 minutes ahead still takes the CGM's current reading as its BG: it is the BG at the bolus.
- When (decided 31 Oct; moved 8 Nov to last, just above 'Save to log'): a date and a time, starting at today and the plate's time, so a meal
  saved late (after the bolus, or the next morning) goes in at the right moment. The date can't be in the future.
  Changing the time works the dose out again with that time's ratios, keeps the plate's time in step, and shows in the
  heading. When the meal is set more than 15 minutes before now (or more than 120 after), the BG box isn't filled in from the CGM (that reading
  is from now, not the meal) and a line says so: type the meter reading from then. Insulin on board is still now's.
  A meal saved to an earlier day is marked ✎ like an entry added to an earlier day (okf/rules/same-day-edits.md).
- Buttons: 'Save to log' saves the meal with these details; 'Back to plate' closes the modal. The dose isn't saved or sent anywhere.
- 'Worked out from your settings (changed …). Check it against the pump before giving.': behind an ⓘ beside
  'Insulin for this meal', in the same tap-to-open popover (decided 8 Nov; it was a footnote).
