# Goal 23 DaVinci Resolve Adapter Audit

Date: 2026-06-14

## Local API Source

Resolve's installed developer docs were found at:

`C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting\README.txt`

Relevant API entries in that local README include:

- `MediaPool.ImportMedia(...)`
- `MediaPool.AppendToTimeline(...)`
- `Timeline.AddTrack(...)`
- `Timeline.SetCurrentTimecode(...)`
- `TimelineItem.SetCDL(...)`
- `TimelineItem.GetNodeGraph(...)`
- `Graph.SetLUT(...)`
- `Graph.ApplyGradeFromDRX(...)`
- `GalleryStillAlbum.ExportStills(..., format=drx)`

## r1 Boundary

r1 evidence is limited to exact Resolve scripting API state:

- timeline/media pool operations
- timeline item properties and track placement
- exact CDL maps passed to `TimelineItem.SetCDL`
- LUT paths passed to `Graph.SetLUT`
- DRX grade payload paths exported/imported via still/gallery flows
- node enable/cache/label values where exposed by the API

## Declared Gaps

Arbitrary Color page grade node internals are not treated as exact unless Resolve exposes them through API values or a DRX/LUT/CDL payload. UI gestures can fill operational gaps as r2/r3 repair evidence, but they cannot satisfy the PASS criterion for grade values.

## Real PASS Gate

The committed tests use a fake Resolve scripting object so CI can verify the adapter contract without launching Resolve. Full PASS still requires Dave's machine:

- record a real edit+grade session
- confirm captured timeline and grade events are API-level
- replay into a fresh project
- compare project/timeline/grade hash
- run 20 cold replays with at least 95 percent success
