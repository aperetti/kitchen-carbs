---
type: Entity
title: "Planned meal"
description: "A plate built ahead for a set date and time, with a name. Not eaten yet, so nothing counts it until it is saved to the log."
tags: [domain]
timestamp: 2026-11-02
status: draft
links:
  contains: [domain/portion.md]
  becomes: [domain/meal.md]
  governed_by: [rules/favorites-use-current-values.md, rules/nightscout-sends-what-was-logged.md]
---
# Planned meal
Decided 2 Nov: a plate for later (tonight's dinner, tomorrow's school lunch), not a pre-bolus timer.
- A name (Breakfast, Lunch or Dinner from the time unless typed), a date from today up to 60 days ahead, a time, and
  the plate's rows as they were: weighed foods with their grams and dry or cooked state, and carbs typed by hand.
- Kept apart from the log: it is not a meal. Day totals, stats, the glucose views, the CSV and PDF exports, Tidepool
  and notifications never count it. Only a meal saved from it does.
- Put back on the plate, each food takes its current values (okf/rules/favorites-use-current-values.md); a food no
  longer in the list is left out and named.
- It ends when it is saved to the log (the meal takes its place) or deleted. A plan whose time has passed stays until
  one of those, shown as overdue.
