# Fusion 360 Adapter Audit

Date: 2026-06-14

Goal: capture Fusion 360 parametric modeling sessions as feature-level timeline evidence, then replay through the Python API and verify the reconstructed design timeline/entities.

## API Surface

Fusion 360 exposes Python add-ins and scripts through the Autodesk `adsk.core` and `adsk.fusion` modules. The adapter design targets:

- `Design.timeline` as the primary decision record.
- Sketch collections, sketch curves, constraints, and dimensions for sketch features.
- Feature collections such as extrude and fillet features for parametric modeling operations.
- User parameters and feature parameter expressions for editable parametric state.
- Design/body/entity snapshots for verification after replay.

## Route Classification

- r1: feature timeline events with exact parameters and original order.
- r1: sketches, profiles, extrudes, fillets, and user parameters when captured through the Fusion API.
- gap: timeline entries with missing parameters, UI-only operations, or hidden feature values.

## Integrity Rule

Feature history cannot be approximated. Timeline order must match the design history exactly and indices must be contiguous from zero. Any approximate/unreadable feature value fails capture.

## File-Level Status

Implemented as `engine/fusion360_adapter.py` with fake-runtime tests. Real PASS still requires a Fusion 360 Python add-in, recorded parametric modeling session, replay proof by timeline/body/entity comparison, 20-run soak at >=95%, and 3 real demo vaults.
