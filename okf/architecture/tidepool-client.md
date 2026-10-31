---
type: Architecture
title: "Tidepool client"
description: "A background job in the server that keeps one continuous Tidepool data set in step with the log: it uploads new and changed records and deletes removed ones, tracked by a table of what was sent."
tags: [architecture, tidepool]
timestamp: 2026-10-31
status: draft
links:
  serves: [features/tidepool-sync.md]
  depends_on: [architecture/storage.md, architecture/migrations.md, architecture/docker-server.md]
---
# Tidepool client
- Servers: test `https://external.integration.tidepool.org`, real `https://api.tidepool.org`. Tidepool asks
  developers to try the integration server first.
- Sign-in: `POST /auth/login` with the email and password (HTTP Basic) returns `X-Tidepool-Session-Token` and the
  user ID. Tidepool marks this login as deprecated in favour of OAuth with a registered app; that is the upgrade path.
  The token is kept in memory and renewed by signing in again on a 401.
- Data set: one per server and account, `POST /v1/users/{userId}/data_sets` with `dataSetType: continuous`,
  client `app.kitchencarbs`, deduplicator `org.tidepool.deduplicator.dataset.delete.origin`. Its ID is kept
  in settings and found again by client name if lost.
- Records carry `origin.id` like `kc-meal-12`, `kc-meal-12-bg`, `kc-meal-12-insulin`, `kc-entry-7-carbs`; sending
  a record with the same origin ID replaces the earlier one. `deviceId` is `KitchenCarbs-{server name}`. Times are the
  server's local time converted to UTC with its `timezoneOffset`.
  - food: `nutrition.carbohydrate {net, units: grams}`, `name` (the foods, up to 100 characters), `meal`
    (breakfast before 10:30, lunch until 15:00, dinner after, the app's own times), `brand: Kitchen Carbs`,
    `code` (the origin ID), and `notes` (how much was eaten).
  - smbg: `subType: manual`, `units: mg/dL`, `value`.
  - Insulin goes as the types Tidepool charts and counts as bolus or basal, not its generic `insulin` event (which
    Tidepool shows without the bolus/basal split). A meal's insulin is at the meal time minus its 'given before' minutes.
    - bolus (bolus or rapid-acting, and insulin with no type): `subType: normal`, `normal` = the units given.
    - basal (basal or long-acting): `deliveryType: scheduled`, `rate` = units ÷ hours per hour, `duration` the hours set in
      settings (`tp_basal_hours`, 24 by default, 1–168; Tidepool's longest basal is 7 days), cut short at the next long-acting dose so two never overlap (Tidepool then shows less than the dose for that
      day). Changing a dose, or adding the next one, re-sends the earlier one with its new length;
      changing the hours re-sends every basal.
- tidepool_sent (migration 16): each origin ID sent, a hash of what was sent and when. Each run builds the records
  wanted from 'Send from' on, uploads the new or changed ones (up to 1,000 a request), and deletes the ones no longer
  wanted with `DELETE /v1/data_sets/{id}/data` and their origin IDs. Changing server or account starts a fresh table.
- Runs every 5 minutes and within about a minute of a meal or entry being saved, changed or deleted. Errors are kept
  for the settings screen; the next run tries again. KC_ENV=qa never sends.
