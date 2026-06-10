---
id: ms-paint-freehand-stroke
name: MS Paint Freehand Stroke
app: MS Paint
app_version: Windows 10/11
author: nxeratech
category: drawing
description: Replay a recorded freehand stroke in the Paint canvas using gesture-first routing.
params: []
tags: [paint, drawing, gesture, null-adapter]
last_verified: 2026-06-10
created: 2026-06-10
routes:
  - type: gesture
    target_window: Paint
    events:
      - kind: mousedown
        timestamp_ms: 0
        x: 100
        y: 100
        normalized_x: 0.25
        normalized_y: 0.25
        button: left
      - kind: mousemove
        timestamp_ms: 40
        x: 130
        y: 130
        normalized_x: 0.32
        normalized_y: 0.32
      - kind: mouseup
        timestamp_ms: 80
        x: 130
        y: 130
        normalized_x: 0.32
        normalized_y: 0.32
        button: left
  - type: visual
    coordinates:
      x: 100
      y: 100
fallback_order: [gesture, visual, ask]
verification:
  type: none
calls: []
depends_on: []
---

# MS Paint Freehand Stroke

Reference T3 workflow for gesture-first canvas replay.