---
type: component
title: "Stats strip"
description: "One row under the day header: time-in-range bar (below / in / above), average, lows, coverage, total carbs."
tags: [design, nightscout]
timestamp: 2026-10-27
status: draft
links:
  implements: [features/glucose-stats-view.md]
  uses_tokens: [design/foundations/color.md, design/foundations/typography.md]
---
# Stats strip
Mocked in the review page's Log screen (screen 3), today so far.
Bar uses three neutral tones with warn for below range; labels carry the numbers so colour is not needed to read it.

- Compact (decided 2 Nov, the log was too much to take in): under the day header one line, e.g.
  'Insulin 6 u bolus · 90% in range · avg 117 · 2 lows ›'. Tapping it opens the Day / 7 days / 14 days switch and
  the full strip below it; tapping again closes it. Without sensor data the line shows only the insulin, and doesn't open.
