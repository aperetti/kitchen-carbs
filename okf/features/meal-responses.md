---
type: Feature
title: "After meals: post-meal responses"
description: "Every logged meal's glucose from 0 to 3 hours after eating, lined up at the meal time, with its rise, time to peak, where it was at 2 and 3 hours and the insulin typed for it; repeats of a food are grouped to compare."
tags: [feature, nightscout]
timestamp: 2026-11-04
status: draft
links:
  uses: [domain/meal.md, domain/meal-glucose.md, domain/glucose-reading.md, domain/target-range.md, domain/food.md]
  constrained_by: [rules/descriptive-stats-only.md, rules/sensor-coverage.md, rules/no-dosing.md]
---
# After meals: post-meal responses
Decided 4 Nov. A page reached from the Log ('After meals', shown when Nightscout has readings), with '‹ Log' to go back.
It reports patterns only. It never suggests a dose, a ratio or a food change: the findings are for the family and the
care team to read (okf/rules/descriptive-stats-only.md).
- Period: the last 14, 30 or 90 days (30 to start), ending today.
- For each meal with a reading at the meal time, from the same 3-hour window as the meal's own curve
  (okf/domain/meal-glucose.md):
  - the rise: the peak in the 3 hours minus the value at the meal time, and the minutes to the peak;
  - where it was at 2 hours and at 3 hours: 'In range at 2 h', else 'In range at 3 h', else 'Above range at 3 h'
    or 'Below range at 3 h' (in the warn colour, like any low);
  - the insulin typed with the meal and its minutes before the meal, plus any other insulin entry (rapid) from an hour
    before to 3 hours after, with its minutes from the meal. 'No insulin added' when there is none. The curve depends
    as much on the insulin and its timing as on the food, so it is always shown beside the numbers.
- The chart: the curves lined up at the meal time, 0 to 3 hours along the bottom. 'Rise' (the start) draws each as
  the change from its meal-time value, so meals starting at different BGs compare; 'mg/dL' draws the readings with the
  target range as the pale band. Each meal is a thin graphite line; the average of the measured ones, every 5 minutes,
  is a thicker line. No colour grades a meal.
- By food: a food (or a carb entered by hand, by its name) that is in 2 or more measured meals gets a row, most meals
  first: 'Pizza, 4 meals: average rise +110 mg/dL, peak at 75 min on average, in range by 3 h in 2 of 4'. Tapping a
  row draws only those meals and lists them; 'All meals' goes back. A meal usually has other foods too, so each listed
  meal shows all its foods and carbs.
- Each meal: newest first, with its date and time, foods, carbs, rise and peak time, 2/3-hour line and insulin.
  Tapping it opens that meal in the Log.
- Left out of averages but still listed, each saying why: under 3 hours ago ('In progress'), sensor coverage under
  70% ('Sensor 55%', okf/rules/sensor-coverage.md), another meal within its 3 hours ('Another meal within 3 h'),
  or no reading at the meal time.
- Footnote: 'Patterns only, to share with the care team. Each curve also depends on the insulin and its timing,
  activity, illness and what came before.'
