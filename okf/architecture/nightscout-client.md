---
type: Architecture
title: "Nightscout client"
description: "A background job in the Docker server that pulls new CGM entries every 5 minutes and caches them in SQLite."
tags: [architecture, nightscout]
timestamp: 2026-10-27
status: draft
links:
  serves: [features/connect-nightscout.md, features/nightscout-send.md, features/meal-glucose-view.md, features/glucose-stats-view.md]
  stores: [domain/glucose-reading.md, domain/insulin-effect.md]
  depends_on: [architecture/storage.md]
---
# Nightscout client
- `GET {site}/api/v1/entries/sgv.json?find[date][$gt]={last}&count=1000&token={token}`
- Family runs the latest Nightscout release. The v1 entries route with a `readable` token works there and on older sites; the v3 API (JWT from `/api/v2/authorization/request/{token}`) is the upgrade path if v1 is ever removed.
- For the meal summary (okf/features/meal-dose-summary.md), read live when it opens, cached for a minute:
  the latest entry (`/api/v1/entries/sgv.json?count=1`) and insulin on board from `/api/v2/properties/iob`
  (Nightscout's IOB plugin: from Loop, OpenAPS or the pump's device status, or bolus treatments), falling back to the
  newest `/api/v1/devicestatus.json` (`loop.iob.iob`, `openaps.iob.iob`, `pump.iob.bolusiob` / `pump.iob.iob`).
  IOB older than 15 minutes counts as missing. The plugin's 'Care Portal' IOB (worked out from the bolus treatments
  in Nightscout, for sites with no Loop, OpenAPS or pump status) comes without a time because it is calculated as it is
  asked; it counts as now and shows as 'Nightscout, from logged boluses' (found 8 Nov: production showed none).
- Profile (targets): `GET {site}/api/v1/profile.json`.
- Insulin treatments (decided 4 Nov, for okf/domain/insulin-effect.md): the same job reads
  `GET {site}/api/v1/treatments.json?find[created_at][$gte]=…&find[created_at][$lt]=…&count=1000` in 3-day chunks
  and keeps each treatment with a number in `insulin` (Bolus, Meal Bolus, Correction Bolus, SMB, Combo Bolus: pump,
  Loop, AAPS or pen apps) in table `ns_insulin(id, date_ms, units, event_type, entered_by)`. Treatments Kitchen Carbs
  sent itself (`enteredBy: "Kitchen Carbs"`) are skipped: the log already has them. Each sync reads the last 24
  hours again and replaces them, so a bolus edited or deleted in Nightscout follows; the first one backfills 90 days.
  Temp basals have no `insulin` and aren't read. Read only, like the glucose.
- First connect backfills 90 days; then incremental. Statistics are computed locally from the cache.
- If Nightscout is unreachable, the app keeps working; glucose views show 'last updated' time.

## Sending treatments (okf/features/nightscout-send.md, decided 1 Nov)
A second background job, like the Tidepool one, keeps Kitchen Carbs' treatments in step with the log. It uses the
v3 API, which deduplicates by `identifier` and can delete one document for good:
- Sign in: `GET /api/v2/authorization/request/{token}` gives a JWT (kept in memory, renewed before it expires or on a
  401) and the token's `permissionGroups`, checked for `api:treatments:create`, `update` and `delete` before
  sending is turned on. Calls send `Authorization: Bearer <jwt>`.
- Each treatment: `date` (epoch ms), `utcOffset`, `app: "kitchen-carbs"`, `enteredBy: "Kitchen Carbs"`, `eventType`,
  and `device: "kitchen-carbs://<origin>"` where origin is e.g. `kc-meal-12`, `kc-meal-12-insulin`, `kc-entry-4-bg`.
  `identifier` is the v5 UUID Nightscout itself computes from device, date and eventType (namespace
  'NightscoutRocks!'), so the two agree. The date gets 1–999 ms from the origin so that Nightscout's fallback
  deduplication on `created_at` + `eventType` never merges it with another app's treatment logged in the same minute.
- `POST /api/v3/treatments` creates, or replaces the one with the same identifier. A moved meal, or a changed kind,
  has a new identifier: the old one is deleted first with `DELETE /api/v3/treatments/{identifier}?permanent=true`.
  A deleted meal or entry is deleted the same way. A 404 on delete counts as done.
- Table `nightscout_sent(origin_id, identifier, hash, sent_at)` records what is there; only new or changed records
  are sent. 'Resend everything' re-posts all (deduplicated by identifier, so nothing doubles).
- v3 sets `created_at` from `date`, so OpenAPS reading `/api/v1/treatments` sees them.
