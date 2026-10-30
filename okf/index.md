---
type: Index
title: "Kitchen Carbs — concept map"
description: "Planning knowledge for a kitchen-tablet carb lookup, plate and meal log app for a child with T1D."
timestamp: 2026-10-26
status: draft
---
# Kitchen Carbs — concept map

This OKF bundle is **planning knowledge only**. The running app does not read it.
Every feature, rule, UI component and architecture choice is a concept with links,
and `tools/okf_check.py` checks that the map is grounded:

- every **Feature** `uses` at least one Domain concept and is `constrained_by` at least one Rule
- every **component** `implements` at least one Feature
- every link points to a real concept

## Sections
- [domain/](domain/) — Food, Portion, Carb value, Nutrition source, Photo, Plate, Meal, Meal log
- [features/](features/) — what a person can do
- [rules/](rules/) — safety and data rules that override convenience
- [design/](design/index.md) — ODSF design-system profile: foundations, components, guidelines
- [architecture/](architecture/) — Docker server, storage, API, offline behaviour
