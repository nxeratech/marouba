---
id: render-chain
name: Render Chain
app: TouchDesigner
description: Demo TouchDesigner adapter vault creating a small TOP render chain.
params: []
tags: [touchdesigner, demo, adapter, r1, topology]
routes:
  - type: adapter
    adapter: touchdesigner
    events:
      - route_tier: r1
        app: TouchDesigner
        kind: network
        action: create_operator
        parent: /project1
        op_type: moviefileinTOP
        name: marouba_source
      - route_tier: r1
        app: TouchDesigner
        kind: network
        action: create_operator
        parent: /project1
        op_type: blurTOP
        name: marouba_blur
      - route_tier: r1
        app: TouchDesigner
        kind: parameter
        action: set_param
        path: /project1/marouba_blur
        param: filter
        value: gaussian
        value_status: exact
      - route_tier: r1
        app: TouchDesigner
        kind: network
        action: connect
        source: /project1/marouba_source
        target: /project1/marouba_blur
        input_index: 0
fallback_order: [adapter, ask]
verification:
  type: network_hash
calls: []
depends_on: []
---

# Render Chain

Demo vault for exact TouchDesigner network topology replay.
