---
type: Entity
title: "Plate"
description: "The meal being assembled right now: foods with their weighed grams, a running carb total and the total food weight."
tags: [domain]
timestamp: 2026-11-10
status: draft
links:
  contains: [domain/portion.md]
  becomes: [domain/meal.md]
---
# Plate
Temporary until saved. One plate for the family (decided 10 Nov, replacing one per tablet): every signed-in device
shows the same plate, kept on the server (okf/architecture/shared-plate.md). Adding, weighing, removing, clearing,
putting a plan on it and saving it to the log show on the other devices within a few seconds.
- Each item starts at its portion's weight and is tuned to what was actually served (decided 27 Oct, replacing the
  ×½ / ×1 / ×1½ / ×2 steps): drag anywhere on its row left or right (decided 27 Oct: the whole row, not only the slider), or type the scale
  reading. Each row labels its numbers plainly: 'g carbs' beside the carb figure, 'Weight' beside the grams.
- The slider follows Apple's Human Interface Guidelines for sliders (decided 27 Oct): a thin rounded track filled in the
  accent colour up to the value, a large white round thumb, the portion's weight as a small tick under the track, and a
  text field with a − / + stepper (1 g a tap) beside it for exact values. A mark on the slider shows
  the portion's own weight. Carbs follow the grams live: grams × carbs per 100 g ÷ 100.
- Slider ticks and snapping (decided 28 Oct, replacing the line '1 serving = 60 g'): ticks with small labels at ½, 1,
  1½ and 2 of the portion (in the weight's own dry or cooked state). Dragging the slider or the row snaps to a tick
  when within 2 % of the slider's range, with a short vibration where the phone supports it. Typed grams, the − / +
  stepper and the scale's 'Use' are never snapped, so a weighed amount stays exact.
- No tap-to-jump (decided 29 Oct, to stop misclicks): tapping the slider's track or the row never changes the weight.
  Only sliding a finger left or right moves it, by how far the finger moved, starting from the current weight.
  The keyboard arrows still work on the slider.
- Weight lock (decided 29 Oct, to stop the weight being moved by accident): a small padlock button at the bottom left
  of each row. Rows start unlocked. Locked, sliding the row or the slider (finger or keyboard) does nothing and the
  slider is greyed out; typing the weight, the − / + stepper and the scale's 'Use' still work, being deliberate.
  Tapping the padlock again unlocks. The lock is kept with the row while it is on the plate.
- Each row also counts the portion it came from, rounded to the nearest quarter (decided 28 Oct): '≈ 1¾ servings',
  '≈ 2¼ Tbsp', worked out from the weight (converted to the portion's dry or cooked state first). Less than an eighth
  shows as 'under ¼'. It is a guide to the amount; the carbs always come from the grams. The '≈' and the number sit in fixed-width
  slots so the line doesn't shift while the weight is dragged.
- The plate shows the total weight of food (the sum of the grams) next to the carb total.
- Saved to the log as the weighed grams (quantity 1); the portion's name is kept as the snapshot label.
- Dry or cooked (decided 28 Oct): for a dry / raw or cooked food, the row says which weight it expects. If the food has
  a measured cooking ratio, a 'Weighed: Dry / raw | Cooked' switch lets the weight be either.
- The switch changes how the same food is weighed, never how much food (decided 28 Oct, replacing a switch that kept the
  grams and changed the carbs): switching converts the grams with the ratio and the carbs stay the same
  (½ serving = 90 g dry = 216 g cooked = 64 g carbs). Under the switch the row says both weights, e.g. '90 g dry / raw
  = about 216 g cooked · ×2.4' (the other weight in whole grams; the date the ratio was weighed is left off the plate,
  decided 28 Oct, and shown on the food). A dry / raw food with a ratio starts on Cooked, the way it is served.
  Without a ratio the row says 'Weigh it dry / raw, before cooking' and that a cooking ratio on the food allows a cooked weight.
- Plate rows follow the food (decided 28 Oct): when a food's cooking ratio, state or carbs change, rows already on the
  plate pick up the change; the amount of food on the plate is kept.
- Carbs entered by hand (decided 29 Oct), for something not in the food list (a slice of party cake, a snack at a
  friend's): '+ Add carbs by hand' under the rows, and on the empty plate, takes grams of carbs (0.5 to 300) and a
  short description, which is required so the log says what it was. The row shows 'Entered by hand' instead of a
  weight; its carbs and description can be changed or the row removed. It counts in the plate total and the meal
  summary's dose, not in the weight of food. It has no food behind it, so it can't be confirmed, weighed or kept in a
  favorite (pinning the plate leaves it out and says so).
- A food the signed-in person hasn't confirmed shows its carbs and a 'Confirm' button on its row
  (okf/features/confirm-food.md).
- With a Bluetooth scale connected, 'Use' copies the steady reading to a row (okf/features/kitchen-scale.md).
