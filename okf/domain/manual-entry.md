---
type: Entity
title: "Manual entry"
description: "A timed log entry typed by a parent: carbs not from the food list, a BG reading (meter, or the CGM's from Correct BG), and/or insulin given (units, rapid or long-acting), with a note."
tags: [domain, safety]
timestamp: 2026-11-14
status: draft
links:
  part_of: [domain/meal-log.md]
  governed_by: [rules/no-dosing.md, rules/same-day-edits.md, rules/glucose-units.md]
---
# Manual entry
- Fields: time, carbs (g), BG (mg/dL) and where it came from (meter | cgm, decided 14 Nov; a meter unless Correct BG
  filled it from the CGM and it wasn't typed over; entries before then are meter), insulin (units, to 0.05), insulin kind (rapid | long), note. At least one value.
- Insulin is a **record of what was given**, typed by the parent from the pump or pen. The app never fills it in,
  also when an entry is edited later (okf/features/manual-log.md).
- Manual carbs count towards the day's carb total. Meter BG is shown as a separate marker, never mixed into CGM statistics.
  A CGM BG on an entry is labelled 'BG (CGM)', isn't drawn as a meter marker and is never sent to Nightscout or
  Tidepool, which have the CGM's own readings. Editing an entry keeps its BG's source unless the BG is changed, which
  makes it a meter reading.
