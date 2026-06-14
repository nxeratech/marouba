---
id: premiere-keyframed-effect
name: Premiere Keyframed Effect
app: Premiere Pro
app_version: latest
author: nxeratech
category: video-edit
description: Effect parameter with exact API keyframe values.
params: []
tags: [premiere, adapter, keyframes]
created: 2026-06-14
routes:
  - type: adapter
    adapter: premiere
    events:
      - route_tier: r1
        app: Premiere Pro
        kind: effect_param
        action: set_effect_param
        clip_id: clip_1
        effect_name: Transform
        param_name: Scale
        value: 100
        value_status: exact
        keyframes:
          - time: 0.0
            value: 100
            value_status: exact
          - time: 2.0
            value: 118
            value_status: exact
fallback_order: [adapter, uia, ask]
verification:
  type: timeline_hash
calls: []
depends_on: []
---

# Premiere Keyframed Effect

Keyframes are valid only when exact ComponentParam values were captured.
