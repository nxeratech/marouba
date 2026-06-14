# ComfyUI Adapter Audit

Goal: ComfyUI must be a T1/r1 adapter, not a browser-pixel workflow.

## Existing Surface

- Profile declares `adapter: comfyui` and `mechanism: http-api + websocket`.
- Existing replay already supports ComfyUI `/prompt` submission with parameter substitution through payload templates.
- Existing API smoke script uses `/prompt`, `/history/{prompt_id}`, `/queue`, `/view`, and `/system_stats`.

## Adapter Decision

- Capture source: workflow graph JSON plus websocket queue events.
- Replay source: exact workflow graph JSON submitted to `/prompt`.
- Taste signal: repeated queue/requeue events are recorded as `queue_requeue` with `taste_signal: true`.
- Forbidden path: no capture or replay dependency on browser pixels, screenshots, or visual button matching.

## Current Verification

- `tests/test_comfyui_adapter.py` proves a 10-edit graph/session produces node-level r1 events.
- Replay test proves exact graph submission with param slots.
- Fake 20-run soak proves 20/20 adapter submissions via injected ComfyUI client.

## Machine-Dependent Remaining Work

The real PASS line still requires Dave's ComfyUI instance:

- Record a real 10-edit ComfyUI session.
- Replay the captured graph on fresh ComfyUI start.
- Run a real 20-run soak against the local ComfyUI API/websocket.

The adapter code is ready for that machine validation; it does not use browser pixels.
