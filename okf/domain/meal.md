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

Fiber (decided 2 Nov), for reference only: each weighed item also keeps its food's fiber per 100 g as it was when saved,
in the same cooked or dry state as its carbs, so a later change to the food doesn't rewrite the log. The meal's fiber
is the sum over its items ('including 6.5 g fiber', to 0.1 g). Items whose food has no fiber, and items entered by
hand, have none, and the meal says which foods ('fiber not known for Juice'). Fiber is never subtracted from the carbs
and a corrected carb total doesn't change it (okf/domain/food.md, okf/rules/no-dosing.md). Meals saved before 2 Nov
got their fiber once from the food as it was that day. A meal item with no fiber gets it later when its food's fiber
is filled in (okf/features/fill-in-fiber.md); one that has fiber keeps it.

Optional details that go with the meal (decided 29 Oct), each left empty unless someone enters it:
- BG at the meal, in mg/dL, and where it came from: the CGM (under 15 minutes old) or a meter.
- Insulin given for the meal: units (to 0.05 u) and Bolus or Basal. Only what a person typed (okf/rules/no-dosing.md).
- When the insulin was given, counted from the meal's time (decided 2 Nov, replacing the Before eating / At the start /
  After starting switches): one box, 'Bolus given N min before the meal', 0 to 120, where 0 means at the meal time.
  It can't be after the meal. A new entry starts at the BG ÷ 10, rounded (BG 150: 15 min), 0 when the BG is under
  80 mg/dL, or 15 when the BG isn't known (decided 4 Nov, was 0), and follows the BG box until the minutes are typed; a saved one shows what was saved. A
  meal saved before 2 Nov with insulin after starting keeps it and says so, until the minutes are changed.
  This is the family's own timing rule as a starting value, not advice; the box can always be changed.
- How long the meal took to eat, in minutes (1–240). No longer asked (8 Nov); meals that have it keep it, and it
  still shows in the log and the export.
They are entered in the meal summary when saving, and can be added or changed from the log, on earlier days too
while the setting allows it (okf/rules/same-day-edits.md). The day's insulin totals include meal insulin; insulin and a meter BG show on the meal's
glucose graph at their own times; the export has them on each of the meal's rows.

A meal can also carry the parent's rating of its GI and speed of rise (okf/domain/meal-rating.md, decided 1 Nov).
Foods changed later (decided 5 Nov): a logged meal's foods can be reweighed, removed or added in Edit; each change is
written into the comments and a corrected total gives way to the foods' new total (okf/rules/snapshot-log-values.md).
