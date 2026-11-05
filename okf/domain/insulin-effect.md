---
type: Value
title: "Estimated insulin effect"
description: "How far the insulin in the log is estimated to have lowered glucose since a meal's time, from a standard rapid-acting curve and the parent's correction factor. For After meals only."
tags: [domain, safety, nightscout]
timestamp: 2026-11-04
status: draft
links:
  derived_from: [domain/meal.md, domain/insulin-settings.md]
  used_by: [features/meal-responses.md]
  governed_by: [rules/no-dosing.md, rules/descriptive-stats-only.md]
---
# Estimated insulin effect
Decided 4 Nov, so meals given different insulin can be compared by what the food did.
- Which insulin, given from 6 hours before the meal to 3 hours after it (decided 4 Nov: Nightscout added the same day):
  - every bolus in Nightscout, from the pump, Loop (automatic boluses too) or a pen app (okf/architecture/nightscout-client.md);
  - every rapid-acting amount in the log (a meal's insulin marked Bolus, an entry marked rapid-acting), except one that
    matches a Nightscout bolus, given within 15 minutes of it and within 10% (or 0.1 u) of its units: that is the same
    insulin typed in both places, and counts once, at Nightscout's time;
  - left out: basal and long-acting, and temp basals (Loop raising or cutting the basal rate), which Nightscout keeps as
    rates, not amounts.
- The curve: the exponential insulin activity curve Loop and OpenAPS use for rapid-acting insulin, peaking at 75
  minutes and lasting 6 hours. The share of a dose that has acted by time t, times its units, times the correction
  factor (okf/domain/insulin-settings.md) for the meal's time, is the mg/dL it has lowered glucose by then.
- Measured from the meal's time: the effect at t minutes after the meal is what all that insulin did between the
  meal time and t, so insulin given before the meal counts only for what it does after it.
- 'Insulin backed out' adds the effect back onto each reading: roughly what glucose would have done from the food
  (and everything else) without that insulin. Without a correction factor set, it can't be worked out and says so.
- It is an estimate for spotting patterns with the care team. It is never used for the dose, never stored, never sent,
  and nothing suggests changing the insulin settings from it (okf/rules/no-dosing.md).
