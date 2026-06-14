---
id: after-effects-comp-keyframe-effect
name: After Effects Comp Keyframe Effect
app: After Effects
app_version: latest
author: nxeratech
category: motion
description: Build a comp with a layer, effect stack, exact keyframes, and expression.
params: []
tags: [after-effects, adapter, keyframes, expressions]
created: 2026-06-14
routes:
  - type: adapter
    adapter: after-effects
    events:
      - route_tier: r1
        app: After Effects
        kind: comp
        action: create_comp
        comp_name: Marouba Motion
        width: 1920
        height: 1080
        duration: 6
        frame_rate: 25
      - route_tier: r1
        app: After Effects
        kind: layer
        action: add_layer
        layer_id: layer_1
        layer_name: Bass Title
        layer_type: text
      - route_tier: r1
        app: After Effects
        kind: effect
        action: add_effect
        layer_id: layer_1
        effect_name: Glow
        match_name: ADBE Glow
      - route_tier: r1
        app: After Effects
        kind: keyframe
        action: set_keyframe
        layer_id: layer_1
        property_path: Transform/Position
        time: 0.0
        value: [960, 540]
        value_status: exact
fallback_order: [adapter, uia, ask]
verification:
  type: comp_hash
calls: []
depends_on: []
---

# After Effects Comp Keyframe Effect

Comp state is rebuilt from exact API events.
