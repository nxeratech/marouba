---
app: OBS Studio
app_version: latest
platform: windows
api_base: obs-websocket
endpoints:
  websocket: ws://127.0.0.1:4455
uia_window_title: OBS
uia_elements:
  scenes: Scenes
  sources: Sources
  filters: Filters
shortcuts:
  start_recording: [ctrl, r]
  studio_mode: [ctrl, shift, s]
cli_commands:
  launch: "obs64.exe"
install_paths:
  - C:\Program Files\obs-studio\bin\64bit\obs64.exe
output_folder: C:\Users\Dave\Videos\Marouba\OBS
---

# OBS Studio Profile

OBS Studio is a T1 adapter through obs-websocket 5.x. Scenes, inputs/sources, source settings, filters and filter settings, scene item transforms, transitions, and audio levels are captured and replayed as r1 API state. UI gestures are not needed for collection reconstruction.
