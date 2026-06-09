#![allow(dead_code)]

use crate::RecordedEvent;

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum EventType {
    ToolbarClick,
    CanvasStroke,
    ShapeDrag,
    FillClick,
    DoubleClick,
    DragToTarget,
    TextInput,
    KeyboardShortcut,
    ParameterDrag,
    MidiNoteEntry,
    BrowserScroll,
    FocusChange,
    MouseMoveIdle,
    Unknown,
}

pub fn classify_event(events: &[RecordedEvent], index: usize) -> EventType {
    let Some(event) = events.get(index) else {
        return EventType::Unknown;
    };

    match event.kind.as_str() {
        "focus" => return EventType::FocusChange,
        "scroll" => return EventType::BrowserScroll,
        "mousemove" => return EventType::MouseMoveIdle,
        "keydown" | "keyup" => {
            return if keyboard_shortcut_context(events, index) {
                EventType::KeyboardShortcut
            } else {
                EventType::TextInput
            };
        }
        "mousedown" => {}
        _ => return EventType::Unknown,
    }

    if is_double_click(events, index) {
        return EventType::DoubleClick;
    }

    let name = lower_name(event);
    if is_midi_note_name(&name) {
        return EventType::MidiNoteEntry;
    }
    if is_parameter_name(&name) {
        return EventType::ParameterDrag;
    }
    if is_fill_name(&name) {
        return EventType::FillClick;
    }

    let Some((up_index, move_count, distance, duration_ms)) = mouse_segment(events, index) else {
        return EventType::Unknown;
    };
    let up = &events[up_index];

    if is_midi_note_name(&lower_name(up)) {
        return EventType::MidiNoteEntry;
    }
    if is_parameter_name(&lower_name(up)) {
        return EventType::ParameterDrag;
    }

    if is_canvas_name(&name) {
        if move_count >= 8 && distance >= 0.08 {
            return EventType::ShapeDrag;
        }
        if move_count >= 8 || duration_ms >= 500 {
            return EventType::CanvasStroke;
        }
        return EventType::FillClick;
    }

    if is_browser_or_file_drag(&name) || (move_count >= 8 && distance >= 0.08) {
        return EventType::DragToTarget;
    }

    if move_count == 0 && distance <= 0.006 {
        return EventType::ToolbarClick;
    }

    if move_count >= 1 && distance <= 0.04 && !name.is_empty() {
        return EventType::ToolbarClick;
    }

    EventType::Unknown
}

fn mouse_segment(events: &[RecordedEvent], index: usize) -> Option<(usize, usize, f64, u128)> {
    let down = events.get(index)?;
    if down.kind != "mousedown" {
        return None;
    }
    let mut move_count = 0usize;
    for cursor in index + 1..events.len() {
        let event = &events[cursor];
        match event.kind.as_str() {
            "mousemove" => move_count += 1,
            "mouseup" => {
                let distance = normalized_distance(down, event).unwrap_or(0.0);
                let duration_ms = event.timestamp_ms.saturating_sub(down.timestamp_ms);
                return Some((cursor, move_count, distance, duration_ms));
            }
            "mousedown" => return None,
            _ => {}
        }
    }
    None
}

fn is_double_click(events: &[RecordedEvent], index: usize) -> bool {
    let Some((first_up, first_moves, first_distance, _)) = mouse_segment(events, index) else {
        return false;
    };
    if first_moves > 1 || first_distance > 0.006 {
        return false;
    }
    let second_down_index = first_up + 1;
    let Some(second_down) = events.get(second_down_index) else {
        return false;
    };
    if second_down.kind != "mousedown" {
        return false;
    }
    let Some((_, second_moves, second_distance, _)) = mouse_segment(events, second_down_index)
    else {
        return false;
    };
    let gap_ms = second_down
        .timestamp_ms
        .saturating_sub(events[first_up].timestamp_ms);
    gap_ms <= 300
        && second_moves <= 1
        && second_distance <= 0.006
        && normalized_distance(&events[index], second_down)
            .map(|distance| distance <= 0.006)
            .unwrap_or(true)
}

fn keyboard_shortcut_context(events: &[RecordedEvent], index: usize) -> bool {
    let Some(event) = events.get(index) else {
        return false;
    };
    let key = event.key.as_deref().unwrap_or("");
    if is_modifier_key(key) {
        return false;
    }

    let start_ms = event.timestamp_ms.saturating_sub(750);
    events[..index].iter().rev().take(8).any(|previous| {
        previous.kind == "keydown"
            && previous.timestamp_ms >= start_ms
            && previous
                .key
                .as_deref()
                .map(is_modifier_key)
                .unwrap_or(false)
    })
}

fn normalized_distance(a: &RecordedEvent, b: &RecordedEvent) -> Option<f64> {
    let dx = b.normalized_x? - a.normalized_x?;
    let dy = b.normalized_y? - a.normalized_y?;
    Some((dx * dx + dy * dy).sqrt())
}

fn lower_name(event: &RecordedEvent) -> String {
    event
        .element_name
        .as_deref()
        .unwrap_or("")
        .trim()
        .to_ascii_lowercase()
}

fn is_modifier_key(key: &str) -> bool {
    matches!(
        key,
        "16" | "160" | "161" | "17" | "162" | "163" | "18" | "164" | "165"
    )
}

fn is_canvas_name(name: &str) -> bool {
    name.contains("canvas") || name.starts_with("using ")
}

fn is_fill_name(name: &str) -> bool {
    name.contains("fill") && name.contains("canvas")
}

fn is_midi_note_name(name: &str) -> bool {
    name.contains("untitled clip") && name.contains("track")
}

fn is_browser_or_file_drag(name: &str) -> bool {
    name.ends_with(".adv")
        || name.ends_with(".adg")
        || name.contains("browser")
        || name.contains("search")
        || name.contains("preset")
}

fn is_parameter_name(name: &str) -> bool {
    name.contains("frequency")
        || name.contains("resonance")
        || name.contains("gain")
        || name.contains("threshold")
        || name.contains("output")
        || name.contains("activator")
        || name.contains("limiter")
        || name.contains("compressor")
        || name.contains("eq")
        || name.contains("filter")
        || name.contains("fine frequency")
        || name.contains("reverb")
        || name.contains("delay")
}
