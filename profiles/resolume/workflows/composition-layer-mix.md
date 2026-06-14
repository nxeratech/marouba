---
id: resolume-composition-layer-mix
name: Resolume Composition Layer Mix
app: Resolume
app_version: latest
author: nxeratech
category: vj
description: Set composition and layer parameters through exact Resolume OSC messages.
params: []
tags: [resolume, osc, layer, composition, adapter, r1]
last_verified: 2026-06-14
created: 2026-06-14
routes:
  - type: adapter
    adapter: resolume
    events:
      - route_tier: r1
        app: Resolume
        kind: osc
        semantic: composition_param
        address: /composition/tempocontroller/tempo
        args: [128.0]
      - route_tier: r1
        app: Resolume
        kind: osc
        semantic: layer_param
        address: /composition/layers/1/opacity
        args: [0.85]
  - type: shortcut
    keys: [space]
fallback_order: [adapter, shortcut, ask]
verification:
  type: osc_hash
calls: []
depends_on: []
---

# Resolume Composition Layer Mix

Set composition tempo and layer opacity through native OSC.
