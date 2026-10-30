---
type: Architecture
title: "Nightscout client"
description: "A background job in the Docker server that pulls new CGM entries every 5 minutes and caches them in SQLite."
tags: [architecture, nightscout]
timestamp: 2026-10-27
status: draft
links:
  serves: [features/connect-nightscout.md, features/meal-glucose-view.md, features/glucose-stats-view.md]
  stores: [domain/glucose-reading.md]
  depends_on: [architecture/storage.md]
---
# Nightscout client
- `GET {site}/api/v1/entries/sgv.json?find[date][$gt]={last}&count=1000&token={token}`
- Family runs the latest Nightscout release. The v1 entries route with a `readable` token works there and on older sites; the v3 API (JWT from `/api/v2/authorization/request/{token}`) is the upgrade path if v1 is ever removed.
- For the meal summary (okf/features/meal-dose-summary.md), read live when it opens, cached for a minute:
  the latest entry (`/api/v1/entries/sgv.json?count=1`) and insulin on board from `/api/v2/properties/iob`
  (Nightscout's IOB plugin: from Loop, OpenAPS or the pump's device status, or bolus treatments), falling back to the
  newest `/api/v1/devicestatus.json` (`loop.iob.iob`, `openaps.iob.iob`, `pump.iob.bolusiob` / `pump.iob.iob`).
  IOB older than 15 minutes counts as missing. Still read-only.
- Profile (targets): `GET {site}/api/v1/profile.json`.
- First connect backfills 90 days; then incremental. Statistics are computed locally from the cache.
- If Nightscout is unreachable, the app keeps working; glucose views show 'last updated' time.
