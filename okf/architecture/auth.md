---
type: Architecture
title: "Authentication: Firebase + server sessions"
description: "Firebase Authentication (Google provider) proves who the person is; the server verifies the ID token and issues its own 30-day session cookie."
tags: [architecture, security]
timestamp: 2026-10-27
status: draft
links:
  serves: [features/sign-in.md]
  depends_on: [architecture/docker-server.md, architecture/https.md, architecture/migrations.md]
---
# Authentication
- Config in .env: FIREBASE_API_KEY, FIREBASE_AUTH_DOMAIN, FIREBASE_PROJECT_ID (web config, not secret) and
  KC_ALLOWED_EMAILS (the first allow list; later edits live in the app's settings). No project → sign-in off.
- Browser: Firebase JS SDK from gstatic, signInWithPopup (redirect fallback), then the ID token is posted to
  /api/auth/session once and Firebase's own sign-in is dropped; the app runs on the server's cookie.
- Server: google-auth verifies the ID token against Google's public keys (audience = project id, verified email),
  checks the allow list, stores a random session id (hashed) in the sessions table (migration 2), and sets
  kc_session (HttpOnly, 30 days, renewed daily while used). Over HTTPS it is Secure, SameSite=None and
  Partitioned (28 Oct), so it also works when the app is shown inside another site's frame (Home Assistant);
  over plain http (dev on localhost) it stays SameSite=Lax.
- Because the cookie is sent from other sites' frames, every request that changes something (not GET) must come
  from the app's own origin: a different Origin header is refused (403).
- Device codes: POST /api/auth/device starts one (code for people, a long poll id for the waiting device, both
  held in memory for 10 minutes, at most 20 waiting); a signed-in parent approves the code
  (POST /api/auth/device/approve, parent PIN), and the waiting device's next poll gets a session for the approver's
  email. A code works once; a server restart drops waiting codes.
- Every /api/ route except /api/auth/* and every photo needs a valid session; the page itself loads so it can show
  the sign-in screen. The check reads the path the router uses (the ASGI path), never a URL rebuilt from the Host
  header: a Host such as 'x/y' once made the rebuilt path look unguarded while /api/log was still served
  (security review, 1 Nov). Requests whose Host isn't a plain host name are refused (400).
- Guarded responses are never stored by Cloudflare or other shared caches: API answers are 'private, no-store',
  photos 'private' (a browser may keep them, nothing in between). Cloudflare caches .pdf, .csv and .jpg by default
  and would otherwise hand a family member's export to anyone asking for the same URL.
- Production and QA refuse to start without a Firebase project (KC_ENV prod or qa), so a missing setting can't
  quietly open the app; only dev runs without sign-in.
- The parent PIN locks for 10 minutes after 10 wrong tries in 10 minutes.
- Security headers on every response: X-Content-Type-Options nosniff and Referrer-Policy same-origin, and
  Content-Security-Policy frame-ancestors: only the app itself and the origins in KC_FRAME_ANCESTORS (.env, e.g. the
  family's Home Assistant) may show it in a frame, so another site can't frame it and trick a signed-in parent into
  clicking. The API docs
  pages are off. Firebase only allows sign-in from its 'Authorized domains', so the site needs a host name
  there (an IP address may not be accepted).
