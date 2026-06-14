# AutoCAD Adapter Audit

Date: 2026-06-14

Goal: capture AutoCAD drawing sessions as command-level r1 events with exact coordinates and parameters, then replay through COM or AutoLISP and verify the resulting drawing entities.

## API Surface

Official Autodesk surfaces used for this design:

- ObjectARX/.NET document command events for command lifecycle capture. The intended bridge subscribes to document command events and records the command name plus command stream values.
- ActiveX/COM automation for replay through the active document, including command submission via the document command channel.
- AutoLISP replay through `(command ...)`, which is a natural representation of AutoCAD command names plus exact point/value arguments.
- Entity verification via the drawing database/entity list rather than screen pixels.

## Route Classification

- r1: command stream events with command name and every parameter captured.
- r1: coordinates, distances, angles, options, layer names, radii, and text values when captured as exact command parameters.
- gap: command names without parameter payload.
- r2/r3: UIA/gesture may help with focus or non-scriptable UI surfaces, but cannot satisfy this goal's r1 command evidence.

## Integrity Rule

Commands captured without parameters fail capture. A command name alone does not prove the drawing operation and cannot be promoted to r1.

## File-Level Status

Implemented as `engine/autocad_adapter.py` with fake-runtime tests. Real PASS still requires an AutoCAD .NET/COM capture bridge, a recorded drawing session, replay proof by comparing DWG entities, 20-run soak at >=95%, and 3 real demo vaults.
