---
id: photoshop-batch-resize
name: Photoshop Batch Resize
app: Photoshop
app_version: latest
author: nxeratech
category: image-processing
tags: [photoshop, batch, resize, marketplace-seed]
last_verified: 2026-06-06
created: 2026-06-06
routes:
  - type: cli
    command: "photoshop.exe -r scripts/photoshop_batch_resize.jsx --input {input_folder} --output {output_folder} --width {width}"
  - type: uia
    app_window: Adobe Photoshop
    element: Batch
    role: MenuItem
  - type: shortcut
    keys: [ctrl, alt, i]
  - type: visual
    snapshot: profiles/photoshop/snapshots/image-size-dialog.png
fallback_order: [cli, uia, shortcut, visual, ask]
verification:
  type: folder_contains
  path: "{output_folder}"
  timeout_seconds: 120
calls: []
depends_on: []
---

# Photoshop Batch Resize

Resize a folder of images to a target width and save the results to an output folder.
