---
type: Feature
title: "Send to Nightscout"
description: "A parent turns on sending the log's carbs, rapid-acting insulin and meter BG to Nightscout as treatments, so OpenAPS (or another app reading Nightscout) can forecast with them. Kept in step as meals and entries are added, changed or deleted."
tags: [feature, nightscout]
timestamp: 2026-11-01
status: draft
links:
  uses: [domain/meal.md, domain/manual-entry.md, domain/meal-log.md]
  constrained_by: [rules/nightscout-sends-what-was-logged.md, rules/nightscout-token-server-only.md, rules/no-dosing.md, rules/glucose-units.md]
  depends_on: [architecture/nightscout-client.md]
---
# Send to Nightscout
Decided 1 Nov: the family doses with pens, a CGM uploads to Nightscout, and they want the logged carbs and insulin in
Nightscout for forecasting with OpenAPS, not a closed loop. Last 30 days included.
- Manage → Nightscout (parent PIN), under the connection: 'Send to Nightscout', with 'Send from' (a date; 30 days
  ago by default) and a switch for each kind, all on by default:
  - **Carbs**: each meal's total (a corrected total wins) as a 'Meal Bolus' treatment with its foods in the notes;
    carbs typed in an entry as a 'Carb Correction'.
  - **Insulin**: rapid-acting (bolus) insulin typed on a meal, at the time it was given (its before/after minutes),
    as a 'Meal Bolus'; on an entry as a 'Correction Bolus'. Long-acting (basal) insulin goes as a 'Note' reading
    'Long-acting insulin 12 u', never as insulin (okf/rules/nightscout-sends-what-was-logged.md).
  - **Meter BG**: a typed meter reading as a 'BG Check' (finger, mg/dL). A meal's BG from the CGM is never sent.
- The token must allow `api:treatments:*` (create, update and delete) as well as reading. Saving checks the token's
  permissions with Nightscout first, and says how to add the role if it can't send: Admin tools → Roles → Add new
  role 'kitchencarbs' with permission `api:treatments:*`; give that role and 'readable' to the token's subject.
- Warnings beside the switches: 'Set long-acting insulin as the profile's basal rate in Nightscout; it is sent only
  as a note.' and 'Switch a kind off if a pump or another app also puts it in Nightscout, or the forecast counts it
  twice.'
- Status: when it last sent and how many treatments are in Nightscout, or the last error in the warn colour.
- Kept in step: a new or changed meal or entry is sent within a minute (and every 5 minutes anyway); a deleted one,
  or a kind switched off, is deleted from Nightscout for good (not just hidden, so nothing reading Nightscout still
  counts it). 'Send now', 'Resend everything', 'Turn off' (leaves what's there) and 'Remove from Nightscout'
  (tapped twice; deletes only what Kitchen Carbs sent) work as for Tidepool (okf/features/tidepool-sync.md).
- Changing the Nightscout address turns sending off and forgets what was sent to the old site.
- Once sent, insulin on board in the meal summary comes from Nightscout's IOB plugin counting these boluses.
- Production only: QA, dev and demo never send.
