---
app: Premiere Pro
app_version: latest
platform: windows
api_base: Premiere Pro UXP / ExtendScript scripting API
endpoints:
  sequence: app.project.sequences
  track_item: sequence.videoTracks[index].clips[index]
  component_param: trackItem.components[index].properties[index]
uia_window_title: Adobe Premiere Pro
uia_elements:
  timeline: Timeline
  effects_controls: Effect Controls
  project_panel: Project
shortcuts:
  save: [ctrl, s]
  razor: [c]
  selection: [v]
cli_commands:
  jsx: "Premiere Pro.exe -r {script_path}"
install_paths:
  - C:\Program Files\Adobe\Adobe Premiere Pro 2026\Adobe Premiere Pro.exe
  - C:\Program Files\Adobe\Adobe Premiere Pro 2025\Adobe Premiere Pro.exe
output_folder: C:\Users\Dave\Videos\Marouba\Premiere
---

# Premiere Pro Profile

Premiere semantic replay uses timeline, TrackItem, and ComponentParam evidence. UIA is only a fallback for surfaces the API cannot expose.
