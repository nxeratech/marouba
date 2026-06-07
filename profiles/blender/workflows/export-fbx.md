---
id: blender-export-fbx
name: Blender Export FBX
app: Blender
app_version: latest
author: nxeratech
category: 3d-export
description: Export the active Blender scene or selected objects to FBX.
params:
  - name: blend_path
    type: string
    required: true
  - name: output_path
    type: string
    required: true
tags: [blender, fbx, export, marketplace-seed]
last_verified: 2026-06-06
created: 2026-06-06
routes:
  - type: cli
    command: "blender --background {blend_path} --python scripts/blender_export_fbx.py -- {output_path}"
  - type: api
    endpoint: bpy.ops.export_scene.fbx
    method: PYTHON
    payload_template: profiles/blender/payloads/export-fbx.py
  - type: uia
    app_window: Blender
    element: FBX
    role: MenuItem
  - type: shortcut
    keys: [f3]
  - type: visual
    snapshot: profiles/blender/snapshots/export-fbx-menu.png
fallback_order: [cli, api, uia, shortcut, visual, ask]
verification:
  type: file_exists
  path: "{output_path}"
  timeout_seconds: 180
calls: []
depends_on: []
---

# Blender Export FBX

Export the active scene or selected objects to FBX.
