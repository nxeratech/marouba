---
app: DaVinci Resolve
app_version: latest
platform: windows
api_base: python
endpoints:
  scripting_api: DaVinciResolveScript.scriptapp("Resolve")
  timeline_api: Project.GetCurrentTimeline
  media_pool_api: Project.GetMediaPool
uia_window_title: DaVinci Resolve
uia_elements:
  color_page: Color
  edit_page: Edit
  deliver_page: Deliver
shortcuts:
  color_page: [shift, "6"]
  edit_page: [shift, "4"]
  save_project: [ctrl, s]
cli_commands:
  script: "python {script_path}"
install_paths:
  - C:\Program Files\Blackmagic Design\DaVinci Resolve\Resolve.exe
developer_docs:
  - C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting\README.txt
output_folder: C:\Users\Dave\Videos\Marouba\Resolve
---

# DaVinci Resolve Profile

DaVinci Resolve is a T1/T2 hybrid. Timeline and media pool operations are replayed through the Python scripting API. Grade replay is r1 only when exact values are captured from API-supported CDL, LUT, node enable/cache state, or DRX still payloads. UI gestures are repair/fallback evidence for gaps and never stand in for grade values.
