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
- Which insulin: every rapid-acting amount in the log (a meal's insulin marked Bolus, an entry marked rapid-acting)
  given from 6 hours before the meal to 3 hours after it. Basal and long-acting are left out, and so is anything not
  typed into the log (a pump's basal, a bolus given on the pump and not logged here).
- The curve: the exponential insulin activity curve Loop and OpenAPS use for rapid-acting insulin, peaking at 75
  minutes and lasting 6 hours. The share of a dose that has acted by time t, times its units, times the correction
  factor (okf/domain/insulin-settings.md) for the meal's time, is the mg/dL it has lowered glucose by then.
- Measured from the meal's time: the effect at t minutes after the meal is what all that insulin did between the
  meal time and t, so insulin given before the meal counts only for what it does after it.
- 'Insulin backed out' adds the effect back onto each reading: roughly what glucose would have done from the food
  (and everything else) without that insulin. Without a correction factor set, it can't be worked out and says so.
- It is an estimate for spotting patterns with the care team. It is never used for the dose, never stored, never sent,
  and nothing suggests changing the insulin settings from it (okf/rules/no-dosing.md).
