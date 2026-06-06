---
id: comfyui-generate-image-001
name: ComfyUI Generate Image
app: ComfyUI
app_version: latest
author: nxeratech
category: image-generation
tags: [comfyui, generate, image]
last_verified: 2026-06-05
created: 2026-06-05
routes:
  - type: api
    endpoint: http://127.0.0.1:8188/prompt
    method: POST
    payload_template: prompts/comfyui-basic.json
  - type: cli
    command: "python comfyui_client.py --prompt {prompt} --output {output_path}"
  - type: uia
    element: queue-prompt-button
    role: Button
    app_window: ComfyUI
  - type: keyboard
    keys: [ctrl, enter]
  - type: visual
    snapshot: snapshots/comfyui-queue-button.png
fallback_order: [api, cli, uia, keyboard, visual, ask]
verification:
  type: file_exists
  path: "{output_path}"
  timeout_seconds: 120
calls: []
depends_on: []
---

# ComfyUI Generate Image

Generate one image in ComfyUI using the direct API route.
