---
type: Feature
title: "Confirm a food's carbs"
description: "Each family account confirms a food's carbs once, from the plate, before relying on it; a change to the carbs asks everyone else to confirm again."
tags: [feature, safety]
timestamp: 2026-10-29
status: draft
links:
  uses: [domain/food.md, domain/plate.md, domain/family-account.md]
  constrained_by: [rules/provenance-required.md]
---
# Confirm a food's carbs
Decided 29 Oct, so that everyone who weighs a meal has looked at each food's carb value at least once.
- A confirmation belongs to one signed-in account (its email) and one food. It is kept in the database, so it follows
  the person to any device.
- On the plate, a food the signed-in person hasn't confirmed shows a 'Not checked by you' line under its name with
  the carbs per 100 g, the cooking ratio if it has one, where the value came from, and a 'Confirm' button. Confirming
  takes no PIN; it is the person's own check. Once confirmed the line goes away.
- An unconfirmed food can still be weighed and saved to the log (not decided otherwise); the line is a prompt.
- When the carbs-to-weight change (the carbs per 100 g, or the cooking ratio's weighed batch), every confirmation of
  that food is cleared except the one of the person who made the change, who counts as having confirmed the new value.
  Other edits (name, tags, photos, portions, notes, fiber) keep confirmations.
- A new food counts as confirmed by the person who added it.
- Foods that existed before 29 Oct start unconfirmed for everyone, including the parent who entered them.
- With sign-in turned off (local development without Firebase) there is no person to confirm, so the line is not shown.
