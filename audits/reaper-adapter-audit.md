# Goal 27 REAPER Adapter Audit

Date: 2026-06-14

## API Sources

REAPER ReaScript supports EEL2, Lua, and Python scripts. The official ReaScript page states scripts can call REAPER actions and most REAPER API functions. The generated API documentation includes the relevant functions for this adapter:

- `Main_OnCommand(actionID, 0)` for actions.
- `InsertTrackAtIndex(...)` / `InsertTrackInProject(...)` for track creation.
- `AddMediaItemToTrack(...)` and media item setters for arrange items.
- `TrackFX_GetParam(...)`, `TrackFX_GetParamNormalized(...)`, and `TrackFX_SetParam(...)` for exact FX parameter reads/writes.
- `InsertEnvelopePoint(...)` and `Envelope_SortPoints(...)` for automation.

Sources: [REAPER ReaScript](https://www.reaper.fm/sdk/reascript/reascript.php) and [ReaScript API generated docs](https://www.reaper.fm/sdk/reascript/reascripthelp.html).

## r1 Boundary

r1 capture stores:

- action IDs invoked
- track index/name/volume/pan
- media item position/length/source metadata
- FX name/index plus exact parameter index/name/value/min/max
- envelope name plus exact point time/value/shape/tension

## Declared Failures

FX parameters are never guessed. If ReaScript exposes a parameter but the capture cannot read its value, the event is a hard failure.

## Remaining Machine Proof

The committed tests use a fake ReaScript runtime so CI can verify the adapter contract without launching REAPER. Full PASS still requires Dave's machine:

- record a real arrange+mix session
- confirm action/item/FX/envelope events are r1 and exact
- replay into a fresh project
- compare project hash
- run 20 cold replays with at least 95 percent success
