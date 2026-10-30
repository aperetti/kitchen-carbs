---
type: Architecture
title: "Database migrations"
description: "Numbered, forward-only schema changes recorded in the database (PRAGMA user_version), each run in a transaction after an automatic backup."
tags: [architecture, data]
timestamp: 2026-10-27
status: draft
links:
  changes: [architecture/storage.md]
  governed_by: [rules/backup-before-change.md]
---
# Database migrations
- `app/server/migrations.py` holds an ordered list; the database stores the last one applied.
- Version 1 is the whole schema as first deployed (27 Oct, to the homelab). It is now frozen: every schema change
  from here on is a new migration appended to the list, which backs up the database first.
- On start, pending migrations run in order, each in its own transaction; a failure rolls back and the app refuses to start.
- Before the first pending migration on an existing database, it is copied to `data/backups/pre-migration-v{from}-to-v{to}-{time}.db`.
- A database newer than the code (e.g. old code started on a QA copy) is refused rather than guessed at.
- Adding a feature that changes tables = append a migration. Never edit or reorder old ones.
- Version 2 (27 Oct): sessions table for Google sign-in (okf/architecture/auth.md).
