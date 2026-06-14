---
id: premiere-timeline-effect-edit
name: Premiere Timeline Effect Edit
app: Premiere Pro
app_version: latest
author: nxeratech
category: video-edit
description: Timeline clip placement and exact effect parameter replay.
params: []
tags: [premiere, adapter, timeline, effects]
created: 2026-06-14
routes:
  - type: adapter
    adapter: premiere
    events:
      - route_tier: r1
        app: Premiere Pro
        kind: sequence
        action: create_sequence
        sequence_name: Marouba Cut
        timebase: 25
      - route_tier: r1
        app: Premiere Pro
        kind: clip
        action: add_clip
        track_type: video
        track_index: 0
        clip_id: clip_1
        clip_name: bassline-shot.mov
        start: 0.0
        end: 4.0
      - route_tier: r1
        app: Premiere Pro
        kind: effect_param
        action: set_effect_param
        clip_id: clip_1
        effect_name: Lumetri Color
        param_name: Exposure
        value: 0.35
        value_status: exact
fallback_order: [adapter, uia, ask]
verification:
  type: timeline_hash
calls: []
depends_on: []
---

# Premiere Timeline Effect Edit

Timeline and effect params are replayed from API evidence.
