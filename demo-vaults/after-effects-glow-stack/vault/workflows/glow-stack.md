---
id: after-effects-glow-stack
name: After Effects Glow Stack
app: After Effects
app_version: latest
author: nxeratech
category: motion
description: Demo effect stack replay from match names.
params: []
tags: [after-effects, adapter, effects, demo]
created: 2026-06-14
routes:
  - type: adapter
    adapter: after-effects
    events:
      - route_tier: r1
        app: After Effects
        kind: layer
        action: add_layer
        layer_id: glow
        layer_name: Glow Solid
        layer_type: solid
      - route_tier: r1
        app: After Effects
        kind: effect
        action: add_effect
        layer_id: glow
        effect_name: Glow
        match_name: ADBE Glow
fallback_order: [adapter, uia, ask]
verification: {type: comp_hash}
calls: []
depends_on: []
---

# After Effects Glow Stack
