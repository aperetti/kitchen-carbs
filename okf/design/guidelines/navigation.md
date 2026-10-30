---
type: guideline
title: "Navigation and cancel"
description: "Every step in Manage is a browser history entry, so Back and Forward work; every form and check screen has a Cancel that leaves without saving."
tags: [design]
timestamp: 2026-10-27
status: draft
links:
  applies_to: [features/manage-foods.md, features/food-lookup.md, features/scan-label.md, features/photo-pipeline.md, features/photo-style-setup.md, features/connect-nightscout.md]
---
# Navigation and cancel
- History entries: Manage section, chosen food, Add-a-food tab (Look up, Scan several or Type it in), a check screen (scan or lookup result).
  The address shows where you are (#manage/foods/pasta-cooked, #manage/foods/add/lookup), so a reload lands in the same place.
- Check screens hold their data in the history entry, so Back from a food you saved returns to the results, and Forward re-opens the check.
- Cancel = leave without saving: it goes back one step when the step came from this session, otherwise to the level above.
- On a phone, a chosen food or Add a food is its own full screen with a '‹ Foods' back bar (okf/design/guidelines/phone-layout.md).
- Unlock and Lock replace the current entry rather than adding one, so Back never re-opens a locked screen.
