---
type: Entity
title: "Family account"
description: "A Google account allowed into the app (a parent, or the child's own), and the long-lived sign-in session of each device that used it."
tags: [domain, security]
timestamp: 2026-10-27
status: draft
links:
  governed_by: [rules/allowlisted-accounts-only.md]
---
# Family account
- An email address on the family's allow list (kept in the app's settings, edited in Manage → Settings).
- A device session: created after a Google sign-in, kept in an HttpOnly cookie for 30 days and renewed while the
  device is used, so the kitchen tablet stays signed in for the child (decided 27 Oct).
- The parent PIN is separate and still guards Manage on a signed-in device.
