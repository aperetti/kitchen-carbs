---
type: Entity
title: "Photo style"
description: "The parent's editable style prompt plus base photos of the family's plate, bowl and dressing container, sent to Gemini with every original photo."
tags: [domain, photos]
timestamp: 2026-10-27
status: draft
links:
  shapes: [domain/photo.md]
  includes: [domain/size-reference.md]
  governed_by: [rules/original-photo-kept.md, rules/estimated-photo-label.md]
---
# Photo style
- Prompt: free text describing the look (counter, light, angle). Starts with the white-quartz default; can be reset.
- Base photos: one each for **plate**, **bowl**, **dressing container**. Each is the empty container on the counter.
- Gemini gets: the parent's original photo (what and how much), the base photo for the container (what it sits in),
  the style prompt, and a fixed instruction that the food and amount must not change. The fixed part can't be edited away.
- Photo note (decided 27 Oct): each portion can carry a short note for Gemini ('rice on the left, ignore the fork',
  'plain white rice, no sauce'), sent with every photo made for that portion. It can describe the food or what to
  leave out, but never overrides the fixed instruction: the amount of food stays as photographed or weighed.
- Note when adding a food (decided 28 Oct): every way of adding a food (type it in, a single scan or lookup, the
  Foods-page add modal, and each Scan several food) has an optional 'Note for Gemini' for the first portion, so the
  best-guess photo made right after saving already uses it.
- Speed (decided 27 Oct, after timing each model on a real photo): **Fast** (default) uses Gemini's lite image model,
  about 3–4 s, 1200 px wide; **Sharp** uses the full model, about 10–15 s, 2400 px wide for large high-DPI screens.
  No available model makes a photo in 1–2 s. Reference photos are sent at most 1600 px wide either way.
- Size references (okf/domain/size-reference.md): objects of known measurement, chosen per portion, for scale.
- Each portion has a container: **Auto** (Gemini matches the container in the original photo to a base photo), a set one,
  or **On the counter** (decided 27 Oct): the food sits straight on the quartz with no plate, bowl, cup or other dish,
  for things like a whole apple. No base photo is sent, and any dish in the photo is left out.
- **In its own package** (decided 27 Oct): the serving shown in or beside its retail package (a granola bar in its opened
  wrapper, a juice box). Uses the package photo from Open Food Facts when the food has one.
- Best guess: when a photo is generated for a portion set to Auto, a fast Gemini text model first picks package, plate,
  bowl, dressing container or counter from the food's name, serving and package photo; the choice is saved on the
  portion, so the parent can see it and change it, then Try again.
- A food found by barcode keeps Open Food Facts' front-of-package photo, sent with its photo requests so Gemini knows
  what the food looks like (never shown as the food's own photo).
