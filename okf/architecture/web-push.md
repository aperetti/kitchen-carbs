---
type: Architecture
title: "Web Push"
description: "The server sends standard Web Push messages (VAPID, encrypted payload) to the browsers' own push services; the service worker shows them."
tags: [architecture]
timestamp: 2026-10-31
status: draft
links:
  serves: [features/notify-family.md]
  depends_on: [architecture/install.md, architecture/https.md, architecture/storage.md, architecture/migrations.md]
---
# Web Push
- Library: pywebpush. The VAPID key pair is made on first use and kept in the settings table on the home server;
  only the public key reaches browsers. The VAPID contact is the app's own https address.
- Each subscription (endpoint and its keys, the account that turned it on, a device label) is a row in
  push_subscriptions (migration 15). Removed when the push service says it's gone (404 or 410).
- Payloads are encrypted for each browser (RFC 8291), so Google's and Apple's push services carry them without
  reading them.
- Sending runs on a background thread after the meal or entry is saved, so saving never waits on a push service and a
  failed push never fails a save.
- The app sends its own subscription endpoint with each save, and that device is skipped.
- sw.js shows the notification and opens or focuses the app on the Log when it's tapped; it still caches nothing.
- KC_ENV=qa sends nothing.
