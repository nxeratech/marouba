---
id: after-effects-expression-stack
name: After Effects Expression Stack
app: After Effects
app_version: latest
author: nxeratech
category: motion
description: Replay expression and effect stack values from scripting evidence.
params: []
tags: [after-effects, adapter, expressions]
created: 2026-06-14
routes:
  - type: adapter
    adapter: after-effects
    events:
      - route_tier: r1
        app: After Effects
        kind: layer
        action: add_layer
        layer_id: layer_1
        layer_name: Pulse Solid
        layer_type: solid
      - route_tier: r1
        app: After Effects
        kind: expression
        action: set_expression
        layer_id: layer_1
        property_path: Transform/Opacity
        expression: "50 + Math.sin(time * 4) * 25"
fallback_order: [adapter, uia, ask]
verification:
  type: comp_hash
calls: []
depends_on: []
---

# After Effects Expression Stack

Expression payload is replayed as text, not inferred from motion.
