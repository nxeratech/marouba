---
app: Fusion 360
app_version: latest
platform: windows
api_base: Autodesk Fusion 360 Python API
endpoints:
  design: adsk.fusion.Design
  timeline: Design.timeline
  sketches: rootComponent.sketches
  extrude_features: rootComponent.features.extrudeFeatures
  fillet_features: rootComponent.features.filletFeatures
uia_window_title: Fusion 360
uia_elements:
  browser: Browser
  timeline: Timeline
  canvas: Canvas
shortcuts:
  save: [ctrl, s]
  sketch: [s]
  extrude: [e]
cli_commands:
  script: "Fusion360.exe --exec {script_path}"
install_paths:
  - C:\Users\Dave\AppData\Local\Autodesk\webdeploy\production\Fusion360.exe
output_folder: C:\Users\Dave\Documents\Marouba\Fusion360
---

# Fusion 360 Profile

Fusion capture mirrors the design history timeline into the vault. Timeline order and feature parameters are part of the proof.
