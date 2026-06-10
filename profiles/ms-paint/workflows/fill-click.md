---
id: ms-paint-fill-click
name: MS Paint Fill Click
app: MS Paint
app_version: Windows 10/11
author: nxeratech
category: drawing
description: Replay a recorded Paint fill click using gesture-first routing.
params: []
tags: [paint, fill, gesture, null-adapter]
last_verified: 2026-06-10
created: 2026-06-10
routes:
  - type: gesture
    target_window: Paint
    events:
      - kind: mousedown
        timestamp_ms: 0
        x: 180
        y: 180
        normalized_x: 0.45
        normalized_y: 0.45
        button: left
      - kind: mouseup
        timestamp_ms: 50
        x: 180
        y: 180
        normalized_x: 0.45
        normalized_y: 0.45
        button: left
  - type: visual
    coordinates:
      x: 180
      y: 180
fallback_order: [gesture, visual, ask]
verification:
  type: none
calls: []
depends_on: []
---

# MS Paint Fill Click

Reference T3 workflow for single-click canvas replay.