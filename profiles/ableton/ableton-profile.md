---
app: Ableton Live
app_version: latest
platform: windows
api_base: null
endpoints:
  max_for_live: local Live Object Model through Max for Live devices
uia_window_title: Ableton Live
uia_elements:
  file_menu: File
  export_audio_video: Export Audio/Video
  render_button: Render
  save_button: Save
shortcuts:
  export_audio_video: [ctrl, shift, r]
  save_live_set: [ctrl, s]
  show_browser: [ctrl, alt, b]
cli_commands:
  max_for_live_bridge: "python tools/ableton_bridge.py --action {action} --set {set_path}"
install_paths:
  - C:\ProgramData\Ableton\Live 12 Suite\Program\Ableton Live 12 Suite.exe
  - C:\ProgramData\Ableton\Live 11 Suite\Program\Ableton Live 11 Suite.exe
output_folder: C:\Users\Dave\Music\Ableton\Exports
---

# Ableton Live Profile

Ableton is primarily desktop-driven. Phase 4 routes combine Max for Live bridge hooks, UIA menu paths, shortcuts, and visual fallbacks.
