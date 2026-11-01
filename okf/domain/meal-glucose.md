---
type: Value
title: "Meal glucose window"
description: "Glucose around a logged meal: value at meal time, peak and lowest in the next 3 hours, value at 2 hours, and the curve."
tags: [domain, nightscout]
timestamp: 2026-10-27
status: draft
links:
  derived_from: [domain/glucose-reading.md, domain/meal.md, domain/target-range.md]
  governed_by: [rules/descriptive-stats-only.md, rules/sensor-coverage.md]
---
# Meal glucose window
Window from 30 minutes before to 3 hours after the logged meal time (3 hours confirmed 27 Oct).
Overlapping meals (snack within 3 hours) are shown together, not split, because effects mix.
Read alongside the eaten note and comments, never as a judgement of the meal.
Also measured (decided 1 Nov, for the meal rating): the rise in the first hour and the minutes to the peak.
