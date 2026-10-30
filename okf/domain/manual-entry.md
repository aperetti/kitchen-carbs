---
type: Entity
title: "Manual entry"
description: "A timed log entry typed by a parent: carbs not from the food list, a meter BG reading, and/or insulin given (units, rapid or long-acting), with a note."
tags: [domain, safety]
timestamp: 2026-10-27
status: draft
links:
  part_of: [domain/meal-log.md]
  governed_by: [rules/no-dosing.md, rules/same-day-edits.md, rules/glucose-units.md]
---
# Manual entry
- Fields: time, carbs (g), BG (mg/dL, from a meter), insulin (units, to 0.05), insulin kind (rapid | long), note. At least one value.
- Insulin is a **record of what was given**, typed by the parent from the pump or pen. The app never fills it in.
- Manual carbs count towards the day's carb total. Meter BG is shown as a separate marker, never mixed into CGM statistics.
