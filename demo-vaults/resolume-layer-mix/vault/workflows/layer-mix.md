---
id: layer-mix
name: Layer Mix
app: Resolume
description: Demo Resolume adapter vault setting layer opacity and blend through exact OSC.
params: []
tags: [resolume, demo, adapter, r1, layer]
routes:
  - type: adapter
    adapter: resolume
    events:
      - route_tier: r1
        app: Resolume
        kind: osc
        semantic: layer_param
        address: /composition/layers/1/opacity
        args: [0.85]
      - route_tier: r1
        app: Resolume
        kind: osc
        semantic: layer_param
        address: /composition/layers/1/transition
        args: [0.25]
fallback_order: [adapter, ask]
verification:
  type: osc_hash
calls: []
depends_on: []
---

# Layer Mix

Demo vault for Resolume layer parameter replay through shared OSC.
