---
type: Feature
title: "Sign in with Google"
description: "Every device signs in once with a family Google account (Firebase Authentication) and stays signed in; parents manage the allow list."
tags: [feature, security]
timestamp: 2026-10-27
status: draft
links:
  uses: [domain/family-account.md]
  constrained_by: [rules/allowlisted-accounts-only.md]
  depends_on: [architecture/auth.md]
---
# Sign in with Google
- A device with no session sees only the sign-in screen: 'Sign in with Google' (a popup, or a full-page redirect if the
  popup is blocked). A Google account not on the list is told so and not let in.
- Signed in, the app works as before; the account shows in Manage → Settings with 'Sign out this device'.
- Manage → Settings (parent PIN): the allow list of emails, and 'Sign out all devices'.
- Inside another page (decided 28 Oct: the Home Assistant dashboard shows the app in a frame): the session cookie
  must still work there, so it is allowed in frames (okf/architecture/auth.md).
- Sign in with a code, for kiosks and app web views where Google refuses to sign in (Google blocks its sign-in
  inside embedded web views with a 403): the sign-in screen offers 'Sign in with a code'. The device shows a short
  code (ABCD-EFGH) and waits. On a device already signed in, a parent opens Manage → Settings (parent PIN) →
  'Sign in another device', types the code and approves; the waiting device is signed in as that parent's account.
  Codes last 10 minutes and work once.
- A meal saved while the server can't be reached still queues on the tablet and syncs once signed in again.
