---
type: Feature
title: "Suggest a meal"
description: "A button on the empty plate builds a meal from the family's own logged meals, sized to a carbs (or bolus) amount set on a slider; tapping a food swaps it for one they usually have instead."
tags: [feature]
timestamp: 2026-11-20
status: draft
links:
  uses: [domain/meal-log.md, domain/food.md, domain/portion.md, domain/plate.md, domain/insulin-settings.md]
  constrained_by: [rules/favorites-use-current-values.md, rules/no-dosing.md, rules/whole-gram-rounding.md, rules/descriptive-stats-only.md]
  depends_on: [features/build-plate.md, features/plan-meal.md]
---
# Suggest a meal
Asked for 20 Nov: 'click a button, and it comes up with a recommendation. A slider selects the carbs or the bolus
amount, starting from historical usage. The user taps items to remove them and something else takes their place.'
- Where: 'Suggest a meal' on the empty plate, under the planned meals. It opens a dialog.
- Meal: Breakfast · Lunch · Dinner, starting on the one whose usual time (Manage → Settings → Meal times) is
  nearest now. Each logged meal counts towards the meal time it is nearest to. Meals marked as not eaten don't count.
  With fewer than 3 of that meal in the last 90 days, every meal counts, the others a fifth as much so that
  meal's own foods still come first (the carbs and number of foods still come from that meal when it has any),
  and the dialog says so.
- Amount: Carbs · Bolus, with a slider.
  - Carbs (5–150 g) starts at the middle (median) carbs of that meal over the last 90 days.
  - Bolus starts at those carbs ÷ the carb ratio at that meal's usual time, rounded down to the insulin step. Moving
    it sets carbs = bolus × carb ratio, shown as a sum ('2.50 u × 15 g/u = 38 g'). It is the inverse of the summary's
    carbs ÷ ratio and uses only the parent's settings (okf/rules/no-dosing.md); it doesn't count BG, correction or
    insulin on board, and says so. It fills in no insulin anywhere: insulin is still only what's typed or filled in
    in the meal summary. Without insulin settings, Bolus is greyed out.
- The foods: as many as that meal usually has (the median, 1 to 5), picked from the foods logged for it, ranked by how
  often they were had, recent meals counting more (a meal 30 days ago counts half), and foods often had together with
  the ones already picked ranked higher. Only foods still in the food list, with their portion today. Foods tagged
  for that meal ('Lunch') but not had for it yet come last, so swapping doesn't run out quickly.
  - Foods that go together come together (asked for 20 Nov: 'ketchup and chicken nuggets, carrots and Italian'). Worked
    out from every meal in the 90 days, whatever the time of day, each pair seen at least 3 times:
    - a side: a food nearly always had with another (that one in 3 of every 4 of its meals) and in at least 30% of that
      one's meals. Ketchup comes with the nuggets, the dressing with the carrots, and a side's own sides come too.
    - a pair: a food in at least 60% of another's meals, added along with the food that leads the group.
    - A group is up to 4 foods, led by the one with the most carbs. A food had a few times doesn't tag along with a
      staple (the 30% rule).
  - Amounts are in half portions (okf/domain/portion.md), starting from how much of each food is usually had, then
    moved half a portion at a time, never under half a portion, until the total is as close to the target as they get.
    Each food stays between half and a quarter more than its usual amount (at least half a portion more).
  - More carbs adds a food rather than piling on (asked for 20 Nov). When the foods shown can't reach the target
    within those amounts, the next best food comes in with its sides (not one under 10 g on its own, unless less is
    missing). With fewer carbs, the last food added goes once the rest reach the target without it. Only when there's
    nothing more to add are portions stretched further (up to twice the usual, 4 at least, 8 at most).
    Each food shows its portion and carbs; the total shows next to the target ('52 g · target 55 g').
  - Carbs use each food's values today (okf/rules/favorites-use-current-values.md), added exactly and rounded once.
- Swap: tapping a food (×) takes it out and puts the next best in its place, preferring a food that shares a tag
  with it (fruit for fruit; the meal tags Breakfast, Lunch, Dinner and Snack don't count) and is often had with the others. A food taken out isn't suggested again while the dialog is
  open; closing it forgets. When nothing is left to suggest, the food is just removed.
  - A swap can also bring in another food if what's left can't reach the target; it never takes a food off.
  - Its sides with fewer carbs than it go too (swap the nuggets and the ketchup goes), unless another food shown has
    them as a side; they don't come back on their own as the replacement. The new food comes with its own sides.
- Lock and servings (asked for 20 Nov: 'allow locking certain items and their servings, allowing modify their
  servings'). Each food has a lock and a − / + stepper.
  - The lock keeps the food and its serving as they are: it isn't swapped (its × is hidden), dropped when the carbs
    come down, or resized. Tapping it again lets the food be sized and swapped again.
  - − and + change the serving by half a portion (half to 20 servings) and lock it, since a serving set by hand
    should stay. The total updates at once; the other foods refit after a short pause.
  - The other foods are sized around the locked ones, and foods are added or dropped for what's left. A locked side
    stays when its food is swapped out. When the locked foods alone are over the target, the total shows it.
  - Locks last while the dialog is open and are cleared by switching meal, like the foods taken out.
  - When adding a food for carbs, the best fit for what's missing of the next 4 best foods comes in, and only if it
    gets closer than leaving it short.
- 'Put on the plate' fills the plate with the foods and amounts, weighed as each food usually is (cooked when it has a
  measured ratio), to be checked or weighed and saved as usual through the meal summary. Nothing is logged by the
  suggestion itself.
- Nothing logged yet: the dialog says that suggestions start once meals are saved to the log.
- It describes what the family has eaten; it never says a meal is better or worse (okf/rules/descriptive-stats-only.md).
