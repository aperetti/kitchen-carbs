---
type: component
title: "Food row"
description: "Food card: the photo fills a rounded card; the name is one line on a frosted pill along the bottom; the whole card adds the food to the plate."
tags: [design]
timestamp: 2026-10-26
status: draft
links:
  implements: [features/browse-foods.md]
  uses_tokens: [design/foundations/color.md, design/foundations/typography.md]
---
# Food card
- The photo fills the card: no border, 14 px corners (decided 27 Oct, 'the different lines don't look good').
- The name is a single line on a frosted, translucent pill inset 8 px from the bottom edge, so every card lines up;
  a long name ends in '…' and is shown in full in the ⓘ details and as the tooltip.
- When the food is on the plate, a round ✓ badge sits in the top-left corner (decided 27 Oct; the grams are in its tooltip, not printed), with
  'Not verified' just below it; otherwise 'Not verified' is the top-left tag; ⓘ (top right) uses the same frosted style; 'Estimated photo' is in
  the ⓘ details only.
- The whole card is the touch target and toggles the food on and off the plate; it dims briefly to confirm.
- A Pinterest-style masonry layout was considered and not used: it reads down columns, so the alphabetical order would
  jump around.
