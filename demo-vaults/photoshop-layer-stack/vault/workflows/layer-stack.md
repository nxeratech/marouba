---
id: photoshop-layer-stack
name: Photoshop Layer Stack
app: Photoshop
app_version: latest
author: nxeratech
category: image-edit
description: Layer operations captured as UXP action descriptors with UI gesture fallback available.
params: []
tags: [photoshop, adapter, layers, demo]
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
        layer_id: 11
        layer_name: Texture Overlay
        descriptor: {_obj: make, _target: [{_ref: layer}], layerID: 11}
      - route_tier: r1
        app: Photoshop
        kind: layer
        action: layer_op
        operation: rename
        layer_id: 11
        layer_name: Texture Overlay Soft Light
        descriptor: {_obj: set, _target: [{_ref: layer, _id: 11}], to: {_obj: layer, name: Texture Overlay Soft Light}}
fallback_order: [adapter, gesture, ask]
verification:
  type: document_hash
calls: []
depends_on: []
---

# Photoshop Layer Stack

Demo vault for semantic layer stack operations.
