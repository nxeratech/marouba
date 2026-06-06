---
app: ComfyUI
app_version: latest
platform: windows
default_port: 8188
api_base: http://127.0.0.1:8188
endpoints:
  queue_prompt: /prompt
  get_history: /history/{prompt_id}
  get_queue: /queue
  interrupt: /interrupt
  system_stats: /system_stats
  object_info: /object_info
  upload_image: /upload/image
  view: /view
uia_window_title: ComfyUI
uia_elements:
  queue_prompt_button: Queue Prompt
  clear_button: Clear
  load_button: Load
  save_button: Save
shortcuts:
  queue_prompt: [ctrl, enter]
  save_workflow: [ctrl, s]
  load_workflow: [ctrl, o]
cli_commands:
  queue_prompt: "python scripts/replay.py --workflow {workflow} --params {params}"
install_paths:
  - C:\Users\Dave\AppData\Local\Programs\ComfyUI
  - C:\Users\Dave\Documents\ComfyUI
output_folder: C:\Users\Dave\AppData\Local\Programs\ComfyUI\output
---

# ComfyUI Profile

ComfyUI is best controlled through its local HTTP API. UIA and shortcut routes are kept as desktop fallbacks for users who run custom frontends or patched builds.
