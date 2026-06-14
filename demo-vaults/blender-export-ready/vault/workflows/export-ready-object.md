---
id: export-ready-object
name: Export Ready Object
app: Blender
description: Demo Blender r1 adapter vault for a named mesh prepared for later export.
params:
  - name: size
    type: number
    required: true
tags: [blender, demo, adapter, r1]
routes:
  - type: adapter
    adapter: blender
    clear_scene: true
    events:
      - route_tier: r1
        app: Blender
        kind: operator
        operator: mesh.primitive_cube_add
        params:
          name: ExportCube
          size: "{size}"
          location: [0, 0, 0]
      - route_tier: r1
        app: Blender
        kind: operator
        operator: object.modifier_add
        params:
          type: WEIGHTED_NORMAL
          name: WeightedNormal
      - route_tier: r1
        app: Blender
        kind: operator
        operator: object.shade_smooth
        params: {}
fallback_order: [adapter, ask]
verification:
  type: scene_hash
calls: []
depends_on: []
---

# Export Ready Object

Demo vault for a Blender object modeled through r1 bpy evidence before export.
