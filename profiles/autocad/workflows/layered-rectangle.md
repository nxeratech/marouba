---
id: autocad-layered-rectangle
name: AutoCAD Layered Rectangle
app: AutoCAD
app_version: latest
author: nxeratech
category: cad
description: Create a layer and rectangle from exact command parameters.
params: []
tags: [autocad, adapter, layers, cad]
created: 2026-06-14
routes:
  - type: adapter
    adapter: autocad
    events:
      - route_tier: r1
        app: AutoCAD
        kind: command
        action: run_command
        command: -LAYER
        parameters: ["M", "Marouba-Walls", "C", "1", "Marouba-Walls", ""]
        capture_source: command-stream
      - route_tier: r1
        app: AutoCAD
        kind: command
        action: run_command
        command: RECTANG
        parameters: [[0, 0, 0], [200, 120, 0]]
        capture_source: command-stream
fallback_order: [adapter, uia, ask]
verification:
  type: dwg_entity_hash
calls: []
depends_on: []
---

# AutoCAD Layered Rectangle

Layer and rectangle commands are replayed as exact command-stream events.
