---
app: Photoshop
app_version: latest
platform: windows
api_base: Photoshop UXP action module / ExtendScript Action Manager
endpoints:
  uxp_batch_play: require('photoshop').action.batchPlay
  uxp_event_listener: require('photoshop').action.addNotificationListener
  uxp_modal: require('photoshop').core.executeAsModal
  extendscript_execute_action: executeAction
uia_window_title: Adobe Photoshop
uia_elements:
  file_menu: File
  export_menu: Export
  save_for_web: Save for Web (Legacy)
  image_size: Image Size
  batch_dialog: Batch
shortcuts:
  save_for_web: [ctrl, alt, shift, s]
  image_size: [ctrl, alt, i]
  save: [ctrl, s]
cli_commands:
  jsx: "photoshop.exe -r {script_path}"
  droplet: "{droplet_path} {input_path}"
install_paths:
  - C:\Program Files\Adobe\Adobe Photoshop 2025\Photoshop.exe
  - C:\Program Files\Adobe\Adobe Photoshop 2024\Photoshop.exe
output_folder: C:\Users\Dave\Pictures\Marouba\Photoshop
---

# Photoshop Profile

Photoshop semantic capture prefers UXP action notifications and actionJSON descriptors. Layer operations, tool changes, filters, and adjustments are r1 only when the descriptor contains exact values; brush strokes stay r3 gesture evidence because timing and movement are part of the taste signal.
