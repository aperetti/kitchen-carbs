---
type: component
title: "Log card (phone)"
description: "On a phone, a meal, entry or plan opened from the log slides in as its own card over the list; it is a history step, so Back, '‹ Log' or a swipe to the right returns to the list where it was."
tags: [design]
timestamp: 2026-11-02
status: draft
links:
  implements: [features/review-log.md, features/annotate-meal.md, features/manual-log.md, features/plan-meal.md]
  guided_by: [design/guidelines/navigation.md, design/guidelines/phone-layout.md]
---
# Log card (phone)
Decided 2 Nov: tapping a meal on a phone scrolled the screen down to its details under the whole list, which was hard to
follow. Screens 680 px wide and under:
- The log shows only the list. Tapping a meal, entry or plan, or 'Add entry', opens a card that slides in from the
  right and covers the screen; the app bar and tabs stay hidden behind it like a food's screen in Manage.
- A sticky bar on top: '‹ Log' and the card's title (the meal's time, the plan's name, 'Add entry').
- Each card is a history step (#log/meal/12, #log/entry/4, #log/plan/3, #log/add): the phone's Back gesture, '‹ Log'
  and a swipe to the right (a finger dragged right more than a quarter of the screen, mostly sideways, not starting on
  a box or slider) all go back, and the card follows the finger while it's dragged. Forward reopens it; a reload of
  that address opens it again.
- Back lands on the list where it was scrolled. Nothing on the list moves.
- Unsaved changes hold the card: Back stays on it and says 'Save or discard the changes first', as choosing another
  meal does. The 'Unsaved changes' bar with Save and Discard stays pinned to the bottom of the screen on the card,
  never inside it where it would need scrolling to (3 Nov: the card moving with the finger had made the bar part of
  the card); the card only moves while it's being dragged.
- With reduced motion the card appears without sliding.
- Tablets and computers keep the list and details side by side; nothing is added to history there.
