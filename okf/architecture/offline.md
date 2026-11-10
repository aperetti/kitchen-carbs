---
type: Architecture
title: "Offline behaviour"
description: "The tablet keeps the food list, plate and unsent meals in its own browser storage; meals sync when the server is back."
tags: [architecture, reliability]
timestamp: 2026-10-26
status: draft
links:
  implements: [rules/offline-queue.md]
---
# Offline
Built 27 Oct. Browsers only allow service workers on HTTPS or localhost, and the tablet opens the app over
plain http on the home network, so there is no service worker:
- foods, a copy of the shared plate (okf/architecture/shared-plate.md) and queued meals are kept in localStorage on the tablet;
- a queued meal carries a client id, so sending it twice saves it once;
- the app keeps working while the page stays open; reloading needs the server.
Upgrade path: production is now reached over HTTPS through Cloudflare (okf/architecture/https.md); a service worker can be added on top.
