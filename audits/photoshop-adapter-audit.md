# Photoshop Adapter Audit

Date: 2026-06-14

Goal: capture Photoshop layered edit sessions as semantic events where Photoshop exposes scriptable state, while declaring brush strokes as gesture evidence.

## API Surface

Photoshop UXP exposes `require('photoshop').action.batchPlay(...)` for executing action descriptors. Adobe documents these descriptors as actionJSON commands with `_obj`, `_target`, and command parameters.

Photoshop UXP also exposes `action.addNotificationListener(['all'], ...)` for low-level action notifications in developer mode, and Adobe's developer tooling can record action commands/notifications to actionJSON files. This is the correct capture source for layer operations, tool changes, filters, and adjustments when the descriptor includes values.

Photoshop state reads can use `get` and `multiGet` descriptors through `batchPlay`, including layer properties such as name, layerID, and opacity. Modifying Photoshop state should run inside `core.executeAsModal(...)`.

ExtendScript remains useful for legacy Action Manager descriptors through `executeAction`; for Goal 29 the preferred representation is still UXP-compatible actionJSON.

## Route Classification

- r1: tool changes when captured as action descriptors.
- r1: layer operations when captured as action descriptors.
- r1: filters and adjustments only when every parameter used by replay is captured numerically.
- r3: brush strokes by design. Timing, movement, and pressure are taste evidence and are replayed as gesture strokes.
- gap: third-party plugin dialogs or filter dialogs that do not expose numeric descriptor values.

## Integrity Rule

If a filter or adjustment value is missing, unreadable, approximate, or non-numeric, capture must fail. A filter dialog value cannot be guessed from pixels or UI labels and still be called r1.

## File-Level Status

Implemented as `engine/photoshop_adapter.py` with fake-runtime tests. Real PASS still requires a Photoshop UXP/ExtendScript capture install, a layered edit recording, replay proof against layer stack/filter values, a 20-run soak at >=95%, and 3 real demo vaults.
