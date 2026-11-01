---
type: Feature
title: "Rate a meal"
description: "From the log, a parent rates a meal's GI and speed of rise after seeing its glucose curve; each food's details then show how the meals it was in were rated."
tags: [feature, nightscout]
timestamp: 2026-11-01
status: draft
links:
  uses: [domain/meal-rating.md, domain/meal.md, domain/food.md, domain/meal-glucose.md]
  constrained_by: [rules/descriptive-stats-only.md, rules/sensor-coverage.md]
---
# Rate a meal
- Log → a meal, under the glucose curve: 'Rating' with two segmented rows, GI (Low, Medium, High) and Rise (Slow,
  Steady, Fast). Tapping the chosen one again clears it. Saved with the meal's other changes from the Save bar
  (okf/features/review-log.md).
- Can be set on any day, even when earlier days are read-only, because a curve is often looked at the next day. It
  changes nothing else about the meal, isn't marked 'Changed later' and isn't sent to Nightscout or Tidepool.
- The curve's numbers gain 'Rose +85 in 1 h' and 'Peak at 55 min' (okf/domain/meal-rating.md).
- Food card details (ⓘ) show 'In rated meals: Rise fast 3, steady 1 · GI high 2'. When at least 2 rated meals agree
  on most of them being fast or slow, the card's corner shows 'Fast rise' or 'Slow rise', so it's seen while
  building the plate.
- The CSV and PDF export have the GI and Rise of each meal.
