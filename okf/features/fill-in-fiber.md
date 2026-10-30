---
type: Feature
title: "Fill in fiber"
description: "Add fiber to foods saved before fiber was kept, read again from each food's own source and confirmed by a parent food by food."
tags: [feature, admin]
timestamp: 2026-10-28
status: draft
links:
  uses: [domain/food.md, domain/nutrition-source.md, domain/nutrition-label.md]
  constrained_by: [rules/label-reading-needs-check.md, rules/provenance-required.md, rules/no-dosing.md, rules/backup-before-change.md]
---
# Fill in fiber
- Manage → Foods shows 'Fill in fiber' while any food has no fiber and a source the app can read again (decided 28 Oct).
- Each food is read again from where it came from, never from another product: Open Food Facts by its barcode,
  FatSecret by its food number, USDA by its FDC number, and a scanned label by its saved label photo (Gemini reads it
  again). Care-team and typed-in foods have nothing to read again; fiber is typed in on the food instead.
- Nothing is read until the parent taps 'Look up fiber'. Each row then shows the source's fiber for the food's own
  serving (scaled when the source's serving weight differs, saying so), the label photo when there is one, and a
  warning when the source's carbs no longer match the saved carbs (the carbs are not changed here).
- The fiber number can be edited; every row needs its own tick ('Matches the label' / 'Matches the source'), and editing
  the number clears it. 'Save N checked' saves fiber only on ticked rows; the carbs, portions and log are untouched.
- A source with no fiber listed says so, and that row can't be saved until a number is typed and ticked.
