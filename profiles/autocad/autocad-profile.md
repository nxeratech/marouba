---
app: AutoCAD
app_version: latest
platform: windows
api_base: AutoCAD COM / .NET / AutoLISP
endpoints:
  dotnet_command_events: Document.CommandWillStart / CommandEnded bridge
  com_send_command: ActiveDocument.SendCommand
  autolisp_command: (command ...)
  entity_snapshot: ModelSpace entity enumeration
uia_window_title: AutoCAD
uia_elements:
  command_line: Command Line
  drawing_canvas: Drawing
  layer_panel: Layers
shortcuts:
  save: [ctrl, s]
  line: [l, enter]
  circle: [c, enter]
cli_commands:
  script: "acad.exe /b {script_path}"
  lisp: "acad.exe /ld {lisp_path}"
install_paths:
  - C:\Program Files\Autodesk\AutoCAD 2026\acad.exe
  - C:\Program Files\Autodesk\AutoCAD 2025\acad.exe
output_folder: C:\Users\Dave\Documents\Marouba\AutoCAD
---

# AutoCAD Profile

AutoCAD capture is command-stream first. Commands are r1 only when every coordinate and parameter is present in the vault.
