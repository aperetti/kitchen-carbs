---
type: Entity
title: "Photo"
description: "Images of a portion: the parent's original photo and a Gemini-styled version made from it."
tags: [domain, photos]
timestamp: 2026-10-26
status: draft
links:
  belongs_to: [domain/portion.md]
  governed_by: [rules/original-photo-kept.md, rules/estimated-photo-label.md]
---
# Photo
- original: parent's shot of the weighed portion (immutable)
- styled: Gemini restyle of the original using the [photo style](photo-style.md): parent's prompt and base container photos (mode A)
- estimated: true when no original exists for this portion and the image was generated from another portion's photo (mode B)
