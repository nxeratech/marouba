---
id: after-effects-expression-pulse
name: After Effects Expression Pulse
app: After Effects
app_version: latest
author: nxeratech
category: motion
description: Demo expression replay.
params: []
tags: [after-effects, adapter, expressions, demo]
created: 2026-06-14
routes:
  - type: adapter
    adapter: after-effects
    events:
      - route_tier: r1
        app: After Effects
        kind: expression
        action: set_expression
        layer_id: pulse
        property_path: Transform/Opacity
        expression: "50 + Math.sin(time * 4) * 25"
fallback_order: [adapter, uia, ask]
verification: {type: comp_hash}
calls: []
depends_on: []
---

# After Effects Expression Pulse
