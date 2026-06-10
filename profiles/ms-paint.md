---
app_name: MS Paint
title_fragment: Paint
adapter: ms-paint
tier: T3
mechanism: null-adapter + gesture
ui_density: medium
coordinate_tolerance_px: 6
supported_routes:
  toolbar_click:
    - gesture
    - ask
  canvas_stroke:
    - gesture
    - ask
  shape_drag:
    - gesture
    - ask
  fill_click:
    - gesture
    - ask
  double_click:
    - gesture
    - ask
  drag_to_target:
    - gesture
    - ask
  text_input:
    - gesture
    - ask
  keyboard_shortcut:
    - gesture
    - ask
  parameter_drag:
    - gesture
    - ask
  midi_note_entry:
    - ask
  browser_scroll:
    - gesture
    - ask
  focus_change:
    - gesture
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

MS Paint is the Marouba T3 null adapter reference. It intentionally resolves
through the formal adapter path to gesture replay only: canvas strokes, shape
drags, toolbar clicks, and fill clicks remain timing- and coordinate-faithful.