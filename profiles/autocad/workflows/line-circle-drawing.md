---
id: autocad-line-circle-drawing
name: AutoCAD Line Circle Drawing
app: AutoCAD
app_version: latest
author: nxeratech
category: cad
description: Draw a line and circle from exact command-stream parameters.
params: []
tags: [autocad, adapter, command-stream, cad]
created: 2026-06-14
routes:
  - type: adapter
    adapter: autocad
    events:
      - route_tier: r1
        app: AutoCAD
        kind: command
        action: run_command
        command: LINE
        parameters: [[0, 0, 0], [100, 0, 0], ""]
        capture_source: command-stream
      - route_tier: r1
        app: AutoCAD
        kind: command
        action: run_command
        command: CIRCLE
        parameters: [[50, 50, 0], 25]
        capture_source: command-stream
fallback_order: [adapter, uia, ask]
verification:
  type: dwg_entity_hash
calls: []
depends_on: []
---

# AutoCAD Line Circle Drawing

Command replay is valid only because coordinates and radius are captured exactly.
