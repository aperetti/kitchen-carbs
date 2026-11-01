---
type: Feature
title: "Meal summary and dose"
description: "Tapping 'Save to log' opens a summary of the plate with the insulin worked out from the parent's ratios, the BG and insulin on board, step by step."
tags: [feature, safety]
timestamp: 2026-10-29
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
- Insulin on board from Nightscout, with its age. Shown even when it isn't used (BG at or below target).
- The dose, large, right under the BG (decided 29 Oct: on a phone it was below the fold), then 'How it's worked out', one line each:
  - Carbs: 62 g ÷ 15 = 4.13 u
  - Correction: (210 − 120) ÷ 50 = 1.80 u
  - Insulin on board: −0.60 u (off the correction only, never below zero)
  - Total 5.33 u → **5.30 u** (rounded down to 0.05 u)
- BG below target: the negative correction lowers the carb dose, never below zero. Below 70 mg/dL the BG shows as low.
- No BG: carbs only, and it says no correction was added. No settings: the summary shows the meal, says the ratios
  aren't set up, and links to Manage → Settings.
- 'What was given (optional)', under the steps (decided 29 Oct): insulin given (empty, never filled in from the dose),
  Bolus or Basal, when it was given (before, at the start, after, with minutes), and how long the meal took to eat.
  The BG in the box is saved with the meal as its BG, marked CGM or meter.
- When (decided 31 Oct): a date and a time under the meal list, starting at today and the plate's time, so a meal
  saved late (after the bolus, or the next morning) goes in at the right moment. The date can't be in the future.
  Changing the time works the dose out again with that time's ratios, keeps the plate's time in step, and shows in the
  heading. When the meal is set more than 15 minutes from now, the BG box isn't filled in from the CGM (that reading
  is from now, not the meal) and a line says so: type the meter reading from then. Insulin on board is still now's.
  A meal saved to an earlier day is marked ✎ like an entry added to an earlier day (okf/rules/same-day-edits.md).
- Buttons: 'Save to log' saves the meal with these details; 'Back to plate' closes the modal. The dose isn't saved or sent anywhere.
- Footnote: 'Worked out from your settings (changed …). Check it against the pump before giving.'
