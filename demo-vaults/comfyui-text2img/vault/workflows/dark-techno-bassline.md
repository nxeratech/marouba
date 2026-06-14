---
id: dark-techno-bassline
name: Dark Techno Bassline
app: ComfyUI
description: Demo ComfyUI adapter vault using graph JSON replay for a dark techno bassline image prompt.
params:
  - name: prompt
    type: string
    required: true
tags: [comfyui, demo, adapter, r1]
routes:
  - type: adapter
    adapter: comfyui
    wait_for_history: true
    graph:
      "1":
        class_type: CLIPTextEncode
        inputs:
          text: "{prompt}"
      "2":
        class_type: SaveImage
        inputs:
          filename_prefix: marouba-dark-techno
fallback_order: [adapter, api, ask]
verification:
  type: none
calls: []
depends_on: []
---

# Dark Techno Bassline

Demo vault for ComfyUI graph replay through the r1 adapter path.
