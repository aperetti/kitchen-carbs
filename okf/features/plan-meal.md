---
type: Feature
title: "Plan a meal"
description: "Build a plate now for a set date and time; it waits in the log as a planned meal, and at mealtime one Submit opens the meal summary, timed at the moment it was tapped."
tags: [feature]
timestamp: 2026-11-17
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
- Next meals (decided 12 Nov): above the boxes, one button for each of the next breakfast, lunch and dinner in
  the coming 24 hours, soonest first, e.g. 'Dinner · today 6:00 PM', 'Breakfast · tomorrow 7:30 AM', 'Lunch ·
  tomorrow 12:00 PM'. Tapping one fills the name, date and time (the name only while it is still a meal name, so a
  typed name stays) and marks it; 'Plan' then saves as before. A new plan starts on the soonest one. The times come
  from Manage → Settings → Meal times (7:30, 12:00 and 18:00 to start), the same for every device; changing them
  needs the parent PIN, reading them doesn't.
- In the log: today's view starts with a 'Planned' list of every plan, overdue first, then by date and time, each
  with its day, name and carbs in a dashed outline. A future day's view (next day goes past today) lists that
  day's plans too (decided 8 Nov). They aren't in any day's total. Opening one shows its foods and carbs, a form to
  change the name, date and time, 'Submit', and 'Delete plan' (tapped twice).
- The empty plate lists today's plans and overdue ones, each with 'Submit', so mealtime starts there.
- 'Submit' (decided 17 Nov; it was 'Put on the plate', which then needed 'Save to log' too) fills the plate from the
  plan with each food's current values and opens the meal summary straight away (okf/features/meal-dose-summary.md).
  The meal starts at the plan's own day and time (decided 17 Nov), not now and not the estimated eat time; it doesn't
  follow the BG, and it can still be changed in the summary. Often it is tapped after the meal, so the tap's time
  is never used. An overdue plan keeps its earlier day. A plan for a later day has no Submit until its day (decided
  18 Nov): its details say 'Submit shows here from Thu, Nov 19', and the plan itself stays as it is. A plan's time more than 15 minutes
  ago takes the CGM reading from then (okf/features/meal-dose-summary.md). If the plate already has food, the first tap asks to tap
  again to replace it. If any of the plan's foods are no longer in the food list, it stops at the plate instead,
  saying which were left out. 'Back to plate' leaves the plan's foods on the plate, which says which plan it came
  from, with 'Update plan' in place of 'Plan for later'.
- 'Save to log' in the summary saves the meal, and the saved meal replaces the plan, in one step on the server, so it holds when the meal was queued offline.
  'Clear plate' leaves the plan as it was.
- Nightscout (okf/features/nightscout-send.md): with Carbs switched on, each plan from the 'Send from' date is sent as a
  'Note' at its planned time, e.g. 'Planned meal: Dinner · Pasta, Apple · 52 g carbs, not eaten yet', with nothing
  in the carbs field, so OpenAPS forecasts never count food that hasn't been eaten. Changing the plan's time moves
  the note; deleting the plan deletes it; saving it to the log deletes the note and sends the meal as a Meal Bolus
  with its real carbs and insulin.
- No dose is worked out for a plan; only the meal summary does that, when it is saved (okf/rules/no-dosing.md).
