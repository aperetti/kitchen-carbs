---
type: Rule
title: "Tidepool gets what was logged"
description: "Only values the family recorded go to Tidepool, each kind only when switched on: never the calculated dose, never CGM readings, and insulin only with a warning about double counting."
tags: [tidepool, safety]
timestamp: 2026-10-31
status: draft
links:
  applies_to: [features/tidepool-sync.md, architecture/tidepool-client.md]
  extends: [rules/no-dosing.md, rules/snapshot-log-values.md]
---
# Tidepool gets what was logged
- The meal summary's worked-out dose is never sent, as it is never stored (okf/rules/no-dosing.md).
- CGM readings, and a meal's BG taken from the CGM, are never sent: they would duplicate the CGM's own data.
- Insulin is off until a parent switches it on, with the double-counting warning shown beside the switch.
- Kitchen Carbs only ever changes or deletes records in its own data set.
