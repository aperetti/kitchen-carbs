---
type: Rule
title: "Allow-listed accounts only"
description: "Only Google accounts with a verified email on the family's allow list can use the app; every API call and photo needs a signed-in session."
tags: [security, safety]
timestamp: 2026-10-27
status: draft
links:
  applies_to: [domain/family-account.md]
---
# Allow-listed accounts only
- The server checks the Firebase ID token itself (signature, project, expiry, verified email) and the allow list
  before creating a session; the browser's word is never taken for who is signed in.
- Removing an email from the list signs out that account's devices at their next request.
- Sign-in is off only when no Firebase project is configured, and only in dev: production and QA refuse to start
  without one.
- Nothing guarded is kept by a shared cache (Cloudflare), so a stored copy can't be served without sign-in.
