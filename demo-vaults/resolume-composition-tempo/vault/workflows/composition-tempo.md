---
id: composition-tempo
name: Composition Tempo
app: Resolume
description: Demo Resolume adapter vault setting composition tempo through exact OSC.
params:
  - name: bpm
    type: number
    required: true
tags: [resolume, demo, adapter, r1, composition]
routes:
  - type: adapter
    adapter: resolume
    events:
      - route_tier: r1
        app: Resolume
        kind: osc
        semantic: composition_param
        address: /composition/tempocontroller/tempo
        args: ["{bpm}"]
fallback_order: [adapter, ask]
verification:
  type: osc_hash
calls: []
depends_on: []
---

# Composition Tempo

Demo vault for Resolume composition parameter replay through shared OSC.
