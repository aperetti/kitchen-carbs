---
type: Feature
title: "Plan a meal"
description: "Build a plate now for a set date and time; it waits in the log as a planned meal, and at mealtime goes back on the plate to be checked, weighed and saved as usual."
tags: [feature]
timestamp: 2026-11-02
status: draft
links:
  uses: [domain/planned-meal.md, domain/plate.md, domain/meal.md]
  constrained_by: [rules/favorites-use-current-values.md, rules/nightscout-sends-what-was-logged.md, rules/no-dosing.md]
  depends_on: [features/build-plate.md, features/log-meal.md, features/nightscout-send.md]
---
# Plan a meal
Decided 2 Nov.
- Plate → 'Plan for later' (beside Clear plate and Pin as favorite): a date (today by default, up to 60 days ahead),
  a time and a name, then 'Plan'. The plate is cleared and the plan shows in the log.
- In the log: today's view starts with a 'Planned' list of every plan, overdue first, then by date and time, each
  with its day, name and carbs in a dashed outline. A future day's view (next day goes past today) lists that
  day's plans too (decided 8 Nov). They aren't in any day's total. Opening one shows its foods and carbs, a form to
  change the name, date and time, 'Put on the plate', and 'Delete plan' (tapped twice).
- The empty plate lists today's plans and overdue ones, each with 'Put on the plate', so mealtime starts there.
- 'Put on the plate' fills the plate from the plan with each food's current values, the time set to now. If the plate
  already has food, the first tap asks to tap again to replace it. The plate then says which plan it came from,
  with 'Update plan' in place of 'Plan for later'.
- 'Save to log' from a planned plate goes through the meal summary as usual (okf/features/meal-dose-summary.md)
  and the saved meal replaces the plan, in one step on the server, so it holds when the meal was queued offline.
  'Clear plate' leaves the plan as it was.
- Nightscout (okf/features/nightscout-send.md): with Carbs switched on, each plan from the 'Send from' date is sent as a
  'Note' at its planned time, e.g. 'Planned meal: Dinner · Pasta, Apple · 52 g carbs, not eaten yet', with nothing
  in the carbs field, so OpenAPS forecasts never count food that hasn't been eaten. Changing the plan's time moves
  the note; deleting the plan deletes it; saving it to the log deletes the note and sends the meal as a Meal Bolus
  with its real carbs and insulin.
- No dose is worked out for a plan; only the meal summary does that, when it is saved (okf/rules/no-dosing.md).
