---
type: Feature
title: "Favorite plates"
description: "Pin the current plate or a logged meal as a named favorite; open Favorites in Foods and put a favorite on the plate in one tap."
tags: [feature]
timestamp: 2026-11-12
status: draft
links:
  uses: [domain/favorite-plate.md, domain/plate.md, domain/portion.md, domain/carb-value.md, domain/photo-style.md]
  constrained_by: [rules/favorites-use-current-values.md, rules/no-dosing.md, rules/estimated-photo-label.md]
---
# Favorite plates
- Foods → **Favorites** filter (first in the row) lists favorites with total carbs.
- Detail shows each item with photo and carbs; 'Put on plate' adds them all; each item's grams can still be tuned on the plate.
- Plate → 'Pin as favorite'; Log meal → 'Pin as favorite'. Unpin and rename from the favorite's detail;
  the name box there takes the full width with 'Rename' on its own line below it, so it fits a phone card (12 Nov).

## Plate photo (decided 30 Oct)
A favorite can have its own photo of the whole meal, made by Gemini from the photos of its foods.
- The favorite's ⓘ offers 'Make a plate photo' ('New plate photo' once it has one). It opens a check screen; making
  or changing the photo needs the parent PIN, asked there when Manage is locked.
- Inputs: every food on the favorite that has a photo (its styled photo, or the parent's own when not styled), each
  with its amount in the favorite; foods without a photo are described by name and grams. Up to 10 photos are sent.
  The parent's style prompt is sent too. Gemini keeps each food in its own dish from its photo, sets them together as
  one meal, changes only how much there is where the favorite's amount differs, and adds nothing.
- The check screen shows the food photos it was made from, with their amounts, next to the result:
  'Use this photo', 'Try again' or 'Discard'. Nothing replaces the card photo until 'Use this photo'.
- Direction for Gemini (decided 12 Nov): above 'Make the photo' (and 'Try again') a box 'Direction for Gemini
  (optional)', e.g. 'Put the apple slices in a blue bowl' or 'View from above'. It is sent with the request, kept with
  the favorite so the next photo starts from it, and followed unless it would change how much food there is or break
  the rules above (nothing added, nothing taken away).
- The favorite's card shows the plate photo once accepted; until then, the first food's photo as before.
  'Remove plate photo' goes back to that.
- The ⓘ says the photo was combined by Gemini and the amounts may not match (okf/rules/estimated-photo-label.md).
  Carbs never come from the photo.
- Removing missing items also removes the plate photo, since it shows foods that are gone.
