---
type: component
title: "Sign-in screen"
description: "Full-screen, quiet page: app name, one 'Sign in with Google' button, and a plain message when an account isn't allowed."
tags: [design]
timestamp: 2026-10-27
status: draft
links:
  implements: [features/sign-in.md]
  uses_tokens: [design/foundations/color.md, design/foundations/typography.md, design/foundations/spacing.md]
---
# Sign-in screen
Same tokens as the rest of the app: no gradients, no illustration, one 56 px button. Shows which account was refused
and how to get added ("Ask a parent to add it in Manage → Settings").
- Below the Google button, a quiet 'Sign in with a code' link (for kiosks and dashboard frames). It shows the code in
  large letters, where to approve it, and a countdown; it signs in by itself once approved.
