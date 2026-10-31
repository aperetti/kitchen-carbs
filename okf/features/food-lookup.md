---
type: Feature
title: "Look up a food"
description: "Find nutrition facts while adding a food: name search across USDA (generic foods) and Open Food Facts (packaged), or a barcode photo / typed digits for a packaged product."
tags: [feature, admin]
timestamp: 2026-10-30
status: draft
links:
  uses: [domain/food.md, domain/nutrition-source.md, domain/carb-value.md, domain/nutrition-label.md, domain/portion.md]
  constrained_by: [rules/label-reading-needs-check.md, rules/provenance-required.md, rules/whole-gram-rounding.md]
---
# Look up a food
- Manage → Foods → Add a food has three tabs: **Look up**, **Scan several** and **Type it in**. Look up holds every camera route: scan a barcode, photograph a barcode, photograph the nutrition label (okf/features/scan-label.md).
- Look up: Typing a name shows two groups: **FatSecret** (generic, restaurant and branded foods) and **Packaged (Open Food Facts)**.
- Barcode: the camera stays hidden until the parent taps 'Scan a barcode'; it then opens with an aiming box and a Stop button,
  and a barcode read twice in a row is looked up automatically (decided 27 Oct: no camera until asked for). Works on a secure address only (the Cloudflare https name, or localhost: okf/architecture/https.md); on plain http by LAN address, or if the camera is refused, photograph the
  barcode (read on the server) or type the digits. The camera stops when you leave the tab.
- Region (decided 27 Oct): packaged name search shows only products sold in one country, set in Manage → Settings
  (default United States, or All countries); results say which country, with a one-tap 'Search all countries'.
  Barcode lookups are never filtered: a barcode is one exact product.
- Packaged results show the package photo, brand and barcode; products without carb data are listed too ('carbs not listed').
- **Quick add by barcode** (decided 27 Oct): 'Scan a barcode' sits at the top of the Manage food list too. The packaged
  check screen has 'Make a photo now (best guess)', ticked by default: after saving (serving size and total carbohydrate still
  confirmed first) a photo of one serving is generated at once, with the container guessed (okf/domain/photo-style.md).
- **Scan several** (decided 27 Oct): the camera stays on and every new barcode (read twice in a row, each code once) is
  looked up in the background and added as a row of a review table: package photo, name, serving grams, carbs per serving,
  warnings, a link to the label photo, and two ticks per row (serving size, total carbohydrate) plus 'make a photo'.
  Editing a number clears its tick. 'Save checked foods' saves only rows with both ticks (each with its portion, see below,
  and, if chosen, a best-guess photo in the background); other rows stay until fixed or removed. Digits can be typed too.
  On a phone (decided 28 Oct, replacing one long card per food): under the scanner, a short list (photo, name, 'Needs
  checking' or 'Checked'). Each food opens its own check screen as soon as it's looked up, with the scanner paused;
  'Done, scan the next' (both ticks needed) or 'Later' goes back to the scanner at the top of the page. Tap a food in the
  list to check it later.
  **Complete** (decided 28 Oct) is how to finish, on every screen size: it saves the checked foods and leaves. If any
  food is still unchecked, the first tap says how many won't be saved and a second tap finishes. Back still keeps the
  list, but Complete is the obvious way out.
  Started from the **scan button beside the search on the Foods page**, it opens Scan several (parent PIN first) and
  Complete returns to the Foods page.
  Tags (decided 30 Oct): each scanned food has 'Tags (choose any)', the same choices as the check screen, none ticked
  to start with; they are saved with the food. Tags don't need a tick to save, unlike the serving and carbs.
- **Packaged result**: same check screen as a label scan. Serving size and total carbohydrate each confirmed; creates a '1 serving' portion;
  the product's nutrition-panel photo, when Open Food Facts has one, is kept as the label photo; the package photo is shown beside it.
- **FatSecret result** (decided 27 Oct, replacing USDA): the same check screen as a packaged food, using FatSecret's
  default serving in grams (or its 100 g serving): serving size and total carbohydrate each confirmed, '1 serving' portion created.
  Its other servings ('1 cup = 158 g') go into the notes for reference only. There is no label photo, so the screen says
  to compare with the package or a trusted source.
- Fiber (decided 28 Oct): the check screen and every Scan several row show fiber per serving beside the carbs,
  editable and confirmed with the carbs tick; it is saved on the food instead of in the notes (okf/domain/food.md).
- Source saved as 'FatSecret food 4501' or 'Open Food Facts, barcode 0016000275287'.
- Portion per row (decided 28 Oct): each Scan several row has the portion as a number and unit beside its grams,
  e.g. '1 bar' = 40 g. It starts from the package's serving text ('1 bar (40 g)' → '1 bar'), or '1 serving' when
  the package gives only grams, and becomes the food's first portion. A single scan's portion starts the same way.
