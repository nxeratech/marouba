---
id: touchdesigner-network-noise-feedback
name: TouchDesigner Network Noise Feedback
app: TouchDesigner
app_version: latest
author: nxeratech
category: realtime-visual
description: Create a small TOP feedback network with exact operator topology and parameter values.
params: []
tags: [touchdesigner, network, parameter, adapter, r1]
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
        op_type: noiseTOP
        name: marouba_noise
        node: {nodeX: 0, nodeY: 0}
      - route_tier: r1
        app: TouchDesigner
        kind: parameter
        action: set_param
        path: /project1/marouba_noise
        param: period
        value: 3.5
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
        kind: parameter
        action: set_param
        path: /project1/marouba_level
        param: opacity
        value: 0.72
        value_status: exact
      - route_tier: r1
        app: TouchDesigner
        kind: network
        action: connect
        source: /project1/marouba_noise
        target: /project1/marouba_level
        input_index: 0
  - type: shortcut
    keys: [f5]
fallback_order: [adapter, shortcut, ask]
verification:
  type: network_hash
calls: []
depends_on: []
---

# TouchDesigner Network Noise Feedback

Rebuild a simple exact TOP network through Python topology events.
