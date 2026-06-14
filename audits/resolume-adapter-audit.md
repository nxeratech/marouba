# Goal 25 Resolume Adapter Audit

Date: 2026-06-14

## Existing Bridge Surface

Ableton's current OSC bridge is implemented in `companion/src-tauri/src/ableton_bridge.rs` and includes app-independent OSC packet encoding/decoding ideas: padded OSC strings, type tags, UDP send/receive, and decoded address/argument pairs.

Goal 25 requires this not to be duplicated for Resolume. The file-level implementation therefore introduces `engine/osc_transport.py` as a shared OSC UDP transport and makes the Resolume adapter depend on it. Resolume-specific code only maps semantic events to OSC addresses and exact values.

## Resolume r1 Boundary

Resolume exposes clips, layers, effects, and composition parameters through native OSC when OSC input/output are enabled. Marouba stores:

- OSC address
- exact typed argument list
- semantic classification: clip trigger, layer parameter, effect parameter, or composition parameter

Replay sends the exact OSC messages through the shared transport.

## Declared Gap

Machine PASS must validate Dave's local Resolume OSC address map from Resolume's OSC preferences/shortcuts. If a touched OSC-exposed parameter value cannot be recorded exactly, capture must fail rather than approximate.

## Remaining Machine Proof

The committed tests use a fake OSC client so CI can verify the adapter contract without Resolume running. Full PASS still requires Dave's machine:

- record a VJ clip-trigger plus effect session
- confirm r1 events contain exact OSC addresses and values
- replay into a fresh composition
- verify visible/audio result and OSC hash
- run 20 cold replays with at least 95 percent success
