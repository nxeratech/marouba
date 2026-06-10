use super::*;

#[cfg(target_os = "windows")]
pub(crate) fn replay_ableton_double_click_if_present(
    events: &[&RecordedEvent],
    start: usize,
    rect: Option<&WindowRect>,
) -> Option<usize> {
    let first_down = events.get(start).copied()?;
    if first_down.kind != "mousedown" || first_down.button.as_deref().unwrap_or("left") != "left" {
        return None;
    }
    if is_ableton_piano_roll_note_event(first_down) {
        return None;
    }
    let first_up_index = compact_click_mouseup_index(events, start)?;
    let second_down_index = first_up_index + 1;
    let second_down = events.get(second_down_index).copied()?;
    if second_down.kind != "mousedown"
        || second_down.button.as_deref().unwrap_or("left") != "left"
        || !is_ableton_event(second_down)
    {
        return None;
    }
    if is_ableton_piano_roll_note_event(second_down) {
        return None;
    }
    let second_up_index = compact_click_mouseup_index(events, second_down_index)?;
    let first_up = events[first_up_index];
    let second_up = events[second_up_index];
    if second_up.button.as_deref().unwrap_or("left") != "left" {
        return None;
    }
    let gap = second_down
        .timestamp_ms
        .checked_sub(first_up.timestamp_ms)
        .unwrap_or(u128::MAX);
    if gap > 300 {
        return None;
    }
    if normalized_distance(first_down, second_down)
        .map(|distance| distance > 0.006)
        .unwrap_or(false)
    {
        return None;
    }

    let (x1, y1) = resolve_ableton_replay_point(first_down, rect);
    let (x2, y2) = resolve_ableton_replay_point(second_down, rect);
    write_debug_log(&format!(
        "ableton double click: first=({x1},{y1}) second=({x2},{y2}) gap_ms={gap}"
    ));
    send_ableton_left_click(x1, y1, replay_event_delay(first_down, Some(first_up)));
    thread::sleep(replay_event_delay(first_up, Some(second_down)));
    send_ableton_left_click(x2, y2, replay_event_delay(second_down, Some(second_up)));
    Some(second_up_index)
}

#[cfg(target_os = "windows")]
pub(crate) fn replay_ableton_drag_if_present(
    events: &[&RecordedEvent],
    start: usize,
    rect: Option<&WindowRect>,
) -> Option<usize> {
    replay_ableton_drag_segment(events, start, rect, Duration::from_millis(30))
}

#[cfg(target_os = "windows")]
pub(crate) fn replay_ableton_drag_segment(
    events: &[&RecordedEvent],
    start: usize,
    rect: Option<&WindowRect>,
    final_hold: Duration,
) -> Option<usize> {
    let down = events.get(start).copied()?;
    if down.kind != "mousedown" || down.button.as_deref().unwrap_or("left") != "left" {
        return None;
    }
    let up_index = matching_mouseup_index(events, start)?;
    let up = events[up_index];
    let endpoint = last_mousemove_before_mouseup(events, start, up_index)?;
    if normalized_distance(down, endpoint)
        .map(|distance| distance < 0.015)
        .unwrap_or(false)
    {
        return None;
    }

    let note_grid_segment = is_ableton_piano_roll_note_event(down);
    let (down_x, down_y) =
        resolve_ableton_replay_point_with_note_context(down, rect, note_grid_segment);
    write_debug_log(&format!(
        "ableton drag segment: down_index={start} up_index={up_index} start=({down_x},{down_y})"
    ));
    if is_ableton_knob_or_eq_event(down) {
        thread::sleep(Duration::from_millis(150));
    }
    send_ableton_mousemove(down_x, down_y);
    thread::sleep(Duration::from_millis(20));
    send_ableton_leftdown(down_x, down_y);

    let mut previous = down;
    for event in events[start + 1..up_index].iter().copied() {
        if event.kind != "mousemove" {
            continue;
        }
        thread::sleep(replay_event_delay(previous, Some(event)));
        let (x, y) = resolve_ableton_replay_point_with_note_context(event, rect, note_grid_segment);
        send_ableton_mousemove(x, y);
        previous = event;
    }

    thread::sleep(replay_event_delay(previous, Some(up)));
    let (up_x, up_y) = resolve_ableton_replay_point_with_note_context(up, rect, note_grid_segment);
    send_ableton_mousemove(up_x, up_y);
    thread::sleep(final_hold);
    send_ableton_leftup(up_x, up_y);
    Some(up_index)
}

#[cfg(target_os = "windows")]
pub(crate) fn replay_ableton_instrument_drag_if_present(
    events: &[&RecordedEvent],
    start: usize,
    rect: Option<&WindowRect>,
) -> Option<usize> {
    let down = events.get(start).copied()?;
    let preset_name = ableton_preset_name(down)?;
    if !is_ableton_instrument_preset_name(&preset_name) {
        return None;
    }
    let up_index = matching_mouseup_index(events, start)?;
    let endpoint = last_mousemove_before_mouseup(events, start, up_index)?;
    if normalized_distance(down, endpoint)
        .map(|distance| distance < 0.015)
        .unwrap_or(false)
    {
        return None;
    }
    write_debug_log(&format!(
        "ableton instrument drag preflight: preset={preset_name:?} down_index={start} up_index={up_index}"
    ));

    let category = ableton_recorded_browser_category(events, start)
        .or_else(|| ableton_browser_category_for_preset(&preset_name).map(str::to_string));
    if let Some(category) = category.as_deref() {
        match click_uia_name_with_timeout(category, down.window_title.as_deref(), 500) {
            Ok(()) => {
                write_debug_log(&format!(
                    "ableton browser category selected before preset lookup: {category}"
                ));
                thread::sleep(Duration::from_millis(180));
            }
            Err(error) => write_debug_log(&format!(
                "ableton browser category selection skipped: category={category} error={error}"
            )),
        }
    }

    let _ = send_ableton_insert_midi_track();
    thread::sleep(Duration::from_millis(500));

    match locate_ableton_preset_with_scroll(&preset_name, down, rect) {
        Some((source_x, source_y)) => {
            let (source_x, source_y) = verify_ableton_browser_source_point(
                &preset_name,
                down.window_title.as_deref(),
                source_x,
                source_y,
            );
            write_debug_log(&format!(
                "ableton instrument located by name: preset={preset_name:?} source=({source_x},{source_y})"
            ));
            replay_ableton_drag_from_source(
                events,
                start,
                rect,
                source_x,
                source_y,
                Duration::from_millis(250),
            )
        }
        None => {
            write_debug_log(&format!(
                "ableton instrument name lookup failed; falling back to recorded coordinates: preset={preset_name:?}"
            ));
            replay_ableton_drag_segment(events, start, rect, Duration::from_millis(250))
        }
    }
}

#[cfg(target_os = "windows")]
pub(crate) fn replay_ableton_group_tracks_if_present(
    events: &[&RecordedEvent],
    start: usize,
    rect: Option<&WindowRect>,
) -> Option<usize> {
    let down = events.get(start).copied()?;
    if down.kind != "mousedown"
        || down.button.as_deref() != Some("right")
        || down.element_name.as_deref() != Some("Track Title Bar")
    {
        return None;
    }
    if !recent_ableton_shift_track_selection(events, start) {
        return None;
    }
    if !upcoming_ableton_search_text(events, start, "GLUE") {
        return None;
    }
    let up_index = matching_mouseup_index(events, start)?;
    write_debug_log(&format!(
        "ableton group repair: right-click Track Title Bar at index {start}; sending Ctrl+G"
    ));
    let _ = send_modified_key(VK_CONTROL, VIRTUAL_KEY(0x47));
    thread::sleep(Duration::from_millis(500));
    let (x, y) = resolve_ableton_replay_point(down, rect);
    write_debug_log(&format!(
        "ableton group repair: selecting new group track at ({x},{y})"
    ));
    send_ableton_left_click(x, y, Duration::from_millis(80));
    thread::sleep(Duration::from_millis(250));
    Some(up_index)
}

pub(crate) fn recent_ableton_shift_track_selection(
    events: &[&RecordedEvent],
    start: usize,
) -> bool {
    let begin = start.saturating_sub(16);
    let mut saw_shift = false;
    let mut saw_track_title_click = false;
    for event in &events[begin..start] {
        if event.kind == "keydown" && matches!(event.key.as_deref(), Some("16") | Some("160")) {
            saw_shift = true;
        }
        if event.kind == "mousedown"
            && event.button.as_deref().unwrap_or("left") == "left"
            && event
                .element_name
                .as_deref()
                .map(|name| {
                    name.eq_ignore_ascii_case("Track Title Bar")
                        || name.to_ascii_lowercase().contains("armed")
                })
                .unwrap_or(false)
        {
            saw_track_title_click = true;
        }
    }
    saw_shift && saw_track_title_click
}

pub(crate) fn upcoming_ableton_search_text(
    events: &[&RecordedEvent],
    start: usize,
    expected: &str,
) -> bool {
    let end = (start + 80).min(events.len());
    let mut saw_search = false;
    let mut typed = String::new();
    for event in &events[start + 1..end] {
        if event.kind == "mousedown" && event.element_name.as_deref() == Some("Search") {
            saw_search = true;
            continue;
        }
        if saw_search && event.kind == "keydown" {
            if let Some(key) = event
                .key
                .as_deref()
                .and_then(|value| value.parse::<u32>().ok())
            {
                if let Some(ch) = char::from_u32(key) {
                    if ch.is_ascii_alphabetic() {
                        typed.push(ch.to_ascii_uppercase());
                        if typed == expected {
                            return true;
                        }
                        if !expected.starts_with(&typed) {
                            return false;
                        }
                    }
                }
            }
        }
    }
    false
}

pub(crate) fn ableton_preset_name(event: &RecordedEvent) -> Option<String> {
    event
        .element_name
        .as_deref()
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .map(str::to_string)
}

pub(crate) fn is_ableton_instrument_preset_name(name: &str) -> bool {
    let lower = name.to_ascii_lowercase();
    lower.ends_with(".adv") || lower.ends_with(".adg")
}

pub(crate) fn ableton_browser_category_for_preset(name: &str) -> Option<&'static str> {
    if is_ableton_instrument_preset_name(name) {
        Some("Instruments")
    } else {
        None
    }
}

pub(crate) fn ableton_recorded_browser_category(
    events: &[&RecordedEvent],
    start: usize,
) -> Option<String> {
    let begin = start.saturating_sub(120);
    events[begin..start]
        .iter()
        .rev()
        .filter(|event| event.kind == "mousedown")
        .filter_map(|event| event.element_name.as_deref().map(str::trim))
        .find(|name| ableton_browser_category_name(name))
        .map(str::to_string)
}

pub(crate) fn ableton_browser_category_name(name: &str) -> bool {
    matches!(
        name,
        "Sounds"
            | "Drums"
            | "Instruments"
            | "Audio Effects"
            | "MIDI Effects"
            | "Max for Live"
            | "Plug-ins"
            | "Clips"
            | "Samples"
            | "Grooves"
            | "Templates"
    )
}

#[cfg(target_os = "windows")]
pub(crate) fn verify_ableton_browser_source_point(
    expected_name: &str,
    _window_title: Option<&str>,
    source_x: i32,
    source_y: i32,
) -> (i32, i32) {
    let mut point = (source_x, source_y);
    for attempt in 0..2 {
        send_ableton_left_click(point.0, point.1, Duration::from_millis(40));
        thread::sleep(Duration::from_millis(140));
        match uia_element_names_and_rect_at_point_with_timeout(point.0, point.1, 500) {
            Ok((names, rect)) => {
                if names
                    .iter()
                    .any(|name| ableton_browser_item_name_matches(expected_name, name))
                {
                    write_debug_log(&format!(
                        "ableton browser selection verified: expected={expected_name:?} names={names:?} point=({}, {})",
                        point.0, point.1
                    ));
                    return point;
                }
                write_debug_log(&format!(
                    "ableton browser selection mismatch attempt={attempt}: expected={expected_name:?} names={names:?} point=({}, {}) rect={}",
                    point.0,
                    point.1,
                    format_window_rect(Some(&rect))
                ));
                point = ableton_next_browser_row_point(point.0, &rect);
            }
            Err(error) => {
                write_debug_log(&format!(
                    "ableton browser selection verification unavailable for {expected_name:?}: {error}; using located point"
                ));
                return (source_x, source_y);
            }
        }
    }
    write_debug_log(&format!(
        "ableton browser selection not verified after retry: expected={expected_name:?}; using point=({}, {})",
        point.0, point.1
    ));
    point
}

pub(crate) fn ableton_browser_item_name_matches(expected: &str, actual: &str) -> bool {
    let expected = expected.trim();
    let actual = actual.trim();
    if expected.eq_ignore_ascii_case(actual) {
        return true;
    }
    browser_item_stem(expected).eq_ignore_ascii_case(&browser_item_stem(actual))
}

pub(crate) fn browser_item_stem(value: &str) -> String {
    let trimmed = value.trim();
    let lower = trimmed.to_ascii_lowercase();
    for suffix in [".adv", ".adg", ".amxd", ".vst3", ".dll"] {
        if lower.ends_with(suffix) {
            return trimmed[..trimmed.len() - suffix.len()].to_string();
        }
    }
    trimmed.to_string()
}

pub(crate) fn ableton_next_browser_row_point(x: i32, rect: &WindowRect) -> (i32, i32) {
    let row_height = rect.height.abs().max(1);
    (x, rect.top + (rect.height / 2) + row_height)
}

#[cfg(target_os = "windows")]
pub(crate) fn replay_ableton_device_drag_if_present(
    events: &[&RecordedEvent],
    start: usize,
    rect: Option<&WindowRect>,
    prior_devices: &[String],
) -> Option<(usize, String)> {
    let down = events.get(start).copied()?;
    let device_name = ableton_device_name(down)?;
    let up_index = matching_mouseup_index(events, start)?;
    let endpoint = last_mousemove_before_mouseup(events, start, up_index)?;
    if normalized_distance(down, endpoint)
        .map(|distance| distance < 0.015)
        .unwrap_or(false)
    {
        return None;
    }
    let category = ableton_recorded_browser_category(events, start)
        .or_else(|| ableton_browser_category_for_device(&device_name).map(str::to_string));
    let target_channel = matching_mouseup_index(events, start)
        .and_then(|up_index| ableton_target_channel_for_device_drag(down, events[up_index]));
    if let Some(channel) = target_channel.as_deref() {
        match click_uia_name_with_timeout(channel, down.window_title.as_deref(), 500) {
            Ok(()) => {
                write_debug_log(&format!(
                    "ableton device target channel focused before add: device={device_name:?} channel={channel:?}"
                ));
                thread::sleep(Duration::from_millis(180));
            }
            Err(error) => write_debug_log(&format!(
                "ableton device target channel focus skipped: device={device_name:?} channel={channel:?} error={error}"
            )),
        }
    }
    if let Some(category) = category.as_deref() {
        match click_uia_name_with_timeout(category, down.window_title.as_deref(), 500) {
            Ok(()) => {
                write_debug_log(&format!(
                    "ableton device category selected before lookup: {category}"
                ));
                thread::sleep(Duration::from_millis(180));
            }
            Err(error) => write_debug_log(&format!(
                "ableton device category selection skipped: category={category} error={error}"
            )),
        }
    }
    match locate_ableton_preset_with_scroll(&device_name, down, rect) {
        Some((source_x, source_y)) => {
            let (source_x, source_y) = verify_ableton_browser_source_point(
                &device_name,
                down.window_title.as_deref(),
                source_x,
                source_y,
            );
            write_debug_log(&format!(
                "ableton device located by name: device={device_name:?} source=({source_x},{source_y})"
            ));
            let up = replay_ableton_drag_from_source(
                events,
                start,
                rect,
                source_x,
                source_y,
                Duration::from_millis(450),
            )?;
            thread::sleep(Duration::from_millis(700));
            verify_ableton_devices_present(prior_devices, down.window_title.as_deref());
            verify_ableton_devices_present(
                std::slice::from_ref(&device_name),
                down.window_title.as_deref(),
            );
            Some((up, device_name))
        }
        None => {
            write_debug_log(&format!(
                "ableton device name lookup failed; falling back to recorded coordinates: device={device_name:?}"
            ));
            let up = replay_ableton_drag_segment(events, start, rect, Duration::from_millis(450))?;
            thread::sleep(Duration::from_millis(700));
            verify_ableton_devices_present(prior_devices, down.window_title.as_deref());
            Some((up, device_name))
        }
    }
}

pub(crate) fn ableton_device_name(event: &RecordedEvent) -> Option<String> {
    if let Some(name) = semantic_tag_value(event, "device:") {
        Some(name.to_string())
    } else {
        let name = event.element_name.as_deref()?.trim();
        if ableton_is_device_name(name) {
            Some(name.to_string())
        } else {
            None
        }
    }
}

pub(crate) fn ableton_target_channel_for_device_drag(
    down: &RecordedEvent,
    up: &RecordedEvent,
) -> Option<String> {
    semantic_tag_value(up, "channel:")
        .or_else(|| semantic_tag_value(down, "channel:"))
        .map(str::to_string)
        .or_else(|| {
            up.element_name
                .as_deref()
                .and_then(ableton_channel_from_element_name)
        })
        .or_else(|| {
            down.element_name
                .as_deref()
                .and_then(ableton_channel_from_element_name)
        })
}

pub(crate) fn ableton_is_device_name(name: &str) -> bool {
    matches!(
        name,
        "EQ Eight"
            | "Glue Compressor"
            | "Limiter"
            | "Compressor"
            | "Reverb"
            | "Delay"
            | "Echo"
            | "Saturator"
            | "Auto Filter"
            | "Utility"
    )
}

pub(crate) fn ableton_browser_category_for_device(name: &str) -> Option<&'static str> {
    if ableton_is_device_name(name) {
        Some("Audio Effects")
    } else {
        None
    }
}

#[cfg(target_os = "windows")]
pub(crate) fn verify_ableton_devices_present(devices: &[String], window_title: Option<&str>) {
    for device in devices {
        match uia_clickable_point_by_name_with_timeout(device, window_title, 500) {
            Ok(_) => write_debug_log(&format!(
                "ableton device verification present: device={device:?}"
            )),
            Err(error) => write_debug_log(&format!(
                "ableton device verification missing after add: device={device:?} error={error}"
            )),
        }
    }
}

#[cfg(target_os = "windows")]
pub(crate) fn locate_ableton_preset_with_scroll(
    preset_name: &str,
    recorded_event: &RecordedEvent,
    rect: Option<&WindowRect>,
) -> Option<(i32, i32)> {
    let window_title = recorded_event.window_title.as_deref();
    for attempt in 0..=8 {
        match uia_clickable_point_by_name_with_timeout(preset_name, window_title, 650) {
            Ok(point) => return Some(point),
            Err(error) => write_debug_log(&format!(
                "ableton preset UIA lookup attempt {attempt} failed: preset={preset_name:?} error={error}"
            )),
        }
        match ocr_ableton_browser_item_point_with_timeout(preset_name, rect, 1800) {
            Ok(point) => {
                write_debug_log(&format!(
                    "ableton preset located by OCR attempt {attempt}: preset={preset_name:?} source=({},{})",
                    point.0, point.1
                ));
                return Some(point);
            }
            Err(error) => write_debug_log(&format!(
                "ableton preset OCR lookup attempt {attempt} failed: preset={preset_name:?} error={error}"
            )),
        }
        if attempt < 8 {
            scroll_ableton_browser_near_recorded_source(recorded_event, rect, attempt);
            thread::sleep(Duration::from_millis(140));
        }
    }
    write_debug_log(&format!(
        "ableton preset UIA/OCR lookup failed; using coordinate fallback: preset={preset_name:?}"
    ));
    None
}

#[cfg(target_os = "windows")]
pub(crate) fn scroll_ableton_browser_near_recorded_source(
    recorded_event: &RecordedEvent,
    rect: Option<&WindowRect>,
    attempt: usize,
) {
    let (x, y) = resolve_ableton_replay_point(recorded_event, rect);
    unsafe {
        let _ = SetCursorPos(x, y);
        let wheel_delta = if attempt < 4 { -360i32 } else { 360i32 };
        mouse_event(MOUSEEVENTF_WHEEL, 0, 0, wheel_delta, 0);
    }
    write_debug_log(&format!(
        "ableton browser scroll attempt {attempt}: anchor=({x},{y})"
    ));
}

#[cfg(target_os = "windows")]
pub(crate) fn replay_ableton_drag_from_source(
    events: &[&RecordedEvent],
    start: usize,
    rect: Option<&WindowRect>,
    source_x: i32,
    source_y: i32,
    final_hold: Duration,
) -> Option<usize> {
    let up_index = matching_mouseup_index(events, start)?;
    let up = events[up_index];
    let endpoint = last_mousemove_before_mouseup(events, start, up_index).unwrap_or(up);
    let (end_x, end_y) = resolve_ableton_replay_point(endpoint, rect);
    let (up_x, up_y) = resolve_ableton_replay_point(up, rect);

    send_ableton_mousemove(source_x, source_y);
    thread::sleep(Duration::from_millis(40));
    send_ableton_leftdown(source_x, source_y);
    thread::sleep(Duration::from_millis(120));
    for step in 1..=10 {
        let t = step as f64 / 10.0;
        let x = source_x as f64 + ((end_x - source_x) as f64 * t);
        let y = source_y as f64 + ((end_y - source_y) as f64 * t);
        send_ableton_mousemove(x.round() as i32, y.round() as i32);
        thread::sleep(Duration::from_millis(35));
    }
    send_ableton_mousemove(up_x, up_y);
    thread::sleep(final_hold);
    send_ableton_leftup(up_x, up_y);
    Some(up_index)
}

#[cfg(target_os = "windows")]
pub(crate) fn replay_ableton_search_segment_if_present(
    events: &[&RecordedEvent],
    start: usize,
    rect: Option<&WindowRect>,
) -> Option<usize> {
    let Some(down) = events.get(start).copied() else {
        return None;
    };
    if down.kind != "mousedown"
        || down.button.as_deref().unwrap_or("left") != "left"
        || down.element_name.as_deref() != Some("Search")
    {
        return None;
    }
    let up_index = matching_mouseup_index(events, start)?;
    let up = events[up_index];
    if up.kind != "mouseup" || up.button.as_deref().unwrap_or("left") != "left" {
        return None;
    }
    let (down_x, down_y) = resolve_ableton_replay_point(down, rect);
    let (up_x, up_y) = resolve_ableton_replay_point(up, rect);
    write_debug_log(&format!(
        "ableton search normalize: down_index={start} up_index={up_index} down=({down_x},{down_y}) up=({up_x},{up_y})"
    ));
    send_ableton_mousemove(down_x, down_y);
    thread::sleep(Duration::from_millis(8));
    send_ableton_leftdown(down_x, down_y);
    let mut previous = down;
    for event in events[start + 1..up_index].iter().copied() {
        if event.kind != "mousemove" {
            continue;
        }
        thread::sleep(replay_event_delay(previous, Some(event)));
        let (x, y) = resolve_ableton_replay_point(event, rect);
        send_ableton_mousemove(x, y);
        previous = event;
    }
    thread::sleep(replay_event_delay(previous, Some(up)));
    send_ableton_mousemove(up_x, up_y);
    send_ableton_leftup(up_x, up_y);
    thread::sleep(Duration::from_millis(80));
    let _ = send_modified_key(VK_CONTROL, VIRTUAL_KEY(0x41));
    thread::sleep(Duration::from_millis(40));
    let _ = send_key(VK_BACK);
    Some(up_index)
}

pub(crate) fn compact_click_mouseup_index(
    events: &[&RecordedEvent],
    start: usize,
) -> Option<usize> {
    let mut moves = 0usize;
    for index in start + 1..events.len() {
        let event = events[index];
        if event.kind == "mousedown" {
            return None;
        }
        if event.kind == "mousemove" {
            moves += 1;
            if moves > 1 {
                return None;
            }
            continue;
        }
        if event.kind == "mouseup" {
            return Some(index);
        }
        return None;
    }
    None
}

#[cfg(target_os = "windows")]
pub(crate) fn replay_keyboard_event(event: &RecordedEvent) -> Result<(), String> {
    let key = event
        .key
        .as_deref()
        .ok_or_else(|| "keyboard event missing key".to_string())
        .and_then(vk_from_recorded_key)?;
    let flags = if matches!(event.kind.as_str(), "keyup" | "note_off") {
        KEYEVENTF_KEYUP
    } else {
        KEYBD_EVENT_FLAGS(0)
    };
    send_keyboard_input(VIRTUAL_KEY(key), flags)
}

pub(crate) fn is_ableton_confirmed_midi_note_event(event: &RecordedEvent) -> bool {
    if !is_ableton_event(event) {
        return false;
    }
    matches!(event.kind.as_str(), "note_on" | "note_off")
        || matches!(
            event.event_type.as_deref(),
            Some("note_on") | Some("note_off")
        )
        || event
            .semantic
            .as_deref()
            .map(|value| {
                value
                    .split(';')
                    .any(|part| part.trim().starts_with("midi_note:"))
            })
            .unwrap_or(false)
}

pub(crate) fn is_ableton_raw_midi_key_event(event: &RecordedEvent) -> bool {
    is_ableton_event(event)
        && matches!(event.kind.as_str(), "keydown" | "keyup")
        && event
            .key
            .as_deref()
            .and_then(|key| vk_from_recorded_key(key).ok())
            .and_then(|vk| ableton_computer_midi_note_for_vk(vk as i32))
            .is_some()
}

pub(crate) fn should_fire_ableton_note_preflight(
    event: &RecordedEvent,
    instrument_loaded: bool,
    piano_roll_open: bool,
    vault_has_instrument_load_events: bool,
) -> bool {
    if !instrument_loaded || !piano_roll_open {
        return false;
    }
    if is_ableton_confirmed_midi_note_event(event) {
        return true;
    }
    vault_has_instrument_load_events && is_ableton_raw_midi_key_event(event)
}

pub(crate) fn should_mark_ableton_piano_roll_open(event: &RecordedEvent) -> bool {
    if !is_ableton_event(event) {
        return false;
    }
    event
        .element_name
        .as_deref()
        .map(|name| {
            let lower = name.to_ascii_lowercase();
            (lower.contains("track") && lower.contains("scene"))
                || lower.contains("playing")
                || lower.contains("untitled clip")
        })
        .unwrap_or(false)
}

pub(crate) fn ableton_double_click_loads_instrument(
    events: &[&RecordedEvent],
    start: usize,
) -> bool {
    events
        .get(start)
        .copied()
        .and_then(ableton_preset_name)
        .map(|name| is_ableton_instrument_preset_name(&name))
        .unwrap_or(false)
}

pub(crate) fn ableton_vault_has_instrument_load_events(events: &[&RecordedEvent]) -> bool {
    for index in 0..events.len() {
        let event = events[index];
        if !is_ableton_event(event) {
            continue;
        }
        if ableton_double_click_loads_instrument(events, index) {
            return true;
        }
        if is_ableton_piano_roll_note_event(event) {
            return true;
        }
        let Some(preset_name) = ableton_preset_name(event) else {
            continue;
        };
        if !is_ableton_instrument_preset_name(&preset_name) {
            continue;
        }
        if let Some(up_index) = matching_mouseup_index(events, index) {
            if let Some(endpoint) = last_mousemove_before_mouseup(events, index, up_index) {
                if normalized_distance(event, endpoint)
                    .map(|distance| distance >= 0.015)
                    .unwrap_or(false)
                {
                    return true;
                }
            }
        }
    }
    false
}

pub(crate) fn prepare_ableton_note_replay_context(payload: &MouseReplayRequest) {
    if let Some(target) = payload.target_window.as_deref().or_else(|| {
        payload
            .events
            .iter()
            .find_map(|event| event.window_title.as_deref())
    }) {
        let _ = focus_target_window(target);
    }
    thread::sleep(Duration::from_millis(120));
    write_debug_log("=== ABLETON NOTE PREFLIGHT ===");
    write_debug_log("ableton note replay preflight: sending Escape to clear focused UI");
    let _ = send_keyboard_input(VIRTUAL_KEY(0x1B), KEYBD_EVENT_FLAGS(0));
    thread::sleep(Duration::from_millis(60));
    let _ = send_keyboard_input(VIRTUAL_KEY(0x1B), KEYEVENTF_KEYUP);
    thread::sleep(Duration::from_millis(200));
}
