---
type: Rule
title: "Scale reading needs a tap"
description: "A scale reading never changes a plate item by itself: the parent taps 'Use' on the item, and only a steady reading can be used."
tags: [safety, data]
timestamp: 2026-10-28
status: draft
links:
  applies_to: [domain/plate.md]
  extends: [rules/label-reading-needs-check.md]
---
# Scale reading needs a tap
The grams become carbs a parent will act on, so a stray, jumping or wrong-item reading must not slip in.
- No automatic weights: the reading is shown live, and only 'Use' on a specific row copies it to that row.
- 'Use' is disabled while the reading is changing, at or below zero, or over 2000 g.
- The weight stays editable after 'Use' (slider, typed grams, − / +), the same as any other weight.
