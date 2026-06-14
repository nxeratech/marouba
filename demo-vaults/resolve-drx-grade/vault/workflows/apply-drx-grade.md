---
id: apply-drx-grade
name: Apply DRX Grade
app: DaVinci Resolve
description: Demo Resolve adapter vault applying an exact DRX grade payload through the scripting API.
params:
  - name: drx_path
    type: string
    required: true
tags: [resolve, demo, adapter, r1, drx]
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
fallback_order: [adapter, uia, ask]
verification:
  type: project_hash
calls: []
depends_on: []
---

# Apply DRX Grade

Demo vault for exact DRX-backed grade replay. Gesture-only grade capture is not enough.
