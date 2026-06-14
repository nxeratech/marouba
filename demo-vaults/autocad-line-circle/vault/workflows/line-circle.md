---
id: autocad-line-circle
name: AutoCAD Line Circle
app: AutoCAD
app_version: latest
author: nxeratech
category: cad
description: Demo line and circle replay from command parameters.
params: []
tags: [autocad, adapter, demo]
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
      - route_tier: r1
        app: AutoCAD
        kind: command
        action: run_command
        command: CIRCLE
        parameters: [[50, 50, 0], 25]
fallback_order: [adapter, uia, ask]
verification: {type: dwg_entity_hash}
calls: []
depends_on: []
---

# AutoCAD Line Circle
