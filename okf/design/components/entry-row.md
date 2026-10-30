---
type: component
title: "Entry row"
description: "Log row for a manual entry: time, then 'BG 142 · 2.5 u rapid · 15 g carbs', note underneath; no carb figure in the accent colour unless carbs were entered."
tags: [design]
timestamp: 2026-10-27
status: draft
links:
  implements: [features/manual-log.md]
  uses_tokens: [design/foundations/color.md, design/foundations/typography.md]
---
# Entry row
Insulin and BG are graphite text, never accent, so they can't be confused with carb numbers.
- A meal row lists each food with its **carbs**, not its weight (decided 29 Oct): 'Toast, whole-wheat 22 g carbs'. The meal's
  details give each food's carbs first and the weighed grams after, in brackets.
