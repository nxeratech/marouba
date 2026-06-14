---
id: noise-level
name: Noise Level
app: TouchDesigner
description: Demo TouchDesigner adapter vault creating a connected noise TOP and level TOP network.
params:
  - name: period
    type: number
    required: true
tags: [touchdesigner, demo, adapter, r1, network]
routes:
  - type: adapter
    adapter: touchdesigner
    events:
      - route_tier: r1
        app: TouchDesigner
        kind: network
        action: create_operator
        parent: /project1
        op_type: noiseTOP
        name: marouba_noise
        node: {nodeX: 0, nodeY: 0}
      - route_tier: r1
        app: TouchDesigner
        kind: parameter
        action: set_param
        path: /project1/marouba_noise
        param: period
        value: "{period}"
        value_status: exact
      - route_tier: r1
        app: TouchDesigner
        kind: network
        action: create_operator
        parent: /project1
        op_type: levelTOP
        name: marouba_level
        node: {nodeX: 180, nodeY: 0}
      - route_tier: r1
        app: TouchDesigner
        kind: network
        action: connect
        source: /project1/marouba_noise
        target: /project1/marouba_level
        input_index: 0
fallback_order: [adapter, ask]
verification:
  type: network_hash
calls: []
depends_on: []
---

# Noise Level

Demo vault for exact TouchDesigner topology replay.
