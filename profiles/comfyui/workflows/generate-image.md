---
id: comfyui-generate-image
name: ComfyUI Generate Image
app: ComfyUI
app_version: latest
author: nxeratech
category: image-generation
description: Queue a ComfyUI text-to-image graph and verify the requested output image exists.
params:
  - name: prompt
    type: string
    required: true
  - name: output_path
    type: string
    required: true
tags: [comfyui, text-to-image, marketplace-seed]
last_verified: 2026-06-06
created: 2026-06-06
routes:
  - type: api
    endpoint: http://127.0.0.1:8188/prompt
    method: POST
    payload_template: prompts/comfyui-basic.json
  - type: cli
    command: "python scripts/replay.py --workflow comfyui-generate-image --params {params}"
  - type: uia
    app_window: ComfyUI
    element: Queue Prompt
    role: Button
  - type: shortcut
    keys: [ctrl, enter]
  - type: visual
    snapshot: profiles/comfyui/snapshots/queue-prompt-button.png
fallback_order: [api, cli, uia, shortcut, visual, ask]
verification:
  type: file_exists
  path: "{output_path}"
  timeout_seconds: 120
calls: []
depends_on: []
---

# ComfyUI Generate Image

Queue a text-to-image graph and verify that the requested output file exists.
