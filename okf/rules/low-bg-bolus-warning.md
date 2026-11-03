---
type: Rule
title: "Warn about a bolus with a low BG"
description: "When a bolus is typed while the BG is under 70 mg/dL, the meal summary and Add entry show a plain warning beside the insulin box. It never blocks saving and never changes or suggests an amount."
tags: [safety]
timestamp: 2026-11-03
status: draft
links:
  applies_to: [features/meal-dose-summary.md, features/manual-log.md]
  related: [rules/no-dosing.md, rules/glucose-units.md]
---
# Warn about a bolus with a low BG
Decided 3 Nov, asked by the parent: giving rapid-acting insulin while the BG is low is a mistake worth stopping for.
- Low means under 70 mg/dL, fixed. It is not the target range set in Settings, which is for time-in-range stats.
- The BG is the one on the same screen: the meter reading typed there, or the CGM reading the summary uses (under
  15 minutes old). On Add entry with no BG typed, the newest CGM reading is used if it is under 15 minutes old and the
  entry's time is within 15 minutes of now.
- It shows only when insulin is typed and is a bolus (meal: Bolus; entry: Rapid-acting, or not chosen yet). Basal and
  long-acting insulin don't trigger it.
- The words: "BG is 62 mg/dL (meter), under 70. Treat the low first and follow the care team's plan before giving a
  bolus." With the CGM: "The CGM shows 62 mg/dL, 4 min ago, under 70. …". Shown in the warn colour, in a box beside the
  insulin box, read out by screen readers.
- In the meal summary, the 'BG is low' line above the worked-out dose says the same when the dose is above 0 u.
- Saving is never blocked and nothing is changed: the log records what was actually given (okf/rules/no-dosing.md).
  It isn't a dose check; it says nothing about the amount.
- Changing an earlier meal or entry in the log doesn't warn: that's a record of what was already done.
