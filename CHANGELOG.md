# Release notes
Each version is what went to the family's kitchen on that date (okf/architecture/releases.md).

## Unreleased
- Manage → Foods and photos: **Generate missing photos** makes a photo for every portion that has none, one at a
  time. Portions of a food that already has a photo are estimated from it; the rest are drawn from the food's name.
  Each one still waits for a parent to check it.
- The app's font is now called Kitchen Sans inside its files (a trimmed IBM Plex Sans, renamed as its license asks).
  It looks the same.
- The Open Food Facts contact address now comes from the server's settings file instead of the code.
- Tidepool records are now sent under the client name `app.kitchencarbs`; after this update every record is sent
  once more, replacing the old ones in the same data set.
- Licensed under the GNU General Public License v3.

## v2026.10.31.4 · 31 Oct 2026, 2:15 pm
- Tidepool: bolus and rapid-acting insulin go to Tidepool as boluses, and basal or long-acting as a basal, so
  Tidepool's bolus/basal split and daily totals include them.
- Tidepool: a parent sets how long a basal dose is spread, from 1 hour to 7 days (24 by default; 42 for Tresiba,
  168 for a weekly insulin). A dose ends early when the next long-acting dose is logged.
- Tidepool: 'Resend everything' sends every record again; Tidepool replaces each one, so nothing doubles.

## v2026.10.31.3 · 31 Oct 2026, 10:17 am
- Tidepool sync in Manage → Settings: carbs, meter BG and insulin (each switched on separately) go to the family's
  Tidepool account in Kitchen Carbs' own data set, kept in step as meals and entries are added, changed or deleted.
  CGM readings and calculated doses are never sent. Try it on Tidepool's test server first.

## v2026.10.31.2 · 31 Oct 2026, 9:27 am
- Log: change a meal in place (time, insulin, how much was eaten, a carbs correction, a comment) and save it all
  from one floating Save bar that appears when something changed.
- Log: manual entries can be edited too: BG, carbs, insulin and its type, and the note.
- Log: 'Add entry' scrolls down to the new entry's form.
- Export: a formatted PDF of the log, with daily glucose traces and time in range, beside the CSV.

## v2026.10.31 · 31 Oct 2026, 8:36 am
- Notifications: parents' phones can get a push notification, with the details, whenever a meal or entry is
  logged. Turn it on per phone in Manage → Settings.
- Log: an edited meal or entry shows a small pencil mark; comments and 'Carbs edited' show in the row, and so does
  the BG saved with a meal.
- Meal summary: choose the meal's date and time before saving it to the log.
- Foods: searching inside a category also lists matches from other categories underneath.
- Scan several: choose tags for each scanned food.
- Manage: accepting a photo saves the food's unsaved changes first.

## v2026.10.30.3 · 30 Oct 2026, 2:21 pm
- Foods: tapping a food with more than one portion asks which portion to add.

## v2026.10.30.2 · 30 Oct 2026, 8:27 am
- Favorites: Gemini combines the photos of a favorite's foods into one photo of the whole plate, checked before
  it's used.

## v2026.10.30 · 30 Oct 2026, 6:43 am
- Manage on phones: the screen no longer scrolls sideways.

## v2026.10.29 · 27–29 Oct 2026
The first version in the kitchen, built up over the deploys of 27 to 29 October (before the code was in git).
- **Foods**: foods with carbs per 100 g from the label, FatSecret or Open Food Facts, named portions, tags
  (Breakfast, Lunch, Dinner and your own), favorites, barcode scanning (one or several at a time), label photos,
  dry/raw/cooked weights with a measured cooking ratio, fiber for reference, and a check that each account confirms
  a food's carbs once.
- **Plate**: weight sliders or a Bluetooth kitchen scale (Etekcity ESN00 and standard scales) for each food, carbs
  typed by hand for anything not in the list, and the total.
- **Meal summary**: BG, insulin given and timing saved with the meal. A dose calculated from the parent's ratios by
  time of day is shown on this one screen only; it is never stored or sent.
- **Log**: meals and manual entries by day, with what was eaten, comments, carb corrections with a reason, moved
  dates and times, soft delete with restore, CGM curves and stats from Nightscout (read only), and CSV export.
- **Photos**: Gemini styles your photos to match the family's plates, estimates other portions from them, or draws
  one from the name; every photo is checked before use and estimated ones are marked.
- Google sign-in with a family allow list, a parent PIN for Manage, installable on phones, and a backup before
  every change.
