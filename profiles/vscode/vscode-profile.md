---
app: VS Code
app_version: latest
platform: windows
api_base: extension-api
endpoints:
  extension_api: vscode.*
  edit_capture: workspace.onDidChangeTextDocument
  command_replay: commands.executeCommand
  workspace_edit: workspace.applyEdit
uia_window_title: Visual Studio Code
uia_elements:
  explorer: Explorer
  editor: Editor
  terminal: Terminal
shortcuts:
  command_palette: [ctrl, shift, p]
  save_file: [ctrl, s]
cli_commands:
  launch: "code ."
install_paths:
  - C:\Users\Dave\AppData\Local\Programs\Microsoft VS Code\Code.exe
output_folder: C:\Users\Dave\Documents\Marouba\VSCode
---

# VS Code Profile

VS Code is a T1 adapter through a local Marouba extension. The extension records text edits, command identifiers/arguments, and terminal command usage locally. It must not require telemetry, network, authentication, or remote services. UIA is a strong r2 fallback for editor chrome only.
