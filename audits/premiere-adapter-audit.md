# Premiere Pro Adapter Audit

Date: 2026-06-14

Premiere Pro exposes scripting surfaces for sequences, track items, components, and component parameters. The current Adobe developer page says Premiere Pro extensibility is moving to UXP for Premiere v25.6 and beyond, while the Premiere Pro scripting guide documents the ExtendScript object model.

Relevant r1 surfaces:

- `Sequence.videoTracks` / `Sequence.audioTracks` for timeline structure.
- `TrackItem.start`, `end`, `inPoint`, `outPoint`, `name`, `mediaType`, `components`, and `move(...)` for clip placement and edits.
- `ComponentParam.getValue()`, `setValue(...)`, `getKeys()`, `getValueAtKey(...)`, `setValueAtKey(...)`, `setTimeVarying(...)`, and interpolation methods for effect parameter values and keyframes.

Integrity rule: Premiere effect params and keyframe values are r1 only when read from the API as exact values. Approximate, unreadable, or UI-label-only values are refused.

File-level status: implemented with fake-runtime tests in `engine/premiere_adapter.py`. Real PASS still requires a Premiere capture plugin/script, recorded timeline/effect session, replay proof against timeline state, 20-run soak at >=95%, and 3 real demo vaults.
