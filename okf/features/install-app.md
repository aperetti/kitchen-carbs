---
type: Feature
title: "Install on a phone"
description: "On a phone's first visit (after sign-in), offer to install Kitchen Carbs to the home screen; asked once."
tags: [feature]
timestamp: 2026-10-28
status: draft
links:
  uses: [domain/family-account.md]
  constrained_by: [rules/allowlisted-accounts-only.md]
  depends_on: [architecture/install.md]
---
# Install on a phone
Decided 28 Oct.
- Phones only (not the kitchen tablet or computers), not when already opened from the home screen, and shown once:
  'Install' or 'Not now' both stop it asking again on that phone. It appears after sign-in, never over the sign-in screen.
- Android (Chrome, Edge, Samsung): 'Install' opens the browser's own install dialog. Where the browser hasn't offered
  that (Firefox, or before Chrome is ready), the card says to use the browser menu → 'Add to Home screen'.
- iPhone and iPad (Safari): there is no install dialog, so the card shows the steps: Share → 'Add to Home Screen'.
- The installed app opens the same address and still needs sign-in; it is not a separate copy.
