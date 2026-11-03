---
type: component
title: "Log details: read first, Edit to change"
description: "A meal, entry or plan opens as a plain summary; its forms appear only after 'Edit', and rare actions sit in a '⋯' menu."
tags: [design]
timestamp: 2026-11-02
status: draft
links:
  implements: [features/review-log.md, features/annotate-meal.md, features/manual-log.md, features/plan-meal.md, features/rate-meal.md]
  guided_by: [design/guidelines/large-text.md, design/components/log-card.md]
---
# Log details: read first, Edit to change
Decided 2 Nov: every meal opened with about ten sections, all of them forms, which was too much for the family.
- Read view (how it opens): the time and carbs, the foods and fiber, one line of what was recorded ('BG 180 (meter) ·
  2 u bolus, 10 min before the meal · eaten in 20 min', or 'No BG or insulin added'), the glucose chart, then the
  quick notes that are tapped after a meal: how fast it rose, how much was eaten, and comments. These still save
  through the 'Unsaved changes' bar.
- Beside the heading: 'Edit' and a '⋯' menu.
  - Edit shows the forms in place of the recorded line, in this order: date and time; Carbs, the meal's total ready
    to change (decided 3 Nov: no longer behind a 'Change total carbs' link), with 'Why it changed' appearing only once
    the number differs and needed to save it; BG, insulin and its minutes before the meal, time to eat; and Note,
    which is added to the meal's comments when saved (the comment box at the bottom moves up into it while editing). The bar on top reads 'Editing' with 'Done'. Saving or discarding the
    changes, or Done with nothing changed, goes back to the read view. On a read-only earlier day, Edit offers only
    the date and time (they can always change, okf/rules/same-day-edits.md).
  - ⋯ holds what is rarely needed: Pin as favorite, Delete meal (tapped twice). Change total carbs left it on 3 Nov,
    as Edit now shows the carbs. An entry's menu has Delete entry; a plan's has Delete plan.
- An entry reads as its BG, carbs, insulin and note, with Edit for its form. A plan reads as its foods and when,
  'Put on the plate' first, and Edit for its name, date and time.
- Opening another meal, entry or plan, or another day, leaves Edit.
