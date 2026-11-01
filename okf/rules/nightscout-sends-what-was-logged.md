---
type: Rule
title: "Nightscout gets only what was logged, and only when switched on"
description: "The app reads glucose from Nightscout. It writes to Nightscout only when a parent turns on 'Send to Nightscout': carbs, rapid-acting insulin and meter BG the family typed, never the calculated dose, never CGM, and never long-acting insulin as insulin."
tags: [nightscout, safety]
timestamp: 2026-11-01
status: draft
links:
  applies_to: [domain/glucose-reading.md, architecture/nightscout-client.md, features/nightscout-send.md]
  extends: [rules/no-dosing.md, rules/snapshot-log-values.md]
---
# Nightscout gets only what was logged
Was 'Nightscout read-only' (27 Oct), while carbs reached Nightscout from a pump or loop app. Changed 1 Nov: the
family uses pens and wants carbs and insulin in Nightscout for forecasting with OpenAPS (not a closed loop).
- Off until a parent switches it on, with a token whose role allows `api:treatments:*`; reading works with a
  `readable` token as before.
- Sent: a meal's carbs, carbs typed in an entry, rapid-acting (bolus) insulin typed on a meal or entry at the time
  it was given, and a meter BG typed on a meal or entry. Each kind can be switched off.
- Never sent: the meal summary's worked-out dose (okf/rules/no-dosing.md), CGM readings, a meal's BG taken from the
  CGM.
- Long-acting (basal) insulin goes as a Note with the units in its text, never in the insulin field: OpenAPS counts
  every insulin treatment as rapid-acting insulin on board, so a 12 u long-acting dose would forecast a crash. Its
  effect belongs in the Nightscout profile's basal rate, set by the family.
- If a pump or another app also puts the same carbs or insulin in Nightscout, switch that kind off here, or the
  forecast counts it twice. The warning sits beside the switches.
- Kitchen Carbs only ever changes or deletes treatments it sent itself (its own identifiers).
- QA, dev and demo never send: their data is a copy or made up.
