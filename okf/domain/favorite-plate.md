---
type: Entity
title: "Favorite plate"
description: "A named, pinned combination of portions and amounts, like 'Usual breakfast: toast 64 g, apple 75 g'."
tags: [domain]
timestamp: 2026-10-30
status: draft
links:
  contains: [domain/portion.md]
  becomes: [domain/plate.md]
  governed_by: [rules/favorites-use-current-values.md]
---
# Favorite plate
- Fields: name, items (portion + amount, stored as a multiple of the portion's weight so it follows today's portion), order,
  and an optional plate photo with a candidate waiting to be checked (decided 30 Oct, okf/features/favorite-plates.md).
- Pinned from the plate or from a logged meal. Anyone at the tablet can pin or unpin; no PIN.
- Carbs are not stored; they come from the foods as they are now.
- Orphaned favorites (decided 28 Oct): a favorite whose foods were all deleted shows 'No foods left' and can't be put
  on the plate. The Favorites tab offers 'Remove them' for all of those at once (a second tap confirms), and a
  favorite with only some foods gone offers 'Remove the missing items' in its details. Nothing is removed without
  that tap (okf/rules/favorites-use-current-values.md).
