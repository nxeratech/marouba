---
app: REAPER
app_version: latest
platform: windows
api_base: reascript
endpoints:
  lua: reaper.*
  python: RPR_*
uia_window_title: REAPER
uia_elements:
  arrange: Track View
  mixer: Mixer
  actions: Actions
shortcuts:
  action_list: ["?"]
  save_project: [ctrl, s]
cli_commands:
  launch: "reaper.exe"
install_paths:
  - C:\Program Files\REAPER (x64)\reaper.exe
output_folder: C:\Users\Dave\Documents\Marouba\REAPER
---

# REAPER Profile

REAPER is a T1 ReaScript adapter. Actions, tracks, media items, FX chains, FX parameter values, and envelope points are captured and replayed through Lua/Python ReaScript APIs. UI gestures are fallback only and cannot satisfy FX parameter capture.
