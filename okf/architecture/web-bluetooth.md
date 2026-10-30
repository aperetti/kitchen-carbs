---
type: Architecture
title: "Web Bluetooth"
description: "The browser connects to the scale over Bluetooth Low Energy; needs a secure address (https or localhost) and Chrome or Edge (Android, ChromeOS, Windows, Mac)."
tags: [architecture]
timestamp: 2026-10-28
status: draft
links:
  serves: [features/kitchen-scale.md]
  depends_on: [architecture/https.md]
---
# Web Bluetooth
- Runs only on a secure address, the Cloudflare https name or localhost (okf/architecture/https.md), and needs a tap to start pairing. Not available in Safari on
  iPad or iPhone. On Linux desktops Chrome needs its experimental web platform features flag.
- Drivers, each a small decoder in app.js:
  - Bluetooth Weight Scale service (0x181D, Weight Measurement 0x2A9D): kg at 5 g steps or lb, no steady flag, so
    the app calls a reading steady when it holds within 1 g for about a second.
  - Decent Scale: notifications on FFF4 (7 or 10 bytes; byte 2 CE steady, CA changing; bytes 3–4 signed tenths of a
    gram). Commands on 36F5 (tare 03 0F 00 00 00 01 0D). The scale sends weight only after a command, so the app
    sends tare when connecting.
  - Etekcity Smart Nutrition Scale ESN00 (bought 28 Oct; protocol from the open-source metekcity project, not
    from Etekcity): service 0x1910, notifications on 0x2C12, commands on 0x2C11 (write without response only, seen on the real scale). Every packet is FE EF C0 A2, type,
    payload length, payload, checksum (sum of type, length and payload, mod 256); one notification may hold several.
    Measurement (type D0): sign (01 = negative), weight as big-endian uint16 in tenths of a gram, unit (00 = grams),
    settled (01 = steady). The app sets the scale to grams on connect (C0, 00; the scale answers D1 00) and zeroes
    with C1, 00, which acts like the scale's TARE button (answer D3; the 2020 notes said C1 01, which the real scale
    ignores). The scale sends a burst of readings on connect, then only when the weight changes.
    Checked 28 Oct on the family's scale from the laptop: 55 g read as D0 05 00 02 26 00 01 = 55.0 g, settled; a reading in
    any other unit is ignored and the scale is switched back to grams.
- Zero uses the scale's own tare when the driver has one, otherwise an offset kept in the app.
- Reconnecting: navigator.bluetooth.getDevices() lists the scales this site was already allowed to use; the app picks
  the one it used last (its id is kept on the device) and calls gatt.connect() without a tap. Attempts are quiet,
  one at a time, give up after 10 seconds, and only run while the plate is on screen and the page is visible.
- Nothing is sent to the server; the reading lives only on the page.
