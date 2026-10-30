---
type: guideline
title: "Phone layout for Manage"
description: "On a phone, adding or editing a food is a full screen built for one hand: list hidden, back bar on top, one column, labels and inputs large and dark enough to read at arm's length."
tags: [design]
timestamp: 2026-10-30
status: draft
links:
  applies_to: [features/manage-foods.md, features/food-lookup.md, features/scan-label.md]
  guided_by: [design/foundations/typography.md, design/foundations/spacing.md, design/guidelines/navigation.md]
---
# Phone layout for Manage (screens 680 px wide and under)
Decided 27 Oct: on a phone, 'Add a food' opened below the whole food list and the form was squeezed; it now opens as its own screen.
- Tapping '+ Add a food' or a food opens a full screen: the app bar, Manage tabs and food list are hidden; a sticky bar on top reads '‹ Foods' and the screen title.
  It is a history step, so the phone's Back gesture also returns to the list.
- Nothing in Manage scrolls the screen sideways (decided 30 Oct: the tab row pushed the whole screen wider than a phone).
  The Manage tabs scroll sideways within their own row, with 'Lock' pinned to its right edge so it is always in reach;
  wide controls wrap or shrink to fit the screen.
- One column. Every input is full width, 56 px tall, 18 px text (16 px or more also stops phones zooming in on focus).
- Field labels are 17 px, weight 500, in ink, not the muted grey (the grey is for help text only).
- 'g carbs per … g of food' stacks as two lines, each a wide input with its unit beside it.
- Add-a-food tabs fill the width in equal parts.
- Save and Cancel sit in a bar pinned to the bottom of the screen while the form is on screen (decided 27 Oct: the save
  button was lost below a long form). On a food's screen the bar scrolls away with the end of the form, since portions
  below save as they change. Secondary actions (Delete food, Scan another photo) sit outside the bar.
- Portions become cards: each value has its label above it instead of a table header.
