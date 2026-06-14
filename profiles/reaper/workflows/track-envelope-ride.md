---
id: reaper-track-envelope-ride
name: REAPER Track Envelope Ride
app: REAPER
app_version: latest
author: nxeratech
category: audio-automation
description: Create a track and insert exact volume envelope points through ReaScript.
params: []
tags: [reaper, envelope, automation, adapter, r1]
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
  - type: shortcut
    keys: [ctrl, s]
fallback_order: [adapter, shortcut, ask]
verification:
  type: project_hash
calls: []
depends_on: []
---

# REAPER Track Envelope Ride

Insert exact automation envelope points through ReaScript.
