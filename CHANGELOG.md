# Release notes
Each version is what went to the family's kitchen on that date (okf/architecture/releases.md).

## Unreleased
- After meals: new Every day · Weekdays · Weekends & holidays buttons. US holidays count automatically, and school breaks or other days off can be added in Manage → Settings → Days off. Meals on a day off say why (Saturday, Thanksgiving, Winter break).
- Plate: one plate for the whole family. Whatever is put on it, weighed or removed on the tablet shows on the phones within a few seconds, and the other way round. Saving it to the log empties it everywhere.
- After meals: "Insulin backed out" is now a tick box beside Rise · mg/dL. With mg/dL, each meal starts at its real BG instead of 0, so you can see where glucose would have gone from there without the insulin.

## v2026.11.09.2 · 9 Nov 2026
- After meals: the explanation under the chart is now behind an ⓘ beside the chart's title.
- After meals: tap a line on the chart to see which meal it is (date, time, foods, carbs and rise), with a link to open it in the log.

## v2026.11.09 · 9 Nov 2026
- Meal summary: simpler layout. The dose and the correction switch at the top with short warnings, a tidy breakdown table (with Details for the long explanations), then what was given, including the date and time.
- Meal summary: a typed BG of 400 or more is highlighted with a "High BG check" so a typo (488 for 188) is caught before using the dose.
- Meal summary: an old CGM reading (like "182 mg/dL, 13 days ago") is no longer shown; it just says there's no CGM reading in the last 15 minutes.
- Meal summary: insulin on board now comes through from Nightscout when it's worked out from logged boluses. Before, it said "Not available".
- Meal summary: "Add a BG correction" is now on the same line as the insulin amount, and greyed out when there's no BG.
- Meal summary: a "Use 2.10 u" button beside Insulin given copies the worked-out dose into the box with one tap. The box still starts empty.
- Meal summary: the blood glucose box is now smaller and sits in the worked-out steps, just above insulin on board.
- Meal summary: the date and time are now at the bottom, just above Save to log.
- Meal summary: shorter. Where the BG came from and "Check it against the pump" are now behind small ⓘ buttons; tap one to read it.
- Meal summary and log: the "Time to eat" box is gone. Meals that already have one keep it.
- Plate: no time box any more; the date and time are set in the meal summary. The "Save to log shows the meal summary first" note is behind an ⓘ.
- Log: the › arrow now goes past today, so you can look at tomorrow and later days to see the meals planned for them.

## v2026.11.08 · 8 Nov 2026
- Log: tapping a meal now shows each food's total weight and portion in brackets, like "Pasta, 45 g carbs (240 g · 2 cups)".

## v2026.11.07 · 7 Nov 2026
- After meals: new Breakfast / Lunch / Dinner buttons show only those meals in the chart, food rows and list. Meals are sorted by the time they were logged: breakfast before 11 am, lunch 11 am–4 pm, dinner after 4 pm.

## v2026.11.06 · 6 Nov 2026
- Copy for school: each planned meal now lists every food with just its carbs (no weights), then a Total line.
- A new portion (like 2× or ½× a serving) now just shows the serving's photo instead of asking Gemini to draw one. It's marked "Same photo as another portion"; you can still upload a real photo or tap Estimate.

## v2026.11.05.4 · 5 Nov 2026
- Editing a meal in the log now lets you change its foods: change a food's weight, remove one with ×, or add one with a quick search of the food list (small photos, compact rows), then pick its serving. The change is written into the meal's comments, so what was first logged is still on record.
- The meal summary has an "Add a BG correction" switch. If a correction was given in the last 3 hours (a Nightscout correction bolus, or a rapid-acting shot logged without carbs), it starts off and names that correction; switching it on shows a warning that the earlier one may still be acting. The 3 hours can be changed (1 to 6) in Manage → Settings, under the insulin settings.
- On a phone, the food list now leaves room at the bottom while the keyboard is open, so the last search results can be scrolled up above it.

## v2026.11.05.3 · 5 Nov 2026
- The Copy button is shorter for meals already eaten: one line each with the carbs and when the bolus was given. Planned meals still list every food.

## v2026.11.05.2 · 5 Nov 2026
- Log → Export has a new Copy button: it copies the day's meals (foods, weights, carbs, BG and insulin as given) and the upcoming planned meals as plain text, ready to paste into an email for school.

## v2026.11.05 · 5 Nov 2026

- After meals now reads his boluses from Nightscout too (pump, Loop including its automatic boluses, or a pen app), so the insulin beside each meal and the "Insulin backed out" view include insulin that was never typed into the app. A bolus that's both logged here and in Nightscout counts once. Temp basals still aren't included.
- After meals has a new "Insulin backed out" view: it adds back roughly what the logged insulin lowered his glucose by, so meals given different insulin can be compared by what the food did. It's an estimate from your correction factor and a standard rapid-acting insulin curve, counts only insulin entered in the app, and is for spotting patterns with the care team, never for working out doses.
- The log now shows when a meal's insulin was given, e.g. "2.5 u bolus @ 5:50 PM", in the list and in the meal's details.
## v2026.11.04 · 4 Nov 2026
- When the sensor misses readings for 10 to 60 minutes, the glucose charts now fill the gap with a dashed estimate (the same AR2 method Nightscout uses for its forecast, run from both sides of the gap). The numbers under the charts still come only from real readings, and longer gaps stay blank.
- New "After meals" page, from the Log: every meal's glucose for the 3 hours after eating, lined up at mealtime, with how much it rose, when it peaked, whether it was back in range by 2 or 3 hours, and the insulin and its timing. Foods eaten 2 or more times are grouped so you can compare them ("Pizza, 4 meals: average rise +110 mg/dL"). It shows patterns only, for you and the care team; it never suggests doses or ratio changes.
- A new meal's time is now the time he'll likely start eating: now plus the wait from his BG (BG ÷ 10 minutes, none under 80), or 15 minutes when there's no BG. It updates if a different BG is typed in the summary, and stays put once you change the time yourself.
- Searching foods now looks through every food, even when a tag like Breakfast or Favorites is chosen, so it never says "nothing matches" while the food is further down. Tapping a tag clears the search.
- Manage now has two tabs, Foods and photos and Settings. Photo style and Tags are sections in Settings, after Food lookup. Their changes save with the same "Unsaved changes" bar. Lock has moved to the top bar, at the right, and shows while Manage is unlocked.
- Editing a meal in the log now shows its carbs ready to change and a Note box. A note is added to the meal's comments. Changing the carbs still asks why. "Change total carbs" is no longer in the ⋯ menu.

## v2026.11.03 · 3 Nov 2026
- If a bolus is typed while the BG is under 70 mg/dL, the meal summary and Add entry now show a warning to treat the low first and follow the care team's plan. It uses the meter reading, or a CGM reading under 15 minutes old. Saving still works, so the log shows what was actually given.
- Settings now save the same way as the log: change anything and an "Unsaved changes" bar floats up with one Save and Discard. The separate Save buttons are gone. Connecting Nightscout or turning on sending to Nightscout or Tidepool still has its own button.
- On a phone, the "Unsaved changes" bar on a meal stays at the bottom of the screen instead of hiding under the card.
- The parent PIN screen fits narrow phones without scrolling sideways.
- A calmer log:
  - A meal, entry or plan now opens as a plain summary. Tap Edit to change the date, time, BG, insulin or carbs; "How fast it rose", "How much was eaten" and comments can still be tapped straight away.
  - Rarely used actions (Change total carbs, Pin as favorite, Delete) are in a ⋯ menu next to Edit.
  - Each row keeps every food's carbs, with one short line under it: BG → 2 h and insulin.
  - Insulin and the day's glucose are one line under the date; tap it for the full stats and the 7 and 14 day views.
  - Export is a single button until you need it.
- On a phone, tapping a meal, entry or plan in the log opens it as its own screen that slides in, instead of scrolling down below the list. The phone's Back gesture, the "‹ Log" button or a swipe to the right takes you back to the list where you were.
- Insulin timing is now counted from the meal's time: one box, "Given N min before the meal" (0 means at the meal time), with the clock time shown beside it. It starts at the BG divided by 10 (BG 150: 15 min), or at the meal time when the BG is under 80 or not known, and follows the BG until you type the minutes. The Before eating / At the start / After starting buttons are gone; older meals logged as "after starting" keep that.
- Plan a meal ahead: build a plate, tap Plan for later and pick a date and time. Plans wait in today's log under Planned and on the empty plate, and aren't counted until you put one on the plate and save it. Nightscout shows a plan as a note with no carbs, so forecasts only count what was eaten.
- The log can show times as 12-hour with AM/PM (6:30 PM) instead of 24-hour. Turn it on under Manage → Settings → Log; it applies for the whole family and to the PDF export.
- The meal summary's insulin can now round down to 0.05, 0.1, 0.5 or 1 unit, to match the pump or pen. Set it under Manage → Settings → Insulin settings; it stays at 0.05 until you change it.

## v2026.11.02.2 · 2 Nov 2026
- **Fill in fiber** (Manage → Foods and photos) now lists every food without fiber. Foods with nothing to look up
  again get a box to type it from the package or the care team's numbers, ticked like the rest. Saving a food's fiber
  also adds it to logged meals with that food that had none.

## v2026.11.02 · 2 Nov 2026
- **Fiber in the log**: each meal shows its fiber beside the carbs ("Including 4.5 g fiber"), and names any foods
  without fiber. The PDF shows each day's fiber total. Fiber is for reference only and is never taken off the carbs.
  Meals saved before today get their fiber from the foods as they are now.

## v2026.11.01.5 · 1 Nov 2026
- Nightscout connects even when it has no glucose readings yet, so the log can be sent before the CGM is set up.

## v2026.11.01.4 · 1 Nov 2026
- Manage: **Nightscout moved into Settings**, and Settings is reordered: food lookup and accounts first, then
  insulin, the log, Nightscout, Tidepool, notifications and the scale. Settings now has a list of its sections down the side (across
  the top on a phone) to jump straight to one. 'Send to Nightscout' now shows even before Nightscout is connected,
  saying to connect it first. On the test copies its options show greyed out, since only the kitchen's real copy sends.

## v2026.11.01.3 · 1 Nov 2026
- Manage → Foods and photos: **Check new photos** goes through every new photo one after another, with Use, Try
  again, Discard and Skip, without opening each food.
- **Send to Nightscout** (Manage → Nightscout, off until switched on): the log's carbs, rapid-acting insulin and meter
  BG go to Nightscout as treatments, so OpenAPS can forecast with them, starting 30 days back. Edits and deletes
  follow within a minute. Long-acting insulin goes only as a note, so it is never counted as insulin on board; set
  it as the basal rate in the Nightscout profile. The token needs a role with `api:treatments:*`.
- **Rate a meal**: in the log, rate how fast glucose rose after each meal (🍭 fast, 🌮 medium or 🍕 slow, as in Loop and twiist). The curve now also shows how much glucose rose in the first hour and when it peaked. Each food's details
  show how the meals it was in were rated, and its card says "🍭 Fast rise" or "🍕 Slow rise" when most of them agree.
  The ratings are in the CSV and PDF too.

## v2026.11.01.2 · 1 Nov 2026
- Only the app itself and the family's own dashboard (set on the server) can show Kitchen Carbs inside a frame.

## v2026.11.01 · 1 Nov 2026
- **Security fix:** a crafted request on the home network could read and change the log without signing in.
  Every request is now checked against the path the server actually serves, odd Host headers are refused, and
  the web framework and other packages are updated past their known security problems.
- Exports and photos are marked private, so Cloudflare never keeps a copy it could hand to someone else.
- The parent PIN locks for 10 minutes after 10 wrong tries. Production and QA won't start without Google sign-in
  set up. Exported CSV files can't carry spreadsheet formulas from food names.
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
