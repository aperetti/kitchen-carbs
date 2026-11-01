---
type: Feature
title: "Photo pipeline"
description: "Upload an original portion photo, generate the Gemini-styled version, review, accept or regenerate."
tags: [feature, photos]
timestamp: 2026-10-26
status: draft
links:
  uses: [domain/photo.md, domain/portion.md, domain/photo-style.md, domain/size-reference.md]
  constrained_by: [rules/original-photo-kept.md, rules/estimated-photo-label.md]
---
# Photo pipeline
1. Upload original (camera or photo library). Optionally add a note for Gemini on the portion (okf/domain/photo-style.md).
2. Server calls Gemini with the original, the base photo of the portion's container (or all of them on Auto) and the parent's style prompt.
   This runs in the background on the server (about 3–4 s on Fast, 10–15 s on Sharp); the portion is marked as generating, and the Manage screen shows
   a progress bar with elapsed time in that portion's row and 'Styling a photo…' in the food list, updating live (checked every second while a photo is being made).
   Only one generation per portion at a time; a server restart marks an unfinished one as interrupted.
3. When it finishes, the check panel appears in place (and a short notice names the portion); a failure shows its reason
   in the row with Try again.
4. Side-by-side review → accept / regenerate / use original. Accepting also saves unsaved changes to the food and its
   portions first (decided 30 Oct, okf/features/manage-foods.md).
5. Stand-in for an unphotographed portion: generate from a sibling portion's **styled** photo (decided 27 Oct: it already has
   the approved counter, dish and light), or its original when it has no styled photo yet; flagged estimated. A portion quick-added as a multiple of a serving starts this
   straight away from that serving's photo when it has one (decided 27 Oct).
6. No photo at all (decided 27 Oct): 'Generate a photo' makes one from the food name, portion name and grams, the
   portion's container (base photo when there is one), its size reference and the style prompt. It is checked like any
   other candidate and flagged estimated until a real photo of that portion is uploaded.
7. A favorite's plate photo (decided 30 Oct): Gemini combines the photos of the favorite's foods into one photo of the
   meal, checked before use and labelled as combined (okf/features/favorite-plates.md). Made while the parent waits,
   not in the background, since it starts from the favorite's check screen.
8. All missing at once (decided 1 Nov): in Manage → Foods and photos, 'Generate missing photos' (with the count, tap
   again to confirm) queues every portion with no photo, no photo to check and no photo being made. A portion whose
   food has another portion with a photo is estimated from it (as in 5); the rest are generated from the name (as in 6).
   They run one at a time on the server, so Gemini isn't flooded; queued portions show 'Waiting its turn'. Each one
   still lands as a photo to check, flagged estimated; nothing is accepted on its own.
