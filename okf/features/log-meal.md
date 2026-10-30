---
type: Feature
title: "Log meal"
description: "Save the plate as a meal with time and note."
tags: [feature]
timestamp: 2026-10-26
status: draft
links:
  uses: [domain/plate.md, domain/meal.md, features/meal-dose-summary.md]
  constrained_by: [rules/snapshot-log-values.md, rules/offline-queue.md]
---
# Log meal
Time defaults to now and can be changed. Clears the plate after saving.
'Save to log' first opens the meal summary with the dose (okf/features/meal-dose-summary.md, decided 29 Oct); saving is confirmed there.
