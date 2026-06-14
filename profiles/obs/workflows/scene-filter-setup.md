---
id: obs-scene-filter-setup
name: OBS Scene Filter Setup
app: OBS Studio
app_version: latest
author: nxeratech
category: streaming
description: Create a scene with a media source, exact source settings, audio level, and a color correction filter.
params:
  - name: media_path
    type: string
    required: true
tags: [obs, scene, filter, adapter, r1]
last_verified: 2026-06-14
created: 2026-06-14
routes:
  - type: adapter
    adapter: obs-studio
    events:
      - route_tier: r1
        app: OBS Studio
        kind: scene
        action: create_scene
        sceneName: Marouba Demo
      - route_tier: r1
        app: OBS Studio
        kind: source
        action: create_input
        sceneName: Marouba Demo
        inputName: Demo Media
        inputKind: ffmpeg_source
        inputSettings:
          local_file: "{media_path}"
          looping: true
      - route_tier: r1
        app: OBS Studio
        kind: filter
        action: create_filter
        sourceName: Demo Media
        filterName: Warm Grade
        filterKind: color_filter
        filterSettings:
          brightness: 0.02
          contrast: 0.08
          saturation: 0.15
      - route_tier: r1
        app: OBS Studio
        kind: audio
        action: set_input_volume
        inputName: Demo Media
        inputVolumeDb: -6.0
  - type: shortcut
    keys: [ctrl, r]
fallback_order: [adapter, shortcut, ask]
verification:
  type: collection_hash
calls: []
depends_on: []
---

# OBS Scene Filter Setup

Create an OBS scene with exact source, filter, and audio state through obs-websocket.
