---
type: Architecture
title: "Docker server"
description: "One container on the home computer: Python (FastAPI) serving the tablet web app, API and photos on the LAN."
tags: [architecture]
timestamp: 2026-10-26
status: draft
links:
  serves: [features/browse-foods.md, features/view-food.md, features/build-plate.md, features/log-meal.md, features/review-log.md, features/export-log.md, features/manage-foods.md, features/photo-pipeline.md, features/annotate-meal.md, features/favorite-plates.md, features/scan-label.md, features/manual-log.md, features/food-lookup.md]
  includes: [architecture/nightscout-client.md]
  depends_on: [architecture/storage.md]
---
# Docker server
- docker compose up; port 8090 on the LAN (8080 is taken on the host); restart: unless-stopped.
- Gemini key mounted as a secret; only the photo pipeline, label reading and the Nightscout client use the internet.
