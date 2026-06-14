---
id: osc-control
name: OSC Control
app: TouchDesigner
description: Demo TouchDesigner adapter vault creating a parameter target and sending an exact OSC value.
params:
  - name: gain
    type: number
    required: true
tags: [touchdesigner, demo, adapter, r1, osc]
routes:
  - type: adapter
    adapter: touchdesigner
    events:
      - route_tier: r1
        app: TouchDesigner
        kind: network
        action: create_operator
        parent: /project1
        op_type: constantCHOP
        name: marouba_gain
      - route_tier: r1
        app: TouchDesigner
        kind: parameter
        action: set_param
        path: /project1/marouba_gain
        param: value0
        value: "{gain}"
        value_status: exact
      - route_tier: r1
        app: TouchDesigner
        kind: osc
        action: send_osc
        address: /marouba/gain
        args: ["{gain}"]
fallback_order: [adapter, ask]
verification:
  type: network_hash
calls: []
depends_on: []
---

# OSC Control

Demo vault for exact TouchDesigner parameter and OSC replay.
