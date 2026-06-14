---
id: camera-grade
name: Camera Grade
app: OBS Studio
description: Demo OBS adapter vault creating a camera source with exact color filter and audio level.
params:
  - name: device_id
    type: string
    required: true
tags: [obs, demo, adapter, r1, filter]
routes:
  - type: adapter
    adapter: obs-studio
    events:
      - route_tier: r1
        app: OBS Studio
        kind: scene
        action: create_scene
        sceneName: Camera Demo
      - route_tier: r1
        app: OBS Studio
        kind: source
        action: create_input
        sceneName: Camera Demo
        inputName: Camera
        inputKind: dshow_input
        inputSettings:
          device_id: "{device_id}"
      - route_tier: r1
        app: OBS Studio
        kind: filter
        action: create_filter
        sourceName: Camera
        filterName: Color Correction
        filterKind: color_filter
        filterSettings:
          gamma: 0.05
          contrast: 0.1
          saturation: 0.08
      - route_tier: r1
        app: OBS Studio
        kind: audio
        action: set_input_volume
        inputName: Camera
        inputVolumeDb: -8.0
fallback_order: [adapter, ask]
verification:
  type: collection_hash
calls: []
depends_on: []
---

# Camera Grade

Demo vault for exact OBS source, filter, and audio replay.
