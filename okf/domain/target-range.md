---
type: Value
title: "Target range"
description: "The glucose range used for time-in-range, set by the parent from the care team's advice."
tags: [domain, nightscout, safety]
timestamp: 2026-10-27
status: draft
links:
  used_by: [domain/glucose-stats.md, domain/meal-glucose.md]
  governed_by: [rules/descriptive-stats-only.md]
---
# Target range
Default 70–180 mg/dL (3.9–10.0 mmol/L), the international consensus range for time in range.
Can be read from the Nightscout profile (`bgTargetBottom`/`bgTargetTop`) or set by hand.
Low is below 70 mg/dL, very low below 54 mg/dL; high is above 180, very high above 250.
