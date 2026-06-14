---
id: envelope-ride
name: Envelope Ride
app: REAPER
description: Demo REAPER adapter vault inserting exact volume envelope points.
params: []
tags: [reaper, demo, adapter, r1, envelope]
routes:
  - type: adapter
    adapter: reaper
    events:
      - route_tier: r1
        app: REAPER
        kind: track
        action: insert_track
        track_index: 0
        name: Marouba Automation
        volume: 1.0
      - route_tier: r1
        app: REAPER
        kind: envelope
        action: insert_envelope_point
        track_index: 0
        envelope_name: Volume
        time: 0.0
        value: 0.75
        shape: 0
        tension: 0.0
        value_status: exact
      - route_tier: r1
        app: REAPER
        kind: envelope
        action: insert_envelope_point
        track_index: 0
        envelope_name: Volume
        time: 4.0
        value: 1.0
        shape: 0
        tension: 0.0
        value_status: exact
fallback_order: [adapter, ask]
verification:
  type: project_hash
calls: []
depends_on: []
---

# Envelope Ride

Demo vault for exact REAPER envelope replay.
