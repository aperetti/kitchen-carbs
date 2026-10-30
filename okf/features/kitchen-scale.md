---
type: Feature
title: "Kitchen scale"
description: "Connect a Bluetooth kitchen scale from the plate; its live reading can be put on a plate item with one tap."
tags: [feature]
timestamp: 2026-10-28
status: draft
links:
  uses: [domain/plate.md, domain/portion.md]
  constrained_by: [rules/scale-reading-needs-tap.md, rules/no-dosing.md, rules/whole-gram-rounding.md]
  depends_on: [architecture/web-bluetooth.md]
---
# Kitchen scale
Chosen 28 Oct: Web Bluetooth, the tablet talks to the scale directly (no server, no extra hardware).
- 'Connect scale' at the top of the plate. The browser asks which scale; this is needed once on each device.
- Auto-connect (decided 28 Oct): after that first time, whenever the plate is showing and the scale isn't connected,
  the app connects to the remembered scale by itself, and keeps trying every 15 seconds so a scale switched on later
  is picked up. Browsers that can't reconnect without a tap (no getDevices) keep the Connect button.
  Auto-connect only connects; it never puts a weight on the plate (okf/rules/scale-reading-needs-tap.md).
- While connected, the plate shows the live reading and whether it is steady, with **Zero** (tare) and **Disconnect**.
  The reading and Zero float at the top while you scroll the plate (29 Oct).
- Each plate row gets **Use 142 g**: sets that item's weight to the current reading. Disabled until the reading is
  steady and above zero. Typical use: plate on the scale, Zero, add one food, Use, Zero, add the next.
- If the connection drops, the app tries to reconnect a few times and otherwise says so; weights already set are kept.
- Scales: the Bluetooth standard Weight Scale service, the Decent Scale (published protocol) and the Etekcity
  ESN00 Smart Nutrition Scale (the family's scale, decided 28 Oct; community-decoded protocol). Other scales use
  their own formats: Settings has a raw-data viewer so a new scale's format can be read and added.
- Browsers without Web Bluetooth (Safari on iPad/iPhone) don't show the button; Settings explains why.
