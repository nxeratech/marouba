---
id: photoshop-color-grade
name: Photoshop Color Grade
app: Photoshop
app_version: latest
author: nxeratech
category: image-edit
description: Exact numeric adjustment event captured from Photoshop action descriptors.
params: []
tags: [photoshop, adapter, adjustment, demo]
created: 2026-06-14
routes:
  - type: adapter
    adapter: photoshop
    events:
      - route_tier: r1
        app: Photoshop
        kind: adjustment
        action: adjustment
        adjustment_name: brightnessContrast
        params: {brightness: 12, contrast: 18}
        value_status: exact
        descriptor: {_obj: brightnessEvent, brightness: 12, center: 18}
      - route_tier: r1
        app: Photoshop
        kind: filter
        action: apply_filter
        filter_name: unsharpMask
        params: {amount: 85, radius: 1.2, threshold: 3}
        value_status: exact
        descriptor: {_obj: unsharpMask, amount: 85, radius: 1.2, threshold: 3}
fallback_order: [adapter, gesture, ask]
verification:
  type: document_hash
calls: []
depends_on: []
---

# Photoshop Color Grade

Demo vault for exact numeric adjustment and filter parameter replay.
