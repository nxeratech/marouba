---
id: media-loop
name: Media Loop
app: OBS Studio
description: Demo OBS adapter vault creating a looping media source.
params:
  - name: media_path
    type: string
    required: true
tags: [obs, demo, adapter, r1, source]
routes:
  - type: adapter
    adapter: obs-studio
    events:
      - route_tier: r1
        app: OBS Studio
        kind: scene
        action: create_scene
        sceneName: Media Loop
      - route_tier: r1
        app: OBS Studio
        kind: source
        action: create_input
        sceneName: Media Loop
        inputName: Looping Media
        inputKind: ffmpeg_source
        inputSettings:
          local_file: "{media_path}"
          looping: true
      - route_tier: r1
        app: OBS Studio
        kind: audio
        action: set_input_mute
        inputName: Looping Media
        inputMuted: false
fallback_order: [adapter, ask]
verification:
  type: collection_hash
calls: []
depends_on: []
---

# Media Loop

Demo vault for exact OBS media source replay.
