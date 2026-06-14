---
id: resolve-edit-and-cdl-grade
name: Resolve Edit And CDL Grade
app: DaVinci Resolve
app_version: latest
author: nxeratech
category: video-edit-grade
description: Import media, append to the active timeline, and apply exact CDL values through the Resolve scripting API.
params:
  - name: media_path
    type: string
    required: true
tags: [resolve, timeline, grade, adapter, r1]
last_verified: 2026-06-14
created: 2026-06-14
routes:
  - type: adapter
    adapter: davinci-resolve
    events:
      - route_tier: r1
        app: DaVinci Resolve
        kind: timeline_op
        action: import_media
        paths: ["{media_path}"]
      - route_tier: r1
        app: DaVinci Resolve
        kind: timeline_op
        action: append_to_timeline
        result_key: timeline_item_1
        clip_infos:
          - mediaPoolItem: "{media_path}"
            trackIndex: 1
            recordFrame: 0
      - route_tier: r1
        app: DaVinci Resolve
        kind: grade_node
        action: set_cdl
        value_source: cdl
        timeline_item: timeline_item_1
        cdl:
          NodeIndex: "1"
          Slope: "1.05 0.98 0.92"
          Offset: "0.01 0.00 -0.01"
          Power: "0.95 1.00 1.08"
          Saturation: "1.15"
  - type: uia
    app_window: DaVinci Resolve
    element: Color
    role: Button
fallback_order: [adapter, uia, ask]
verification:
  type: project_hash
calls: []
depends_on: []
---

# Resolve Edit And CDL Grade

API-level edit and exact CDL grade replay.
