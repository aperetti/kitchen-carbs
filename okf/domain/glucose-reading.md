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
- Gaps (sensor warm-up, signal loss) are kept as gaps, never filled in.
