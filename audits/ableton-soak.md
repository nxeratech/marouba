# Ableton Goal-15 Soak Plan

Date prepared: 2026-06-12
Status: Prepared only. Do not run until Dave declares the machine free.
Candidate workflow: `ablebass2`

## Goal

Run a 20-run cold-launch soak against the proven multi-route Ableton vault and record whether the Ableton adapter is stable enough for the next shipping gate.

## Candidate Vault

Use `ablebass2` from the local vault:

- Workflow: `C:\Users\Dave\AppData\Local\Marouba\vault\workflows\ablebass2.md`
- Steps: `C:\Users\Dave\AppData\Local\Marouba\vault\workflows\ablebass2.steps.md`
- Captured events: 344
- Compiled steps: 83
- Step mix:
  - `load_device`: 1
  - `play_midi_note`: 29
  - `set_parameter`: 13
  - `legacy_gesture_sequence`: 40
- Route mix:
  - `api`: 43
  - `gesture`: 54
  - `shortcut`: 29
  - `uia`: 13

Reason: `ablebass2` exercises the adapter across device load, LOM parameter routes, MIDI note routes, shortcuts, UIA value routes, and gesture fallbacks. It is a better soak candidate than a narrow drag fixture.

## Harness Plan

Run 20 iterations. Each iteration must start from a cold Ableton launch.

Per iteration:

1. Ensure no stale Ableton or Marouba companion process is carrying replay state.
2. Launch Ableton through Marouba replay.
3. Wait for `execute-v3` bridge readiness.
4. Replay `ablebass2`.
5. Save the run log from `C:\Users\Dave\AppData\Local\Marouba\vault\runs`.
6. Record route counts, failed route reasons, replayed step count, and final status.
7. Close Ableton before the next iteration.

## Success Criteria

Pass criteria:

- 20 runs completed.
- At least 95% of expected steps replay successfully across the full soak.
- Zero `r4` repair routes.
- No blind gesture fallback for API-primary steps.
- No unhandled bridge readiness failures.
- No repeated failure signature across more than one run without a classified cause.

Failure criteria:

- Any `r4` repair route.
- Any API-primary `load_device` or `load_sample` step falling back blindly.
- More than one cold-launch bridge readiness timeout.
- Overall step success below 95%.

## Declared Scope Limits

These are honest adapter limits, not soak failures:

- Simpler sample loads remain `capture_gap` until a dedicated safe sample loader exists.
- Filename-only sample payloads remain `capture_gap` unless an absolute path is captured or resolved with confidence.
- Browser/plugin/device UI gestures remain gesture or repair territory when not represented by LOM.

## Pre-Soak Note

`dragtest7` cold replay take two was visually confirmed by Dave: audio track created at the recorded index and the sample clip appeared in slot 0 with waveform loaded. The saved run log still reported a verifier failure:

```json
{
  "routes": [
    {
      "route": "gesture",
      "step": "step_001"
    },
    {
      "failed_route": "api",
      "reason": "audio clip outcome verification failed: clip sample/name mismatch",
      "route": "repair",
      "step": "step_002"
    }
  ],
  "status": "failed",
  "timestamp_ms": 1781272071676,
  "workflow": "dragtest7"
}
```

Treat this as a verifier/reporting follow-up, not as a `load_sample` route absence. The route executed far enough to create the observed track and clip.

## Report Template

| Run | Start mode | Status | Replayed steps | Step success % | r4 count | API failures | Notes |
|---|---|---:|---:|---:|---:|---|---|
| 01 | cold launch | pending |  |  |  |  |  |
| 02 | cold launch | pending |  |  |  |  |  |
| 03 | cold launch | pending |  |  |  |  |  |
| 04 | cold launch | pending |  |  |  |  |  |
| 05 | cold launch | pending |  |  |  |  |  |
| 06 | cold launch | pending |  |  |  |  |  |
| 07 | cold launch | pending |  |  |  |  |  |
| 08 | cold launch | pending |  |  |  |  |  |
| 09 | cold launch | pending |  |  |  |  |  |
| 10 | cold launch | pending |  |  |  |  |  |
| 11 | cold launch | pending |  |  |  |  |  |
| 12 | cold launch | pending |  |  |  |  |  |
| 13 | cold launch | pending |  |  |  |  |  |
| 14 | cold launch | pending |  |  |  |  |  |
| 15 | cold launch | pending |  |  |  |  |  |
| 16 | cold launch | pending |  |  |  |  |  |
| 17 | cold launch | pending |  |  |  |  |  |
| 18 | cold launch | pending |  |  |  |  |  |
| 19 | cold launch | pending |  |  |  |  |  |
| 20 | cold launch | pending |  |  |  |  |  |

