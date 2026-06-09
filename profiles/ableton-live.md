---
app_name: Ableton Live
title_fragment: Ableton Live
ui_density: high
coordinate_tolerance_px: 3
supported_routes:
  toolbar_click:
    - uia
    - shortcut
    - gesture
    - visual
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
    - uia
    - gesture
    - ask
  drag_to_target:
    - app_script
    - uia
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
    - app_script
    - uia
    - gesture
    - visual
    - ask
  midi_note_entry:
    - app_script
    - uia
    - gesture
    - ask
  browser_scroll:
    - uia
    - gesture
    - visual
    - ask
  focus_change:
    - uia
    - shortcut
    - ask
  mouse_move_idle:
    - gesture
known_shortcuts:
  new_live_set: Ctrl+N
  open_live_set: Ctrl+O
  save_live_set: Ctrl+S
  insert_midi_track: Ctrl+Shift+T
  insert_audio_track: Ctrl+T
  duplicate: Ctrl+D
  group_tracks: Ctrl+G
  play_stop: Space
  search_browser: Ctrl+F
  undo: Ctrl+Z
  redo: Ctrl+Y
---

# Ableton Live Profile

Ableton Live is a dense creative UI. Prefer semantic routes where available for
browser search, device parameters, and MIDI note entry. Gesture replay remains
available, but coordinate tolerance is intentionally tight.
