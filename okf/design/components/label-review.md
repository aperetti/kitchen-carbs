---
type: component
title: "Label review"
description: "Two columns: the label photo at readable size on the left, the pre-filled form on the right with warnings above it in the warn colour."
tags: [design, safety]
timestamp: 2026-10-27
status: draft
links:
  implements: [features/scan-label.md, features/food-lookup.md]
  uses_tokens: [design/foundations/color.md, design/foundations/typography.md, design/foundations/spacing.md]
---
# Label review
Fields read from the label carry a small 'from label' note. Two confirmations sit under the numbers, each naming its value:
'Serving size is 40 g on the label' and 'Total carbohydrate is 31 g per serving on the label'. Both start unticked; editing a number unticks its confirmation.
Stacks to one column in portrait, label first.
