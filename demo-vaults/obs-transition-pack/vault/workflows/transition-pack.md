---
id: transition-pack
name: Transition Pack
app: OBS Studio
description: Demo OBS adapter vault setting transition and duration through obs-websocket.
params: []
tags: [obs, demo, adapter, r1, transition]
routes:
  - type: adapter
    adapter: obs-studio
    events:
      - route_tier: r1
        app: OBS Studio
        kind: transition
        action: set_current_transition
        transitionName: Fade
      - route_tier: r1
        app: OBS Studio
        kind: transition
        action: set_transition_duration
        transitionDuration: 450
fallback_order: [adapter, ask]
verification:
  type: collection_hash
calls: []
depends_on: []
---

# Transition Pack

Demo vault for exact OBS transition replay.
