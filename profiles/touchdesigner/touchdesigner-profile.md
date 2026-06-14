---
app: TouchDesigner
app_version: latest
platform: windows
api_base: python + osc
endpoints:
  python_api: TouchDesigner embedded Python OP/COMP/Par classes
  osc_input: udp://127.0.0.1:7000
  osc_output: udp://127.0.0.1:7001
uia_window_title: TouchDesigner
uia_elements:
  network: Network Editor
  parameter_dialog: Parameters
shortcuts:
  pulse_cook: [f5]
  save_project: [ctrl, s]
cli_commands:
  launch: "TouchDesigner.exe"
install_paths:
  - C:\Program Files\Derivative\TouchDesigner\bin\TouchDesigner.exe
output_folder: C:\Users\Dave\Documents\Marouba\TouchDesigner
---

# TouchDesigner Profile

TouchDesigner is a T1 Python + OSC adapter. Network topology is captured through Python operator evidence: created OP type/name/path, parameter values, node placement, and connections. OSC messages are captured as exact address/argument events for live control, but replay cannot pass unless the network topology itself is present.
