---
type: Entity
title: "Meal"
description: "A saved plate with time, items, total carbs and an optional note."
tags: [domain]
timestamp: 2026-10-26
status: draft
links:
  part_of: [domain/meal-log.md]
  has: [domain/meal-note.md, domain/meal-glucose.md, domain/meal-rating.md]
  governed_by: [rules/snapshot-log-values.md, rules/same-day-edits.md]
---
# Meal
Each item stores food name, portion label, grams, quantity and carbs **as they were when saved**.
Corrected total (decided 29 Oct, for a discrepancy found later): 'Change total carbs' on a logged meal takes the new
total and a reason, which is required. The items keep their saved carbs; the meal shows the corrected total with
'corrected from 65 g', and the day's totals, stats and the export use it (the export also keeps the original). The
reason is added as a comment, dated, saying 'Carbs changed from 65 to 55 g: …'. Setting it back to the items' own total
removes the correction (with its own comment). It follows the rules for changing earlier days
(okf/rules/same-day-edits.md), so a correction on an earlier day is also marked 'Changed later'.
An item entered by hand (okf/domain/plate.md) stores its description as the name, 'Carbs entered by hand' as the
label and the carbs as typed, with no weight; the log and the export show it that way.

Optional details that go with the meal (decided 29 Oct), each left empty unless someone enters it:
- BG at the meal, in mg/dL, and where it came from: the CGM (under 15 minutes old) or a meter.
- Insulin given for the meal: units (to 0.05 u) and Bolus or Basal. Only what a person typed (okf/rules/no-dosing.md).
- When the insulin was given: at the start of the meal, or a number of minutes before or after starting to eat (0–120).
  A new entry starts on **Before eating, 15 min** (decided 29 Oct: the usual pre-bolus); a saved one shows what was saved.
- How long the meal took to eat, in minutes (1–240).
They are entered in the meal summary when saving, and can be added or changed from the log, on earlier days too
while the setting allows it (okf/rules/same-day-edits.md). The day's insulin totals include meal insulin; insulin and a meter BG show on the meal's
glucose graph at their own times; the export has them on each of the meal's rows.

A meal can also carry the parent's rating of its GI and speed of rise (okf/domain/meal-rating.md, decided 1 Nov).
