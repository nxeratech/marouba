---
id: resolume-clip-effect-pulse
name: Resolume Clip Effect Pulse
app: Resolume
app_version: latest
author: nxeratech
category: vj
description: Trigger a clip and set an effect parameter through exact Resolume OSC messages.
params: []
tags: [resolume, osc, clip, effect, adapter, r1]
last_verified: 2026-06-14
created: 2026-06-14
routes:
  - type: adapter
    adapter: resolume
    events:
      - route_tier: r1
        app: Resolume
        kind: osc
        semantic: clip_trigger
        address: /composition/layers/1/clips/1/connect
        args: [1]
      - route_tier: r1
        app: Resolume
        kind: osc
        semantic: effect_param
        address: /composition/layers/1/video/effects/1/params/1
        args: [0.72]
  - type: shortcut
    keys: [enter]
fallback_order: [adapter, shortcut, ask]
verification:
  type: osc_hash
calls: []
depends_on: []
---

# Resolume Clip Effect Pulse

Trigger a clip and set an effect parameter through native OSC.
