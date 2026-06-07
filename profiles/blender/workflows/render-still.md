---
id: blender-render-still
name: Blender Render Still
app: Blender
app_version: latest
author: nxeratech
category: 3d-render
description: Render a single still frame from a Blender file.
params:
  - name: blend_path
    type: string
    required: true
  - name: output_path
    type: string
    required: true
  - name: frame
    type: integer
    required: true
tags: [blender, render, still, marketplace-seed]
last_verified: 2026-06-06
created: 2026-06-06
routes:
  - type: cli
    command: "blender --background {blend_path} --render-output {output_path} --render-frame {frame}"
  - type: api
    endpoint: bpy.ops.render.render
    method: PYTHON
    payload_template: profiles/blender/payloads/render-still.py
  - type: uia
    app_window: Blender
    element: Render Image
    role: MenuItem
  - type: shortcut
    keys: [f12]
  - type: visual
    snapshot: profiles/blender/snapshots/render-image-menu.png
fallback_order: [cli, api, uia, shortcut, visual, ask]
verification:
  type: file_exists
  path: "{output_path}"
  timeout_seconds: 300
calls: []
depends_on: []
---

# Blender Render Still

Render a single still frame from a `.blend` file.
