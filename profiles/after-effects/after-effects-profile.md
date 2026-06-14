---
app: After Effects
app_version: latest
platform: windows
api_base: After Effects ExtendScript scripting API
endpoints:
  comp: app.project.items
  layer: comp.layers
  property: layer.property(...)
  expression: property.expression
uia_window_title: Adobe After Effects
uia_elements:
  timeline: Timeline
  effects_controls: Effect Controls
  project_panel: Project
shortcuts:
  save: [ctrl, s]
  reveal_expression: [e, e]
  reveal_keyframes: [u]
cli_commands:
  jsx: "AfterFX.exe -r {script_path}"
install_paths:
  - C:\Program Files\Adobe\Adobe After Effects 2026\Support Files\AfterFX.exe
  - C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\AfterFX.exe
output_folder: C:\Users\Dave\Videos\Marouba\AfterEffects
---

# After Effects Profile

After Effects semantic replay uses comp, layer, effect, property, keyframe, and expression evidence from ExtendScript.
