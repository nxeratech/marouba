---
id: photoshop-export-for-web
name: Photoshop Export for Web
app: Photoshop
app_version: latest
author: nxeratech
category: image-export
tags: [photoshop, export, web, marketplace-seed]
last_verified: 2026-06-06
created: 2026-06-06
routes:
  - type: cli
    command: "photoshop.exe -r scripts/photoshop_export_for_web.jsx --input {input_path} --output {output_path} --format {format}"
  - type: uia
    app_window: Adobe Photoshop
    element: Save for Web (Legacy)
    role: MenuItem
  - type: shortcut
    keys: [ctrl, alt, shift, s]
  - type: visual
    snapshot: profiles/photoshop/snapshots/save-for-web-dialog.png
fallback_order: [cli, uia, shortcut, visual, ask]
verification:
  type: file_exists
  path: "{output_path}"
  timeout_seconds: 60
calls: []
depends_on: []
---

# Photoshop Export for Web

Export the open document to a web-ready image using JSX first, then Photoshop UI fallbacks.
