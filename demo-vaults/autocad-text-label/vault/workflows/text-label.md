---
id: autocad-text-label
name: AutoCAD Text Label
app: AutoCAD
app_version: latest
author: nxeratech
category: cad
description: Demo text command with exact insertion point, height, rotation, and string.
params: []
tags: [autocad, adapter, text, demo]
created: 2026-06-14
routes:
  - type: adapter
    adapter: autocad
    events:
      - route_tier: r1
        app: AutoCAD
        kind: command
        action: run_command
        command: TEXT
        parameters: [[10, 10, 0], 2.5, 0, "MAROUBA"]
fallback_order: [adapter, uia, ask]
verification: {type: dwg_entity_hash}
calls: []
depends_on: []
---

# AutoCAD Text Label
