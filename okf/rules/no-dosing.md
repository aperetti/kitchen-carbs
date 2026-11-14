---
type: Rule
title: "Dosing only in the meal summary and Correct BG"
description: "Two places calculate insulin, both from the parent's own settings with every step shown: the summary shown when a meal is saved, and Add entry's Correct BG. Nothing else in the app suggests, checks or fills in a dose."
tags: [safety]
timestamp: 2026-11-13
status: draft
links:
  applies_to: [features/meal-dose-summary.md, features/manual-log.md, domain/insulin-settings.md]
---
# Dosing only in the meal summary
Until 29 Oct the app never calculated insulin. On 29 Oct the parent decided the meal summary should show a calculated dose
(okf/features/meal-dose-summary.md). On 13 Nov the parent added a correction-only version to Log → Add entry, 'Correct BG'
(okf/features/manual-log.md), with the same rules below. Everywhere else the old rule stands.
- Only the meal summary and Add entry's Correct BG calculate. The log, stats, food cards and entries never suggest, check or pre-fill a dose;
  insulin in the log is still only what a parent typed (okf/domain/manual-entry.md, okf/domain/meal.md). The insulin box
  in the meal summary starts empty. Beside it, '← Fill in 2.10 u' copies the calculated dose in with one tap (decided 8 Nov,
  instead of pre-filling: nothing is logged as given unless someone taps it or types it; called 'Use 2.10 u' until
  10 Nov, when it confused a family member). Once in the box it is an
  ordinary typed amount: it doesn't follow later changes to the dose, and can be changed or cleared before saving.
- A warning when a bolus is typed with a BG under 70 mg/dL (okf/rules/low-bg-bolus-warning.md, decided 3 Nov) is not a
  dose check: it says nothing about the amount and never blocks saving.
- Inputs are the parent's own settings, set behind the parent PIN (okf/domain/insulin-settings.md). No settings, no number.
- Every step is on screen: carbs ÷ carb ratio, (BG − target) ÷ correction factor, insulin on board, the total.
- Rounded **down** to the step set with the insulin settings (0.05, 0.1, 0.5 or 1 u, matching the pump or pen; 0.05 u
  unless changed, decided 2 Nov), never up, and never below zero.
- BG from the CGM only if the reading is under 15 minutes old; otherwise it must be typed. It can always be overwritten.
- Insulin on board comes from Nightscout and is taken off the correction only. If Nightscout has none, the summary says
  plainly that nothing was taken off.
- The app never gives the dose to the pump, never writes it to Nightscout (okf/rules/nightscout-sends-what-was-logged.md) and never
  logs it as given unless a parent puts it in the insulin box ('Fill in … u' or typing). It says to check it against the pump before giving.
