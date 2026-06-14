---
id: obs-transition-setup
name: OBS Transition Setup
app: OBS Studio
app_version: latest
author: nxeratech
category: streaming
description: Set the current OBS transition and duration through obs-websocket.
params: []
tags: [obs, transition, adapter, r1]
last_verified: 2026-06-14
created: 2026-06-14
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
  - type: shortcut
    keys: [ctrl, shift, s]
fallback_order: [adapter, shortcut, ask]
verification:
  type: collection_hash
calls: []
depends_on: []
---

# OBS Transition Setup

Set transition state through obs-websocket.
