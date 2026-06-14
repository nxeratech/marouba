---
app: Resolume
app_version: latest
platform: windows
api_base: osc
endpoints:
  osc_input: udp://127.0.0.1:7000
  osc_output: udp://127.0.0.1:7001
uia_window_title: Resolume
uia_elements:
  composition: Composition
  layers: Layers
  clips: Clips
shortcuts:
  trigger_selected_clip: [enter]
  bpm_tap: [space]
cli_commands:
  launch: "Resolume Arena.exe"
install_paths:
  - C:\Program Files\Resolume Arena\Arena.exe
  - C:\Program Files\Resolume Avenue\Avenue.exe
output_folder: C:\Users\Dave\Videos\Marouba\Resolume
---

# Resolume Profile

Resolume is a T1 OSC adapter when OSC input/output are enabled. Marouba records exact OSC addresses and values for clips, layers, effects, and composition parameters, then replays through the same shared OSC UDP transport used for OSC-capable adapters. UI gestures are not part of the r1 route.
