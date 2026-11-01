---
type: Architecture
title: "Nutrition APIs"
description: "Server-side, read-only clients for FatSecret (OAuth 2.0 client credentials from .env) and Open Food Facts (no key; User-Agent with a contact email set in Settings)."
tags: [architecture]
timestamp: 2026-10-27
status: draft
links:
  serves: [features/food-lookup.md]
  depends_on: [architecture/docker-server.md]
---
# Nutrition APIs
- FatSecret (replaces USDA in search, decided 27 Oct): OAuth 2.0 client credentials (FAT_SECRET_CLIENT_ID and
  FAT_SECRET_CLIENT_SECRET in .env; scope basic); the server caches the token until shortly before it expires (24 h).
  foods.search (generic, restaurant and branded foods) and food.get for servings: each serving has its grams and carbs.
  FatSecret only answers from IP addresses on the app's allowlist in its developer portal: add the server's public address.
  Free tier: results show 'Powered by FatSecret' with a link.
- USDA FoodData Central: no longer searched; foods saved from it keep their 'USDA FDC' source.
- Open Food Facts: /api/v2/product/{barcode}; name search via search.openfoodfacts.org (each word tried as word, word*, word's,
  so 'yoshida' finds "Mr. Yoshida's"; filtered by countries_tags, e.g. en:united-states, for the region setting), falling back to the older /cgi/search.pl when it's down. Read only; the app never writes. ODbL, so attribution is shown with the source.
  User-Agent 'KitchenCarbs/1.0 (contact)'; the contact defaults to KC_OFF_CONTACT in .env (else the first
  allowed account) and is editable in Manage → Settings. No address is written in the code.
- Barcodes in photos are read on the server with zxing-cpp (no Gemini call).
- Calls go from the server, so keys and the contact address never reach the tablet.
