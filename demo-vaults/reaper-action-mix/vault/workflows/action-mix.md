---
id: action-mix
name: Action Mix
app: REAPER
description: Demo REAPER adapter vault combining an action with exact track mix state.
params: []
tags: [reaper, demo, adapter, r1, action]
routes:
  - type: adapter
    adapter: reaper
    events:
      - route_tier: r1
        app: REAPER
        kind: action
        action: run_action
        command_id: 40001
      - route_tier: r1
        app: REAPER
        kind: track
        action: insert_track
        track_index: 0
        name: Marouba Mix
        volume: 0.9
        pan: -0.15
fallback_order: [adapter, ask]
verification:
  type: project_hash
calls: []
depends_on: []
---

# Action Mix

Demo vault for REAPER action and track mix replay through ReaScript.
