---
type: Rule
title: "Tidepool login stays on the server"
description: "The Tidepool password is kept only in the home server's settings, behind the parent PIN, and is never sent back to any screen."
tags: [tidepool, security]
timestamp: 2026-10-31
status: draft
links:
  applies_to: [architecture/tidepool-client.md]
  extends: [rules/nightscout-token-server-only.md]
---
# Tidepool login stays on the server
- Saved with the parent PIN; the settings screen only shows that a password is saved, never the password.
- Calls to Tidepool go from the server; no device talks to Tidepool directly.
- Not logged, not exported, not in backups shared outside the home server.
