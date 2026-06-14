---
id: fusion360-sketch-extrude
name: Fusion 360 Sketch Extrude
app: Fusion 360
app_version: latest
author: nxeratech
category: cad
description: Demo sketch plus extrude feature replay.
params: []
tags: [fusion360, adapter, demo]
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
        action: extrude
        timeline_index: 1
        feature_id: extrude_base
        profile_id: profile_rect
        operation: new_body
        parameters: {distance: 10}
fallback_order: [adapter, uia, ask]
verification: {type: timeline_feature_hash}
calls: []
depends_on: []
---

# Fusion 360 Sketch Extrude
