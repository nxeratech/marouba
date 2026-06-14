---
id: fusion360-sketch-extrude-fillet
name: Fusion 360 Sketch Extrude Fillet
app: Fusion 360
app_version: latest
author: nxeratech
category: cad
description: Create a rectangle sketch, extrude it, and add a fillet from exact timeline features.
params: []
tags: [fusion360, adapter, timeline, parametric-cad]
created: 2026-06-14
routes:
  - type: adapter
    adapter: fusion360
    events:
      - route_tier: r1
        app: Fusion 360
        kind: feature
        action: create_sketch
        timeline_index: 0
        feature_id: sketch_base
        plane: XY
        parameters: {plane: XY}
      - route_tier: r1
        app: Fusion 360
        kind: feature
        action: add_profile
        timeline_index: 1
        feature_id: profile_rect
        sketch_id: sketch_base
        profile_type: rectangle
        parameters: {corner_a: [0, 0], corner_b: [80, 40]}
      - route_tier: r1
        app: Fusion 360
        kind: feature
        action: extrude
        timeline_index: 2
        feature_id: extrude_body
        profile_id: profile_rect
        operation: new_body
        parameters: {distance: 12}
      - route_tier: r1
        app: Fusion 360
        kind: feature
        action: fillet
        timeline_index: 3
        feature_id: fillet_edges
        edge_refs: [top_edges]
        parameters: {radius: 2}
fallback_order: [adapter, uia, ask]
verification:
  type: timeline_feature_hash
calls: []
depends_on: []
---

# Fusion 360 Sketch Extrude Fillet

Timeline order and exact feature parameters are the replay proof.
