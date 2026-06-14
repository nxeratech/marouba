---
id: touchdesigner-osc-driven-parameter
name: TouchDesigner OSC Driven Parameter
app: TouchDesigner
app_version: latest
author: nxeratech
category: realtime-control
description: Create a TouchDesigner parameter target and send an exact OSC control message.
params:
  - name: gain
    type: number
    required: true
tags: [touchdesigner, osc, parameter, adapter, r1]
last_verified: 2026-06-14
created: 2026-06-14
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
  - type: shortcut
    keys: [f5]
fallback_order: [adapter, shortcut, ask]
verification:
  type: network_hash
calls: []
depends_on: []
---

# TouchDesigner OSC Driven Parameter

Create an exact parameter target and replay a matching OSC control value.
