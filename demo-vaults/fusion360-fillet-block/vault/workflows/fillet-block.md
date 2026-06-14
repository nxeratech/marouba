---
id: fusion360-fillet-block
name: Fusion 360 Fillet Block
app: Fusion 360
app_version: latest
author: nxeratech
category: cad
description: Demo fillet feature replay with exact radius.
params: []
tags: [fusion360, adapter, fillet, demo]
created: 2026-06-14
routes:
  - type: adapter
    adapter: fusion360
    events:
      - route_tier: r1
        app: Fusion 360
        kind: feature
        action: fillet
        timeline_index: 0
        feature_id: fillet_edges
        edge_refs: [top_edges]
        parameters: {radius: 2}
fallback_order: [adapter, uia, ask]
verification: {type: timeline_feature_hash}
calls: []
depends_on: []
---

# Fusion 360 Fillet Block
