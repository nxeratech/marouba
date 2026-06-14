---
id: premiere-timeline-cut
name: Premiere Timeline Cut
app: Premiere Pro
app_version: latest
author: nxeratech
category: video-edit
description: Demo timeline clip placement from API-level Premiere evidence.
params: []
tags: [premiere, adapter, demo]
created: 2026-06-14
routes:
  - type: adapter
    adapter: premiere
    events:
      - route_tier: r1
        app: Premiere Pro
        kind: sequence
        action: create_sequence
        sequence_name: Demo Cut
        timebase: 25
      - route_tier: r1
        app: Premiere Pro
        kind: clip
        action: add_clip
        track_type: video
        track_index: 0
        clip_id: clip_1
        clip_name: shot-a.mov
        start: 0.0
        end: 3.0
fallback_order: [adapter, uia, ask]
verification: {type: timeline_hash}
calls: []
depends_on: []
---

# Premiere Timeline Cut
