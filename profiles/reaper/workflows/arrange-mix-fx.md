---
id: reaper-arrange-mix-fx
name: REAPER Arrange Mix FX
app: REAPER
app_version: latest
author: nxeratech
category: audio-production
description: Create a track, add an item, insert ReaEQ, and set exact FX parameter values.
params: []
tags: [reaper, reascript, arrange, fx, adapter, r1]
last_verified: 2026-06-14
created: 2026-06-14
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
        value: 0.42
        value_status: exact
  - type: shortcut
    keys: ["?"]
fallback_order: [adapter, shortcut, ask]
verification:
  type: project_hash
calls: []
depends_on: []
---

# REAPER Arrange Mix FX

Create arrange and mix state through exact ReaScript events.
