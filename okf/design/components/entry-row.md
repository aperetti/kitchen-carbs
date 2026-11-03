---
type: component
title: "Entry row"
description: "Log row for a manual entry: time, then 'BG 142 · 2.5 u rapid · 15 g carbs', note underneath; no carb figure in the accent colour unless carbs were entered."
tags: [design]
timestamp: 2026-10-27
status: draft
links:
  implements: [features/manual-log.md]
  uses_tokens: [design/foundations/color.md, design/foundations/typography.md]
---
# Entry row
Insulin and BG are graphite text, never accent, so they can't be confused with carb numbers.
- A meal row lists each food with its **carbs**, not its weight (decided 29 Oct): 'Toast, whole-wheat 22 g carbs'. The meal's
  details give each food's carbs first and the weighed grams after, in brackets.
- Modified mark (decided 31 Oct): a meal or entry that was moved or changed after its day shows a small pencil icon
  (✎, warn colour, labelled 'Modified' for screen readers) after its time, in the row and in its details. No dates and
  no 'moved from' time in the log; those stay in the CSV export (okf/rules/same-day-edits.md).
- A meal whose total carbs were changed by hand says 'Carbs edited' in warn colour in its row (okf/domain/meal.md).
- A meal row shows its comments' text, newest last, instead of a comment count, so the reason for a carbs edit is
  visible without opening the meal. Long comments are cut to two lines.
- A meal row's second line is short (decided 2 Nov, the log was too busy): the BG saved with the meal and the sensor
  two hours later, then insulin: 'BG 182 → 2 h 169 · 2.5 u bolus'. 'Eaten' and fiber are only in the meal's details.
  The foods keep their carbs on the first line, which the family finds handy at a glance. 'BG' is the reading typed or taken from the CGM at mealtime; '2 h'
  is the sensor two hours later.
