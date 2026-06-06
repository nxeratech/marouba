---
app: Blender
app_version: latest
platform: windows
api_base: python
endpoints:
  python_api: bpy
  background_render: blender --background
uia_window_title: Blender
uia_elements:
  render_menu: Render
  render_image: Render Image
  export_menu: Export
  fbx_export: FBX
shortcuts:
  render_still: [f12]
  save_file: [ctrl, s]
  search: [f3]
cli_commands:
  background_render: "blender --background {blend_path} --render-output {output_path} --render-frame {frame}"
  export_fbx: "blender --background {blend_path} --python scripts/blender_export_fbx.py -- {output_path}"
install_paths:
  - C:\Program Files\Blender Foundation\Blender 4.2\blender.exe
  - C:\Program Files\Blender Foundation\Blender 4.1\blender.exe
output_folder: C:\Users\Dave\Pictures\Marouba\Blender
---

# Blender Profile

Blender has strong CLI and Python APIs, so desktop routes are fallbacks for open interactive scenes.
