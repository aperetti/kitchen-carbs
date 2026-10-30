---
type: Feature
title: "Glucose after a meal"
description: "In the log, each meal shows a small glucose curve for its window with start, peak and 2-hour values."
tags: [feature, nightscout]
timestamp: 2026-10-27
status: draft
links:
  uses: [domain/meal.md, domain/meal-glucose.md, domain/glucose-reading.md]
  constrained_by: [rules/descriptive-stats-only.md, rules/sensor-coverage.md, rules/no-dosing.md]
---
# Glucose after a meal
Appears once 3 hours have passed (a partial curve before that, labelled 'in progress').
