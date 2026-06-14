---
id: after-effects-title-move
name: After Effects Title Move
app: After Effects
app_version: latest
author: nxeratech
category: motion
description: Demo comp/layer/keyframe replay.
params: []
tags: [after-effects, adapter, demo]
created: 2026-06-14
routes:
  - type: adapter
    adapter: after-effects
    events:
      - route_tier: r1
        app: After Effects
        kind: comp
        action: create_comp
        comp_name: Title Move
        width: 1920
        height: 1080
        duration: 5
        frame_rate: 25
      - route_tier: r1
        app: After Effects
        kind: layer
        action: add_layer
        layer_id: title
        layer_name: Title
        layer_type: text
      - route_tier: r1
        app: After Effects
        kind: keyframe
        action: set_keyframe
        layer_id: title
        property_path: Transform/Position
        time: 0.0
        value: [960, 540]
        value_status: exact
fallback_order: [adapter, uia, ask]
verification: {type: comp_hash}
calls: []
depends_on: []
---

# After Effects Title Move
