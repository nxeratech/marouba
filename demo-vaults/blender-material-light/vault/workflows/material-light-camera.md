---
id: material-light-camera
name: Material Light Camera
app: Blender
description: Demo Blender r1 adapter vault that captures object, material, light, and camera operators.
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
          name: LitCube
          size: "{size}"
          location: [0, 0, 0]
      - route_tier: r1
        app: Blender
        kind: operator
        operator: object.light_add
        params:
          type: AREA
          location: [2, -3, 4]
      - route_tier: r1
        app: Blender
        kind: operator
        operator: object.camera_add
        params:
          location: [4, -5, 3]
          rotation: [1.1, 0, 0.68]
fallback_order: [adapter, ask]
verification:
  type: scene_hash
calls: []
depends_on: []
---

# Material Light Camera

Demo vault for Blender scene construction through bpy operator replay.
