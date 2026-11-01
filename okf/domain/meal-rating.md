---
type: Value
title: "Meal rating"
description: "A parent's own judgement of how fast glucose rose after a logged meal: fast, medium or slow. Each food sums up the ratings of the meals it was in."
tags: [domain, nightscout]
timestamp: 2026-11-01
status: draft
links:
  part_of: [domain/meal.md]
  derived_from: [domain/meal-glucose.md]
  governed_by: [rules/descriptive-stats-only.md, rules/snapshot-log-values.md]
---
# Meal rating
Decided 1 Nov: rate each meal after seeing its curve, and see the ratings again on each food when building the next
plate. Only the rise (decided 1 Nov, GI dropped): GI is a property of a food, while the rise is what this meal did,
with its fat, fibre, pre-bolus and the day all mixed in. It matches how Loop-based pumps such as twiist ask how fast
a meal's carbs absorb, not their GI.
- One optional choice on a meal: **Rise** Fast / Medium / Slow, the words and order Loop and twiist use for
  absorption speed (decided 1 Nov). It is the parent's judgement; the app never sets or
  suggests it.
- Beside them, measured from the CGM when there is a reading at the meal: how much glucose rose in the first hour
  (highest reading in the hour after the meal time minus the reading at the meal, in mg/dL), and minutes from the
  meal time to the peak within 3 hours. Shown as numbers only, with the sensor coverage (okf/rules/sensor-coverage.md).
- Food summary: for each food, the ratings of the not-deleted meals it was in, counted per choice, e.g. 'Rise fast 3,
  medium 1'. A meal with several foods counts for each of them, so it says 'in meals with this food',
  not that the food caused it.
- Neutral colours throughout: no rating is shown as good or bad (okf/rules/descriptive-stats-only.md).
