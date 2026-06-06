---
id: ableton-bounce-stems
name: Ableton Bounce Stems
app: Ableton Live
app_version: latest
author: nxeratech
category: audio-export
tags: [ableton, stems, export, marketplace-seed]
last_verified: 2026-06-06
created: 2026-06-06
routes:
  - type: cli
    command: "python tools/ableton_bridge.py --action bounce-stems --set {set_path} --output {output_folder}"
  - type: uia
    app_window: Ableton Live
    element: Export Audio/Video
    role: MenuItem
  - type: shortcut
    keys: [ctrl, shift, r]
  - type: visual
    snapshot: profiles/ableton/snapshots/export-audio-video.png
fallback_order: [cli, uia, shortcut, visual, ask]
verification:
  type: folder_contains
  path: "{output_folder}"
  timeout_seconds: 300
calls: []
depends_on: []
---

# Ableton Bounce Stems

Export selected tracks or all tracks as individual stem files.
