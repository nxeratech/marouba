---
app: Photoshop
app_version: latest
platform: windows
api_base: null
endpoints: {}
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

Photoshop automation is usually fastest through JSX scripts. UIA and shortcuts cover export dialogs when scripting is unavailable.
