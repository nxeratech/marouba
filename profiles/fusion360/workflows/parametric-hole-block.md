---
id: fusion360-parametric-hole-block
name: Fusion 360 Parametric Hole Block
app: Fusion 360
app_version: latest
author: nxeratech
category: cad
description: Set a user parameter and replay dependent sketch/extrude features.
params: []
tags: [fusion360, adapter, parameters]
created: 2026-06-14
routes:
  - type: adapter
    adapter: fusion360
    events:
      - route_tier: r1
        app: Fusion 360
        kind: feature
        action: set_parameter
        timeline_index: 0
        feature_id: param_width
        parameter_name: width
        expression: 80 mm
        parameters: {unit: mm, value: 80}
      - route_tier: r1
        app: Fusion 360
        kind: feature
        action: create_sketch
        timeline_index: 1
        feature_id: sketch_hole
        plane: XY
        parameters: {plane: XY}
fallback_order: [adapter, uia, ask]
verification:
  type: timeline_feature_hash
calls: []
depends_on: []
---

# Fusion 360 Parametric Hole Block

User parameter and downstream features are represented as ordered timeline evidence.
