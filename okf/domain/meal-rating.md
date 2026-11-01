---
type: Value
title: "Meal rating"
description: "A parent's own judgement of a logged meal: its GI (low, medium, high) and how fast glucose rose (slow, steady, fast). Each food sums up the ratings of the meals it was in."
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
plate.
- Two optional choices on a meal, either can be left empty: **GI** Low / Medium / High, and **Rise** Slow / Steady /
  Fast. They are the parent's judgement; the app never sets or suggests them.
- Beside them, measured from the CGM when there is a reading at the meal: how much glucose rose in the first hour
  (highest reading in the hour after the meal time minus the reading at the meal, in mg/dL), and minutes from the
  meal time to the peak within 3 hours. Shown as numbers only, with the sensor coverage (okf/rules/sensor-coverage.md).
- Food summary: for each food, the ratings of the not-deleted meals it was in, counted per choice, e.g. 'Rise: fast 3,
  steady 1 · GI: high 2'. A meal with several foods counts for each of them, so it says 'in meals with this food',
  not that the food caused it.
- Neutral colours throughout: no rating is shown as good or bad (okf/rules/descriptive-stats-only.md).
