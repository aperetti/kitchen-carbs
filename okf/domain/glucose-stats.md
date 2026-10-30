---
type: Value
title: "Glucose statistics"
description: "Descriptive numbers for a day or period: time in range, time low/high, average, GMI, variability, sensor coverage."
tags: [domain, nightscout]
timestamp: 2026-10-27
status: draft
links:
  derived_from: [domain/glucose-reading.md, domain/target-range.md]
  governed_by: [rules/descriptive-stats-only.md, rules/sensor-coverage.md]
---
# Glucose statistics
| stat | meaning |
|---|---|
| Time in range | % of readings within the target range |
| Time below / very low | % < 70 and % < 54 mg/dL |
| Time above / very high | % > 180 and % > 250 mg/dL |
| Average glucose | mean of readings |
| GMI | 3.31 + 0.02392 × mean mg/dL (estimate of A1c, needs ≥ 14 days) |
| Variability (CV) | standard deviation ÷ mean |
| Coverage | % of expected readings present |
Shown next to the day's total carbs from the meal log.
