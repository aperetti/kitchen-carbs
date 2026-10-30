---
type: Rule
title: "Dosing only in the meal summary"
description: "One place calculates insulin: the summary shown when a meal is saved, from the parent's own ratios, with every step shown. Nothing else in the app suggests, checks or fills in a dose."
tags: [safety]
timestamp: 2026-10-29
status: draft
links:
  applies_to: [features/meal-dose-summary.md, domain/insulin-settings.md]
---
# Dosing only in the meal summary
Until 29 Oct the app never calculated insulin. On 29 Oct the parent decided the meal summary should show a calculated dose
(okf/features/meal-dose-summary.md). Everywhere else the old rule stands.
- Only the meal summary calculates. The log, stats, food cards and manual entries never suggest, check or pre-fill a dose;
  insulin in the log is still only what a parent typed (okf/domain/manual-entry.md, okf/domain/meal.md). The insulin box
  in the meal summary starts empty and is never filled in from the calculated dose.
- Inputs are the parent's own settings, set behind the parent PIN (okf/domain/insulin-settings.md). No settings, no number.
- Every step is on screen: carbs ÷ carb ratio, (BG − target) ÷ correction factor, insulin on board, the total.
- Rounded **down** to 0.05 u, never up, and never below zero.
- BG from the CGM only if the reading is under 15 minutes old; otherwise it must be typed. It can always be overwritten.
- Insulin on board comes from Nightscout and is taken off the correction only. If Nightscout has none, the summary says
  plainly that nothing was taken off.
- The app never gives the dose to the pump, never writes it to Nightscout (okf/rules/nightscout-read-only.md) and never
  logs it as given. It says to check it against the pump before giving.
