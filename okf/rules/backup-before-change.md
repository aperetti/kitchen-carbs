---
type: Rule
title: "Back up before any change"
description: "No change touches the production database without a copy first: migrations back up automatically, deploys snapshot production, and new code is tried on a QA copy."
tags: [data, safety]
timestamp: 2026-10-27
status: draft
links:
  applies_to: [architecture/storage.md, domain/meal-log.md]
---
# Back up before any change
The meal log is a medical record for the family and care team; losing it is not acceptable.
Backups are plain SQLite files; restoring is copying one back to data/app.db with the app stopped.
