---
id: img2img-remix
name: Img2Img Remix
app: ComfyUI
description: Demo ComfyUI adapter vault for img2img-style graph replay.
params:
  - name: input_path
    type: string
    required: true
  - name: prompt
    type: string
    required: true
tags: [comfyui, demo, img2img, adapter, r1]
routes:
  - type: adapter
    adapter: comfyui
    wait_for_history: true
    graph:
      "1":
        class_type: LoadImage
        inputs:
          image: "{input_path}"
      "2":
        class_type: CLIPTextEncode
        inputs:
          text: "{prompt}"
      "3":
        class_type: SaveImage
        inputs:
          filename_prefix: marouba-img2img
fallback_order: [adapter, api, ask]
verification:
  type: none
calls: []
depends_on: []
---

# Img2Img Remix

Demo vault for replaying an img2img graph without browser pixels.
