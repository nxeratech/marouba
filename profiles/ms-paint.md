---
app_name: MS Paint
title_fragment: Paint
ui_density: medium
coordinate_tolerance_px: 6
supported_routes:
  toolbar_click:
    - uia
    - gesture
    - visual
    - ask
  canvas_stroke:
    - gesture
    - visual
    - ask
  shape_drag:
    - gesture
    - visual
    - ask
  fill_click:
    - gesture
    - uia
    - visual
    - ask
  double_click:
    - gesture
    - uia
    - ask
  drag_to_target:
    - gesture
    - visual
    - ask
  text_input:
    - shortcut
    - gesture
    - ask
  keyboard_shortcut:
    - shortcut
    - gesture
    - ask
  parameter_drag:
    - gesture
    - visual
    - ask
  midi_note_entry:
    - ask
  browser_scroll:
    - gesture
    - ask
  focus_change:
    - uia
    - shortcut
    - ask
  mouse_move_idle:
    - gesture
known_shortcuts:
  new_file: Ctrl+N
  open_file: Ctrl+O
  save_file: Ctrl+S
  undo: Ctrl+Z
  redo: Ctrl+Y
  select_all: Ctrl+A
  copy: Ctrl+C
  paste: Ctrl+V
---

# MS Paint Profile

MS Paint supports UIA for named ribbon controls and gesture replay for canvas actions.
Canvas strokes, shape drags, and fill clicks should remain gesture-first because the
creative motion is the workflow.
