---
type: Feature
title: "After meals: post-meal responses"
description: "Every logged meal's glucose from 0 to 3 hours after eating, lined up at the meal time, with its rise, time to peak, where it was at 2 and 3 hours and the insulin typed for it; repeats of a food are grouped to compare."
tags: [feature, nightscout]
timestamp: 2026-11-09
status: draft
links:
  uses: [domain/meal.md, domain/insulin-effect.md, domain/meal-glucose.md, domain/glucose-reading.md, domain/target-range.md, domain/food.md]
  constrained_by: [rules/descriptive-stats-only.md, rules/sensor-coverage.md, rules/no-dosing.md]
---
# After meals: post-meal responses
Decided 4 Nov. A page reached from the Log ('After meals', shown when Nightscout has readings), with '‹ Log' to go back.
It reports patterns only. It never suggests a dose, a ratio or a food change: the findings are for the family and the
care team to read (okf/rules/descriptive-stats-only.md).
- Period: the last 14, 30 or 90 days (30 to start), ending today.
- Meal of the day (decided 7 Nov): All · Breakfast · Lunch · Dinner, each with its count, by the meal's logged time:
  breakfast before 11:00, lunch 11:00 to 15:59, dinner from 16:00. Picking one limits the chart, the averages, the
  by-food rows and the meal list to those meals; 'All' (the start) shows every meal. A meal with another within 3 h is
  still left out of the averages even when that other meal is in a different part of the day.
- For each meal with a reading at the meal time, from the same 3-hour window as the meal's own curve
  (okf/domain/meal-glucose.md):
  - the rise: the peak in the 3 hours minus the value at the meal time, and the minutes to the peak;
  - where it was at 2 hours and at 3 hours: 'In range at 2 h', else 'In range at 3 h', else 'Above range at 3 h'
    or 'Below range at 3 h' (in the warn colour, like any low);
  - the insulin typed with the meal and its minutes before the meal, plus any other insulin entry (rapid) from an hour
    before to 3 hours after, with its minutes from the meal, and the Nightscout boluses in that time marked
    'Nightscout' (a logged dose that matches one is shown once, okf/domain/insulin-effect.md). 'No insulin added' when there is none. The curve depends
    as much on the insulin and its timing as on the food, so it is always shown beside the numbers.
- The chart: the curves lined up at the meal time, 0 to 3 hours along the bottom. 'Rise' (the start) draws each as
  the change from its meal-time value, so meals starting at different BGs compare; 'mg/dL' draws the readings with the
  target range as the pale band. 'Insulin backed out' (decided 4 Nov) adds the estimated insulin effect back
  (okf/domain/insulin-effect.md), so meals given different insulin compare by what the food did. Since 9 Nov it is a
  switch beside Rise · mg/dL rather than a third choice, so it works both ways: with Rise each starts at 0; with mg/dL
  each starts at its real meal-time reading, over the target band, showing where glucose would have gone from there.
  With the switch on each meal also shows 'Without the insulin (estimate): rise +X · insulin lowered about Y by 3 h' (adding 'including insulin
  from earlier still acting' when a dose from more than an hour before counts)
  and each food 'without the insulin, average rise +X (estimate)'; a meal with no insulin in the log says its curve is
  unchanged. The chart's ⓘ says it is an estimate from the correction factor and a standard rapid-acting
  curve, counting boluses from Nightscout and the log but not
  temp basals. Without a correction factor, the button says it needs one in Manage →
  Settings. Each meal is a thin graphite line; the average of the measured ones, every 5 minutes,
  is a thicker line. No colour grades a meal.
- Tapping a line (decided 9 Nov) picks that meal: its line is drawn on top, thicker in the accent colour with the average faded, and under the chart
  a line gives its date and time, foods, carbs and rise, with 'Open in log ›'. Tapping it again, or the chart away
  from any line, lets it go; changing the period, meal of the day, food or mode does too. Each line has a wider
  invisible edge so a finger can hit it. The chart's explanation (what the thin and thick lines are, how they are drawn, the estimate note in 'Insulin backed out', dashed gaps, and 'Tap a line to see its meal.') is behind an ⓘ beside the chart's title, not printed under it (decided 9 Nov). The picked line is marked by weight, not a grading colour.
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
