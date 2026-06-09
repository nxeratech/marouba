---
app_name: Notepad++
title_fragment: Notepad++
ui_density: low
coordinate_tolerance_px: 10
supported_routes:
  toolbar_click:
    - uia
    - shortcut
    - gesture
    - ask
  canvas_stroke:
    - ask
  shape_drag:
    - ask
  fill_click:
    - ask
  double_click:
    - gesture
    - uia
    - ask
  drag_to_target:
    - gesture
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
  save_as: Ctrl+Alt+S
  undo: Ctrl+Z
  redo: Ctrl+Y
  find: Ctrl+F
  replace: Ctrl+H
  select_all: Ctrl+A
  copy: Ctrl+C
  paste: Ctrl+V
---

# Notepad++ Profile

Notepad++ is text-first. Text input and keyboard shortcuts should be preferred over
coordinate replay whenever possible; gestures are mainly fallback for focus and UI
selection.
