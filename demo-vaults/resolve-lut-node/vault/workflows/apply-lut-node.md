---
id: apply-lut-node
name: Apply LUT Node
app: DaVinci Resolve
description: Demo Resolve adapter vault applying a LUT to a specific grade node through the scripting API.
params:
  - name: lut_path
    type: string
    required: true
tags: [resolve, demo, adapter, r1, lut]
routes:
  - type: adapter
    adapter: davinci-resolve
    events:
      - route_tier: r1
        app: DaVinci Resolve
        kind: grade_node
        action: set_lut
        value_source: lut
        timeline_item: timeline_item_1
        node_index: 1
        lut_path: "{lut_path}"
fallback_order: [adapter, uia, ask]
verification:
  type: project_hash
calls: []
depends_on: []
---

# Apply LUT Node

Demo vault for exact LUT node replay through Resolve's graph API.
