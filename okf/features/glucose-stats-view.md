---
type: Feature
title: "Glucose statistics"
description: "Day, 7-day and 14-day statistics from Nightscout, next to the carbs logged in the same period."
tags: [feature, nightscout]
timestamp: 2026-10-27
status: draft
links:
  uses: [domain/glucose-stats.md, domain/meal-log.md, domain/target-range.md]
  constrained_by: [rules/descriptive-stats-only.md, rules/sensor-coverage.md, rules/no-dosing.md]
---
# Glucose statistics
- Day view in the log: time in range bar, average, lows count, total carbs.
- Period view (7 / 14 days): adds GMI and variability; included in the CSV export as a summary.
