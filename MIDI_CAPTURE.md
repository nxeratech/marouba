# MIDI Capture

Marouba currently captures Ableton computer-keyboard-as-MIDI input when Ableton Live is the focused window and the user is not typing into the browser search field.

Captured note events are saved in the vault as human-readable entries:

```json
{
  "kind": "note_on",
  "event_type": "note_on",
  "key": "z",
  "note": "C3",
  "velocity": 100,
  "semantic": "midi_note:C3"
}
```

Replay sends the recorded key down/up events back to Ableton with the original timestamp spacing.

Raw physical MIDI device capture is not implemented in this pass. It should be added as a dedicated Windows MIDI input layer so note pitch, velocity, channel, and timing can be captured without affecting other apps.
