---
type: component
title: "Plate photo"
description: "Card-width 4:3 photo on each food card, with an 'Estimated photo' tag when it is a stand-in."
tags: [design, photos]
timestamp: 2026-10-26
status: draft
links:
  implements: [features/view-food.md]
  uses_tokens: [design/foundations/color.md]
---
# Plate photo
- Shown at card width, 4:3, never cropped differently from the original framing.
- Sharp on high-DPI screens: the server makes smaller copies (320–2400 px) on demand and the browser picks the one that
  matches the card size.
