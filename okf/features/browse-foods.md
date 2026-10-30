---
type: Feature
title: "Browse foods"
description: "Find foods in a grid of cards with photos, portions and carbs; search and filter by tag or Favorites."
tags: [feature]
timestamp: 2026-10-26
status: draft
links:
  uses: [domain/food.md, domain/portion.md, domain/photo.md, domain/tag.md, domain/nutrition-source.md]
  constrained_by: [rules/provenance-required.md, rules/no-dosing.md, rules/label-reading-needs-check.md]
---
# Browse foods
- A grid of food cards fills the screen (decided 27 Oct: the list beside one large photo wasted space). Search as you
  type; filter by tag (Breakfast, Lunch, Dinner…) or open Favorites, which become cards too with 'Put on plate'.
- Opens on the meal (decided 29 Oct): when the app is first loaded, the filter is set to the tag named for the time of
  day, Breakfast before 10:30, Lunch until 15:00, Dinner after (the same times that name a favorite plate). If that tag
  doesn't exist, the last filter used stays. Picking another filter works as usual until the app is next opened.
- Each card: photo at card size with the name over it, and 'Not verified' if trust = draft; tapping it adds the serving.
- No automatic Free snacks tab (decided 28 Oct, replacing the same day's carb-limit tab): a family that wants one
  makes a 'Free snacks' tag in Manage and puts foods in it by hand, like any tag.
- Searching for several foods in a row (decided 29 Oct): tapping a card while a search is typed adds it, then clears the
  search and puts the cursor back in the search box, so the next name can be typed straight away.
- Added-to-plate feedback (decided 29 Oct): the tapped card's photo flies to the plate count ('Plate (3)' on a phone,
  the plate total beside the grid on a tablet), which then gives a small bump. With reduced motion set on the device,
  only the bump plays. Taking a food off the plate (a second tap) doesn't fly.
- No match, add it (decided 28 Oct): when a search finds no food, 'No foods match' has a button 'Look up “…” and add it'.
  It opens a modal over the food grid (the foods stay where they were): parent PIN first if Manage is locked, then the
  top result of the same name search Manage uses (FatSecret first, then Open Food Facts), already on the usual check
  screen (serving size and total carbohydrate each confirmed, okf/rules/label-reading-needs-check.md). 'Not this one?'
  lists the other results. Saving closes the modal and the new food appears under the search; Cancel or × leaves nothing.
- Phones show two cards per row; the tablet and wide screens as many as fit, with the plate in a column on the right.
