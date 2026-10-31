---
type: Feature
title: "Notify parents' phones"
description: "A phone that turns it on gets a notification whenever a meal is saved or a manual entry (BG, insulin, carbs) is added, from any device, with the numbers that were logged."
tags: [feature]
timestamp: 2026-10-31
status: draft
links:
  uses: [domain/meal.md, domain/manual-entry.md, domain/meal-log.md, domain/family-account.md]
  constrained_by: [rules/no-dosing.md, rules/glucose-units.md, rules/allowlisted-accounts-only.md]
  depends_on: [architecture/web-push.md]
---
# Notify parents' phones
Decided 31 Oct: a parent wants to know when a meal or measurement is logged without opening the app. Delivered as
phone push from the app itself (no separate app or account); the notification shows the full details.
- Manage → Settings → Notifications (parent PIN): 'Notify this device' turns it on for the phone or browser in hand
  (the browser asks for permission first), 'Turn off' stops it, 'Send a test' sends one to this device only.
  The list below shows every device that gets notifications, by account and device type, each with Remove.
- iPhone and iPad only allow it once the app is installed to the Home Screen and opened from there (iOS 16.4 or
  later); in Safari the section says so with the Share → Add to Home Screen steps (okf/features/install-app.md).
- Sent when a meal is saved (including a queued meal arriving later) and when a manual entry is added. Not for
  edits, comments, moves or deletes. The device that logged it is not notified.
- Meal: 'Meal logged · 48 g carbs', then the time (with the day if not today), the foods, and any BG and insulin typed
  with it: '12:30 · Pasta, Apple · BG 182 mg/dL · 2.5 u rapid-acting'.
- Entry: 'BG 182 mg/dL · 2.5 u rapid-acting · 15 g carbs' (what was typed, in that order), then the time and note.
- Never includes the calculated dose from the meal summary (okf/rules/no-dosing.md); insulin is only what was typed.
- Tapping the notification opens the app on the Log.
- Off in QA: QA's database is a copy of production's, so its copied phone subscriptions must not get test meals.
