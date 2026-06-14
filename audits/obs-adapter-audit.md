# Goal 24 OBS Studio Adapter Audit

Date: 2026-06-14

## API Source

The obs-websocket 5.x protocol documents a JSON websocket RPC with request/response and batch request support. The protocol exposes request families for scenes, inputs, transitions, filters, scene items, outputs, media inputs, and UI.

Goal 24 r1 coverage maps to these obs-websocket requests:

- scenes: `GetSceneList`, `CreateScene`, `SetCurrentProgramScene`
- sources/inputs: `GetInputList`, `CreateInput`, `GetInputSettings`, `SetInputSettings`
- filters: `GetSourceFilterList`, `CreateSourceFilter`, `SetSourceFilterSettings`, `SetSourceFilterEnabled`
- transitions: `GetCurrentSceneTransition`, `SetCurrentSceneTransition`, `SetCurrentSceneTransitionDuration`, `SetCurrentSceneTransitionSettings`
- audio: `GetInputVolume`, `SetInputVolume`, `GetInputMute`, `SetInputMute`
- scene items: `GetSceneItemList`, `SetSceneItemTransform`, `SetSceneItemEnabled`

Reference used: `https://raw.githubusercontent.com/obsproject/obs-websocket/master/docs/generated/protocol.md`

## r1 Boundary

OBS collection reconstruction is r1 when driven by obs-websocket state. If obs-websocket returns a filter and its `filterSettings`, Marouba must capture and replay those exact settings. Missing exposed filter settings are a hard failure, not an approximation gap.

## Remaining Machine Proof

The committed tests use a fake obs-websocket client so CI can verify the adapter contract without OBS running. Full PASS still requires Dave's OBS machine:

- record a scene/filter setup session
- replay into a clean OBS profile/scene collection
- compare collection hash
- run 20 cold replays with at least 95 percent success
