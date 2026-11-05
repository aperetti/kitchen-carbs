---
type: component
title: "Glucose curve"
description: "Small line chart of the meal window: target range as a pale band, meal time as a vertical hairline, values labelled at start, peak and 2 h."
tags: [design, nightscout]
timestamp: 2026-10-27
status: draft
links:
  implements: [features/meal-glucose-view.md, features/meal-responses.md]
  uses_tokens: [design/foundations/color.md, design/foundations/typography.md]
---
# Glucose curve
Mocked in the review page's Log screen (screen 3).
Line in graphite, range band in surface-sunk, lows in warn. No red/green grading.
After meals (okf/features/meal-responses.md) uses the same style for many curves at once: thin graphite lines
at low opacity, the average thicker, the x axis in minutes after the meal (0, 1 h, 2 h, 3 h) instead of clock times.
