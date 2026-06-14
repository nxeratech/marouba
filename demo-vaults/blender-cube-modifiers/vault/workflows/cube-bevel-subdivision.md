---
id: cube-bevel-subdivision
name: Cube Bevel Subdivision
app: Blender
description: Demo Blender r1 adapter vault that creates a cube and applies modifier datablock changes.
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
          name: DemoCube
          size: "{size}"
          location: [0, 0, 0]
      - route_tier: r1
        app: Blender
        kind: operator
        operator: object.modifier_add
        params:
          type: BEVEL
          name: Bevel
      - route_tier: r1
        app: Blender
        kind: datablock_changed
        datablock: object:DemoCube
        path: modifiers.Bevel.width
        value: 0.12
fallback_order: [adapter, ask]
verification:
  type: scene_hash
calls: []
depends_on: []
---

# Cube Bevel Subdivision

Demo vault for Blender operator/datablock replay through the r1 bpy adapter path.
