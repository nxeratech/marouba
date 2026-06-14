---
id: photoshop-layered-edit
name: Photoshop Layered Edit
app: Photoshop
app_version: latest
author: nxeratech
category: image-edit
description: Record and replay a layered Photoshop edit using UXP action descriptors with brush strokes declared as r3 gesture.
params: []
tags: [photoshop, adapter, uxp, layer, filter]
created: 2026-06-14
routes:
  - type: adapter
    adapter: photoshop
    events:
      - route_tier: r1
        app: Photoshop
        kind: layer
        action: layer_op
        operation: make
        layer_id: 7
        layer_name: Glow Pass
        descriptor: {_obj: make, _target: [{_ref: layer}], layerID: 7}
      - route_tier: r1
        app: Photoshop
        kind: filter
        action: apply_filter
        filter_name: gaussianBlur
        params: {radius: 4.5}
        value_status: exact
        descriptor: {_obj: gaussianBlur, radius: {_unit: pixelsUnit, _value: 4.5}}
      - route_tier: r3
        app: Photoshop
        kind: brush_stroke
        action: brush_stroke
        points: [{x: 10, y: 20}, {x: 30, y: 45}]
        timing_ms: [0, 92]
fallback_order: [adapter, gesture, ask]
verification:
  type: document_hash
calls: []
depends_on: []
---

# Photoshop Layered Edit

Layer and filter steps are replayed from UXP action descriptors. Brush strokes remain r3 gesture because stroke timing is taste evidence.
