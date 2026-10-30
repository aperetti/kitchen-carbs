---
type: component
title: "Scale bar"
description: "Strip at the top of the plate: Connect scale, or the live reading with a steady dot, Zero and Disconnect; rows get a 'Use' button."
tags: [design]
timestamp: 2026-10-29
status: draft
links:
  implements: [features/kitchen-scale.md]
  uses_tokens: [design/foundations/color.md, design/foundations/spacing.md]
---
# Scale bar
- Not connected: a quiet 'Connect scale' button. Hidden where the browser has no Bluetooth.
- Connected: the scale name, the reading in large tabular figures, a dot (green steady, grey changing), Zero, Disconnect.
- Each plate row: a small 'Use 142 g' button by the weight field, updated live without redrawing the row.
- Floats while connected (decided 29 Oct): the strip sticks to the top of the plate as you scroll, so the reading
  and Zero stay in reach beside any row, on phone and tablet. Disconnected, it scrolls away with the page.
