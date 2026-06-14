---
id: resolve-apply-drx-grade
name: Resolve Apply DRX Grade
app: DaVinci Resolve
app_version: latest
author: nxeratech
category: video-grade
description: Apply an exact DRX grade payload to a timeline item through the Resolve scripting API.
params:
  - name: drx_path
    type: string
    required: true
tags: [resolve, grade, drx, adapter, r1]
last_verified: 2026-06-14
created: 2026-06-14
routes:
  - type: adapter
    adapter: davinci-resolve
    events:
      - route_tier: r1
        app: DaVinci Resolve
        kind: grade_node
        action: apply_grade_from_drx
        value_source: drx
        timeline_item: timeline_item_1
        node_index: 1
        drx_path: "{drx_path}"
        grade_mode: 0
  - type: uia
    app_window: DaVinci Resolve
    element: Gallery
    role: Pane
fallback_order: [adapter, uia, ask]
verification:
  type: project_hash
calls: []
depends_on: []
---

# Resolve Apply DRX Grade

DRX-backed grade replay. Arbitrary grade slider approximation is explicitly out of scope.
