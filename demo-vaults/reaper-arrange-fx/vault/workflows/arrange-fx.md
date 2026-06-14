---
id: arrange-fx
name: Arrange FX
app: REAPER
description: Demo REAPER adapter vault creating arrange item and exact FX parameter state.
params:
  - name: freq
    type: number
    required: true
tags: [reaper, demo, adapter, r1, fx]
routes:
  - type: adapter
    adapter: reaper
    events:
      - route_tier: r1
        app: REAPER
        kind: track
        action: insert_track
        track_index: 0
        name: Marouba Bass
        volume: 0.82
        pan: 0.0
      - route_tier: r1
        app: REAPER
        kind: item
        action: add_media_item
        track_index: 0
        position: 0.0
        length: 4.0
        name: bass-loop
      - route_tier: r1
        app: REAPER
        kind: fx
        action: add_fx
        track_index: 0
        fx_index: 0
        fx_name: ReaEQ
      - route_tier: r1
        app: REAPER
        kind: fx_param
        action: set_fx_param
        track_index: 0
        fx_index: 0
        param_index: 0
        param_name: Band 1 Frequency
        value: "{freq}"
        value_status: exact
fallback_order: [adapter, ask]
verification:
  type: project_hash
calls: []
depends_on: []
---

# Arrange FX

Demo vault for exact REAPER arrange and FX parameter replay.
