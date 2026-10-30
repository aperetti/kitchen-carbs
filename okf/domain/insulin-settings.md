---
type: Value
title: "Insulin settings"
description: "The parent's carb ratio, correction factor and target BG, each by time of day, from the care team. Used only by the meal summary."
tags: [domain, safety]
timestamp: 2026-10-29
status: draft
links:
  used_by: [features/meal-dose-summary.md]
  governed_by: [rules/no-dosing.md, rules/glucose-units.md]
---
# Insulin settings
Decided 29 Oct: by time of day, like a pump's settings. Set in Manage → Settings, behind the parent PIN.
- Carb ratio: grams of carbs covered by 1 u (1–150 g).
- Correction factor: mg/dL that 1 u lowers BG (5–500 mg/dL).
- Target BG: the BG a correction aims for (70–200 mg/dL). Not the same as the time-in-range target range.
- Each is a list of blocks by start time; the first starts at 00:00 and a block runs until the next one starts.
  Example: 00:00 1:15, 06:00 1:12, 11:00 1:15.
- The summary uses the blocks for the meal's time. The date they were last changed is shown under the numbers.
- Values are copied from the pump or the care team's plan; the app never suggests or adjusts them.
