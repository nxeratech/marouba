---
id: ableton-export-master
name: Ableton Export Master
app: Ableton Live
app_version: latest
author: nxeratech
category: audio-export
description: Export the Ableton Live master mix to a single audio file.
params:
  - name: set_path
    type: string
    required: true
  - name: output_path
    type: string
    required: true
tags: [ableton, master, wav, marketplace-seed]
last_verified: 2026-06-06
created: 2026-06-06
routes:
  - type: cli
    command: "python tools/ableton_bridge.py --action export-master --set {set_path} --output {output_path}"
  - type: uia
    app_window: Ableton Live
    element: Render
    role: Button
  - type: shortcut
    keys: [ctrl, shift, r]
  - type: visual
    snapshot: profiles/ableton/snapshots/render-button.png
fallback_order: [cli, uia, shortcut, visual, ask]
verification:
  type: file_exists
  path: "{output_path}"
  timeout_seconds: 300
calls: []
depends_on: []
---

# Ableton Export Master

Export the master mix to a single audio file.
