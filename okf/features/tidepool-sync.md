---
type: Feature
title: "Send to Tidepool"
description: "A parent turns on sending the log to the family's Tidepool account in Manage → Settings, choosing which kinds of data go: carbs, meter BG and insulin. It keeps Tidepool in step as meals and entries are added, changed or deleted."
tags: [feature, tidepool]
timestamp: 2026-10-31
status: draft
links:
  uses: [domain/meal.md, domain/manual-entry.md, domain/meal-log.md]
  constrained_by: [rules/tidepool-sends-what-was-logged.md, rules/tidepool-login-server-only.md, rules/no-dosing.md, rules/glucose-units.md]
  depends_on: [architecture/tidepool-client.md]
---
# Send to Tidepool
Decided 31 Oct: the family asked to synchronise the log to Tidepool, set up in Settings, with every kind of data
available and each one switchable.
- Manage → Settings → Tidepool (parent PIN): server (Tidepool's test server, or Tidepool), the Tidepool email and
  password, optionally the Tidepool account ID to send to when signing in as a caregiver, 'Send from' (a date;
  30 days ago by default), and a switch for each kind of data:
  - **Carbs** (on by default): each meal as a food record with its foods and total carbs (a corrected total wins),
    and each entry's typed carbs.
  - **Meter BG** (off by default): BG typed from a meter, on a meal or an entry. A meal's BG taken from the CGM is
    never sent; Tidepool gets CGM from the CGM itself.
  - **Insulin** (off by default): insulin typed on a meal or an entry, as an injection record (rapid- or
    long-acting), at the time it was given. It warns: 'Only turn this on if the pump's or pen's own data doesn't reach
    Tidepool, or Tidepool will count the same insulin twice.'
- 'Connect' signs in once to check the login, then saving turns sending on. The status shows the server, the account,
  when it last sent and how many records are in Tidepool, or the last error in the warn colour.
- Kept in step: a new or changed meal or entry is sent within a minute (and every 5 minutes anyway); a deleted one,
  or one whose kind is switched off, is removed from Tidepool. Edits re-send the record, replacing the old one.
- 'Send now' sends straight away. 'Turn off' stops sending and leaves what's in Tidepool. 'Remove from Tidepool'
  (tapped twice) deletes everything Kitchen Carbs sent, and nothing else.
- Kitchen Carbs' records live in their own Tidepool data set ('Kitchen Carbs'), apart from the pump's and CGM's, so
  nothing from other devices is changed or removed.
- Off in QA and when no login is saved. Dev should use Tidepool's test server.
