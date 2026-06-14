---
id: clip-effect
name: Clip Effect
app: Resolume
description: Demo Resolume adapter vault triggering a clip and setting an effect parameter through exact OSC.
params:
  - name: effect_amount
    type: number
    required: true
tags: [resolume, demo, adapter, r1, osc]
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
        args: ["{effect_amount}"]
fallback_order: [adapter, ask]
verification:
  type: osc_hash
calls: []
depends_on: []
---

# Clip Effect

Demo vault for Resolume clip trigger and exact effect parameter replay.
