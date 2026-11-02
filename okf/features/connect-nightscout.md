---
type: Feature
title: "Connect Nightscout"
description: "Parent enters the Nightscout site address and a read-only access token; the app tests it and shows the latest reading."
tags: [feature, admin, nightscout]
timestamp: 2026-10-27
status: draft
links:
  uses: [domain/glucose-reading.md, domain/target-range.md]
  constrained_by: [rules/nightscout-sends-what-was-logged.md, rules/nightscout-token-server-only.md, rules/glucose-units.md]
---
# Connect Nightscout
- Behind the parent PIN, in Manage → Settings, under the Nightscout heading (its own tab until 1 Nov; see
  design/components/settings-nav.md). The target range is set there too.
- Ask for an access token with the `readable` role (Nightscout Admin tools → Subjects), not the API_SECRET.
- Test button: fetch the latest entry and show its time and value.
- Units: mg/dL (confirmed).
