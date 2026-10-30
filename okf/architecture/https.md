---
type: Architecture
title: "HTTPS through Cloudflare"
description: "Production is reached over HTTPS through the family's Cloudflare Tunnel, which handles the certificate; the app itself serves plain http, and dev runs plain http on localhost."
tags: [architecture]
timestamp: 2026-10-28
status: draft
links:
  serves: [features/food-lookup.md]
  depends_on: [architecture/docker-server.md]
---
# HTTPS through Cloudflare
Decided 28 Oct, replacing Caddy with its own certificate (production) and the self-signed certificate (dev).
- Production: a Cloudflare Tunnel, set up outside this app, terminates HTTPS and forwards to the app's plain http port
  (8092). Nothing in this project handles certificates. The sign-in cookie is marked Secure when the tunnel says the
  request came in over https (X-Forwarded-Proto).
- Anyone reaching the app over plain http through Cloudflare (X-Forwarded-Proto: http) is redirected to the same
  address on https (28 Oct): a Home Assistant card pointing at http:// couldn't keep the sign-in cookie. Direct LAN
  and localhost requests carry no such header and are left alone.
- Dev: plain http. Browsers treat http://localhost as secure, so the camera, Bluetooth and Google sign-in work on the
  laptop itself. From another device by LAN address (plain http) the live barcode scanner and the kitchen scale are
  unavailable; the photo and typed-digit fallbacks still work.
- Camera (live barcode scanner) and Web Bluetooth (kitchen scale) both need this secure address.
- The app's pages, scripts and styles are sent with `Cache-Control: no-cache` (28 Oct): Cloudflare otherwise told
  browsers to keep .js and .css for 4 hours, so a deploy (sign-in) didn't reach a browser that had the old app.js. Cloudflare's Browser Cache TTL overrides that
  header for .js and .css, so the page (never cached) also asks for them by a hash of their contents (app.js?v=…).
