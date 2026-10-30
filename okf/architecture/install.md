---
type: Architecture
title: "Installable web app"
description: "Manifest with PNG icons and a pass-through service worker, so phones can install the app; nothing is cached by the worker."
tags: [architecture]
timestamp: 2026-10-28
status: draft
links:
  serves: [features/install-app.md]
  depends_on: [architecture/https.md]
---
# Installable web app
- manifest.webmanifest: name, start page, standalone display, icons 192 and 512 px PNG plus a maskable 512 px (and the SVG);
  a 180 px apple-touch-icon for iPhone and iPad.
- Icon (decided 28 Oct, option C on the review page): a green apple on a white plate on the quartz counter, drawn edge to
  edge with no rounded box of its own, so each phone's own square, squircle or circle mask shapes it; the plate sits
  inside the maskable safe zone. The browser-tab SVG has its own rounded corners.
- sw.js: Chrome only offers its install prompt when a service worker with a fetch handler is registered. The worker
  passes every request straight to the network and caches nothing, so offline behaviour stays as described in
  okf/architecture/offline.md and a deploy is never hidden behind an old copy.
- Needs the secure address (Cloudflare https, or localhost in dev).
