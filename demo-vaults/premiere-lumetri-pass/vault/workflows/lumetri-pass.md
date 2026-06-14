---
id: premiere-lumetri-pass
name: Premiere Lumetri Pass
app: Premiere Pro
app_version: latest
author: nxeratech
category: video-edit
description: Demo exact Lumetri parameter replay.
params: []
tags: [premiere, adapter, effects, demo]
created: 2026-06-14
routes:
  - type: adapter
    adapter: premiere
    events:
      - route_tier: r1
        app: Premiere Pro
        kind: effect_param
        action: set_effect_param
        clip_id: clip_1
        effect_name: Lumetri Color
        param_name: Exposure
        value: 0.25
        value_status: exact
fallback_order: [adapter, uia, ask]
verification: {type: timeline_hash}
calls: []
depends_on: []
---

# Premiere Lumetri Pass
