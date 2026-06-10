use super::*;

pub(crate) fn is_colour_select_event(event: &RecordedEvent) -> bool {
    event.kind == "mousedown"
        && event.semantic.as_deref() == Some("colour_select")
        && event.colour_hex.is_some()
        && is_ms_paint_event(event)
}

pub(crate) fn is_ms_paint_event(event: &RecordedEvent) -> bool {
    event
        .app_name
        .as_deref()
        .map(title_is_ms_paint)
        .unwrap_or(false)
        || event
            .window_title
            .as_deref()
            .map(title_is_ms_paint)
            .unwrap_or(false)
}

pub(crate) fn title_is_ms_paint(value: &str) -> bool {
    value.to_ascii_lowercase().contains("paint")
}

pub(crate) fn replay_payload_targets_ms_paint(payload: &MouseReplayRequest) -> bool {
    payload
        .target_window
        .as_deref()
        .map(title_is_ms_paint)
        .unwrap_or(false)
        || payload
            .workflow_app
            .as_deref()
            .map(title_is_ms_paint)
            .unwrap_or(false)
        || first_valid_event_window_title(&payload.events)
            .as_deref()
            .map(title_is_ms_paint)
            .unwrap_or(false)
        || payload.events.iter().any(is_ms_paint_event)
}

#[cfg(target_os = "windows")]
pub(crate) fn resolve_target_replay_rect(
    payload: &MouseReplayRequest,
) -> Result<WindowRect, String> {
    if replay_payload_targets_ms_paint(payload) {
        return prepare_ms_paint_replay_tool(payload);
    }
    let title = payload
        .target_window
        .clone()
        .or_else(|| first_valid_event_window_title(&payload.events))
        .ok_or_else(|| "gesture replay needs a target window title".to_string())?;
    let hwnd = find_window_containing(&title)
        .ok_or_else(|| format!("no visible top-level window contains '{title}'"))?;
    window_rect_for_hwnd(hwnd).ok_or_else(|| format!("failed to get window rect for '{title}'"))
}

fn first_valid_event_window_title(events: &[RecordedEvent]) -> Option<String> {
    events
        .iter()
        .find(|event| !is_empty_unknown_system_event(event))
        .and_then(|event| event.window_title.as_ref())
        .map(|title| title.trim().to_string())
        .filter(|title| !title.is_empty())
}

#[cfg(target_os = "windows")]
pub(crate) fn sample_screen_colour_hex(x: i32, y: i32) -> Option<String> {
    unsafe {
        let screen_hwnd = HWND(std::ptr::null_mut());
        let screen_dc = GetDC(screen_hwnd);
        if screen_dc.0.is_null() {
            eprintln!("[Marouba] GetDC(null HWND) returned null while sampling colour");
            return None;
        }

        let mem_dc = CreateCompatibleDC(screen_dc);
        if mem_dc.0.is_null() {
            let _ = ReleaseDC(screen_hwnd, screen_dc);
            eprintln!("[Marouba] CreateCompatibleDC failed while sampling colour");
            return None;
        }

        let bitmap = CreateCompatibleBitmap(screen_dc, 1, 1);
        if bitmap.0.is_null() {
            let _ = DeleteDC(mem_dc);
            let _ = ReleaseDC(screen_hwnd, screen_dc);
            eprintln!("[Marouba] CreateCompatibleBitmap failed while sampling colour");
            return None;
        }

        let old_object = SelectObject(mem_dc, bitmap);
        if old_object.0.is_null() {
            let _ = DeleteObject(bitmap);
            let _ = DeleteDC(mem_dc);
            let _ = ReleaseDC(screen_hwnd, screen_dc);
            eprintln!("[Marouba] SelectObject failed while sampling colour");
            return None;
        }

        if BitBlt(mem_dc, 0, 0, 1, 1, screen_dc, x, y, SRCCOPY).is_err() {
            let _ = SelectObject(mem_dc, old_object);
            let _ = DeleteObject(bitmap);
            let _ = DeleteDC(mem_dc);
            let _ = ReleaseDC(screen_hwnd, screen_dc);
            eprintln!("[Marouba] BitBlt failed while sampling colour at ({x}, {y})");
            return None;
        }

        let colour = GetPixel(mem_dc, 0, 0);
        eprintln!(
            "[Marouba] Raw COLORREF sampled at ({x}, {y}): 0x{:08X}",
            colour.0
        );
        let _ = SelectObject(mem_dc, old_object);
        let _ = DeleteObject(bitmap);
        let _ = DeleteDC(mem_dc);
        let _ = ReleaseDC(screen_hwnd, screen_dc);
        if colour.0 == 0xFFFF_FFFF {
            eprintln!("[Marouba] GetPixel returned CLR_INVALID at ({x}, {y})");
            return None;
        }
        let value = colour.0;
        let red = value & 0xFF;
        let green = (value >> 8) & 0xFF;
        let blue = (value >> 16) & 0xFF;
        Some(format!("#{red:02X}{green:02X}{blue:02X}"))
    }
}

#[cfg(not(target_os = "windows"))]
pub(crate) fn sample_screen_colour_hex(_: i32, _: i32) -> Option<String> {
    None
}

#[cfg(target_os = "windows")]
fn prepare_ms_paint_replay_tool(payload: &MouseReplayRequest) -> Result<WindowRect, String> {
    let (hwnd, rect) = find_paint_window(payload)
        .ok_or_else(|| "Could not find MS Paint window for replay prelude".to_string())?;
    write_debug_log(&format!(
        "Paint HWND found, rect: {} {} {} {}",
        rect.left, rect.top, rect.width, rect.height
    ));
    unsafe {
        if !SetForegroundWindow(hwnd).as_bool() {
            return Err("SetForegroundWindow returned false for Paint prelude".to_string());
        }
    }
    write_debug_log("SetForegroundWindow sent");
    // Tool prelude removed - was causing selection state. Re-add when UIA toolbar click is implemented.
    thread::sleep(Duration::from_millis(500));
    Ok(rect)
}

#[cfg(target_os = "windows")]
fn find_paint_window(payload: &MouseReplayRequest) -> Option<(HWND, WindowRect)> {
    let mut candidates = Vec::new();
    if let Some(target) = payload
        .target_window
        .as_deref()
        .filter(|value| title_is_ms_paint(value))
    {
        candidates.push(target.to_string());
    }
    if let Some(app) = payload
        .workflow_app
        .as_deref()
        .filter(|value| title_is_ms_paint(value))
    {
        candidates.push(app.to_string());
    }
    if let Some(title) =
        first_valid_event_window_title(&payload.events).filter(|value| title_is_ms_paint(value))
    {
        candidates.push(title);
    }
    for event in &payload.events {
        if let Some(title) = event
            .window_title
            .as_deref()
            .filter(|value| title_is_ms_paint(value))
        {
            if !candidates
                .iter()
                .any(|candidate| candidate.eq_ignore_ascii_case(title))
            {
                candidates.push(title.to_string());
            }
        }
    }
    if candidates.is_empty() {
        candidates.push("paint".to_string());
    }
    for candidate in candidates {
        if let Some(hwnd) = find_window_containing(&candidate) {
            if let Some(rect) = window_rect_for_hwnd(hwnd) {
                return Some((hwnd, rect));
            }
        }
    }
    None
}

#[cfg(target_os = "windows")]
fn window_rect_for_hwnd(hwnd: HWND) -> Option<WindowRect> {
    unsafe {
        let mut rect = RECT::default();
        if GetWindowRect(hwnd, &mut rect).is_ok() {
            Some(WindowRect {
                left: rect.left,
                top: rect.top,
                width: rect.right - rect.left,
                height: rect.bottom - rect.top,
            })
        } else {
            None
        }
    }
}

#[cfg(target_os = "windows")]
pub(crate) fn replay_ms_paint_colour_select(colour_hex: &str) -> Result<(), String> {
    let (red, green, blue) = parse_colour_hex(colour_hex)?;
    send_modified_key(VK_MENU, VIRTUAL_KEY(0x45))?;
    thread::sleep(Duration::from_millis(80));
    send_key(VIRTUAL_KEY(0x43))?;
    thread::sleep(Duration::from_millis(400));
    replace_current_field(red)?;
    send_key(VK_TAB)?;
    replace_current_field(green)?;
    send_key(VK_TAB)?;
    replace_current_field(blue)?;
    send_key(VK_RETURN)
}

#[cfg(not(target_os = "windows"))]
pub(crate) fn replay_ms_paint_colour_select(_: &str) -> Result<(), String> {
    Err("semantic colour replay is not implemented on this platform".to_string())
}

fn parse_colour_hex(value: &str) -> Result<(u8, u8, u8), String> {
    let hex = value.trim().trim_start_matches('#');
    if hex.len() != 6 {
        return Err(format!("invalid colour hex '{value}'"));
    }
    let red = u8::from_str_radix(&hex[0..2], 16)
        .map_err(|_| format!("invalid red value in '{value}'"))?;
    let green = u8::from_str_radix(&hex[2..4], 16)
        .map_err(|_| format!("invalid green value in '{value}'"))?;
    let blue = u8::from_str_radix(&hex[4..6], 16)
        .map_err(|_| format!("invalid blue value in '{value}'"))?;
    Ok((red, green, blue))
}

#[cfg(target_os = "windows")]
fn replace_current_field(value: u8) -> Result<(), String> {
    send_modified_key(VK_CONTROL, VIRTUAL_KEY(0x41))?;
    send_key(VK_BACK)?;
    type_ascii(&value.to_string())
}

#[cfg(target_os = "windows")]
fn type_ascii(value: &str) -> Result<(), String> {
    for byte in value.bytes() {
        send_key(VIRTUAL_KEY(byte as u16))?;
        thread::sleep(Duration::from_millis(20));
    }
    Ok(())
}
