---
id: comfyui-img2img
name: ComfyUI Img2Img
app: ComfyUI
app_version: latest
author: nxeratech
category: image-generation
description: Load a source image into a ComfyUI img2img graph, queue it, and verify the generated output.
params:
  - name: input_path
    type: string
    required: true
  - name: prompt
    type: string
    required: true
  - name: output_path
    type: string
    required: true
tags: [comfyui, img2img, marketplace-seed]
last_verified: 2026-06-06
created: 2026-06-06
routes:
  - type: api
    endpoint: http://127.0.0.1:8188/prompt
    method: POST
    payload_template: prompts/comfyui-img2img.json
  - type: cli
    command: "python tools/comfyui_client.py --mode img2img --input {input_path} --prompt {prompt} --output {output_path}"
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
  timeout_seconds: 180
calls: []
depends_on: []
---

# ComfyUI Img2Img

Load a source image into an img2img graph, queue it, and verify the generated output.
