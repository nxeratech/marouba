# Goal 22 Blender Adapter Audit

Date: 2026-06-14

## Existing Surface

- `profiles/blender/manifest.yaml` already declares Blender as a T1 adapter with full scene, operator, render, and export state.
- `profiles/blender/blender-profile.md` already identifies `bpy` as the primary Python API and CLI/background render as non-gesture routes.
- Existing workflow seeds are render/export focused. They include visual fallbacks, but the Goal 22 modeling path needs a dedicated r1 adapter route rather than browser pixels or viewport gestures.

## r1 Capture Boundary

Blender has a stable Python API through `bpy`. Goal 22 capture should treat these as r1 evidence:

- operator log entries: `bpy.ops.*` operator name plus exact params
- datablock changes: object, mesh, material, modifier, camera, light, and scene properties observed before/after a capture window

Viewport gestures are not semantic enough to rebuild a scene. They are retained only as r3 taste/context signals and are ignored by deterministic replay.

## Replay Boundary

Replay is via `bpy`:

- clear scene unless the route explicitly opts out
- replay r1 operator events in order
- apply r1 datablock changes
- hash deterministic scene data after replay

The adapter refuses routes with no r1 operator/datablock events. It does not depend on browser pixels.

## Remaining Machine Proof

The committed tests use an injected fake `bpy` module so CI can verify the contract without a Blender install. Full PASS still requires Dave's Blender machine:

- record a 10-edit/simple-object session with real `bpy` handlers
- replay on fresh Blender start
- compare real mesh scene hashes
- run 20 cold replays and confirm at least 95 percent success
