---
type: Architecture
title: "Storage"
description: "SQLite database and photo files on a Docker volume; nightly JSON/CSV backup into the same volume."
tags: [architecture]
timestamp: 2026-10-26
status: draft
links:
  governed_by: [rules/backup-before-change.md]
  stores: [domain/manual-entry.md, domain/tag.md, domain/favorite-plate.md, domain/food.md, domain/portion.md, domain/photo.md, domain/meal-log.md, domain/glucose-reading.md]
---
# Storage
./data/app.db, ./data/photos/{original,styled}/, ./data/backups/.
