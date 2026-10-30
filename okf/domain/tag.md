---
type: Entity
title: "Tag"
description: "A label for grouping foods, such as Breakfast, Lunch or Dinner. A food can have several tags."
tags: [domain]
timestamp: 2026-10-27
status: draft
links:
  labels: [domain/food.md]
---
# Tag
- Starts with Breakfast, Lunch, Dinner. A parent can add, rename or remove tags in Manage.
- Many-to-many: apple can be Breakfast and Lunch.
- Replaces the single 'category' field (old categories were turned into tags).
- 'Favorites' is not a tag: it lists favorite plates (see [favorite plate](favorite-plate.md)).
