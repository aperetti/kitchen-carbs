---
type: Entity
title: "Glucose reading"
description: "One CGM sensor value pulled from Nightscout: time, glucose, trend direction."
tags: [domain, nightscout]
timestamp: 2026-10-27
status: draft
links:
  sourced_from: [architecture/nightscout-client.md]
  governed_by: [rules/nightscout-sends-what-was-logged.md, rules/glucose-units.md]
---
# Glucose reading
- From Nightscout `entries` (type `sgv`): `date` (ms), `sgv` (always mg/dL in the API), `direction`.
- Stored as a local copy for speed and offline use; Nightscout stays the source of truth.
- Gaps (sensor warm-up, signal loss) are kept as gaps in what is stored; nothing estimated is ever saved or sent.
- Drawn gaps are filled with an estimate (decided 4 Nov, replacing 'never filled in'): a gap of more than 10 minutes
  and up to 60, with readings on both sides, is drawn as a dashed line through 5-minute estimates. Each estimate is
  Nightscout's AR2 forecast (ln(BG ÷ 140), next = 1.716 × last − 0.723 × the one before) run forward from the two
  readings before the gap and backward from the two after it, blended by distance (the nearer side counts more), kept
  to 39–400 mg/dL. Longer gaps stay blank.
- Estimates are for drawing only: every number shown (at the meal, peak, rise, 2 h, 3 h, lowest, lows, time in range,
  sensor coverage) comes from real readings. The one exception is the average line in After meals
  (okf/features/meal-responses.md), which may use them so a short gap doesn't drop a meal from that 5-minute step.
