#![windows_subsystem = "windows"]

mod classifier;
mod route_switcher;

use rand::{distributions::Alphanumeric, Rng};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::HashSet;
use std::ffi::c_void;
use std::path::PathBuf;
use std::process::Command;
use std::sync::{mpsc, Arc, Mutex};
use std::thread;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};
use tauri::image::Image;
use tauri::menu::{Menu, MenuItem};
use tauri::tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent};
use tauri::{AppHandle, Manager};
use tiny_http::{Header, Method, Response, Server, StatusCode};

#[cfg(target_os = "windows")]
use windows::core::VARIANT;
#[cfg(target_os = "windows")]
use windows::core::{BSTR, PCWSTR};
#[cfg(target_os = "windows")]
use windows::Win32::Foundation::{BOOL, HWND, LPARAM, POINT, RECT};
#[cfg(target_os = "windows")]
use windows::Win32::Graphics::Gdi::{
    BitBlt, CreateCompatibleBitmap, CreateCompatibleDC, DeleteDC, DeleteObject, GetDC, GetDIBits,
    GetPixel, ReleaseDC, SelectObject, BITMAPINFO, BITMAPINFOHEADER, BI_RGB, DIB_RGB_COLORS,
    SRCCOPY,
};
#[cfg(target_os = "windows")]
use windows::Win32::System::Com::{
    CoCreateInstance, CoInitializeEx, CLSCTX_INPROC_SERVER, COINIT_MULTITHREADED,
};
#[cfg(target_os = "windows")]
use windows::Win32::UI::Accessibility::{
    CUIAutomation, IUIAutomation, IUIAutomationElement, IUIAutomationInvokePattern,
    TreeScope_Subtree, UIA_InvokePatternId, UIA_LegacyIAccessibleNamePropertyId,
    UIA_NamePropertyId,
};
#[cfg(target_os = "windows")]
use windows::Win32::UI::Input::KeyboardAndMouse::{
    mouse_event, GetAsyncKeyState, SendInput, INPUT, INPUT_0, INPUT_KEYBOARD, INPUT_MOUSE,
    KEYBDINPUT, KEYBD_EVENT_FLAGS, KEYEVENTF_KEYUP, MOUSEEVENTF_ABSOLUTE, MOUSEEVENTF_LEFTDOWN,
    MOUSEEVENTF_LEFTUP, MOUSEEVENTF_MOVE, MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP,
    MOUSEEVENTF_WHEEL, MOUSEINPUT, VIRTUAL_KEY, VK_BACK, VK_CONTROL, VK_LBUTTON, VK_MENU,
    VK_RBUTTON, VK_RETURN, VK_SHIFT, VK_TAB,
};
#[cfg(target_os = "windows")]
use windows::Win32::UI::Shell::ShellExecuteW;
#[cfg(target_os = "windows")]
use windows::Win32::UI::WindowsAndMessaging::{
    EnumWindows, GetCursorPos, GetForegroundWindow, GetSystemMetrics, GetWindowRect,
    GetWindowTextW, IsWindowVisible, SetCursorPos, SetForegroundWindow, ShowWindow, SM_CXSCREEN,
    SM_CYSCREEN, SW_SHOWNORMAL,
};

#[derive(Clone, Debug)]
struct AppState {
    recording: bool,
    events: Vec<RecordedEvent>,
    last_actions: Vec<String>,
    started_polling: bool,
    active_window: WindowInfo,
}

#[derive(Debug, Deserialize)]
struct UiaRequest {
    name: Option<String>,
    role: Option<String>,
    window_title: Option<String>,
    x: Option<i32>,
    y: Option<i32>,
}

#[derive(Debug, Deserialize)]
struct ScreenshotRequest {
    x: Option<i32>,
    y: Option<i32>,
    width: Option<i32>,
    height: Option<i32>,
}

#[derive(Debug, Deserialize)]
struct MouseReplayRequest {
    target_window: Option<String>,
    workflow_app: Option<String>,
    events: Vec<RecordedEvent>,
}

#[derive(Debug, Deserialize)]
struct ReplayWorkflowRequest {
    name: String,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
struct WindowRect {
    left: i32,
    top: i32,
    width: i32,
    height: i32,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
struct RecordedEvent {
    kind: String,
    event_type: Option<String>,
    timestamp_ms: u128,
    x: Option<i32>,
    y: Option<i32>,
    normalized_x: Option<f64>,
    normalized_y: Option<f64>,
    button: Option<String>,
    key: Option<String>,
    note: Option<String>,
    velocity: Option<u8>,
    window_title: Option<String>,
    app_name: Option<String>,
    window_rect: Option<WindowRect>,
    element_name: Option<String>,
    element_role: Option<String>,
    colour_hex: Option<String>,
    semantic: Option<String>,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
struct WindowInfo {
    title: String,
    app_name: String,
}

#[derive(Debug, Deserialize)]
struct SaveWorkflowRequest {
    name: String,
    keep_indexes: Vec<usize>,
}

#[derive(Debug, Serialize)]
struct RecordingStatus {
    mode: String,
    active_window: WindowInfo,
    steps: Vec<RecordedEvent>,
    last_actions: Vec<String>,
}

#[derive(Debug, Serialize)]
struct VaultWorkflowSummary {
    name: String,
    size_kb: u64,
    modified: String,
}

#[derive(Clone, Debug, Deserialize)]
struct OcrWord {
    text: String,
    left: i32,
    top: i32,
    width: i32,
    height: i32,
}

fn main() {
    let token = load_or_create_token();
    let state = Arc::new(Mutex::new(AppState {
        recording: false,
        events: Vec::new(),
        last_actions: vec!["Companion started".to_string()],
        started_polling: false,
        active_window: active_window(),
    }));

    let api_state = state.clone();
    thread::spawn(move || start_http_api(token, api_state));

    tauri::Builder::default()
        .manage(state)
        .invoke_handler(tauri::generate_handler![
            start_recording,
            stop_recording,
            recording_status,
            save_workflow,
            delete_step,
            open_vault,
            pick_workflows,
            companion_token
        ])
        .setup(|app| {
            setup_tray(app)?;
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running Marouba Companion");
}

fn setup_tray(app: &mut tauri::App) -> tauri::Result<()> {
    let record = MenuItem::with_id(app, "record", "Record", true, None::<&str>)?;
    let stop = MenuItem::with_id(app, "stop", "Stop", true, None::<&str>)?;
    let vault = MenuItem::with_id(app, "open_vault", "Open Vault", true, None::<&str>)?;
    let quit = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;
    let menu = Menu::with_items(app, &[&record, &stop, &vault, &quit])?;

    let mut builder = TrayIconBuilder::new()
        .tooltip("Marouba")
        .menu(&menu)
        .show_menu_on_left_click(false)
        .on_menu_event(|app, event| match event.id().as_ref() {
            "record" => {
                if let Some(state) = app.try_state::<Arc<Mutex<AppState>>>() {
                    let _ = start_recording_from_state(state.inner().clone());
                }
                show_popup(app);
            }
            "stop" => {
                if let Some(state) = app.try_state::<Arc<Mutex<AppState>>>() {
                    let _ = stop_recording_from_state(state.inner().clone());
                }
                show_popup(app);
            }
            "open_vault" => {
                let _ = open_vault_folder();
            }
            "quit" => app.exit(0),
            _ => {}
        })
        .on_tray_icon_event(|tray, event| {
            if let TrayIconEvent::Click {
                button: MouseButton::Left,
                button_state: MouseButtonState::Up,
                ..
            } = event
            {
                toggle_popup(tray.app_handle());
            }
        });

    builder = builder.icon(Image::new(
        include_bytes!("../icons/tray_icon_rgba.bin"),
        32,
        32,
    ));
    let tray = builder.build(app)?;
    app.manage(tray);
    Ok(())
}

fn toggle_popup(app: &AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        if window.is_visible().unwrap_or(false) {
            let _ = window.hide();
        } else {
            show_popup(app);
        }
    }
}

fn show_popup(app: &AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.show();
        let _ = window.center();
        let _ = window.set_focus();
    }
}

#[tauri::command]
fn start_recording(state: tauri::State<Arc<Mutex<AppState>>>) -> Result<RecordingStatus, String> {
    start_recording_from_state(state.inner().clone())?;
    Ok(status_from_state(&state))
}

#[tauri::command]
fn stop_recording(state: tauri::State<Arc<Mutex<AppState>>>) -> Result<RecordingStatus, String> {
    stop_recording_from_state(state.inner().clone())?;
    Ok(status_from_state(&state))
}

#[tauri::command]
fn recording_status(state: tauri::State<Arc<Mutex<AppState>>>) -> RecordingStatus {
    status_from_state(&state)
}

#[tauri::command]
fn delete_step(
    index: usize,
    state: tauri::State<Arc<Mutex<AppState>>>,
) -> Result<RecordingStatus, String> {
    let mut guard = state
        .lock()
        .map_err(|_| "recording state is unavailable".to_string())?;
    if index < guard.events.len() {
        guard.events.remove(index);
        push_log(&mut guard, format!("Deleted step {}", index + 1));
    }
    drop(guard);
    Ok(status_from_state(&state))
}

#[tauri::command]
fn save_workflow(
    request: SaveWorkflowRequest,
    state: tauri::State<Arc<Mutex<AppState>>>,
) -> Result<String, String> {
    let guard = state
        .lock()
        .map_err(|_| "recording state is unavailable".to_string())?;
    let keep: HashSet<usize> = request.keep_indexes.into_iter().collect();
    let events: Vec<RecordedEvent> = guard
        .events
        .iter()
        .enumerate()
        .filter_map(|(index, event)| {
            (keep.contains(&index) && !is_marouba_event(event)).then(|| event.clone())
        })
        .collect();
    drop(guard);

    if events.is_empty() {
        return Err("No steps selected for this workflow".to_string());
    }
    let metadata = describe_with_claude(&request.name, &events);
    let path = write_workflow(&request.name, &events, metadata)?;
    let mut guard = state
        .lock()
        .map_err(|_| "recording state is unavailable".to_string())?;
    push_log(&mut guard, format!("Saved {}", path.display()));
    Ok(path.display().to_string())
}
#[tauri::command]
fn open_vault() -> Result<(), String> {
    open_vault_folder()
}

#[tauri::command]
fn pick_workflows() -> Result<Vec<VaultWorkflowSummary>, String> {
    let dir = vault_workflows_dir();
    std::fs::create_dir_all(&dir).map_err(|error| error.to_string())?;
    let Some(paths) = rfd::FileDialog::new()
        .set_title("Open Marouba workflows")
        .set_directory(&dir)
        .add_filter("Marouba workflows", &["md"])
        .pick_files()
    else {
        return Ok(Vec::new());
    };

    let mut workflows = Vec::new();
    for path in paths {
        if path.extension().and_then(|value| value.to_str()) != Some("md") {
            continue;
        }
        if let Some(workflow) = workflow_summary_from_path(path) {
            workflows.push(workflow);
        }
    }
    Ok(workflows)
}

#[tauri::command]
fn companion_token() -> Result<String, String> {
    std::fs::read_to_string(token_path())
        .map(|token| token.trim().to_string())
        .map_err(|error| error.to_string())
}

fn start_recording_from_state(state: Arc<Mutex<AppState>>) -> Result<(), String> {
    let should_spawn = {
        let mut guard = state
            .lock()
            .map_err(|_| "recording state is unavailable".to_string())?;
        guard.recording = true;
        guard.events.clear();
        push_log(&mut guard, "Recording started".to_string());
        if guard.started_polling {
            false
        } else {
            guard.started_polling = true;
            true
        }
    };
    if should_spawn {
        thread::spawn(move || recorder_loop(state));
    }
    Ok(())
}

fn stop_recording_from_state(state: Arc<Mutex<AppState>>) -> Result<(), String> {
    let mut guard = state
        .lock()
        .map_err(|_| "recording state is unavailable".to_string())?;
    guard.recording = false;
    let before_count = guard.events.len();
    guard.events.retain(|event| !is_marouba_event(event));
    let event_count = guard.events.len();
    let removed_count = before_count.saturating_sub(event_count);
    if removed_count > 0 {
        push_log(
            &mut guard,
            format!("Filtered {removed_count} Marouba control steps"),
        );
    }
    push_log(
        &mut guard,
        format!("Recording stopped: {event_count} steps"),
    );
    Ok(())
}
fn status_from_state(state: &Arc<Mutex<AppState>>) -> RecordingStatus {
    match state.lock() {
        Ok(guard) => RecordingStatus {
            mode: if guard.recording { "recording" } else { "idle" }.to_string(),
            active_window: guard.active_window.clone(),
            steps: guard.events.clone(),
            last_actions: guard.last_actions.clone(),
        },
        Err(_) => RecordingStatus {
            mode: "offline".to_string(),
            active_window: WindowInfo {
                title: "unknown".to_string(),
                app_name: "unknown".to_string(),
            },
            steps: Vec::new(),
            last_actions: vec!["Recording state unavailable".to_string()],
        },
    }
}

fn recorder_loop(state: Arc<Mutex<AppState>>) {
    let started = Instant::now();
    let mut last_pos: Option<(i32, i32)> = None;
    let mut last_left = false;
    let mut last_right = false;
    let mut last_keys = HashSet::<i32>::new();
    let mut last_title = String::new();
    let mut current_app_name = String::new();
    let mut last_mousemove_pos: Option<(i32, i32)> = None;
    let mut ableton_text_entry_until_ms = 0u128;
    let mut active_ableton_midi_keys = HashSet::<i32>::new();

    loop {
        let recording = state.lock().map(|guard| guard.recording).unwrap_or(false);
        let window = active_window();
        if let Ok(mut guard) = state.lock() {
            guard.active_window = window.clone();
        }

        if !recording {
            thread::sleep(Duration::from_millis(120));
            continue;
        }

        if window.title != last_title {
            last_title = window.title.clone();
            current_app_name = app_name_from_title(&window.title);
            push_event(
                &state,
                RecordedEvent {
                    kind: "focus".to_string(),
                    event_type: None,
                    timestamp_ms: started.elapsed().as_millis(),
                    x: None,
                    y: None,
                    normalized_x: None,
                    normalized_y: None,
                    button: None,
                    key: None,
                    note: None,
                    velocity: None,
                    window_title: Some(window.title.clone()),
                    app_name: Some(current_app_name.clone()),
                    window_rect: active_window_rect(),
                    element_name: None,
                    element_role: None,
                    colour_hex: None,
                    semantic: None,
                },
            );
        } else if current_app_name.is_empty() || current_app_name == "unknown" {
            current_app_name = app_name_from_title(&window.title);
        }

        if let Some((x, y)) = cursor_position() {
            #[cfg(target_os = "windows")]
            let left = key_is_down(VK_LBUTTON.0 as i32);
            #[cfg(not(target_os = "windows"))]
            let left = false;

            if last_pos != Some((x, y)) {
                last_pos = Some((x, y));
                let mousemove_threshold = if left { 2.0 } else { 8.0 };
                if should_record_mousemove(last_mousemove_pos, x, y, mousemove_threshold) {
                    last_mousemove_pos = Some((x, y));
                    push_event(
                        &state,
                        mouse_event_record(
                            "mousemove",
                            x,
                            y,
                            None,
                            started.elapsed().as_millis(),
                            &window,
                            &current_app_name,
                        ),
                    );
                }
            }

            if left != last_left {
                last_left = left;
                let timestamp_ms = started.elapsed().as_millis();
                let event = mouse_event_record(
                    if left { "mousedown" } else { "mouseup" },
                    x,
                    y,
                    Some("left".to_string()),
                    timestamp_ms,
                    &window,
                    &current_app_name,
                );
                if title_is_ableton(&window.title) && event.kind == "mousedown" {
                    if event.element_name.as_deref() == Some("Search") {
                        ableton_text_entry_until_ms = timestamp_ms + 6_000;
                    } else {
                        ableton_text_entry_until_ms = 0;
                    }
                }
                push_event(&state, event);
            }

            #[cfg(target_os = "windows")]
            let right = key_is_down(VK_RBUTTON.0 as i32);
            #[cfg(not(target_os = "windows"))]
            let right = false;
            if right != last_right {
                last_right = right;
                push_event(
                    &state,
                    mouse_event_record(
                        if right { "mousedown" } else { "mouseup" },
                        x,
                        y,
                        Some("right".to_string()),
                        started.elapsed().as_millis(),
                        &window,
                        &current_app_name,
                    ),
                );
            }
        }

        let mut current_keys = HashSet::new();
        for vk in 8..=254 {
            if key_is_down(vk) {
                current_keys.insert(vk);
                if !last_keys.contains(&vk) {
                    let timestamp_ms = started.elapsed().as_millis();
                    let capture_as_midi_note = title_is_ableton(&window.title)
                        && timestamp_ms > ableton_text_entry_until_ms
                        && ableton_computer_midi_note_for_vk(vk).is_some();
                    if capture_as_midi_note {
                        active_ableton_midi_keys.insert(vk);
                    }
                    push_event(
                        &state,
                        keyboard_event_record(
                            "keydown",
                            vk,
                            timestamp_ms,
                            &window,
                            &current_app_name,
                            capture_as_midi_note,
                        ),
                    );
                }
            }
        }
        for vk in last_keys.difference(&current_keys) {
            let timestamp_ms = started.elapsed().as_millis();
            let capture_as_midi_note = active_ableton_midi_keys.remove(vk);
            push_event(
                &state,
                keyboard_event_record(
                    "keyup",
                    *vk,
                    timestamp_ms,
                    &window,
                    &current_app_name,
                    capture_as_midi_note,
                ),
            );
        }
        last_keys = current_keys;
        let poll_interval_ms = if last_left { 10 } else { 45 };
        thread::sleep(Duration::from_millis(poll_interval_ms));
    }
}
fn push_event(state: &Arc<Mutex<AppState>>, event: RecordedEvent) {
    if let Ok(mut guard) = state.lock() {
        if !guard.recording {
            return;
        }
        if is_empty_unknown_system_event(&event) {
            return;
        }
        let label = event_label(&event);
        guard.events.push(event);
        push_log(&mut guard, label);
    }
}

fn is_empty_unknown_system_event(event: &RecordedEvent) -> bool {
    app_name_is_unknown_or_empty(event.app_name.as_deref())
        && event
            .window_title
            .as_deref()
            .map(str::trim)
            .unwrap_or("")
            .is_empty()
}

fn app_name_is_unknown_or_empty(value: Option<&str>) -> bool {
    let value = value.unwrap_or("").trim();
    value.is_empty() || value.eq_ignore_ascii_case("unknown")
}

fn should_record_mousemove(previous: Option<(i32, i32)>, x: i32, y: i32, threshold: f64) -> bool {
    match previous {
        None => true,
        Some((previous_x, previous_y)) => {
            let dx = (x - previous_x) as f64;
            let dy = (y - previous_y) as f64;
            (dx * dx + dy * dy).sqrt() > threshold
        }
    }
}

fn push_log(state: &mut AppState, label: String) {
    state.last_actions.insert(0, label);
    state.last_actions.truncate(5);
}

fn event_label(event: &RecordedEvent) -> String {
    match event.kind.as_str() {
        "mousemove" => format!(
            "Mouse move {}, {}",
            event.x.unwrap_or(0),
            event.y.unwrap_or(0)
        ),
        "mousedown" | "mouseup" => format!(
            "{} {} {}, {}",
            event.kind,
            event.button.as_deref().unwrap_or("left"),
            event.x.unwrap_or(0),
            event.y.unwrap_or(0)
        ),
        "keydown" | "keyup" => format!("{} {}", event.kind, event.key.as_deref().unwrap_or("?")),
        "note_on" | "note_off" => format!(
            "{} {} via {}",
            event.kind,
            event.note.as_deref().unwrap_or("?"),
            event.key.as_deref().unwrap_or("?")
        ),
        "focus" => format!(
            "Focus {}",
            event.window_title.as_deref().unwrap_or("unknown")
        ),
        _ => event.kind.clone(),
    }
}

fn mouse_event_record(
    kind: &str,
    x: i32,
    y: i32,
    button: Option<String>,
    timestamp_ms: u128,
    window: &WindowInfo,
    current_app_name: &str,
) -> RecordedEvent {
    let rect = active_window_rect();
    let app_name = if current_app_name.trim().is_empty()
        || current_app_name.trim().eq_ignore_ascii_case("unknown")
    {
        app_name_from_title(&window.title)
    } else {
        current_app_name.to_string()
    };
    let (normalized_x, normalized_y) = match rect.as_ref() {
        Some(rect) if rect.width > 0 && rect.height > 0 => (
            Some((x - rect.left) as f64 / rect.width as f64),
            Some((y - rect.top) as f64 / rect.height as f64),
        ),
        _ => (None, None),
    };
    let mut event = RecordedEvent {
        kind: kind.to_string(),
        event_type: None,
        timestamp_ms,
        x: Some(x),
        y: Some(y),
        normalized_x,
        normalized_y,
        button,
        key: None,
        note: None,
        velocity: None,
        window_title: Some(window.title.clone()),
        app_name: Some(app_name),
        window_rect: rect,
        element_name: None,
        element_role: None,
        colour_hex: None,
        semantic: None,
    };
    if kind == "mousedown" || (kind == "mouseup" && title_is_ableton(&window.title)) {
        if let Ok((element, _)) = find_uia_element(&UiaRequest {
            name: None,
            role: None,
            window_title: None,
            x: Some(x),
            y: Some(y),
        }) {
            let body = element_json(
                &element,
                event.window_title.as_deref().unwrap_or(""),
                &UiaRequest {
                    name: None,
                    role: None,
                    window_title: None,
                    x: Some(x),
                    y: Some(y),
                },
            );
            event.element_name = body.get("name").and_then(Value::as_str).map(str::to_string);
            event.element_role = body.get("control_type").map(Value::to_string);
        }
    }
    if is_ableton_event(&event) {
        enrich_ableton_recorded_event(&mut event, y);
    }
    if kind == "mousedown" {
        if is_ableton_piano_roll_note_event(&event) {
            let mut captured_midi_semantic = false;
            match ableton_midi_note_name_at_point_with_timeout(
                event.window_title.as_deref(),
                x,
                y,
                650,
            ) {
                Ok(note_name) => {
                    write_debug_log(&format!(
                        "ableton midi note captured: note={note_name} screen_y={y}"
                    ));
                    if event
                        .element_name
                        .as_deref()
                        .map(str::trim)
                        .filter(|name| !name.is_empty())
                        .is_none()
                    {
                        event.element_name = Some(note_name.clone());
                    }
                    add_semantic_tag(&mut event, format!("midi_note:{note_name}"));
                    captured_midi_semantic = true;
                }
                Err(error) => write_debug_log(&format!(
                    "ableton midi note capture unavailable: screen_y={y} error={error}"
                )),
            }
            match ableton_pitch_label_near_y_with_timeout(event.window_title.as_deref(), y, 500) {
                Ok((pitch, _row_y)) => {
                    add_semantic_tag(&mut event, format!("midi_pitch:{pitch}"));
                    captured_midi_semantic = true;
                }
                Err(error) => write_debug_log(&format!(
                    "ableton midi pitch capture unavailable: screen_y={y} error={error}"
                )),
            }
            if !captured_midi_semantic {
                match ocr_ableton_row_label_near_y_with_timeout(event.window_rect.as_ref(), y, 1200)
                {
                    Ok(note_name) => {
                        write_debug_log(&format!(
                            "ableton midi note captured by OCR: note={note_name} screen_y={y}"
                        ));
                        if event
                            .element_name
                            .as_deref()
                            .map(|name| !ableton_note_name_is_row_label(name))
                            .unwrap_or(true)
                        {
                            event.element_name = Some(note_name.clone());
                        }
                        add_semantic_tag(&mut event, format!("midi_note:{note_name}"));
                        captured_midi_semantic = true;
                    }
                    Err(error) => write_debug_log(&format!(
                        "ableton midi note OCR capture unavailable: screen_y={y} error={error}"
                    )),
                }
            }
            if !captured_midi_semantic {
                if let Some(row) = event.normalized_y {
                    add_semantic_tag(&mut event, format!("midi_row:{row:.6}"));
                    write_debug_log(&format!(
                        "ableton midi row captured from normalized coordinate: row={row:.6}"
                    ));
                }
            }
        }
        let paint_window = is_ms_paint_event(&event) || title_is_ms_paint(&window.title);
        let in_colour_bar = normalized_y
            .zip(normalized_x)
            .map(|(y, x)| y < 0.18 && y > 0.09 && x > 0.45)
            .unwrap_or(false);
        if paint_window && in_colour_bar {
            match sample_screen_colour_hex(x, y) {
                Some(colour_hex) => {
                    eprintln!(
                        "[Marouba] Captured MS Paint colour {colour_hex} at ({x}, {y}) in '{}'",
                        window.title
                    );
                    event.colour_hex = Some(colour_hex);
                    event.semantic = Some("colour_select".to_string());
                }
                None => {
                    eprintln!(
                        "[Marouba] Failed to capture MS Paint colour at ({x}, {y}) in '{}'",
                        window.title
                    );
                }
            }
        } else if title_is_ms_paint(&window.title) {
            eprintln!(
                "[Marouba] MS Paint mousedown outside colour bar at normalized_y={:?}",
                normalized_y
            );
        } else {
            eprintln!(
                "[Marouba] Colour capture skipped; window title '{}' app '{}'",
                window.title, current_app_name
            );
        }
    }
    event
}

fn keyboard_event_record(
    kind: &str,
    vk: i32,
    timestamp_ms: u128,
    window: &WindowInfo,
    current_app_name: &str,
    capture_as_midi_note: bool,
) -> RecordedEvent {
    let app_name = if current_app_name.trim().is_empty()
        || current_app_name.trim().eq_ignore_ascii_case("unknown")
    {
        app_name_from_title(&window.title)
    } else {
        current_app_name.to_string()
    };
    let midi_note = capture_as_midi_note
        .then(|| ableton_computer_midi_note_for_vk(vk))
        .flatten();
    let key_label = midi_note
        .as_ref()
        .and_then(|_| key_label_for_vk(vk))
        .unwrap_or_else(|| vk.to_string());
    let kind = match (kind, midi_note.as_ref()) {
        ("keydown", Some(_)) => "note_on",
        ("keyup", Some(_)) => "note_off",
        _ => kind,
    };
    RecordedEvent {
        kind: kind.to_string(),
        event_type: midi_note.as_ref().map(|_| kind.to_string()),
        timestamp_ms,
        x: None,
        y: None,
        normalized_x: None,
        normalized_y: None,
        button: None,
        key: Some(key_label),
        note: midi_note.clone(),
        velocity: midi_note.as_ref().map(|_| 100),
        window_title: Some(window.title.clone()),
        app_name: Some(app_name),
        window_rect: active_window_rect(),
        element_name: None,
        element_role: None,
        colour_hex: None,
        semantic: midi_note.map(|note| format!("midi_note:{note}")),
    }
}

fn key_label_for_vk(vk: i32) -> Option<String> {
    let vk = u32::try_from(vk).ok()?;
    let ch = char::from_u32(vk)?;
    ch.is_ascii_alphanumeric()
        .then(|| ch.to_ascii_lowercase().to_string())
}

fn ableton_computer_midi_note_for_vk(vk: i32) -> Option<String> {
    let key = key_label_for_vk(vk)?;
    let note = match key.as_str() {
        "z" => "C3",
        "s" => "C#3",
        "x" => "D3",
        "d" => "D#3",
        "c" => "E3",
        "v" => "F3",
        "g" => "F#3",
        "b" => "G3",
        "h" => "G#3",
        "n" => "A3",
        "j" => "A#3",
        "m" => "B3",
        "q" => "C4",
        "2" => "C#4",
        "w" => "D4",
        "3" => "D#4",
        "e" => "E4",
        "r" => "F4",
        "5" => "F#4",
        "t" => "G4",
        "6" => "G#4",
        "y" => "A4",
        "7" => "A#4",
        "u" => "B4",
        "i" => "C5",
        "9" => "C#5",
        "o" => "D5",
        "0" => "D#5",
        "p" => "E5",
        _ => return None,
    };
    Some(note.to_string())
}

fn start_http_api(token: String, state: Arc<Mutex<AppState>>) {
    let server = Server::http("127.0.0.1:7842").expect("failed to bind companion API");
    for mut request in server.incoming_requests() {
        if request.method() == &Method::Options {
            let _ = request.respond(cors_response(json!({}), 204));
            continue;
        }
        if !is_authorized(&request, &token) {
            let _ = request.respond(json_response(json!({"error": "unauthorized"}), 401));
            continue;
        }
        let method = request.method().clone();
        let url = request.url().to_string();
        let response = match (method, url.as_str()) {
            (Method::Get, "/health") => json_response(json!({"status": "ok"}), 200),
            (Method::Get, "/window") => json_response(json!(active_window()), 200),
            (Method::Get, "/workflows") => {
                let (body, status) = list_saved_workflows();
                json_response(body, status)
            }
            (Method::Get, "/recording") => json_response(json!(status_from_state(&state)), 200),
            (Method::Post, "/record/start") => {
                let _ = start_recording_from_state(state.clone());
                json_response(json!(status_from_state(&state)), 200)
            }
            (Method::Post, "/record/stop") => {
                let _ = stop_recording_from_state(state.clone());
                json_response(json!(status_from_state(&state)), 200)
            }
            (Method::Post, "/uia/find") => {
                let payload: UiaRequest = read_json(&mut request);
                let (body, status) = find_uia(payload);
                json_response(body, status)
            }
            (Method::Post, "/uia/click") => {
                let payload: UiaRequest = read_json(&mut request);
                let (body, status) = click_uia(payload);
                json_response(body, status)
            }
            (Method::Post, "/mouse") => {
                let payload: MouseReplayRequest = read_json(&mut request);
                let (body, status) = replay_mouse(payload);
                json_response(body, status)
            }
            (Method::Post, "/replay") => {
                let payload: ReplayWorkflowRequest = read_json(&mut request);
                let (body, status) = start_replay_workflow(payload);
                json_response(body, status)
            }
            (Method::Post, "/workflow/delete") => {
                let payload: ReplayWorkflowRequest = read_json(&mut request);
                let (body, status) = delete_saved_workflow(payload);
                json_response(body, status)
            }
            (Method::Post, "/open-vault") => match open_vault_folder() {
                Ok(()) => json_response(json!({"status": "opened"}), 200),
                Err(error) => json_response(json!({"status": "failed", "error": error}), 500),
            },
            (Method::Post, "/screenshot") => {
                let payload: ScreenshotRequest = read_json(&mut request);
                json_response(screenshot(payload), 200)
            }
            _ => json_response(json!({"error": "not found"}), 404),
        };
        let _ = request.respond(response);
    }
}

fn load_or_create_token() -> String {
    let token_path = token_path();
    if let Ok(token) = std::fs::read_to_string(&token_path) {
        let token = token.trim().to_string();
        if !token.is_empty() {
            return token;
        }
    }
    let token: String = rand::thread_rng()
        .sample_iter(&Alphanumeric)
        .take(48)
        .map(char::from)
        .collect();
    if let Some(parent) = token_path.parent() {
        let _ = std::fs::create_dir_all(parent);
    }
    let _ = std::fs::write(&token_path, &token);
    token
}

fn token_path() -> PathBuf {
    let home = std::env::var("USERPROFILE")
        .or_else(|_| std::env::var("HOME"))
        .unwrap_or_else(|_| ".".to_string());
    PathBuf::from(home).join(".marouba").join("companion.token")
}

fn vault_workflows_dir() -> PathBuf {
    vault_dir().join("workflows")
}

fn vault_dir() -> PathBuf {
    if let Ok(path) = std::env::var("MAROUBA_VAULT_PATH") {
        let trimmed = path.trim();
        if !trimmed.is_empty() {
            return PathBuf::from(trimmed);
        }
    }
    std::env::var("LOCALAPPDATA")
        .map(|path| PathBuf::from(path).join("Marouba").join("vault"))
        .unwrap_or_else(|_| PathBuf::from(r"C:\Users\Dave\AppData\Local\Marouba\vault"))
}

fn marouba_root_dir() -> PathBuf {
    PathBuf::from(r"C:\Share\Marouba")
}

fn list_saved_workflows() -> (Value, u16) {
    let dir = vault_workflows_dir();
    let mut workflows = Vec::new();
    let entries = match std::fs::read_dir(&dir) {
        Ok(entries) => entries,
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => return (json!([]), 200),
        Err(error) => {
            return (
                json!({"error": format!("failed to read workflow vault: {error}")}),
                500,
            )
        }
    };

    for entry in entries.flatten() {
        let path = entry.path();
        if !path.is_file() || path.extension().and_then(|value| value.to_str()) != Some("md") {
            continue;
        }
        if let Some(workflow) = workflow_summary_from_path(path) {
            workflows.push(workflow);
        }
    }

    workflows.sort_by(|left, right| left.name.cmp(&right.name));
    (json!(workflows), 200)
}

fn workflow_summary_from_path(path: PathBuf) -> Option<VaultWorkflowSummary> {
    let metadata = std::fs::metadata(&path).ok()?;
    let name = path
        .file_stem()
        .and_then(|value| value.to_str())
        .unwrap_or("workflow")
        .to_string();
    Some(VaultWorkflowSummary {
        name,
        size_kb: (metadata.len() + 1023) / 1024,
        modified: metadata
            .modified()
            .ok()
            .map(|modified| format_modified_time(&path, modified))
            .unwrap_or_else(|| "unknown".to_string()),
    })
}

fn start_replay_workflow(payload: ReplayWorkflowRequest) -> (Value, u16) {
    let name = match safe_workflow_name(&payload.name) {
        Ok(name) => name,
        Err(error) => return (json!({"status": "failed", "error": error}), 400),
    };

    if let Some(events) = parse_gesture_workflow(&name) {
        let target_windows = replay_target_windows(&name, &events);
        let focused_window = if target_windows.is_empty() {
            None
        } else {
            match ensure_target_window_ready(&target_windows) {
                Ok(window_title) => Some(window_title),
                Err(error) => {
                    let tried = target_windows.join(", ");
                    let target_app = target_windows
                        .first()
                        .map(|title| app_name_from_title(title))
                        .unwrap_or_else(|| "the target app".to_string());
                    return (
                        json!({
                            "status": "failed",
                            "error": error.clone(),
                            "detail": error,
                            "target_app": target_app,
                            "target_windows": tried
                        }),
                        200,
                    );
                }
            }
        };
        if let Some(window_title) = focused_window.as_deref() {
            println!("[Marouba] Focused replay target window: {window_title}");
        }
        thread::sleep(Duration::from_millis(500));
        let (mut body, status) = replay_mouse(MouseReplayRequest {
            target_window: focused_window.clone(),
            workflow_app: parse_workflow_app_name(&name),
            events,
        });
        if status >= 400 || body.get("ok").and_then(Value::as_bool) == Some(false) {
            return (
                json!({
                    "status": "failed",
                    "error": body
                        .get("error")
                        .and_then(Value::as_str)
                        .unwrap_or("gesture replay failed"),
                    "detail": body,
                    "target_window": focused_window
                }),
                status,
            );
        }
        if let Value::Object(ref mut object) = body {
            object.insert("status".to_string(), json!("ok"));
            object.insert("focused_window".to_string(), json!(focused_window));
        }
        return (body, status);
    }

    let mut command = Command::new(replay_python_command());
    command.current_dir(marouba_root_dir()).args([
        "scripts/replay.py",
        "--workflow",
        &name,
        "--params",
        "{}",
    ]);
    let child = no_window_command(&mut command).spawn();
    match child {
        Ok(child) => (json!({"status": "started", "pid": child.id()}), 200),
        Err(error) => (
            json!({"status": "failed", "error": format!("failed to start replay: {error}")}),
            500,
        ),
    }
}

fn replay_target_windows(name: &str, events: &[RecordedEvent]) -> Vec<String> {
    let mut candidates = Vec::new();
    for event in events {
        if let Some(title) = event.window_title.as_ref() {
            push_unique_window(&mut candidates, title.clone());
            if let Some(app_name) = app_name_hint_from_window_title(title) {
                push_unique_window(&mut candidates, app_name);
            }
        }
        if let Some(app_name) = event.app_name.as_ref() {
            push_unique_window(&mut candidates, app_name.clone());
        }
    }
    if let Some(app_name) = parse_workflow_app_name(name) {
        push_unique_window(&mut candidates, app_name);
    }
    candidates.sort_by_key(|title| {
        if is_known_creative_window(title) {
            0
        } else {
            1
        }
    });
    candidates
}

fn push_unique_window(candidates: &mut Vec<String>, title: String) {
    let trimmed = title.trim();
    if trimmed.is_empty() {
        return;
    }
    if !candidates
        .iter()
        .any(|candidate| candidate.eq_ignore_ascii_case(trimmed))
    {
        candidates.push(trimmed.to_string());
    }
}

fn is_known_creative_window(title: &str) -> bool {
    let lower = title.to_ascii_lowercase();
    [
        "paint",
        "notepad++",
        "photoshop",
        "ableton",
        "blender",
        "comfyui",
        "chrome",
        "edge",
    ]
    .iter()
    .any(|needle| lower.contains(needle))
}

fn app_name_hint_from_window_title(title: &str) -> Option<String> {
    let title = title.trim().trim_start_matches('*').trim();
    if title.is_empty() {
        return None;
    }
    title
        .rsplit_once(" - ")
        .map(|(_, app)| app.trim().trim_start_matches('*').trim().to_string())
        .filter(|app| !app.is_empty())
}

fn app_name_hints_for_targets(candidates: &[String]) -> Vec<String> {
    let mut hints = Vec::new();
    for candidate in candidates {
        if let Some(app_name) = app_name_hint_from_window_title(candidate) {
            push_unique_window(&mut hints, app_name);
        }
        push_unique_window(
            &mut hints,
            candidate.trim_start_matches('*').trim().to_string(),
        );
    }
    hints
}

fn display_app_name_for_targets(candidates: &[String]) -> Option<String> {
    app_name_hints_for_targets(candidates)
        .into_iter()
        .find(|value| !value.trim().is_empty())
}

#[cfg(target_os = "windows")]
fn ensure_target_window_ready(candidates: &[String]) -> Result<String, String> {
    if let Ok(window_title) = focus_first_available_window(candidates) {
        return Ok(window_title);
    }
    if is_ableton_target(candidates) {
        return ensure_ableton_window_ready(candidates);
    }
    if let Ok(window_title) = focus_running_process_for_targets(candidates) {
        return Ok(window_title);
    }
    let app = launchable_app_for_targets(candidates).ok_or_else(|| {
        let app_name = display_app_name_for_targets(candidates)
            .unwrap_or_else(|| "the target app".to_string());
        format!("Could not find {app_name} — please open it manually and retry")
    })?;
    launch_app(&app)?;
    for _ in 0..12 {
        thread::sleep(Duration::from_millis(500));
        if let Ok(window_title) = focus_first_available_window(candidates) {
            return Ok(window_title);
        }
        if let Ok(window_title) = focus_running_process_for_targets(candidates) {
            return Ok(window_title);
        }
    }
    Err(format!(
        "Could not find {} — please open it manually and retry",
        app.display_name
    ))
}

#[cfg(target_os = "windows")]
fn ensure_ableton_window_ready(candidates: &[String]) -> Result<String, String> {
    if let Ok(window_title) = focus_running_process_for_targets(candidates) {
        return Ok(window_title);
    }
    let executable = find_ableton_live_executable()
        .ok_or_else(|| "Ableton Live not found. Please open it manually and retry.".to_string())?;
    write_debug_log(&format!(
        "Ableton launch: direct executable path found: {}",
        executable.display()
    ));
    let mut command = Command::new(&executable);
    no_window_command(&mut command)
        .spawn()
        .map_err(|error| {
            format!(
                "Could not launch Ableton Live directly from {}. Please open it manually and retry. ({error})",
                executable.display()
            )
        })?;
    for _ in 0..60 {
        thread::sleep(Duration::from_millis(500));
        if let Ok(window_title) = focus_first_available_window(candidates) {
            return Ok(window_title);
        }
        if let Ok(window_title) = focus_running_process_for_targets(candidates) {
            return Ok(window_title);
        }
    }
    Err("Ableton Live not found. Please open it manually and retry.".to_string())
}

#[cfg(not(target_os = "windows"))]
fn ensure_target_window_ready(candidates: &[String]) -> Result<String, String> {
    focus_first_available_window(candidates)
}

#[cfg(target_os = "windows")]
struct LaunchableApp {
    display_name: String,
    executable: String,
}

#[cfg(target_os = "windows")]
fn launchable_app_for_targets(candidates: &[String]) -> Option<LaunchableApp> {
    for app_name in app_name_hints_for_targets(candidates) {
        let lower = app_name.to_ascii_lowercase();
        if lower.contains("ableton") {
            continue;
        }
        if lower.contains("paint") {
            return Some(LaunchableApp {
                display_name: "Paint".to_string(),
                executable: "mspaint.exe".to_string(),
            });
        }
        if lower.contains("notepad++") {
            for path in [
                r"C:\Program Files\Notepad++\notepad++.exe",
                r"C:\Program Files (x86)\Notepad++\notepad++.exe",
            ] {
                if PathBuf::from(path).is_file() {
                    return Some(LaunchableApp {
                        display_name: "Notepad++".to_string(),
                        executable: path.to_string(),
                    });
                }
            }
        }
        if let Some(path) = find_matching_executable(&app_name) {
            return Some(LaunchableApp {
                display_name: app_name,
                executable: path,
            });
        }
    }
    None
}

fn is_ableton_target(candidates: &[String]) -> bool {
    candidates
        .iter()
        .any(|candidate| candidate.to_ascii_lowercase().contains("ableton live"))
}

#[cfg(target_os = "windows")]
fn find_ableton_live_executable() -> Option<PathBuf> {
    let roots = [
        PathBuf::from(r"C:\ProgramData\Ableton"),
        PathBuf::from(r"C:\Program Files\Ableton"),
        PathBuf::from(r"C:\Program Files (x86)\Ableton"),
    ];
    roots
        .iter()
        .filter(|root| root.is_dir())
        .find_map(find_ableton_live_executable_in_tree)
}

#[cfg(target_os = "windows")]
fn find_ableton_live_executable_in_tree(root: &PathBuf) -> Option<PathBuf> {
    let mut stack = vec![root.clone()];
    while let Some(dir) = stack.pop() {
        let Ok(entries) = std::fs::read_dir(&dir) else {
            continue;
        };
        for entry in entries.flatten() {
            let path = entry.path();
            if path.is_dir() {
                stack.push(path);
                continue;
            }
            let is_exe = path
                .extension()
                .and_then(|value| value.to_str())
                .map(|value| value.eq_ignore_ascii_case("exe"))
                .unwrap_or(false);
            if !is_exe {
                continue;
            }
            let file_name = path
                .file_name()
                .and_then(|value| value.to_str())
                .unwrap_or("")
                .to_ascii_lowercase();
            if file_name.contains("ableton live") {
                return Some(path);
            }
        }
    }
    None
}

#[cfg(target_os = "windows")]
fn launch_app(app: &LaunchableApp) -> Result<(), String> {
    if app
        .executable
        .to_ascii_lowercase()
        .ends_with("notepad++.exe")
    {
        let escaped_path = app.executable.replace('\'', "''");
        let script = format!(
            "Start-Process -FilePath '{}' -ArgumentList '-multiInst'",
            escaped_path
        );
        let mut command = Command::new("powershell.exe");
        command.args(["-NoProfile", "-Command", &script]);
        let output = no_window_command(&mut command).output().map_err(|error| {
            format!(
                "Could not launch {}. Please open it manually. ({error})",
                app.display_name
            )
        })?;
        if output.status.success() {
            return Ok(());
        }
        let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();
        return Err(format!(
            "Could not launch {}. Please open it manually. ({})",
            app.display_name,
            if stderr.is_empty() {
                "launcher returned a failure"
            } else {
                &stderr
            }
        ));
    }
    shell_execute(&app.executable).map_err(|error| {
        format!(
            "Could not launch {}. Please open it manually. ({error})",
            app.display_name
        )
    })
}

#[cfg(target_os = "windows")]
fn focus_running_process_for_targets(candidates: &[String]) -> Result<String, String> {
    for app_name in app_name_hints_for_targets(candidates) {
        let process_name = executable_stem_hint(&app_name);
        if process_name.is_empty() {
            continue;
        }
        let mut command = Command::new("powershell.exe");
        command.args([
            "-NoProfile",
            "-Command",
            "Get-Process | Where-Object { $_.MainWindowHandle -ne 0 -and $_.ProcessName -like $args[0] } | Select-Object -First 1 -ExpandProperty MainWindowTitle",
            &format!("*{process_name}*"),
        ]);
        let output = no_window_command(&mut command).output();
        let Ok(output) = output else {
            continue;
        };
        if !output.status.success() {
            continue;
        }
        let title = String::from_utf8_lossy(&output.stdout).trim().to_string();
        if title.is_empty() {
            continue;
        }
        if focus_target_window(&title).is_ok() {
            return Ok(title);
        }
    }
    Err("no matching running process with a visible window".to_string())
}

#[cfg(target_os = "windows")]
fn find_matching_executable(app_name: &str) -> Option<String> {
    let wanted = normalize_app_name(app_name);
    if wanted.is_empty() {
        return None;
    }
    let exact_exe = format!("{}.exe", executable_stem_hint(app_name));
    if command_exists(&exact_exe) {
        return Some(exact_exe);
    }

    let mut roots = Vec::new();
    for key in [
        "ProgramFiles",
        "ProgramFiles(x86)",
        "LOCALAPPDATA",
        "APPDATA",
    ] {
        if let Ok(path) = std::env::var(key) {
            push_unique_path(&mut roots, PathBuf::from(path));
        }
    }
    push_unique_path(&mut roots, PathBuf::from(r"C:\Program Files"));
    push_unique_path(&mut roots, PathBuf::from(r"C:\Program Files (x86)"));
    if let Ok(userprofile) = std::env::var("USERPROFILE") {
        push_unique_path(&mut roots, PathBuf::from(userprofile).join("AppData"));
    }

    for root in &roots {
        let direct = root.join(app_name.trim()).join(&exact_exe);
        if direct.is_file() {
            return Some(direct.display().to_string());
        }
    }

    let mut best: Option<String> = None;
    for root in roots {
        if let Some(path) = find_executable_in_tree(&root, &wanted, 40_000) {
            best = Some(path);
            break;
        }
    }
    best
}

#[cfg(target_os = "windows")]
fn push_unique_path(paths: &mut Vec<PathBuf>, path: PathBuf) {
    if !paths.iter().any(|existing| existing == &path) {
        paths.push(path);
    }
}

#[cfg(target_os = "windows")]
fn find_executable_in_tree(root: &PathBuf, wanted: &str, max_entries: usize) -> Option<String> {
    let mut stack = vec![root.clone()];
    let mut seen = 0usize;
    while let Some(dir) = stack.pop() {
        let Ok(entries) = std::fs::read_dir(&dir) else {
            continue;
        };
        for entry in entries.flatten() {
            seen += 1;
            if seen > max_entries {
                return None;
            }
            let path = entry.path();
            if path.is_dir() {
                stack.push(path);
                continue;
            }
            if path
                .extension()
                .and_then(|value| value.to_str())
                .map(|value| value.eq_ignore_ascii_case("exe"))
                != Some(true)
            {
                continue;
            }
            let stem = path
                .file_stem()
                .and_then(|value| value.to_str())
                .map(normalize_app_name)
                .unwrap_or_default();
            if stem == wanted || stem.contains(wanted) || wanted.contains(&stem) {
                return Some(path.display().to_string());
            }
        }
    }
    None
}

fn executable_stem_hint(app_name: &str) -> String {
    let lower = app_name.trim().trim_start_matches('*').to_ascii_lowercase();
    if lower.contains("notepad++") {
        "notepad++".to_string()
    } else if lower.contains("paint") {
        "mspaint".to_string()
    } else {
        app_name
            .trim()
            .trim_start_matches('*')
            .split_whitespace()
            .next()
            .unwrap_or("")
            .trim_matches(|ch: char| {
                !ch.is_ascii_alphanumeric() && ch != '+' && ch != '-' && ch != '_'
            })
            .to_string()
    }
}

fn normalize_app_name(value: &str) -> String {
    value
        .chars()
        .flat_map(char::to_lowercase)
        .filter(|ch| ch.is_ascii_alphanumeric() || *ch == '+')
        .collect()
}

#[cfg(target_os = "windows")]
fn focus_first_available_window(candidates: &[String]) -> Result<String, String> {
    let mut errors = Vec::new();
    for title in candidates {
        match focus_target_window(title) {
            Ok(()) => return Ok(title.clone()),
            Err(error) => errors.push(format!("{title}: {error}")),
        }
    }
    Err(errors.join("; "))
}

#[cfg(not(target_os = "windows"))]
fn focus_first_available_window(candidates: &[String]) -> Result<String, String> {
    Err(format!(
        "window focus is not implemented on this platform; tried {}",
        candidates.join(", ")
    ))
}

fn parse_gesture_workflow(name: &str) -> Option<Vec<RecordedEvent>> {
    let content = workflow_content(name)?;
    let frontmatter = frontmatter_block(&content)?;
    let routes_text = yaml_field_block(frontmatter, "routes")?;
    let routes: Value = serde_json::from_str(&routes_text).ok()?;
    for route in routes.as_array()? {
        if route.get("type").and_then(Value::as_str) == Some("gesture") {
            let events = route.get("events")?.clone();
            return serde_json::from_value(events).ok();
        }
    }
    None
}

fn parse_workflow_app_name(name: &str) -> Option<String> {
    let content = workflow_content(name)?;
    let frontmatter = frontmatter_block(&content)?;
    yaml_scalar_field(frontmatter, "app")
}

fn workflow_content(name: &str) -> Option<String> {
    let path = vault_workflows_dir().join(format!("{name}.md"));
    std::fs::read_to_string(path).ok()
}

fn frontmatter_block(content: &str) -> Option<&str> {
    let mut parts = content.splitn(3, "---");
    if !parts.next()?.trim().is_empty() {
        return None;
    }
    parts.next()
}

fn yaml_field_block(frontmatter: &str, field: &str) -> Option<String> {
    let prefix = format!("{field}:");
    let mut collecting = false;
    let mut lines = Vec::new();
    for line in frontmatter.lines() {
        if collecting {
            if is_top_level_yaml_field(line) {
                break;
            }
            lines.push(line.to_string());
            continue;
        }
        if let Some(rest) = line.strip_prefix(&prefix) {
            collecting = true;
            let rest = rest.trim();
            if !rest.is_empty() {
                lines.push(rest.to_string());
            }
        }
    }
    if lines.is_empty() {
        None
    } else {
        Some(lines.join("\n"))
    }
}

fn yaml_scalar_field(frontmatter: &str, field: &str) -> Option<String> {
    let prefix = format!("{field}:");
    for line in frontmatter.lines() {
        let Some(rest) = line.strip_prefix(&prefix) else {
            continue;
        };
        let value = rest.trim();
        if value.is_empty() {
            return None;
        }
        if let Ok(parsed) = serde_json::from_str::<String>(value) {
            return Some(parsed);
        }
        return Some(value.trim_matches('"').trim_matches('\'').to_string());
    }
    None
}

fn is_top_level_yaml_field(line: &str) -> bool {
    if line.is_empty() || line.starts_with(char::is_whitespace) {
        return false;
    }
    line.split_once(':')
        .map(|(key, _)| {
            !key.is_empty()
                && key
                    .chars()
                    .all(|ch| ch.is_ascii_alphanumeric() || ch == '_' || ch == '-')
        })
        .unwrap_or(false)
}

#[cfg(target_os = "windows")]
fn focus_target_window(window_title: &str) -> Result<(), String> {
    let hwnd = find_window_containing(window_title)
        .ok_or_else(|| format!("no visible top-level window contains '{window_title}'"))?;
    unsafe {
        let _ = ShowWindow(hwnd, SW_SHOWNORMAL);
        thread::sleep(Duration::from_millis(120));
        if SetForegroundWindow(hwnd).as_bool() {
            Ok(())
        } else if send_key(VK_MENU).is_ok() && SetForegroundWindow(hwnd).as_bool() {
            Ok(())
        } else {
            Err("SetForegroundWindow returned false".to_string())
        }
    }
}

#[cfg(target_os = "windows")]
struct WindowSearch {
    needles: Vec<String>,
    hwnd: Option<HWND>,
}

#[cfg(target_os = "windows")]
fn find_window_containing(target: &str) -> Option<HWND> {
    let target = target.trim();
    if target.is_empty() {
        return None;
    }
    let mut needles = vec![target.to_ascii_lowercase()];
    if let Some((_, app_hint)) = target.rsplit_once(" - ") {
        let app_hint = app_hint.trim().to_ascii_lowercase();
        if !app_hint.is_empty() && !needles.iter().any(|needle| needle == &app_hint) {
            needles.push(app_hint);
        }
    }
    let mut search = WindowSearch {
        needles,
        hwnd: None,
    };
    unsafe {
        let search_ptr = &mut search as *mut WindowSearch;
        let _ = EnumWindows(Some(enum_windows_match_title), LPARAM(search_ptr as isize));
    }
    search.hwnd
}

#[cfg(target_os = "windows")]
unsafe extern "system" fn enum_windows_match_title(hwnd: HWND, lparam: LPARAM) -> BOOL {
    let search = &mut *(lparam.0 as *mut WindowSearch);
    if !IsWindowVisible(hwnd).as_bool() {
        return true.into();
    }
    let mut buffer = [0u16; 512];
    let len = GetWindowTextW(hwnd, &mut buffer);
    if len <= 0 {
        return true.into();
    }
    let title = String::from_utf16_lossy(&buffer[..len as usize]).to_ascii_lowercase();
    if search.needles.iter().any(|needle| title.contains(needle)) {
        search.hwnd = Some(hwnd);
        return false.into();
    }
    true.into()
}

#[cfg(not(target_os = "windows"))]
fn focus_target_window(_: &str) -> Result<(), String> {
    Err("window focus is not implemented on this platform".to_string())
}

fn replay_python_command() -> &'static str {
    if command_exists("python") {
        "python"
    } else {
        "python3"
    }
}

fn command_exists(command: &str) -> bool {
    let mut command = Command::new(command);
    command.arg("--version");
    no_window_command(&mut command)
        .output()
        .map(|output| output.status.success())
        .unwrap_or(false)
}

fn delete_saved_workflow(payload: ReplayWorkflowRequest) -> (Value, u16) {
    let name = match safe_workflow_name(&payload.name) {
        Ok(name) => name,
        Err(error) => return (json!({"status": "failed", "error": error}), 400),
    };
    let path = vault_workflows_dir().join(format!("{name}.md"));
    match std::fs::remove_file(&path) {
        Ok(_) => (json!({"status": "deleted", "name": name}), 200),
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => (
            json!({"status": "failed", "error": "workflow not found"}),
            404,
        ),
        Err(error) => (
            json!({"status": "failed", "error": format!("failed to delete workflow: {error}")}),
            500,
        ),
    }
}

fn safe_workflow_name(value: &str) -> Result<String, String> {
    let name = value.trim();
    if name.is_empty()
        || !name
            .chars()
            .all(|ch| ch.is_ascii_alphanumeric() || ch == '-' || ch == '_')
    {
        Err("workflow name must contain only letters, numbers, hyphen, or underscore".to_string())
    } else {
        Ok(name.to_string())
    }
}

fn format_modified_time(path: &PathBuf, modified: SystemTime) -> String {
    let mut command = Command::new("powershell.exe");
    command.args([
        "-NoProfile",
        "-Command",
        "(Get-Item -LiteralPath $args[0]).LastWriteTime.ToString('yyyy-MM-dd HH:mm')",
        &path.display().to_string(),
    ]);
    let output = no_window_command(&mut command).output();
    if let Ok(output) = output {
        if output.status.success() {
            let value = String::from_utf8_lossy(&output.stdout).trim().to_string();
            if !value.is_empty() {
                return value;
            }
        }
    }
    let seconds = modified
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_secs())
        .unwrap_or(0);
    format!("unix-{seconds}")
}

fn is_authorized(request: &tiny_http::Request, token: &str) -> bool {
    let expected = format!("Bearer {}", token);
    request
        .headers()
        .iter()
        .any(|header| header.field.equiv("Authorization") && header.value.as_str() == expected)
}

fn read_json<T: for<'de> Deserialize<'de>>(request: &mut tiny_http::Request) -> T {
    let mut body = String::new();
    let _ = request.as_reader().read_to_string(&mut body);
    serde_json::from_str(&body).unwrap_or_else(|_| serde_json::from_value(json!({})).unwrap())
}

fn json_response(value: Value, status: u16) -> Response<std::io::Cursor<Vec<u8>>> {
    cors_response(value, status)
}

fn cors_response(value: Value, status: u16) -> Response<std::io::Cursor<Vec<u8>>> {
    let body = serde_json::to_vec(&value).unwrap_or_else(|_| b"{}".to_vec());
    let content_type = Header::from_bytes("Content-Type", "application/json").unwrap();
    let allow_origin = Header::from_bytes("Access-Control-Allow-Origin", "*").unwrap();
    let allow_methods =
        Header::from_bytes("Access-Control-Allow-Methods", "GET, POST, OPTIONS").unwrap();
    let allow_headers = Header::from_bytes(
        "Access-Control-Allow-Headers",
        "Authorization, Content-Type",
    )
    .unwrap();
    Response::from_data(body)
        .with_status_code(StatusCode(status))
        .with_header(content_type)
        .with_header(allow_origin)
        .with_header(allow_methods)
        .with_header(allow_headers)
}

fn find_uia(payload: UiaRequest) -> (Value, u16) {
    find_uia_impl(payload)
}

fn click_uia(payload: UiaRequest) -> (Value, u16) {
    click_uia_impl(payload)
}

fn screenshot(payload: ScreenshotRequest) -> Value {
    json!({
        "ok": true,
        "format": "png",
        "path": null,
        "region": {
            "x": payload.x.unwrap_or(0),
            "y": payload.y.unwrap_or(0),
            "width": payload.width.unwrap_or(0),
            "height": payload.height.unwrap_or(0)
        }
    })
}

#[cfg(target_os = "windows")]
fn replay_mouse(payload: MouseReplayRequest) -> (Value, u16) {
    let replay_rect = active_window_rect();
    if let Some(rect) = replay_rect.as_ref() {
        write_debug_log(&format!(
            "live replay rect: {}",
            format_window_rect(Some(rect))
        ));
    }
    let mut replayed = 0usize;
    let mut skipped_toolbar_mousedown = false;
    let mut skipped_uia_mousedown = false;
    let mut left_button_down = false;
    let mut ableton_note_grid_mouse_down = false;
    let mut ableton_added_devices: Vec<String> = Vec::new();
    let mut logged_first_canvas_mousemove = false;
    let replay_events: Vec<&RecordedEvent> = payload
        .events
        .iter()
        .filter(|e| {
            matches!(
                e.kind.as_str(),
                "mousemove"
                    | "mousedown"
                    | "mouseup"
                    | "keydown"
                    | "keyup"
                    | "note_on"
                    | "note_off"
            )
        })
        .collect();
    let profile_window_title = payload
        .target_window
        .as_deref()
        .or_else(|| {
            payload
                .events
                .iter()
                .find_map(|event| event.window_title.as_deref())
        })
        .unwrap_or("");
    let app_profile = route_switcher::load_app_profile(profile_window_title);
    if let Some(profile) = app_profile.as_ref() {
        write_debug_log(&format!(
            "route switcher profile loaded: app={} title_fragment={}",
            profile.app_name, profile.title_fragment
        ));
    } else {
        write_debug_log(&format!(
            "route switcher profile not found for title={profile_window_title:?}; using coordinates"
        ));
    }
    let mut index = 0usize;
    while index < replay_events.len() {
        let event = replay_events[index];
        let event_type =
            classifier::classify_event(&payload.events, source_event_index(&payload.events, event));
        let selected_route =
            route_switcher::select_route_for_event(&event_type, event, app_profile.as_ref());
        write_debug_log(&format!(
            "route decision: event_index={} event_type={} route={} element_name={:?}",
            index,
            route_switcher::event_type_key(&event_type),
            route_debug_name(&selected_route),
            event.element_name
        ));
        if let route_switcher::Route::Api(endpoint) = &selected_route {
            write_debug_log(&format!(
                "API route planned for {} endpoint={} - falling back to coordinates",
                app_profile
                    .as_ref()
                    .map(|profile| profile.app_name.as_str())
                    .unwrap_or("unknown app"),
                endpoint
            ));
        }
        if matches!(
            event.kind.as_str(),
            "keydown" | "keyup" | "note_on" | "note_off"
        ) {
            if let Some(target) = payload
                .target_window
                .as_deref()
                .filter(|_| !is_ableton_event(event))
            {
                let _ = focus_target_window(target);
            }
            let keyboard_result = if is_ableton_event(event) {
                replay_keyboard_event(event)
            } else {
                match &selected_route {
                    route_switcher::Route::KeyboardShortcut(keys) if event.kind == "keydown" => {
                        send_shortcut_keys(keys)
                    }
                    _ => replay_keyboard_event(event),
                }
            };
            if keyboard_result.is_ok() {
                replayed += 1;
            }
            thread::sleep(replay_event_delay(
                event,
                replay_events.get(index + 1).copied(),
            ));
            index += 1;
            continue;
        }
        if event.kind == "mousemove"
            && normalized_event_outside_window(event)
            && !(left_button_down && is_ableton_event(event))
        {
            index += 1;
            continue;
        }
        if skipped_toolbar_mousedown && event.kind == "mouseup" {
            skipped_toolbar_mousedown = false;
            ableton_note_grid_mouse_down = false;
            thread::sleep(replay_event_delay(
                event,
                replay_events.get(index + 1).copied(),
            ));
            index += 1;
            continue;
        }
        if skipped_uia_mousedown && event.kind == "mouseup" {
            skipped_uia_mousedown = false;
            ableton_note_grid_mouse_down = false;
            thread::sleep(replay_event_delay(
                event,
                replay_events.get(index + 1).copied(),
            ));
            index += 1;
            continue;
        }
        if left_button_down
            && event.kind == "mousedown"
            && event.normalized_y.map(|y| y < 0.15).unwrap_or(false)
        {
            skipped_toolbar_mousedown = true;
            index += 1;
            continue;
        }
        if event.kind == "mouseup" {
            skipped_toolbar_mousedown = false;
            skipped_uia_mousedown = false;
        }
        let (x, y) = if is_ableton_event(event) {
            resolve_ableton_replay_point_with_note_context(
                event,
                replay_rect.as_ref(),
                ableton_note_grid_mouse_down,
            )
        } else {
            resolve_replay_point(event, replay_rect.as_ref())
        };
        if event.kind == "mousedown" {
            write_debug_log(&format!(
                "mousedown: stored_x={:?} stored_y={:?} normalized_x={:?} normalized_y={:?} resolution_rect={} resolved_x={} resolved_y={}",
                event.x,
                event.y,
                event.normalized_x,
                event.normalized_y,
                format_window_rect(replay_rect.as_ref()),
                x,
                y
            ));
            if !left_button_down && is_ableton_event(event) {
                if let Some(up_index) = replay_ableton_group_tracks_if_present(
                    &replay_events,
                    index,
                    replay_rect.as_ref(),
                ) {
                    replayed += up_index - index + 1;
                    thread::sleep(replay_event_delay(
                        replay_events[up_index],
                        replay_events.get(up_index + 1).copied(),
                    ));
                    index = up_index + 1;
                    continue;
                }
                if let Some(up_index) = replay_ableton_double_click_if_present(
                    &replay_events,
                    index,
                    replay_rect.as_ref(),
                ) {
                    replayed += 4;
                    thread::sleep(replay_event_delay(
                        replay_events[up_index],
                        replay_events.get(up_index + 1).copied(),
                    ));
                    index = up_index + 1;
                    continue;
                }
                if let Some(up_index) = replay_ableton_search_segment_if_present(
                    &replay_events,
                    index,
                    replay_rect.as_ref(),
                ) {
                    replayed += up_index - index + 1;
                    thread::sleep(replay_event_delay(
                        replay_events[up_index],
                        replay_events.get(up_index + 1).copied(),
                    ));
                    index = up_index + 1;
                    continue;
                }
                if let Some(up_index) = replay_ableton_instrument_drag_if_present(
                    &replay_events,
                    index,
                    replay_rect.as_ref(),
                ) {
                    replayed += up_index - index + 1;
                    thread::sleep(replay_event_delay(
                        replay_events[up_index],
                        replay_events.get(up_index + 1).copied(),
                    ));
                    index = up_index + 1;
                    continue;
                }
                if let Some((up_index, device_name)) = replay_ableton_device_drag_if_present(
                    &replay_events,
                    index,
                    replay_rect.as_ref(),
                    &ableton_added_devices,
                ) {
                    ableton_added_devices.push(device_name);
                    replayed += up_index - index + 1;
                    thread::sleep(replay_event_delay(
                        replay_events[up_index],
                        replay_events.get(up_index + 1).copied(),
                    ));
                    index = up_index + 1;
                    continue;
                }
                if let Some(up_index) =
                    replay_ableton_drag_if_present(&replay_events, index, replay_rect.as_ref())
                {
                    replayed += up_index - index + 1;
                    thread::sleep(replay_event_delay(
                        replay_events[up_index],
                        replay_events.get(up_index + 1).copied(),
                    ));
                    index = up_index + 1;
                    continue;
                }
            }
            if !left_button_down
                && matches!(selected_route, route_switcher::Route::UIA)
                && try_uia_named_mousedown(event)
            {
                skipped_uia_mousedown = true;
                replayed += 1;
                thread::sleep(replay_event_delay(
                    event,
                    replay_events.get(index + 1).copied(),
                ));
                index += 1;
                continue;
            }
            if !left_button_down && is_fill_canvas_click(event) {
                if let Some(up_index) = matching_mouseup_index(&replay_events, index) {
                    let up_event = replay_events[up_index];
                    let (up_x, up_y) = resolve_replay_point(up_event, replay_rect.as_ref());
                    write_debug_log(&format!(
                        "fill click segment: down_index={index} up_index={up_index} resolved_down=({x},{y}) resolved_up=({up_x},{up_y})"
                    ));
                    send_absolute_mouse_input(x, y, MOUSEEVENTF_MOVE | MOUSEEVENTF_LEFTDOWN);
                    replayed += 1;
                    thread::sleep(replay_event_delay(event, Some(up_event)));
                    send_absolute_mouse_input(up_x, up_y, MOUSEEVENTF_MOVE | MOUSEEVENTF_LEFTUP);
                    replayed += 1;
                    thread::sleep(replay_event_delay(
                        up_event,
                        replay_events.get(up_index + 1).copied(),
                    ));
                    index = up_index + 1;
                    continue;
                }
            }
            if !left_button_down && is_shape_canvas_drag(event) {
                if let Some(up_index) = matching_mouseup_index(&replay_events, index) {
                    let up_event = replay_events[up_index];
                    if normalized_distance(event, up_event)
                        .map(|distance| distance > 0.03)
                        .unwrap_or(true)
                    {
                        let endpoint =
                            last_mousemove_before_mouseup(&replay_events, index, up_index)
                                .unwrap_or(up_event);
                        let (end_x, end_y) = resolve_replay_point(endpoint, replay_rect.as_ref());
                        let (up_x, up_y) = resolve_replay_point(up_event, replay_rect.as_ref());
                        write_debug_log(&format!(
                            "shape drag segment: down_index={index} up_index={up_index} endpoint=({end_x},{end_y}) up=({up_x},{up_y})"
                        ));
                        send_absolute_mouse_input(x, y, MOUSEEVENTF_MOVE | MOUSEEVENTF_LEFTDOWN);
                        replayed += 1;
                        thread::sleep(replay_event_delay(event, Some(endpoint)));
                        send_absolute_mousemove(end_x, end_y);
                        replayed += 1;
                        thread::sleep(replay_event_delay(endpoint, Some(up_event)));
                        send_absolute_mouse_input(
                            up_x,
                            up_y,
                            MOUSEEVENTF_MOVE | MOUSEEVENTF_LEFTUP,
                        );
                        replayed += 1;
                        thread::sleep(replay_event_delay(
                            up_event,
                            replay_events.get(up_index + 1).copied(),
                        ));
                        index = up_index + 1;
                        continue;
                    }
                }
            }
        } else if !logged_first_canvas_mousemove && event.kind == "mousemove" && left_button_down {
            logged_first_canvas_mousemove = true;
            write_debug_log(&format!(
                "first canvas mousemove: stored_x={:?} stored_y={:?} normalized_x={:?} normalized_y={:?} resolution_rect={} resolved_x={} resolved_y={}",
                event.x,
                event.y,
                event.normalized_x,
                event.normalized_y,
                format_window_rect(replay_rect.as_ref()),
                x,
                y
            ));
        }

        match (
            event.kind.as_str(),
            event.button.as_deref().unwrap_or("left"),
        ) {
            ("mousemove", _) if left_button_down => send_absolute_mousemove(x, y),
            ("mousemove", _) => send_absolute_mouse_input(x, y, MOUSEEVENTF_MOVE),
            ("mousedown", "right") => {
                send_absolute_mouse_input(x, y, MOUSEEVENTF_MOVE | MOUSEEVENTF_RIGHTDOWN);
            }
            ("mouseup", "right") => {
                send_absolute_mouse_input(x, y, MOUSEEVENTF_MOVE | MOUSEEVENTF_RIGHTUP);
            }
            ("mousedown", _) => {
                left_button_down = true;
                ableton_note_grid_mouse_down = is_ableton_piano_roll_note_event(event);
                if is_ableton_event(event) {
                    send_ableton_mousemove(x, y);
                    thread::sleep(Duration::from_millis(8));
                    send_ableton_leftdown(x, y);
                } else {
                    send_absolute_mouse_input(x, y, MOUSEEVENTF_MOVE | MOUSEEVENTF_LEFTDOWN);
                }
            }
            ("mouseup", _) => {
                if is_ableton_event(event) {
                    send_ableton_mousemove(x, y);
                    thread::sleep(Duration::from_millis(8));
                    send_ableton_leftup(x, y);
                    if is_ableton_automation_record_event(event) {
                        write_debug_log(
                            "ableton automation record pressed: waiting 500ms for automation mode",
                        );
                        thread::sleep(Duration::from_millis(500));
                    }
                } else {
                    send_absolute_mouse_input(x, y, MOUSEEVENTF_MOVE | MOUSEEVENTF_LEFTUP);
                }
                left_button_down = false;
                ableton_note_grid_mouse_down = false;
            }
            _ => {}
        }
        replayed += 1;
        thread::sleep(replay_event_delay(
            event,
            replay_events.get(index + 1).copied(),
        ));
        index += 1;
    }
    (
        json!({"ok": true, "replayed": replayed, "target_window": payload.target_window}),
        200,
    )
}

fn is_fill_canvas_click(event: &RecordedEvent) -> bool {
    let name = event
        .element_name
        .as_deref()
        .unwrap_or("")
        .to_ascii_lowercase();
    name.contains("fill") && name.contains("canvas")
}

fn is_shape_canvas_drag(event: &RecordedEvent) -> bool {
    let name = event
        .element_name
        .as_deref()
        .unwrap_or("")
        .to_ascii_lowercase();
    name.contains("canvas")
        && (name.contains("shape")
            || name.contains("oval")
            || name.contains("ellipse")
            || name.contains("rectangle")
            || name.contains("line")
            || name.contains("arrow"))
}

fn matching_mouseup_index(events: &[&RecordedEvent], start: usize) -> Option<usize> {
    events
        .iter()
        .enumerate()
        .skip(start + 1)
        .find_map(|(index, event)| (event.kind == "mouseup").then_some(index))
}

fn last_mousemove_before_mouseup<'a>(
    events: &'a [&'a RecordedEvent],
    start: usize,
    up_index: usize,
) -> Option<&'a RecordedEvent> {
    events[start + 1..up_index]
        .iter()
        .rev()
        .copied()
        .find(|event| event.kind == "mousemove")
}

fn normalized_distance(start: &RecordedEvent, end: &RecordedEvent) -> Option<f64> {
    let dx = end.normalized_x? - start.normalized_x?;
    let dy = end.normalized_y? - start.normalized_y?;
    Some((dx * dx + dy * dy).sqrt())
}

#[cfg(target_os = "windows")]
fn replay_ableton_double_click_if_present(
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
fn replay_ableton_drag_if_present(
    events: &[&RecordedEvent],
    start: usize,
    rect: Option<&WindowRect>,
) -> Option<usize> {
    replay_ableton_drag_segment(events, start, rect, Duration::from_millis(30))
}

#[cfg(target_os = "windows")]
fn replay_ableton_drag_segment(
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
fn replay_ableton_instrument_drag_if_present(
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
fn replay_ableton_group_tracks_if_present(
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

fn recent_ableton_shift_track_selection(events: &[&RecordedEvent], start: usize) -> bool {
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

fn upcoming_ableton_search_text(events: &[&RecordedEvent], start: usize, expected: &str) -> bool {
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

fn ableton_preset_name(event: &RecordedEvent) -> Option<String> {
    event
        .element_name
        .as_deref()
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .map(str::to_string)
}

fn is_ableton_instrument_preset_name(name: &str) -> bool {
    let lower = name.to_ascii_lowercase();
    lower.ends_with(".adv") || lower.ends_with(".adg")
}

fn ableton_browser_category_for_preset(name: &str) -> Option<&'static str> {
    if is_ableton_instrument_preset_name(name) {
        Some("Instruments")
    } else {
        None
    }
}

fn ableton_recorded_browser_category(events: &[&RecordedEvent], start: usize) -> Option<String> {
    let begin = start.saturating_sub(120);
    events[begin..start]
        .iter()
        .rev()
        .filter(|event| event.kind == "mousedown")
        .filter_map(|event| event.element_name.as_deref().map(str::trim))
        .find(|name| ableton_browser_category_name(name))
        .map(str::to_string)
}

fn ableton_browser_category_name(name: &str) -> bool {
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
fn verify_ableton_browser_source_point(
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

fn ableton_browser_item_name_matches(expected: &str, actual: &str) -> bool {
    let expected = expected.trim();
    let actual = actual.trim();
    if expected.eq_ignore_ascii_case(actual) {
        return true;
    }
    browser_item_stem(expected).eq_ignore_ascii_case(&browser_item_stem(actual))
}

fn browser_item_stem(value: &str) -> String {
    let trimmed = value.trim();
    let lower = trimmed.to_ascii_lowercase();
    for suffix in [".adv", ".adg", ".amxd", ".vst3", ".dll"] {
        if lower.ends_with(suffix) {
            return trimmed[..trimmed.len() - suffix.len()].to_string();
        }
    }
    trimmed.to_string()
}

fn ableton_next_browser_row_point(x: i32, rect: &WindowRect) -> (i32, i32) {
    let row_height = rect.height.abs().max(1);
    (x, rect.top + (rect.height / 2) + row_height)
}

#[cfg(target_os = "windows")]
fn replay_ableton_device_drag_if_present(
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

fn ableton_device_name(event: &RecordedEvent) -> Option<String> {
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

fn ableton_target_channel_for_device_drag(
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

fn ableton_is_device_name(name: &str) -> bool {
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

fn ableton_browser_category_for_device(name: &str) -> Option<&'static str> {
    if ableton_is_device_name(name) {
        Some("Audio Effects")
    } else {
        None
    }
}

#[cfg(target_os = "windows")]
fn verify_ableton_devices_present(devices: &[String], window_title: Option<&str>) {
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
fn locate_ableton_preset_with_scroll(
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
fn scroll_ableton_browser_near_recorded_source(
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
fn replay_ableton_drag_from_source(
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
fn replay_ableton_search_segment_if_present(
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

fn compact_click_mouseup_index(events: &[&RecordedEvent], start: usize) -> Option<usize> {
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
fn replay_keyboard_event(event: &RecordedEvent) -> Result<(), String> {
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

fn vk_from_recorded_key(value: &str) -> Result<u16, String> {
    if let Ok(key) = value.parse::<u16>() {
        return Ok(key);
    }
    let trimmed = value.trim();
    if trimmed.len() == 1 {
        let byte = trimmed.as_bytes()[0];
        if byte.is_ascii_alphanumeric() {
            return Ok(byte.to_ascii_uppercase() as u16);
        }
    }
    Err(format!("invalid keyboard key: {value}"))
}

#[cfg(not(target_os = "windows"))]
fn replay_keyboard_event(_: &RecordedEvent) -> Result<(), String> {
    Err("keyboard replay not implemented on this platform".to_string())
}

#[cfg(target_os = "windows")]
fn try_uia_named_mousedown(event: &RecordedEvent) -> bool {
    if is_ableton_event(event) {
        return false;
    }
    let Some(name) = event
        .element_name
        .as_deref()
        .map(str::trim)
        .filter(|value| !value.is_empty())
    else {
        return false;
    };
    let lower_name = name.to_lowercase();
    if lower_name.contains("canvas") || lower_name.starts_with("using ") {
        return false;
    }
    let name = name.to_string();
    let window_title = event.window_title.clone();
    let (sender, receiver) = mpsc::channel();
    let worker_name = name.clone();
    thread::spawn(move || {
        let result = invoke_or_click_uia_element_by_name(&worker_name, window_title.as_deref());
        let _ = sender.send(result);
    });
    match receiver.recv_timeout(Duration::from_millis(500)) {
        Ok(Ok(())) => {
            write_debug_log(&format!(
                "uia invoke/click succeeded: element_name={name:?}"
            ));
            true
        }
        Ok(Err(error)) => {
            write_debug_log(&format!(
                "uia invoke/click failed: element_name={name:?} error={error}"
            ));
            false
        }
        Err(_) => {
            write_debug_log(&format!(
                "uia invoke/click timed out: element_name={name:?}"
            ));
            false
        }
    }
}

#[cfg(not(target_os = "windows"))]
fn try_uia_named_mousedown(_: &RecordedEvent) -> bool {
    false
}

fn is_ableton_event(event: &RecordedEvent) -> bool {
    event
        .window_title
        .as_deref()
        .map(title_is_ableton)
        .unwrap_or(false)
        || event
            .app_name
            .as_deref()
            .map(title_is_ableton)
            .unwrap_or(false)
}

fn title_is_ableton(value: &str) -> bool {
    value.to_ascii_lowercase().contains("ableton live")
}

fn add_semantic_tag(event: &mut RecordedEvent, tag: impl Into<String>) {
    let tag = tag.into();
    let tag = tag.trim();
    if tag.is_empty() {
        return;
    }
    let mut tags: Vec<String> = event
        .semantic
        .as_deref()
        .unwrap_or("")
        .split(';')
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .map(str::to_string)
        .collect();
    if !tags.iter().any(|value| value.eq_ignore_ascii_case(tag)) {
        tags.push(tag.to_string());
    }
    event.semantic = (!tags.is_empty()).then(|| tags.join(";"));
}

fn semantic_tag_value<'a>(event: &'a RecordedEvent, prefix: &str) -> Option<&'a str> {
    event
        .semantic
        .as_deref()
        .unwrap_or("")
        .split(';')
        .map(str::trim)
        .find_map(|tag| tag.strip_prefix(prefix).map(str::trim))
        .filter(|value| !value.is_empty())
}

fn enrich_ableton_recorded_event(event: &mut RecordedEvent, _screen_y: i32) {
    if !is_ableton_event(event) {
        return;
    }
    let Some(name) = event
        .element_name
        .as_deref()
        .map(str::trim)
        .map(str::to_string)
    else {
        return;
    };
    if name.is_empty() {
        return;
    }
    if ableton_browser_category_name(&name) {
        add_semantic_tag(event, format!("browser_category:{name}"));
    }
    if ableton_is_device_name(&name) {
        add_semantic_tag(event, format!("device:{name}"));
    }
    if let Some(channel) = ableton_channel_from_element_name(&name) {
        add_semantic_tag(event, format!("channel:{channel}"));
    }
    if ableton_is_automation_record_name(&name) {
        add_semantic_tag(event, "automation_record");
    }
    if ableton_is_automation_parameter_name(&name) {
        add_semantic_tag(event, format!("automation_parameter:{name}"));
    }
}

fn ableton_channel_from_element_name(name: &str) -> Option<String> {
    let lower = name.to_ascii_lowercase();
    if lower.contains("master") || lower.contains("main") {
        return Some("Master".to_string());
    }
    for marker in ["in track ", "track "] {
        if let Some(after) = lower
            .find(marker)
            .and_then(|index| name.get(index + marker.len()..))
        {
            let channel = after
                .split([',', ';'])
                .next()
                .unwrap_or(after)
                .trim()
                .trim_matches('"');
            if !channel.is_empty() {
                return Some(channel.to_string());
            }
        }
    }
    None
}

fn ableton_is_automation_record_name(name: &str) -> bool {
    let lower = name.to_ascii_lowercase();
    lower == "arrangement record"
        || lower == "session record"
        || lower.contains("automation arm")
        || lower.contains("automation record")
}

fn ableton_is_automation_parameter_name(name: &str) -> bool {
    let lower = name.to_ascii_lowercase();
    lower.contains("send")
        || lower.contains("reverb")
        || lower.contains("delay")
        || lower.contains("frequency")
        || lower.contains("resonance")
        || lower.contains("gain")
        || lower.contains("threshold")
        || lower.contains("output")
        || lower.starts_with("a-")
        || lower.starts_with("b-")
}

#[cfg(target_os = "windows")]
fn ableton_midi_note_name_at_point_with_timeout(
    window_title: Option<&str>,
    x: i32,
    y: i32,
    timeout_ms: u64,
) -> Result<String, String> {
    let (sender, receiver) = mpsc::channel();
    let worker_window_title = window_title.map(str::to_string);
    thread::spawn(move || {
        let result = ableton_midi_note_name_at_point(worker_window_title.as_deref(), x, y);
        let _ = sender.send(result);
    });
    match receiver.recv_timeout(Duration::from_millis(timeout_ms)) {
        Ok(result) => result,
        Err(_) => Err(format!(
            "Ableton MIDI note UIA lookup timed out after {timeout_ms}ms"
        )),
    }
}

#[cfg(target_os = "windows")]
fn ableton_midi_note_name_at_point(
    window_title: Option<&str>,
    x: i32,
    y: i32,
) -> Result<String, String> {
    let payload = UiaRequest {
        name: None,
        role: None,
        window_title: window_title.map(str::to_string),
        x: Some(x),
        y: Some(y),
    };
    if let Ok((element, _)) = find_uia_element(&payload) {
        for name in uia_element_names(&element) {
            if ableton_note_name_is_row_label(&name) {
                return Ok(name);
            }
        }
    }
    ableton_pitch_label_near_y(window_title, y).map(|(pitch, _)| pitch)
}

#[cfg(not(target_os = "windows"))]
fn ableton_midi_note_name_at_point_with_timeout(
    _: Option<&str>,
    _: i32,
    _: i32,
    _: u64,
) -> Result<String, String> {
    Err("Ableton MIDI note lookup not implemented on this platform".to_string())
}

fn ableton_note_name_is_row_label(name: &str) -> bool {
    let lower = name.trim().to_ascii_lowercase();
    if lower.is_empty() || lower.contains("untitled clip") || lower.contains("scene ") {
        return false;
    }
    first_pitch_token(name).is_some()
        || [
            "bass drum",
            "kick",
            "snare",
            "closed hi hat",
            "open hi hat",
            "crash",
            "ride",
            "tom",
            "clap",
            "rim",
            "cowbell",
        ]
        .iter()
        .any(|needle| lower.contains(needle))
}

fn source_event_index(events: &[RecordedEvent], target: &RecordedEvent) -> usize {
    events
        .iter()
        .position(|event| std::ptr::eq(event, target))
        .unwrap_or(0)
}

fn route_debug_name(route: &route_switcher::Route) -> String {
    match route {
        route_switcher::Route::UIA => "uia".to_string(),
        route_switcher::Route::KeyboardShortcut(keys) => format!("shortcut({keys})"),
        route_switcher::Route::Coordinates => "coordinates".to_string(),
        route_switcher::Route::Api(endpoint) => format!("api({endpoint})"),
    }
}

#[cfg(target_os = "windows")]
fn invoke_or_click_uia_element_by_name(
    name: &str,
    window_title: Option<&str>,
) -> Result<(), String> {
    unsafe {
        let automation =
            create_uia().map_err(|error| format!("failed to start UIAutomation: {error}"))?;
        let hwnd = target_hwnd(window_title);
        if hwnd.0.is_null() {
            return Err("no active window".to_string());
        }
        let root = automation
            .ElementFromHandle(hwnd)
            .map_err(|error| format!("failed to read focused window UIA tree: {error}"))?;
        let element = find_uia_element_by_name(&automation, &root, name)
            .ok_or_else(|| format!("UIA element named '{name}' not found"))?;

        let mut point = POINT { x: 0, y: 0 };
        match element.GetClickablePoint(&mut point) {
            Ok(got_clickable) if got_clickable.as_bool() => {
                SetCursorPos(point.x, point.y).map_err(|error| {
                    format!("failed to move cursor to UIA element '{name}': {error}")
                })?;
                send_recordable_left_click(point.x, point.y);
                Ok(())
            }
            Ok(_) => invoke_uia_element(&element, name),
            Err(_) => invoke_uia_element(&element, name),
        }
    }
}

#[cfg(target_os = "windows")]
fn click_uia_name_with_timeout(
    name: &str,
    window_title: Option<&str>,
    timeout_ms: u64,
) -> Result<(), String> {
    let (sender, receiver) = mpsc::channel();
    let worker_name = name.to_string();
    let worker_window_title = window_title.map(str::to_string);
    thread::spawn(move || {
        let result =
            invoke_or_click_uia_element_by_name(&worker_name, worker_window_title.as_deref());
        let _ = sender.send(result);
    });
    match receiver.recv_timeout(Duration::from_millis(timeout_ms)) {
        Ok(result) => result,
        Err(_) => Err(format!("UIA click timed out after {timeout_ms}ms")),
    }
}

#[cfg(target_os = "windows")]
fn uia_clickable_point_by_name_with_timeout(
    name: &str,
    window_title: Option<&str>,
    timeout_ms: u64,
) -> Result<(i32, i32), String> {
    let (sender, receiver) = mpsc::channel();
    let worker_name = name.to_string();
    let worker_window_title = window_title.map(str::to_string);
    thread::spawn(move || {
        let result = uia_clickable_point_by_name(&worker_name, worker_window_title.as_deref());
        let _ = sender.send(result);
    });
    match receiver.recv_timeout(Duration::from_millis(timeout_ms)) {
        Ok(result) => result,
        Err(_) => Err(format!("UIA point lookup timed out after {timeout_ms}ms")),
    }
}

#[cfg(target_os = "windows")]
fn uia_clickable_point_by_name(
    name: &str,
    window_title: Option<&str>,
) -> Result<(i32, i32), String> {
    unsafe {
        let automation =
            create_uia().map_err(|error| format!("failed to start UIAutomation: {error}"))?;
        let hwnd = target_hwnd(window_title);
        if hwnd.0.is_null() {
            return Err("no active window".to_string());
        }
        let root = automation
            .ElementFromHandle(hwnd)
            .map_err(|error| format!("failed to read focused window UIA tree: {error}"))?;
        let element = find_uia_element_by_name(&automation, &root, name)
            .ok_or_else(|| format!("UIA element named '{name}' not found"))?;
        let mut point = POINT { x: 0, y: 0 };
        match element.GetClickablePoint(&mut point) {
            Ok(got_clickable) if got_clickable.as_bool() => Ok((point.x, point.y)),
            Ok(_) => {
                let rect = element
                    .CurrentBoundingRectangle()
                    .map_err(|error| format!("UIA element '{name}' has no point/rect: {error}"))?;
                Ok(((rect.left + rect.right) / 2, (rect.top + rect.bottom) / 2))
            }
            Err(error) => {
                let rect = element.CurrentBoundingRectangle().map_err(|rect_error| {
                    format!(
                        "failed to get point for UIA element '{name}': {error}; rect failed: {rect_error}"
                    )
                })?;
                Ok(((rect.left + rect.right) / 2, (rect.top + rect.bottom) / 2))
            }
        }
    }
}

#[cfg(target_os = "windows")]
fn ableton_pitch_label_near_y_with_timeout(
    window_title: Option<&str>,
    y: i32,
    timeout_ms: u64,
) -> Result<(String, i32), String> {
    let (sender, receiver) = mpsc::channel();
    let worker_window_title = window_title.map(str::to_string);
    thread::spawn(move || {
        let result = ableton_pitch_label_near_y(worker_window_title.as_deref(), y);
        let _ = sender.send(result);
    });
    match receiver.recv_timeout(Duration::from_millis(timeout_ms)) {
        Ok(result) => result,
        Err(_) => Err(format!(
            "Ableton pitch UIA scan timed out after {timeout_ms}ms"
        )),
    }
}

#[cfg(target_os = "windows")]
fn ableton_pitch_label_y_with_timeout(
    window_title: Option<&str>,
    pitch: &str,
    timeout_ms: u64,
) -> Result<i32, String> {
    let (sender, receiver) = mpsc::channel();
    let worker_window_title = window_title.map(str::to_string);
    let worker_pitch = pitch.to_string();
    thread::spawn(move || {
        let result = ableton_pitch_label_y(worker_window_title.as_deref(), &worker_pitch);
        let _ = sender.send(result);
    });
    match receiver.recv_timeout(Duration::from_millis(timeout_ms)) {
        Ok(result) => result,
        Err(_) => Err(format!(
            "Ableton pitch UIA lookup timed out after {timeout_ms}ms"
        )),
    }
}

#[cfg(target_os = "windows")]
fn ableton_pitch_label_near_y(window_title: Option<&str>, y: i32) -> Result<(String, i32), String> {
    let labels = ableton_pitch_labels(window_title)?;
    labels
        .into_iter()
        .min_by_key(|(_, label_y)| (label_y - y).abs())
        .filter(|(_, label_y)| (label_y - y).abs() <= 24)
        .ok_or_else(|| format!("no Ableton pitch label near y={y}"))
}

#[cfg(target_os = "windows")]
fn ableton_pitch_label_y(window_title: Option<&str>, pitch: &str) -> Result<i32, String> {
    let wanted = pitch.trim().to_ascii_lowercase();
    ableton_pitch_labels(window_title)?
        .into_iter()
        .find_map(|(label, y)| (label.to_ascii_lowercase() == wanted).then_some(y))
        .ok_or_else(|| format!("Ableton pitch label '{pitch}' not found"))
}

#[cfg(target_os = "windows")]
fn ocr_ableton_browser_item_point_with_timeout(
    preset_name: &str,
    rect: Option<&WindowRect>,
    timeout_ms: u64,
) -> Result<(i32, i32), String> {
    let rect = rect
        .cloned()
        .ok_or_else(|| "no live Ableton rect for OCR".to_string())?;
    let preset_name = preset_name.to_string();
    let (sender, receiver) = mpsc::channel();
    thread::spawn(move || {
        let result = ocr_ableton_browser_item_point(&preset_name, &rect);
        let _ = sender.send(result);
    });
    match receiver.recv_timeout(Duration::from_millis(timeout_ms)) {
        Ok(result) => result,
        Err(_) => Err(format!(
            "Ableton browser OCR timed out after {timeout_ms}ms"
        )),
    }
}

#[cfg(target_os = "windows")]
fn ocr_ableton_pitch_label_y_with_timeout(
    rect: Option<&WindowRect>,
    pitch: &str,
    timeout_ms: u64,
) -> Result<i32, String> {
    let rect = rect
        .cloned()
        .ok_or_else(|| "no live Ableton rect for OCR".to_string())?;
    let pitch = pitch.to_string();
    let (sender, receiver) = mpsc::channel();
    thread::spawn(move || {
        let result = ocr_ableton_pitch_label_y(&pitch, &rect);
        let _ = sender.send(result);
    });
    match receiver.recv_timeout(Duration::from_millis(timeout_ms)) {
        Ok(result) => result,
        Err(_) => Err(format!("Ableton pitch OCR timed out after {timeout_ms}ms")),
    }
}

#[cfg(target_os = "windows")]
fn ocr_ableton_row_label_near_y_with_timeout(
    rect: Option<&WindowRect>,
    y: i32,
    timeout_ms: u64,
) -> Result<String, String> {
    let rect = rect
        .cloned()
        .ok_or_else(|| "no live Ableton rect for row OCR".to_string())?;
    let (sender, receiver) = mpsc::channel();
    thread::spawn(move || {
        let result = ocr_ableton_row_label_near_y(&rect, y);
        let _ = sender.send(result);
    });
    match receiver.recv_timeout(Duration::from_millis(timeout_ms)) {
        Ok(result) => result,
        Err(_) => Err(format!("Ableton row OCR timed out after {timeout_ms}ms")),
    }
}

#[cfg(target_os = "windows")]
fn ocr_ableton_browser_item_point(
    preset_name: &str,
    rect: &WindowRect,
) -> Result<(i32, i32), String> {
    let region = ableton_browser_ocr_region(rect);
    let words = ocr_words_in_region(region)?;
    ocr_match_point(&words, preset_name)
        .ok_or_else(|| format!("OCR did not find browser item '{preset_name}'"))
}

#[cfg(target_os = "windows")]
fn ocr_ableton_pitch_label_y(pitch: &str, rect: &WindowRect) -> Result<i32, String> {
    let region = ableton_pitch_ocr_region(rect);
    let words = ocr_words_in_region(region)?;
    ocr_match_point(&words, pitch)
        .map(|(_, y)| y)
        .ok_or_else(|| format!("OCR did not find pitch label '{pitch}'"))
}

#[cfg(target_os = "windows")]
fn ocr_ableton_row_label_near_y(rect: &WindowRect, y: i32) -> Result<String, String> {
    let region = ableton_row_label_ocr_region(rect, y);
    let words = ocr_words_in_scaled_region(region, 4)?;
    ocr_row_label_near_y(&words, y)
        .ok_or_else(|| format!("OCR did not find Ableton row label near y={y}"))
}

fn ocr_row_label_near_y(words: &[OcrWord], y: i32) -> Option<String> {
    let mut candidates = Vec::new();
    for row in ocr_words_grouped_by_row(words, 10) {
        let center_y = row
            .iter()
            .map(|word| word.top + word.height / 2)
            .sum::<i32>()
            / row.len().max(1) as i32;
        if (center_y - y).abs() > 32 {
            continue;
        }
        let text = row
            .iter()
            .map(|word| word.text.trim())
            .filter(|value| !value.is_empty())
            .collect::<Vec<_>>()
            .join(" ");
        if text.is_empty() || text.len() > 24 {
            continue;
        }
        if first_pitch_token(&text).is_none() && !ableton_note_name_is_row_label(&text) {
            continue;
        }
        candidates.push((text.to_string(), center_y));
    }
    candidates
        .into_iter()
        .min_by_key(|(_, center_y)| (center_y - y).abs())
        .map(|(text, _)| text)
}

fn ocr_words_grouped_by_row(words: &[OcrWord], tolerance: i32) -> Vec<Vec<OcrWord>> {
    let mut sorted = words.to_vec();
    sorted.sort_by_key(|word| (word.top + word.height / 2, word.left));
    let mut rows: Vec<Vec<OcrWord>> = Vec::new();
    for word in sorted {
        let center_y = word.top + word.height / 2;
        if let Some(row) = rows.iter_mut().find(|row| {
            let row_center = row
                .iter()
                .map(|existing| existing.top + existing.height / 2)
                .sum::<i32>()
                / row.len().max(1) as i32;
            (row_center - center_y).abs() <= tolerance
        }) {
            row.push(word);
            row.sort_by_key(|value| value.left);
        } else {
            rows.push(vec![word]);
        }
    }
    rows
}

#[cfg(target_os = "windows")]
fn ableton_browser_ocr_region(rect: &WindowRect) -> WindowRect {
    WindowRect {
        left: rect.left,
        top: rect.top + (rect.height as f64 * 0.14).round() as i32,
        width: (rect.width as f64 * 0.26).round() as i32,
        height: (rect.height as f64 * 0.74).round() as i32,
    }
}

#[cfg(target_os = "windows")]
fn ableton_pitch_ocr_region(rect: &WindowRect) -> WindowRect {
    WindowRect {
        left: rect.left + (rect.width as f64 * 0.08).round() as i32,
        top: rect.top + (rect.height as f64 * 0.50).round() as i32,
        width: (rect.width as f64 * 0.16).round() as i32,
        height: (rect.height as f64 * 0.46).round() as i32,
    }
}

#[cfg(target_os = "windows")]
fn ableton_row_label_ocr_region(rect: &WindowRect, y: i32) -> WindowRect {
    let left = rect.left + (rect.width as f64 * 0.095).round() as i32;
    let top = (y - 34).max(rect.top + (rect.height as f64 * 0.48).round() as i32);
    let bottom = (y + 34).min(rect.top + rect.height);
    WindowRect {
        left,
        top,
        width: (rect.width as f64 * 0.12).round() as i32,
        height: (bottom - top).max(24),
    }
}

#[cfg(target_os = "windows")]
fn ocr_match_point(words: &[OcrWord], needle: &str) -> Option<(i32, i32)> {
    let wanted = normalize_ocr_text(needle);
    if wanted.is_empty() {
        return None;
    }
    for start in 0..words.len() {
        let mut combined = String::new();
        for end in start..words.len().min(start + 8) {
            combined.push_str(&normalize_ocr_text(&words[end].text));
            if combined == wanted {
                return Some(ocr_bounds_center(&words[start..=end]));
            }
            if combined.len() > wanted.len() + 12 {
                break;
            }
        }
    }
    words.iter().find_map(|word| {
        let text = normalize_ocr_text(&word.text);
        (text == wanted || text.contains(&wanted))
            .then(|| (word.left + word.width / 2, word.top + word.height / 2))
    })
}

fn ocr_bounds_center(words: &[OcrWord]) -> (i32, i32) {
    let left = words.iter().map(|word| word.left).min().unwrap_or(0);
    let top = words.iter().map(|word| word.top).min().unwrap_or(0);
    let right = words
        .iter()
        .map(|word| word.left + word.width)
        .max()
        .unwrap_or(left);
    let bottom = words
        .iter()
        .map(|word| word.top + word.height)
        .max()
        .unwrap_or(top);
    ((left + right) / 2, (top + bottom) / 2)
}

fn normalize_ocr_text(value: &str) -> String {
    value
        .chars()
        .filter(|ch| ch.is_ascii_alphanumeric())
        .flat_map(char::to_lowercase)
        .collect()
}

#[cfg(target_os = "windows")]
fn ocr_words_in_region(region: WindowRect) -> Result<Vec<OcrWord>, String> {
    if region.width <= 0 || region.height <= 0 {
        return Err(format!(
            "invalid OCR region: {}",
            format_window_rect(Some(&region))
        ));
    }
    let path = std::env::temp_dir().join(format!(
        "marouba-ocr-{}-{}.bmp",
        std::process::id(),
        current_millis()
    ));
    capture_region_bmp(&region, &path)?;
    let result = run_ocr_script(&path, region.left, region.top);
    let _ = std::fs::remove_file(&path);
    result
}

#[cfg(target_os = "windows")]
fn ocr_words_in_scaled_region(region: WindowRect, scale: i32) -> Result<Vec<OcrWord>, String> {
    if scale <= 1 {
        return ocr_words_in_region(region);
    }
    if region.width <= 0 || region.height <= 0 {
        return Err(format!(
            "invalid OCR region: {}",
            format_window_rect(Some(&region))
        ));
    }
    let path = std::env::temp_dir().join(format!(
        "marouba-ocr-{}-{}-scaled.bmp",
        std::process::id(),
        current_millis()
    ));
    capture_region_scaled_bmp(&region, &path, scale)?;
    let mut words = run_ocr_script(&path, 0, 0)?;
    let _ = std::fs::remove_file(&path);
    for word in &mut words {
        word.left = region.left + (word.left as f64 / scale as f64).round() as i32;
        word.top = region.top + (word.top as f64 / scale as f64).round() as i32;
        word.width = (word.width as f64 / scale as f64).round().max(1.0) as i32;
        word.height = (word.height as f64 / scale as f64).round().max(1.0) as i32;
    }
    Ok(words)
}

fn current_millis() -> u128 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_millis())
        .unwrap_or(0)
}

#[cfg(target_os = "windows")]
fn run_ocr_script(path: &PathBuf, origin_x: i32, origin_y: i32) -> Result<Vec<OcrWord>, String> {
    let script = ocr_script_path().ok_or_else(|| "OCR helper script not found".to_string())?;
    let mut command = Command::new("powershell.exe");
    command.args([
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        &script.display().to_string(),
        "-Path",
        &path.display().to_string(),
        "-X",
        &origin_x.to_string(),
        "-Y",
        &origin_y.to_string(),
    ]);
    let output = no_window_command(&mut command)
        .output()
        .map_err(|error| format!("failed to run OCR helper: {error}"))?;
    if !output.status.success() {
        return Err(String::from_utf8_lossy(&output.stderr).trim().to_string());
    }
    let stdout = String::from_utf8_lossy(&output.stdout).trim().to_string();
    if stdout.is_empty() {
        return Ok(Vec::new());
    }
    parse_ocr_words(&stdout)
}

#[cfg(target_os = "windows")]
fn parse_ocr_words(stdout: &str) -> Result<Vec<OcrWord>, String> {
    let value: Value = serde_json::from_str(stdout)
        .map_err(|error| format!("failed to parse OCR JSON: {error}; output={stdout}"))?;
    if value.is_array() {
        serde_json::from_value(value).map_err(|error| format!("invalid OCR words: {error}"))
    } else if value.is_object() {
        serde_json::from_value(value)
            .map(|word| vec![word])
            .map_err(|error| format!("invalid OCR word: {error}"))
    } else {
        Ok(Vec::new())
    }
}

#[cfg(target_os = "windows")]
fn ocr_script_path() -> Option<PathBuf> {
    let mut candidates = Vec::new();
    if let Ok(cwd) = std::env::current_dir() {
        candidates.push(cwd.join("scripts").join("ocr_region.ps1"));
    }
    if let Ok(exe) = std::env::current_exe() {
        if let Some(parent) = exe.parent() {
            candidates.push(parent.join("scripts").join("ocr_region.ps1"));
            candidates.push(parent.join("..").join("scripts").join("ocr_region.ps1"));
            candidates.push(
                parent
                    .join("..")
                    .join("..")
                    .join("..")
                    .join("scripts")
                    .join("ocr_region.ps1"),
            );
        }
    }
    candidates.push(PathBuf::from(
        r"C:\Share\Marouba\companion\scripts\ocr_region.ps1",
    ));
    candidates.into_iter().find(|path| path.is_file())
}

#[cfg(target_os = "windows")]
fn capture_region_bmp(region: &WindowRect, path: &PathBuf) -> Result<(), String> {
    unsafe {
        let screen_hwnd = HWND(std::ptr::null_mut());
        let screen_dc = GetDC(screen_hwnd);
        if screen_dc.0.is_null() {
            return Err("GetDC(null HWND) returned null".to_string());
        }
        let mem_dc = CreateCompatibleDC(screen_dc);
        if mem_dc.0.is_null() {
            let _ = ReleaseDC(screen_hwnd, screen_dc);
            return Err("CreateCompatibleDC failed".to_string());
        }
        let bitmap = CreateCompatibleBitmap(screen_dc, region.width, region.height);
        if bitmap.0.is_null() {
            let _ = DeleteDC(mem_dc);
            let _ = ReleaseDC(screen_hwnd, screen_dc);
            return Err("CreateCompatibleBitmap failed".to_string());
        }
        let old_object = SelectObject(mem_dc, bitmap);
        if old_object.0.is_null() {
            let _ = DeleteObject(bitmap);
            let _ = DeleteDC(mem_dc);
            let _ = ReleaseDC(screen_hwnd, screen_dc);
            return Err("SelectObject failed".to_string());
        }
        let blit = BitBlt(
            mem_dc,
            0,
            0,
            region.width,
            region.height,
            screen_dc,
            region.left,
            region.top,
            SRCCOPY,
        );
        if blit.is_err() {
            let _ = SelectObject(mem_dc, old_object);
            let _ = DeleteObject(bitmap);
            let _ = DeleteDC(mem_dc);
            let _ = ReleaseDC(screen_hwnd, screen_dc);
            return Err("BitBlt failed".to_string());
        }
        let stride = (region.width as usize) * 4;
        let image_size = stride * region.height as usize;
        let mut pixels = vec![0u8; image_size];
        let mut info = BITMAPINFO {
            bmiHeader: BITMAPINFOHEADER {
                biSize: std::mem::size_of::<BITMAPINFOHEADER>() as u32,
                biWidth: region.width,
                biHeight: -region.height,
                biPlanes: 1,
                biBitCount: 32,
                biCompression: BI_RGB.0,
                biSizeImage: image_size as u32,
                biXPelsPerMeter: 0,
                biYPelsPerMeter: 0,
                biClrUsed: 0,
                biClrImportant: 0,
            },
            bmiColors: [Default::default(); 1],
        };
        let lines = GetDIBits(
            mem_dc,
            bitmap,
            0,
            region.height as u32,
            Some(pixels.as_mut_ptr() as *mut c_void),
            &mut info,
            DIB_RGB_COLORS,
        );
        let _ = SelectObject(mem_dc, old_object);
        let _ = DeleteObject(bitmap);
        let _ = DeleteDC(mem_dc);
        let _ = ReleaseDC(screen_hwnd, screen_dc);
        if lines == 0 {
            return Err("GetDIBits failed".to_string());
        }
        write_bmp(path, region.width, region.height, &pixels)
    }
}

#[cfg(target_os = "windows")]
fn capture_region_scaled_bmp(
    region: &WindowRect,
    path: &PathBuf,
    scale: i32,
) -> Result<(), String> {
    let native_path = std::env::temp_dir().join(format!(
        "marouba-ocr-{}-{}-native.bmp",
        std::process::id(),
        current_millis()
    ));
    capture_region_bmp(region, &native_path)?;
    let native = std::fs::read(&native_path)
        .map_err(|error| format!("failed to read native OCR bitmap: {error}"))?;
    let _ = std::fs::remove_file(&native_path);
    let header_size = 54usize;
    if native.len() < header_size {
        return Err("native OCR bitmap is too small".to_string());
    }
    let source_pixels = &native[header_size..];
    let source_width = region.width.max(1) as usize;
    let source_height = region.height.max(1) as usize;
    let scale = scale.max(1) as usize;
    let target_width = source_width * scale;
    let target_height = source_height * scale;
    let mut target_pixels = vec![0u8; target_width * target_height * 4];
    for y in 0..target_height {
        let source_y = y / scale;
        for x in 0..target_width {
            let source_x = x / scale;
            let source_index = (source_y * source_width + source_x) * 4;
            let target_index = (y * target_width + x) * 4;
            target_pixels[target_index..target_index + 4]
                .copy_from_slice(&source_pixels[source_index..source_index + 4]);
        }
    }
    write_bmp(
        path,
        target_width as i32,
        target_height as i32,
        &target_pixels,
    )
}

#[cfg(target_os = "windows")]
fn write_bmp(path: &PathBuf, width: i32, height: i32, pixels: &[u8]) -> Result<(), String> {
    let pixel_bytes = pixels.len() as u32;
    let file_size = 14u32 + 40u32 + pixel_bytes;
    let mut bytes = Vec::with_capacity(file_size as usize);
    bytes.extend_from_slice(b"BM");
    bytes.extend_from_slice(&file_size.to_le_bytes());
    bytes.extend_from_slice(&0u16.to_le_bytes());
    bytes.extend_from_slice(&0u16.to_le_bytes());
    bytes.extend_from_slice(&(54u32).to_le_bytes());
    bytes.extend_from_slice(&(40u32).to_le_bytes());
    bytes.extend_from_slice(&width.to_le_bytes());
    bytes.extend_from_slice(&(-height).to_le_bytes());
    bytes.extend_from_slice(&(1u16).to_le_bytes());
    bytes.extend_from_slice(&(32u16).to_le_bytes());
    bytes.extend_from_slice(&(0u32).to_le_bytes());
    bytes.extend_from_slice(&pixel_bytes.to_le_bytes());
    bytes.extend_from_slice(&(0i32).to_le_bytes());
    bytes.extend_from_slice(&(0i32).to_le_bytes());
    bytes.extend_from_slice(&(0u32).to_le_bytes());
    bytes.extend_from_slice(&(0u32).to_le_bytes());
    bytes.extend_from_slice(pixels);
    std::fs::write(path, bytes).map_err(|error| format!("failed to write OCR bitmap: {error}"))
}

#[cfg(target_os = "windows")]
fn ableton_pitch_labels(window_title: Option<&str>) -> Result<Vec<(String, i32)>, String> {
    unsafe {
        let automation =
            create_uia().map_err(|error| format!("failed to start UIAutomation: {error}"))?;
        let hwnd = target_hwnd(window_title);
        if hwnd.0.is_null() {
            return Err("no active window".to_string());
        }
        let root = automation
            .ElementFromHandle(hwnd)
            .map_err(|error| format!("failed to read Ableton UIA tree: {error}"))?;
        let walker = automation
            .ControlViewWalker()
            .map_err(|error| format!("failed to create UIA walker: {error}"))?;
        let mut labels = Vec::new();
        let mut stack = vec![root];
        while let Some(element) = stack.pop() {
            for name in uia_element_names(&element) {
                if let Some(pitch) = first_pitch_token(&name) {
                    if let Ok(rect) = element.CurrentBoundingRectangle() {
                        let y = (rect.top + rect.bottom) / 2;
                        labels.push((pitch, y));
                    }
                }
            }
            if let Ok(first_child) = walker.GetFirstChildElement(&element) {
                let mut siblings = vec![first_child.clone()];
                let mut current = first_child;
                while let Ok(next) = walker.GetNextSiblingElement(&current) {
                    siblings.push(next.clone());
                    current = next;
                }
                for child in siblings.into_iter().rev() {
                    stack.push(child);
                }
            }
        }
        if labels.is_empty() {
            Err("Ableton UIA exposed no pitch labels".to_string())
        } else {
            Ok(labels)
        }
    }
}

#[cfg(target_os = "windows")]
fn uia_element_names(element: &IUIAutomationElement) -> Vec<String> {
    let mut names = Vec::new();
    if let Ok(name) = unsafe { element.CurrentName() } {
        let name = name.to_string();
        if !name.trim().is_empty() {
            names.push(name);
        }
    }
    if let Some(name) = uia_legacy_accessible_name(element) {
        if !names.iter().any(|value| value.eq_ignore_ascii_case(&name)) {
            names.push(name);
        }
    }
    names
}

#[cfg(target_os = "windows")]
fn uia_element_names_and_rect_at_point_with_timeout(
    x: i32,
    y: i32,
    timeout_ms: u64,
) -> Result<(Vec<String>, WindowRect), String> {
    let (sender, receiver) = mpsc::channel();
    thread::spawn(move || {
        let result = uia_element_names_and_rect_at_point(x, y);
        let _ = sender.send(result);
    });
    match receiver.recv_timeout(Duration::from_millis(timeout_ms)) {
        Ok(result) => result,
        Err(_) => Err(format!(
            "UIA element-at-point lookup timed out after {timeout_ms}ms"
        )),
    }
}

#[cfg(target_os = "windows")]
fn uia_element_names_and_rect_at_point(
    x: i32,
    y: i32,
) -> Result<(Vec<String>, WindowRect), String> {
    let payload = UiaRequest {
        name: None,
        role: None,
        window_title: None,
        x: Some(x),
        y: Some(y),
    };
    let (element, _) = find_uia_element(&payload)?;
    let names = uia_element_names(&element);
    let rect = unsafe {
        element
            .CurrentBoundingRectangle()
            .map_err(|error| format!("UIA element at ({x}, {y}) has no rect: {error}"))?
    };
    Ok((
        names,
        WindowRect {
            left: rect.left,
            top: rect.top,
            width: rect.right - rect.left,
            height: rect.bottom - rect.top,
        },
    ))
}

#[cfg(target_os = "windows")]
fn uia_legacy_accessible_name(element: &IUIAutomationElement) -> Option<String> {
    unsafe {
        let value = element
            .GetCurrentPropertyValue(UIA_LegacyIAccessibleNamePropertyId)
            .ok()?;
        let bstr = BSTR::try_from(&value).ok()?;
        let name = bstr.to_string().trim().to_string();
        (!name.is_empty()).then_some(name)
    }
}

fn ableton_pitch_from_semantic(event: &RecordedEvent) -> Option<String> {
    semantic_tag_value(event, "midi_pitch:").map(str::to_string)
}

fn ableton_note_from_semantic(event: &RecordedEvent) -> Option<String> {
    semantic_tag_value(event, "midi_note:").map(str::to_string)
}

fn ableton_row_from_semantic(event: &RecordedEvent) -> Option<f64> {
    semantic_tag_value(event, "midi_row:").and_then(|value| value.parse::<f64>().ok())
}

fn first_pitch_token(value: &str) -> Option<String> {
    let chars: Vec<char> = value.chars().collect();
    for index in 0..chars.len() {
        let note = chars[index].to_ascii_uppercase();
        if !matches!(note, 'A'..='G') {
            continue;
        }
        let mut cursor = index + 1;
        let mut token = String::new();
        token.push(note);
        if cursor < chars.len() && matches!(chars[cursor], '#' | 'b' | 'B') {
            token.push(if chars[cursor] == '#' { '#' } else { 'b' });
            cursor += 1;
        }
        if cursor < chars.len() && chars[cursor] == '-' {
            token.push('-');
            cursor += 1;
        }
        let digit_start = cursor;
        while cursor < chars.len() && chars[cursor].is_ascii_digit() {
            token.push(chars[cursor]);
            cursor += 1;
        }
        if cursor > digit_start && pitch_token_has_boundaries(&chars, index, cursor) {
            return Some(token);
        }
    }
    None
}

fn pitch_token_has_boundaries(chars: &[char], start: usize, end: usize) -> bool {
    let before_ok =
        start == 0 || !chars[start - 1].is_ascii_alphanumeric() && chars[start - 1] != '#';
    let after_ok = end >= chars.len() || !chars[end].is_ascii_alphanumeric() && chars[end] != '#';
    before_ok && after_ok
}

#[cfg(target_os = "windows")]
fn invoke_uia_element(element: &IUIAutomationElement, name: &str) -> Result<(), String> {
    unsafe {
        let pattern = element
            .GetCurrentPatternAs::<IUIAutomationInvokePattern>(UIA_InvokePatternId)
            .map_err(|error| {
                format!(
                    "UIA element '{name}' has no clickable point and no invoke pattern: {error}"
                )
            })?;
        pattern
            .Invoke()
            .map_err(|error| format!("failed to invoke UIA element '{name}': {error}"))
    }
}

#[cfg(target_os = "windows")]
fn find_uia_element_by_name(
    automation: &IUIAutomation,
    root: &IUIAutomationElement,
    name: &str,
) -> Option<IUIAutomationElement> {
    let exact_value = VARIANT::from(name);
    if let Ok(condition) =
        unsafe { automation.CreatePropertyCondition(UIA_NamePropertyId, &exact_value) }
    {
        if let Ok(element) = unsafe { root.FindFirst(TreeScope_Subtree, &condition) } {
            return Some(element);
        }
    }

    let needle = name.to_lowercase();
    unsafe {
        let walker = automation.ControlViewWalker().ok()?;
        let mut stack = vec![root.clone()];
        while let Some(element) = stack.pop() {
            if element
                .CurrentName()
                .map(|value| value.to_string().to_lowercase().contains(&needle))
                .unwrap_or(false)
            {
                return Some(element);
            }
            if let Ok(first_child) = walker.GetFirstChildElement(&element) {
                let mut siblings = vec![first_child.clone()];
                let mut current = first_child;
                while let Ok(next) = walker.GetNextSiblingElement(&current) {
                    siblings.push(next.clone());
                    current = next;
                }
                for child in siblings.into_iter().rev() {
                    stack.push(child);
                }
            }
        }
    }
    None
}

fn replay_event_delay(current: &RecordedEvent, next: Option<&RecordedEvent>) -> Duration {
    let Some(next) = next else {
        return Duration::from_millis(20);
    };
    if next.timestamp_ms == 0 || next.timestamp_ms <= current.timestamp_ms {
        return Duration::from_millis(20);
    }
    let max_delay_ms = if is_ableton_event(current) || is_ableton_event(next) {
        30_000
    } else {
        1_000
    };
    let delta_ms = (next.timestamp_ms - current.timestamp_ms).clamp(8, max_delay_ms) as u64;
    Duration::from_millis(delta_ms)
}

fn format_window_rect(rect: Option<&WindowRect>) -> String {
    match rect {
        Some(rect) => format!(
            "left={} top={} width={} height={}",
            rect.left, rect.top, rect.width, rect.height
        ),
        None => "none".to_string(),
    }
}

#[cfg(target_os = "windows")]
fn send_absolute_mousemove(x: i32, y: i32) {
    send_absolute_mouse_input(x, y, MOUSEEVENTF_MOVE);
}

#[cfg(target_os = "windows")]
fn send_absolute_mouse_input(
    x: i32,
    y: i32,
    flags: windows::Win32::UI::Input::KeyboardAndMouse::MOUSE_EVENT_FLAGS,
) {
    let (dx, dy) = absolute_mouse_coordinates(x, y);
    unsafe {
        let input = INPUT {
            r#type: INPUT_MOUSE,
            Anonymous: INPUT_0 {
                mi: MOUSEINPUT {
                    dx,
                    dy,
                    mouseData: 0,
                    dwFlags: flags | MOUSEEVENTF_ABSOLUTE,
                    time: 0,
                    dwExtraInfo: 0,
                },
            },
        };
        let _ = SendInput(&[input], std::mem::size_of::<INPUT>() as i32);
    }
}

#[cfg(target_os = "windows")]
fn send_ableton_left_click(x: i32, y: i32, hold_delay: Duration) {
    send_ableton_mousemove(x, y);
    thread::sleep(Duration::from_millis(8));
    send_ableton_leftdown(x, y);
    thread::sleep(hold_delay);
    send_ableton_leftup(x, y);
}

#[cfg(target_os = "windows")]
fn send_ableton_mousemove(x: i32, y: i32) {
    send_ableton_mouse_input(x, y, MOUSEEVENTF_MOVE);
}

#[cfg(target_os = "windows")]
fn send_ableton_leftdown(x: i32, y: i32) {
    send_ableton_mouse_input(x, y, MOUSEEVENTF_MOVE | MOUSEEVENTF_LEFTDOWN);
}

#[cfg(target_os = "windows")]
fn send_ableton_leftup(x: i32, y: i32) {
    send_ableton_mouse_input(x, y, MOUSEEVENTF_MOVE | MOUSEEVENTF_LEFTUP);
}

#[cfg(target_os = "windows")]
fn send_ableton_mouse_input(
    x: i32,
    y: i32,
    flags: windows::Win32::UI::Input::KeyboardAndMouse::MOUSE_EVENT_FLAGS,
) {
    let (dx, dy) = precise_absolute_mouse_coordinates(x, y);
    unsafe {
        let input = INPUT {
            r#type: INPUT_MOUSE,
            Anonymous: INPUT_0 {
                mi: MOUSEINPUT {
                    dx,
                    dy,
                    mouseData: 0,
                    dwFlags: flags | MOUSEEVENTF_ABSOLUTE,
                    time: 0,
                    dwExtraInfo: 0,
                },
            },
        };
        let _ = SendInput(&[input], std::mem::size_of::<INPUT>() as i32);
    }
}

#[cfg(target_os = "windows")]
fn send_cursor_mousemove(x: i32, y: i32) {
    unsafe {
        let _ = SetCursorPos(x, y);
        mouse_event(MOUSEEVENTF_MOVE, 0, 0, 0, 0);
    }
}

#[cfg(target_os = "windows")]
fn send_cursor_leftdown(x: i32, y: i32) {
    unsafe {
        let _ = SetCursorPos(x, y);
        mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0);
    }
}

#[cfg(target_os = "windows")]
fn send_cursor_leftup(x: i32, y: i32) {
    unsafe {
        let _ = SetCursorPos(x, y);
        mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0);
    }
}

#[cfg(target_os = "windows")]
fn absolute_mouse_coordinates(x: i32, y: i32) -> (i32, i32) {
    unsafe {
        let screen_width = GetSystemMetrics(SM_CXSCREEN).max(1);
        let screen_height = GetSystemMetrics(SM_CYSCREEN).max(1);
        (
            (x.clamp(0, screen_width) * 65_535) / screen_width,
            (y.clamp(0, screen_height) * 65_535) / screen_height,
        )
    }
}

#[cfg(target_os = "windows")]
fn precise_absolute_mouse_coordinates(x: i32, y: i32) -> (i32, i32) {
    unsafe {
        let screen_width = GetSystemMetrics(SM_CXSCREEN).max(1) as i64;
        let screen_height = GetSystemMetrics(SM_CYSCREEN).max(1) as i64;
        let x = x.clamp(0, screen_width as i32) as i64;
        let y = y.clamp(0, screen_height as i32) as i64;
        (
            (((x * 65_535) + (screen_width / 2)) / screen_width) as i32,
            (((y * 65_535) + (screen_height / 2)) / screen_height) as i32,
        )
    }
}

#[cfg(target_os = "windows")]
fn send_recordable_left_click(x: i32, y: i32) {
    unsafe {
        mouse_event(MOUSEEVENTF_LEFTDOWN, x, y, 0, 0);
        thread::sleep(Duration::from_millis(80));
        mouse_event(MOUSEEVENTF_LEFTUP, x, y, 0, 0);
    }
}

#[cfg(not(target_os = "windows"))]
fn replay_mouse(payload: MouseReplayRequest) -> (Value, u16) {
    (
        json!({"ok": false, "replayed": 0, "target_window": payload.target_window, "error": "mouse replay not implemented on this platform"}),
        501,
    )
}

fn resolve_replay_point(event: &RecordedEvent, rect: Option<&WindowRect>) -> (i32, i32) {
    if let (Some(rect), Some(nx), Some(ny)) = (rect, event.normalized_x, event.normalized_y) {
        let x = rect.left + (nx * rect.width as f64).round() as i32;
        let y = rect.top + (ny * rect.height as f64).round() as i32;
        return (x, y);
    }
    (event.x.unwrap_or(0), event.y.unwrap_or(0))
}

fn resolve_ableton_replay_point(event: &RecordedEvent, rect: Option<&WindowRect>) -> (i32, i32) {
    resolve_ableton_replay_point_with_note_context(event, rect, false)
}

fn resolve_ableton_replay_point_with_note_context(
    event: &RecordedEvent,
    rect: Option<&WindowRect>,
    note_grid_context: bool,
) -> (i32, i32) {
    let (mut x, mut y) =
        if let (Some(rect), Some(nx), Some(ny)) = (rect, event.normalized_x, event.normalized_y) {
            let x = rect.left as f64 + (nx * rect.width as f64);
            let y = rect.top as f64 + (ny * rect.height as f64);
            (x.round() as i32, y.round() as i32)
        } else {
            (event.x.unwrap_or(0), event.y.unwrap_or(0))
        };

    if note_grid_context || is_ableton_piano_roll_note_event(event) {
        if let Some(note_name) = ableton_note_from_semantic(event) {
            match ableton_note_label_y_with_timeout(
                event.window_title.as_deref(),
                &note_name,
                500,
            ) {
                Ok(row_y) => {
                    write_debug_log(&format!(
                        "ableton midi note resolved by UIA: note={note_name} y={row_y}"
                    ));
                    y = row_y;
                }
                Err(error) => write_debug_log(&format!(
                    "ableton midi note UIA lookup failed; trying OCR/normalized row: note={note_name} error={error}"
                )),
            }
            if let Ok(row_y) = ocr_ableton_pitch_label_y_with_timeout(rect, &note_name, 1800) {
                write_debug_log(&format!(
                    "ableton midi note resolved by OCR: note={note_name} y={row_y}"
                ));
                y = row_y;
            }
        } else if let Some(pitch) = ableton_pitch_from_semantic(event) {
            match ableton_pitch_label_y_with_timeout(
                event.window_title.as_deref(),
                &pitch,
                500,
            ) {
                Ok(row_y) => {
                    write_debug_log(&format!(
                        "ableton midi pitch resolved by UIA: pitch={pitch} y={row_y}"
                    ));
                    y = row_y;
                }
                Err(error) => write_debug_log(&format!(
                    "ableton midi pitch UIA lookup failed; using normalized row: pitch={pitch} error={error}"
                )),
            }
            if let Ok(row_y) = ocr_ableton_pitch_label_y_with_timeout(rect, &pitch, 1800) {
                write_debug_log(&format!(
                    "ableton midi pitch resolved by OCR: pitch={pitch} y={row_y}"
                ));
                y = row_y;
            }
        } else if let Some(row) = ableton_row_from_semantic(event) {
            write_debug_log(&format!(
                "ableton midi row semantic present; using normalized coordinate row={row:.6}"
            ));
        } else if is_ableton_piano_roll_note_event(event) {
            let correction = ableton_legacy_octave_correction_px(rect);
            y += correction;
            write_debug_log(&format!(
                "ableton legacy MIDI note corrected down one octave: y_offset={correction}"
            ));
        }
    }
    if is_ableton_knob_or_eq_event(event) {
        if let (Some(live_rect), Some(record_rect), Some(record_x), Some(record_y)) =
            (rect, event.window_rect.as_ref(), event.x, event.y)
        {
            x = live_rect.left + (record_x - record_rect.left);
            y = live_rect.top + (record_y - record_rect.top);
        }
    }
    (x, y)
}

fn is_ableton_piano_roll_note_event(event: &RecordedEvent) -> bool {
    if !is_ableton_event(event)
        || !matches!(event.kind.as_str(), "mousedown" | "mousemove" | "mouseup")
    {
        return false;
    }
    let name = event
        .element_name
        .as_deref()
        .unwrap_or("")
        .to_ascii_lowercase();
    if event.normalized_y.map(|y| y > 0.45).unwrap_or(false)
        && ableton_note_name_is_row_label(&name)
    {
        return true;
    }
    name.contains("untitled clip")
        && name.contains("track")
        && event.normalized_y.map(|y| y > 0.50).unwrap_or(false)
}

fn is_ableton_knob_or_eq_event(event: &RecordedEvent) -> bool {
    if !is_ableton_event(event) {
        return false;
    }
    if semantic_tag_value(event, "automation_parameter:").is_some() {
        return true;
    }
    let name = event
        .element_name
        .as_deref()
        .unwrap_or("")
        .to_ascii_lowercase();
    name.contains("frequency")
        || name.contains("resonance")
        || name.contains("gain")
        || name.contains("eq")
        || name.contains("filter")
        || name.contains("threshold")
        || name.contains("output gain")
        || name.contains("fine frequency")
        || name.contains("reverb")
        || name.contains("delay")
        || name.contains("send")
        || name.starts_with("a-")
        || name.starts_with("b-")
}

fn is_ableton_automation_record_event(event: &RecordedEvent) -> bool {
    if !is_ableton_event(event) {
        return false;
    }
    if event
        .semantic
        .as_deref()
        .unwrap_or("")
        .split(';')
        .map(str::trim)
        .any(|tag| tag.eq_ignore_ascii_case("automation_record"))
    {
        return true;
    }
    if event
        .element_name
        .as_deref()
        .map(ableton_is_automation_record_name)
        .unwrap_or(false)
    {
        return true;
    }
    matches!(event.kind.as_str(), "mousedown" | "mouseup")
        && event
            .normalized_x
            .zip(event.normalized_y)
            .map(|(x, y)| (x - 0.46436).abs() < 0.004 && (y - 0.07275).abs() < 0.006)
            .unwrap_or(false)
}

fn is_colour_select_event(event: &RecordedEvent) -> bool {
    event.kind == "mousedown"
        && event.semantic.as_deref() == Some("colour_select")
        && event.colour_hex.is_some()
        && is_ms_paint_event(event)
}

fn is_ms_paint_event(event: &RecordedEvent) -> bool {
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

fn title_is_ms_paint(value: &str) -> bool {
    value.to_ascii_lowercase().contains("paint")
}

fn replay_payload_targets_ms_paint(payload: &MouseReplayRequest) -> bool {
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

fn normalized_event_outside_window(event: &RecordedEvent) -> bool {
    event
        .normalized_x
        .map(|value| !(0.0..=1.0).contains(&value))
        .unwrap_or(false)
        || event
            .normalized_y
            .map(|value| !(0.0..=1.0).contains(&value))
            .unwrap_or(false)
}

#[cfg(target_os = "windows")]
fn resolve_target_replay_rect(payload: &MouseReplayRequest) -> Result<WindowRect, String> {
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

fn write_debug_log(msg: &str) {
    let timestamp = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_millis())
        .unwrap_or(0);
    let line = format!("[{timestamp}] {msg}\n");
    if let Ok(mut file) = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(r"C:\Users\Public\marouba-replay-debug.log")
    {
        use std::io::Write;
        let _ = file.write_all(line.as_bytes());
    }
}

#[cfg(target_os = "windows")]
fn sample_screen_colour_hex(x: i32, y: i32) -> Option<String> {
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
fn sample_screen_colour_hex(_: i32, _: i32) -> Option<String> {
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
    // Tool prelude removed — was causing selection state. Re-add when UIA toolbar click is implemented.
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
fn replay_ms_paint_colour_select(colour_hex: &str) -> Result<(), String> {
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
fn replay_ms_paint_colour_select(_: &str) -> Result<(), String> {
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

#[cfg(target_os = "windows")]
fn send_modified_key(modifier: VIRTUAL_KEY, key: VIRTUAL_KEY) -> Result<(), String> {
    send_key_down(modifier)?;
    send_key(key)?;
    send_key_up(modifier)
}

#[cfg(target_os = "windows")]
fn send_shortcut_keys(keys: &str) -> Result<(), String> {
    let mut modifiers = Vec::new();
    let mut primary = None;
    for part in keys
        .split('+')
        .map(str::trim)
        .filter(|part| !part.is_empty())
    {
        match part.to_ascii_lowercase().as_str() {
            "ctrl" | "control" => modifiers.push(VK_CONTROL),
            "shift" => modifiers.push(VK_SHIFT),
            "alt" => modifiers.push(VK_MENU),
            "enter" | "return" => primary = Some(VK_RETURN),
            "tab" => primary = Some(VK_TAB),
            "backspace" => primary = Some(VK_BACK),
            "space" => primary = Some(VIRTUAL_KEY(0x20)),
            value if value.len() == 1 => {
                primary = Some(VIRTUAL_KEY(value.as_bytes()[0].to_ascii_uppercase() as u16));
            }
            value => return Err(format!("unsupported shortcut key: {value}")),
        }
    }
    let primary = primary.ok_or_else(|| format!("shortcut has no primary key: {keys}"))?;
    write_debug_log(&format!("route switcher sending shortcut: {keys}"));
    for modifier in &modifiers {
        send_key_down(*modifier)?;
    }
    send_key(primary)?;
    for modifier in modifiers.iter().rev() {
        send_key_up(*modifier)?;
    }
    Ok(())
}

#[cfg(not(target_os = "windows"))]
fn send_shortcut_keys(_: &str) -> Result<(), String> {
    Err("shortcut replay not implemented on this platform".to_string())
}

#[cfg(target_os = "windows")]
fn send_ableton_insert_midi_track() -> Result<(), String> {
    write_debug_log("ableton insert MIDI track: Ctrl+Shift+T");
    send_key_down(VK_CONTROL)?;
    send_key_down(VK_SHIFT)?;
    send_key(VIRTUAL_KEY(0x54))?;
    send_key_up(VK_SHIFT)?;
    send_key_up(VK_CONTROL)
}

#[cfg(target_os = "windows")]
fn send_key(key: VIRTUAL_KEY) -> Result<(), String> {
    send_key_down(key)?;
    thread::sleep(Duration::from_millis(20));
    send_key_up(key)
}

#[cfg(target_os = "windows")]
fn send_key_down(key: VIRTUAL_KEY) -> Result<(), String> {
    send_keyboard_input(key, KEYBD_EVENT_FLAGS(0))
}

#[cfg(target_os = "windows")]
fn send_key_up(key: VIRTUAL_KEY) -> Result<(), String> {
    send_keyboard_input(key, KEYEVENTF_KEYUP)
}

#[cfg(target_os = "windows")]
fn send_keyboard_input(key: VIRTUAL_KEY, flags: KEYBD_EVENT_FLAGS) -> Result<(), String> {
    let input = INPUT {
        r#type: INPUT_KEYBOARD,
        Anonymous: INPUT_0 {
            ki: KEYBDINPUT {
                wVk: key,
                wScan: 0,
                dwFlags: flags,
                time: 0,
                dwExtraInfo: 0,
            },
        },
    };
    let sent = unsafe { SendInput(&[input], std::mem::size_of::<INPUT>() as i32) };
    if sent == 1 {
        Ok(())
    } else {
        Err(format!("SendInput failed for virtual key {}", key.0))
    }
}

#[cfg(target_os = "windows")]
fn find_uia_impl(payload: UiaRequest) -> (Value, u16) {
    match find_uia_element(&payload) {
        Ok((element, window_title)) => (element_json(&element, &window_title, &payload), 200),
        Err(error) => (
            json!({
                "ok": false,
                "found": false,
                "name": payload.name,
                "role": payload.role,
                "window_title": payload.window_title,
                "error": error
            }),
            404,
        ),
    }
}

#[cfg(not(target_os = "windows"))]
fn find_uia_impl(payload: UiaRequest) -> (Value, u16) {
    (
        json!({
            "ok": false,
            "found": false,
            "name": payload.name,
            "role": payload.role,
            "window_title": payload.window_title,
            "error": "UIA not implemented on this platform"
        }),
        501,
    )
}

#[cfg(target_os = "windows")]
fn click_uia_impl(payload: UiaRequest) -> (Value, u16) {
    match find_uia_element(&payload) {
        Ok((element, window_title)) => unsafe {
            let mut point = POINT { x: 0, y: 0 };
            match element.GetClickablePoint(&mut point) {
                Ok(got_clickable) if got_clickable.as_bool() => {
                    if let Err(error) = SetCursorPos(point.x, point.y) {
                        return (
                            json!({
                                "ok": false,
                                "clicked": false,
                                "error": format!("failed to move cursor: {error}")
                            }),
                            500,
                        );
                    }
                    send_recordable_left_click(point.x, point.y);
                    let mut body = element_json(&element, &window_title, &payload);
                    body["clicked"] = json!(true);
                    (body, 200)
                }
                Ok(_) => (
                    json!({
                        "ok": false,
                        "clicked": false,
                        "name": payload.name,
                        "role": payload.role,
                        "window_title": window_title,
                        "error": "UIA element has no clickable point"
                    }),
                    404,
                ),
                Err(error) => (
                    json!({
                        "ok": false,
                        "clicked": false,
                        "name": payload.name,
                        "role": payload.role,
                        "window_title": window_title,
                        "error": format!("failed to get clickable point: {error}")
                    }),
                    500,
                ),
            }
        },
        Err(error) => (
            json!({
                "ok": false,
                "clicked": false,
                "name": payload.name,
                "role": payload.role,
                "window_title": payload.window_title,
                "error": error
            }),
            404,
        ),
    }
}

#[cfg(not(target_os = "windows"))]
fn click_uia_impl(payload: UiaRequest) -> (Value, u16) {
    (
        json!({
            "ok": false,
            "clicked": false,
            "name": payload.name,
            "role": payload.role,
            "window_title": payload.window_title,
            "error": "UIA not implemented on this platform"
        }),
        501,
    )
}

#[cfg(target_os = "windows")]
fn find_uia_element(payload: &UiaRequest) -> Result<(IUIAutomationElement, String), String> {
    unsafe {
        let automation =
            create_uia().map_err(|error| format!("failed to start UIAutomation: {error}"))?;

        if let (Some(x), Some(y)) = (payload.x, payload.y) {
            let window_title = active_window_title();
            return automation
                .ElementFromPoint(POINT { x, y })
                .map(|element| (element, window_title))
                .map_err(|error| format!("no UIA element at ({x}, {y}): {error}"));
        }

        let hwnd = target_hwnd(payload.window_title.as_deref());
        if hwnd.0.is_null() {
            return Err("no active window".to_string());
        }
        let window_title = window_title_for_hwnd(hwnd).unwrap_or_else(active_window_title);

        let root = automation
            .ElementFromHandle(hwnd)
            .map_err(|error| format!("failed to read active window UIA tree: {error}"))?;

        if let Some(name) = payload
            .name
            .as_ref()
            .filter(|value| !value.trim().is_empty())
        {
            let value = VARIANT::from(name.as_str());
            let condition = automation
                .CreatePropertyCondition(UIA_NamePropertyId, &value)
                .map_err(|error| format!("failed to create name condition: {error}"))?;
            return root
                .FindFirst(TreeScope_Subtree, &condition)
                .map(|element| (element, window_title))
                .map_err(|error| format!("UIA element named '{name}' not found: {error}"));
        }

        Ok((root, window_title))
    }
}

#[cfg(target_os = "windows")]
fn target_hwnd(window_title: Option<&str>) -> HWND {
    if let Some(title) = window_title
        .map(str::trim)
        .filter(|value| !value.is_empty())
    {
        if let Some(hwnd) = find_window_containing(title) {
            return hwnd;
        }
    }
    unsafe { GetForegroundWindow() }
}

#[cfg(target_os = "windows")]
fn window_title_for_hwnd(hwnd: HWND) -> Option<String> {
    unsafe {
        let mut buffer = [0u16; 512];
        let len = GetWindowTextW(hwnd, &mut buffer);
        (len > 0).then(|| String::from_utf16_lossy(&buffer[..len as usize]))
    }
}

#[cfg(target_os = "windows")]
fn create_uia() -> windows::core::Result<IUIAutomation> {
    unsafe {
        let _ = CoInitializeEx(None, COINIT_MULTITHREADED);
        CoCreateInstance(&CUIAutomation, None, CLSCTX_INPROC_SERVER)
    }
}

#[cfg(target_os = "windows")]
fn element_json(element: &IUIAutomationElement, window_title: &str, payload: &UiaRequest) -> Value {
    unsafe {
        let name = element
            .CurrentName()
            .map(|value| value.to_string())
            .unwrap_or_default();
        let control_type = element
            .CurrentControlType()
            .map(|value| value.0)
            .unwrap_or(0);
        let rect = element.CurrentBoundingRectangle().ok();
        let bounding_rect = rect.map(|value| {
            json!({
                "left": value.left,
                "top": value.top,
                "right": value.right,
                "bottom": value.bottom,
                "width": value.right - value.left,
                "height": value.bottom - value.top
            })
        });

        json!({
            "ok": true,
            "found": true,
            "name": name,
            "requested_name": payload.name,
            "role": payload.role,
            "control_type": control_type,
            "window_title": window_title,
            "bounding_rect": bounding_rect
        })
    }
}

#[cfg(not(target_os = "windows"))]
fn find_uia_element(_: &UiaRequest) -> Result<((), String), String> {
    Err("UIA not implemented on this platform".to_string())
}

#[cfg(not(target_os = "windows"))]
fn element_json(_: &(), _: &str, _: &UiaRequest) -> Value {
    json!({"ok": false, "found": false})
}

fn active_window() -> WindowInfo {
    let title = active_window_title();
    WindowInfo {
        app_name: app_name_from_title(&title),
        title,
    }
}

fn app_name_from_title(title: &str) -> String {
    let trimmed = title.trim();
    if trimmed.is_empty() {
        return "unknown".to_string();
    }
    let lower = trimmed.to_ascii_lowercase();
    if lower.contains("notepad++") {
        "Notepad++".to_string()
    } else if lower.contains("paint") {
        "MS Paint".to_string()
    } else if lower.contains("notepad") {
        "Notepad".to_string()
    } else if lower.contains("photoshop") {
        "Photoshop".to_string()
    } else if lower.contains("ableton") {
        "Ableton Live".to_string()
    } else if lower.contains("blender") {
        "Blender".to_string()
    } else if lower.contains("chrome") {
        "Chrome".to_string()
    } else if lower.contains("edge") {
        "Microsoft Edge".to_string()
    } else {
        trimmed.to_string()
    }
}

fn is_marouba_event(event: &RecordedEvent) -> bool {
    event
        .window_title
        .as_deref()
        .map(|title| title.trim().eq_ignore_ascii_case("Marouba"))
        .unwrap_or(false)
        || event
            .app_name
            .as_deref()
            .map(|name| name.trim().eq_ignore_ascii_case("Marouba"))
            .unwrap_or(false)
}
#[cfg(target_os = "windows")]
fn active_window_title() -> String {
    unsafe {
        let hwnd: HWND = GetForegroundWindow();
        let mut buffer = [0u16; 512];
        let len = GetWindowTextW(hwnd, &mut buffer);
        String::from_utf16_lossy(&buffer[..len as usize])
    }
}

#[cfg(not(target_os = "windows"))]
fn active_window_title() -> String {
    "unsupported platform".to_string()
}

#[cfg(target_os = "windows")]
fn active_window_rect() -> Option<WindowRect> {
    unsafe {
        let hwnd = GetForegroundWindow();
        if hwnd.0.is_null() {
            return None;
        }
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

#[cfg(not(target_os = "windows"))]
fn active_window_rect() -> Option<WindowRect> {
    None
}

#[cfg(target_os = "windows")]
fn cursor_position() -> Option<(i32, i32)> {
    unsafe {
        let mut point = POINT { x: 0, y: 0 };
        if GetCursorPos(&mut point).is_ok() {
            Some((point.x, point.y))
        } else {
            None
        }
    }
}

#[cfg(not(target_os = "windows"))]
fn cursor_position() -> Option<(i32, i32)> {
    None
}

#[cfg(target_os = "windows")]
fn key_is_down(vk: i32) -> bool {
    unsafe { (GetAsyncKeyState(vk) & 0x8000u16 as i16) != 0 }
}

#[cfg(not(target_os = "windows"))]
fn key_is_down(_: i32) -> bool {
    false
}

fn open_vault_folder() -> Result<(), String> {
    let path = vault_workflows_dir();
    std::fs::create_dir_all(&path).map_err(|error| error.to_string())?;
    #[cfg(target_os = "windows")]
    {
        open_folder_with_shell_execute(&path)
    }
    #[cfg(not(target_os = "windows"))]
    {
        let mut command = Command::new("explorer.exe");
        command.arg(path);
        no_window_command(&mut command)
            .spawn()
            .map(|_| ())
            .map_err(|error| error.to_string())
    }
}

#[cfg(target_os = "windows")]
fn open_folder_with_shell_execute(path: &PathBuf) -> Result<(), String> {
    shell_execute(&path.to_string_lossy()).or_else(|shell_error| {
        let mut command = Command::new("explorer.exe");
        command.arg(path);
        no_window_command(&mut command)
            .spawn()
            .map(|_| ())
            .map_err(|explorer_error| {
                format!(
                    "ShellExecuteW failed ({shell_error}); explorer.exe fallback failed ({explorer_error})"
                )
            })
    })
}

#[cfg(target_os = "windows")]
fn shell_execute(file: &str) -> Result<(), String> {
    let operation: Vec<u16> = "open".encode_utf16().chain(Some(0)).collect();
    let file: Vec<u16> = file.encode_utf16().chain(Some(0)).collect();
    unsafe {
        let result = ShellExecuteW(
            HWND(std::ptr::null_mut()),
            PCWSTR(operation.as_ptr()),
            PCWSTR(file.as_ptr()),
            PCWSTR::null(),
            PCWSTR::null(),
            SW_SHOWNORMAL,
        );
        if (result.0 as isize) <= 32 {
            Err(format!(
                "ShellExecuteW failed with code {}",
                result.0 as isize
            ))
        } else {
            Ok(())
        }
    }
}

fn no_window_command(command: &mut Command) -> &mut Command {
    #[cfg(target_os = "windows")]
    {
        use std::os::windows::process::CommandExt;
        command.creation_flags(0x08000000);
    }
    command
}

#[derive(Clone, Debug)]
struct WorkflowMetadata {
    description: String,
    tags: Vec<String>,
}

fn describe_with_claude(name: &str, events: &[RecordedEvent]) -> WorkflowMetadata {
    if std::env::var("ANTHROPIC_API_KEY")
        .ok()
        .filter(|value| !value.trim().is_empty())
        .is_none()
    {
        return fallback_metadata(name, events);
    }
    call_claude_summary(name, events).unwrap_or_else(|| fallback_metadata(name, events))
}

fn call_claude_summary(name: &str, events: &[RecordedEvent]) -> Option<WorkflowMetadata> {
    let api_key = std::env::var("ANTHROPIC_API_KEY").ok()?;
    let prompt = format!(
        "Summarize this Marouba recorded workflow as strict JSON with keys description and tags. Name: {name}. Steps: {}",
        serde_json::to_string(events).ok()?
    );
    let request_body = json!({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 220,
        "messages": [{"role": "user", "content": prompt}]
    });
    let temp = token_path().with_file_name("claude-summary-request.json");
    std::fs::write(&temp, serde_json::to_vec(&request_body).ok()?).ok()?;
    let mut command = Command::new("curl.exe");
    command.args([
        "-sS",
        "https://api.anthropic.com/v1/messages",
        "-H",
        &format!("x-api-key: {api_key}"),
        "-H",
        "anthropic-version: 2023-06-01",
        "-H",
        "content-type: application/json",
        "--data-binary",
        &format!("@{}", temp.display()),
    ]);
    let output = no_window_command(&mut command).output().ok()?;
    if !output.status.success() {
        return None;
    }
    let response: Value = serde_json::from_slice(&output.stdout).ok()?;
    let text = response
        .get("content")?
        .as_array()?
        .iter()
        .find_map(|part| part.get("text").and_then(Value::as_str))?;
    let parsed: Value = serde_json::from_str(text).ok()?;
    let description = parsed.get("description")?.as_str()?.trim().to_string();
    let tags = parsed
        .get("tags")
        .and_then(Value::as_array)
        .map(|values| {
            values
                .iter()
                .filter_map(Value::as_str)
                .map(slugify)
                .collect()
        })
        .unwrap_or_else(|| vec!["tray".to_string(), "recorded".to_string()]);
    Some(WorkflowMetadata { description, tags })
}

fn fallback_metadata(name: &str, events: &[RecordedEvent]) -> WorkflowMetadata {
    let apps: HashSet<String> = events
        .iter()
        .filter_map(|event| event.app_name.clone())
        .collect();
    WorkflowMetadata {
        description: format!(
            "Tray-recorded workflow '{}' with {} captured events.",
            name,
            events.len()
        ),
        tags: vec![
            "tray".to_string(),
            "recorded".to_string(),
            apps.iter()
                .next()
                .map(|value| slugify(value))
                .unwrap_or_else(|| "workflow".to_string()),
        ],
    }
}

fn write_workflow(
    name: &str,
    events: &[RecordedEvent],
    metadata: WorkflowMetadata,
) -> Result<PathBuf, String> {
    let id = slugify(name);
    let today = current_date_string();
    let app = workflow_app_from_events(events);
    let events_json = serde_json::to_string_pretty(events).map_err(|error| error.to_string())?;
    let routes_json = format!(
        "[\n  {{\n    \"type\": \"gesture\",\n    \"events\": {},\n    \"target_window\": {}\n  }}\n]",
        indent_json_value(&events_json, 4),
        yaml_scalar(&app),
    );

    let body = format!(
        "---\n\
id: {}\n\
name: {}\n\
app: {}\n\
description: {}\n\
params: []\n\
tags: {}\n\
author: nxeratech\n\
created: {}\n\
last_verified: {}\n\
source: self_taught\n\
routes: {}\n\
fallback_order: [gesture, ask]\n\
verification: {{\"type\":\"none\"}}\n\
calls: []\n\
depends_on: []\n\
---\n\n\
# {}\n\n{}\n\nCaptured raw event stream is stored in the gesture route.\n",
        yaml_scalar(&id),
        yaml_scalar(name),
        yaml_scalar(&app),
        yaml_scalar(&metadata.description),
        serde_json::to_string(&metadata.tags).unwrap_or_else(|_| "[]".to_string()),
        today,
        today,
        routes_json.replace('\n', "\n  "),
        name,
        metadata.description,
    );
    let dir = vault_workflows_dir();
    std::fs::create_dir_all(&dir).map_err(|error| error.to_string())?;
    let path = dir.join(format!("{id}.md"));
    std::fs::write(&path, body).map_err(|error| error.to_string())?;
    Ok(path)
}

fn workflow_app_from_events(events: &[RecordedEvent]) -> String {
    for event in events
        .iter()
        .filter(|event| !is_empty_unknown_system_event(event))
    {
        if let Some(app_name) = event.app_name.as_deref().map(str::trim) {
            if !app_name.is_empty() && !app_name.eq_ignore_ascii_case("unknown") {
                return app_name.to_string();
            }
        }
    }
    for event in events
        .iter()
        .filter(|event| !is_empty_unknown_system_event(event))
    {
        if let Some(window_title) = event.window_title.as_deref().map(str::trim) {
            if !window_title.is_empty() {
                return window_title.to_string();
            }
        }
    }
    "Windows".to_string()
}

fn yaml_scalar(value: &str) -> String {
    serde_json::to_string(value).unwrap_or_else(|_| "\"\"".to_string())
}

fn indent_json_value(value: &str, spaces: usize) -> String {
    let padding = " ".repeat(spaces);
    value
        .lines()
        .enumerate()
        .map(|(index, line)| {
            if index == 0 {
                line.to_string()
            } else {
                format!("{padding}{line}")
            }
        })
        .collect::<Vec<_>>()
        .join("\n")
}

fn slugify(value: &str) -> String {
    let mut slug = String::new();
    let mut last_dash = false;
    for ch in value.chars().flat_map(char::to_lowercase) {
        if ch.is_ascii_alphanumeric() {
            slug.push(ch);
            last_dash = false;
        } else if !last_dash {
            slug.push('-');
            last_dash = true;
        }
    }
    let slug = slug.trim_matches('-').to_string();
    if slug.is_empty() {
        "workflow".to_string()
    } else {
        slug
    }
}

fn current_date_string() -> String {
    let mut command = Command::new("powershell.exe");
    command.args(["-NoProfile", "-Command", "Get-Date -Format yyyy-MM-dd"]);
    let output = no_window_command(&mut command).output();
    if let Ok(output) = output {
        if output.status.success() {
            let value = String::from_utf8_lossy(&output.stdout).trim().to_string();
            if !value.is_empty() {
                return value;
            }
        }
    }
    let days = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_secs() / 86_400)
        .unwrap_or(0);
    format!("unix-day-{days}")
}

#[cfg(target_os = "windows")]
fn ableton_note_label_y_with_timeout(
    window_title: Option<&str>,
    note_name: &str,
    timeout_ms: u64,
) -> Result<i32, String> {
    let (sender, receiver) = mpsc::channel();
    let worker_name = note_name.to_string();
    let worker_window_title = window_title.map(str::to_string);
    thread::spawn(move || {
        let result = uia_clickable_point_by_name(&worker_name, worker_window_title.as_deref())
            .map(|(_x, y)| y);
        let _ = sender.send(result);
    });
    match receiver.recv_timeout(Duration::from_millis(timeout_ms)) {
        Ok(result) => result,
        Err(_) => Err(format!(
            "Ableton note label lookup timed out after {timeout_ms}ms"
        )),
    }
}

#[cfg(not(target_os = "windows"))]
fn ableton_note_label_y_with_timeout(_: Option<&str>, _: &str, _: u64) -> Result<i32, String> {
    Err("Ableton note label lookup not implemented on this platform".to_string())
}

fn ableton_legacy_octave_correction_px(rect: Option<&WindowRect>) -> i32 {
    rect.map(|value| ((value.height as f64) * 0.091).round() as i32)
        .unwrap_or(84)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ocr_match_point_uses_phrase_bounds_for_multi_word_preset() {
        let words = vec![
            OcrWord {
                text: "Audio".to_string(),
                left: 10,
                top: 10,
                width: 40,
                height: 12,
            },
            OcrWord {
                text: "Azimuth".to_string(),
                left: 100,
                top: 40,
                width: 60,
                height: 14,
            },
            OcrWord {
                text: "Bass.adv".to_string(),
                left: 164,
                top: 40,
                width: 62,
                height: 14,
            },
        ];

        assert_eq!(ocr_match_point(&words, "Azimuth Bass.adv"), Some((163, 47)));
    }

    #[test]
    fn ocr_row_label_near_y_combines_split_drum_names() {
        let words = vec![
            OcrWord {
                text: "Low".to_string(),
                left: 57,
                top: 70,
                width: 54,
                height: 22,
            },
            OcrWord {
                text: "tom".to_string(),
                left: 119,
                top: 65,
                width: 60,
                height: 23,
            },
            OcrWord {
                text: "Snare".to_string(),
                left: 60,
                top: 140,
                width: 82,
                height: 24,
            },
            OcrWord {
                text: "Drum".to_string(),
                left: 150,
                top: 136,
                width: 78,
                height: 24,
            },
        ];

        assert_eq!(
            ocr_row_label_near_y(&words, 150),
            Some("Snare Drum".to_string())
        );
    }

    #[test]
    fn add_semantic_tag_appends_without_overwriting_ableton_context() {
        let mut event = RecordedEvent {
            kind: "mousedown".to_string(),
            event_type: None,
            timestamp_ms: 0,
            x: None,
            y: None,
            normalized_x: None,
            normalized_y: None,
            button: Some("left".to_string()),
            key: None,
            note: None,
            velocity: None,
            window_title: Some("Untitled - Ableton Live 12 Suite".to_string()),
            app_name: Some("Ableton Live".to_string()),
            window_rect: None,
            element_name: None,
            element_role: None,
            colour_hex: None,
            semantic: Some("channel:Drums".to_string()),
        };

        add_semantic_tag(&mut event, "midi_note:Crash");
        add_semantic_tag(&mut event, "midi_note:Crash");

        assert_eq!(
            event.semantic.as_deref(),
            Some("channel:Drums;midi_note:Crash")
        );
    }

    fn ableton_test_event(name: &str, semantic: Option<&str>) -> RecordedEvent {
        RecordedEvent {
            kind: "mousedown".to_string(),
            event_type: None,
            timestamp_ms: 0,
            x: Some(100),
            y: Some(500),
            normalized_x: Some(0.25),
            normalized_y: Some(0.75),
            button: Some("left".to_string()),
            key: None,
            note: None,
            velocity: None,
            window_title: Some("Untitled - Ableton Live 12 Suite".to_string()),
            app_name: Some("Ableton Live".to_string()),
            window_rect: Some(WindowRect {
                left: 10,
                top: 20,
                width: 800,
                height: 900,
            }),
            element_name: Some(name.to_string()),
            element_role: Some("50026".to_string()),
            colour_hex: None,
            semantic: semantic.map(str::to_string),
        }
    }

    #[test]
    fn legacy_ableton_note_without_semantic_gets_octave_correction() {
        let event = ableton_test_event("Untitled clip, in track Drums, scene 1, 1.1.2", None);
        let live_rect = WindowRect {
            left: 10,
            top: 20,
            width: 800,
            height: 900,
        };

        let (_x, y) =
            resolve_ableton_replay_point_with_note_context(&event, Some(&live_rect), false);

        assert_eq!(y, 20 + (0.75_f64 * 900.0).round() as i32 + 82);
    }

    #[test]
    fn ableton_note_with_midi_row_semantic_does_not_get_legacy_octave_offset() {
        let event = ableton_test_event(
            "Untitled clip, in track Drums, scene 1, 1.1.2",
            Some("channel:Drums;midi_row:0.750000"),
        );
        let live_rect = WindowRect {
            left: 10,
            top: 20,
            width: 800,
            height: 900,
        };

        let (_x, y) =
            resolve_ableton_replay_point_with_note_context(&event, Some(&live_rect), false);

        assert_eq!(y, 20 + (0.75_f64 * 900.0).round() as i32);
    }

    #[test]
    fn ableton_row_label_element_is_treated_as_note_event() {
        let event = ableton_test_event("Closed Hi Hat", None);

        assert!(is_ableton_piano_roll_note_event(&event));
    }

    #[test]
    fn ableton_browser_category_semantic_is_recorded_without_overwriting_context() {
        let mut event = ableton_test_event("Instruments", Some("channel:3 Azimuth Bass"));

        enrich_ableton_recorded_event(&mut event, 700);

        assert_eq!(
            event.semantic.as_deref(),
            Some("channel:3 Azimuth Bass;browser_category:Instruments")
        );
    }

    #[test]
    fn ableton_device_and_target_channel_semantics_are_detected() {
        let down = ableton_test_event("Limiter", Some("device:Limiter"));
        let up = ableton_test_event("Master", Some("channel:Master"));

        assert_eq!(ableton_device_name(&down), Some("Limiter".to_string()));
        assert_eq!(
            ableton_target_channel_for_device_drag(&down, &up),
            Some("Master".to_string())
        );
        assert!(ableton_is_device_name("EQ Eight"));
        assert_eq!(
            ableton_browser_category_for_device("EQ Eight"),
            Some("Audio Effects")
        );
    }

    #[test]
    fn ableton_channel_names_cover_master_main_and_instrument_tracks() {
        assert_eq!(
            ableton_channel_from_element_name("Main"),
            Some("Master".to_string())
        );
        assert_eq!(
            ableton_channel_from_element_name("Limiter, in track 3 Azimuth Bass"),
            Some("3 Azimuth Bass".to_string())
        );
        assert_eq!(
            ableton_channel_from_element_name("Track 5 Group"),
            Some("5 Group".to_string())
        );
    }

    #[test]
    fn ableton_send_knobs_and_automation_arm_are_recognized() {
        let send = ableton_test_event("A-Reverb", Some("automation_parameter:A-Reverb"));
        let automation = ableton_test_event("Arrangement Record", Some("automation_record"));

        assert!(is_ableton_knob_or_eq_event(&send));
        assert!(is_ableton_automation_record_event(&automation));
        assert!(ableton_is_automation_parameter_name("Send A"));
        assert!(ableton_is_automation_parameter_name("B-Delay"));
    }

    #[test]
    fn ableton_replay_timing_preserves_automation_gaps() {
        let current = ableton_test_event("A-Reverb", Some("automation_parameter:A-Reverb"));
        let mut next = ableton_test_event("A-Reverb", Some("automation_parameter:A-Reverb"));
        next.timestamp_ms = 5_000;

        assert_eq!(
            replay_event_delay(&current, Some(&next)),
            Duration::from_millis(5_000)
        );
    }

    #[cfg(target_os = "windows")]
    #[test]
    fn ableton_executable_search_matches_direct_live_exe() {
        let root = std::env::temp_dir().join(format!(
            "marouba-ableton-search-test-{}",
            std::process::id()
        ));
        let program = root.join("Live 12 Suite").join("Program");
        std::fs::create_dir_all(&program).expect("create fake Ableton install");
        let exe = program.join("Ableton Live 12 Suite.exe");
        std::fs::write(&exe, b"").expect("write fake Ableton exe");

        assert_eq!(find_ableton_live_executable_in_tree(&root), Some(exe));

        let _ = std::fs::remove_dir_all(root);
    }

    #[test]
    fn ableton_browser_item_matching_rejects_neighbor_rows() {
        assert!(ableton_browser_item_name_matches(
            "E-Piano Dreamy.adv",
            "E-Piano Dreamy.adg"
        ));
        assert!(!ableton_browser_item_name_matches(
            "E-Piano Dreamy.adv",
            "E-Piano Detuned.adv"
        ));
    }

    #[test]
    fn ableton_browser_retry_point_uses_detected_row_height() {
        let rect = WindowRect {
            left: 680,
            top: 410,
            width: 180,
            height: 18,
        };

        assert_eq!(ableton_next_browser_row_point(705, &rect), (705, 437));
    }

    #[test]
    fn ableton_computer_keyboard_note_mapping_matches_vault_format() {
        let window = WindowInfo {
            title: "Untitled - Ableton Live 12 Suite".to_string(),
            app_name: "Ableton Live".to_string(),
        };
        let event = keyboard_event_record("keydown", 90, 1234, &window, "Ableton Live", true);

        assert_eq!(event.kind, "note_on");
        assert_eq!(event.event_type.as_deref(), Some("note_on"));
        assert_eq!(event.key.as_deref(), Some("z"));
        assert_eq!(event.note.as_deref(), Some("C3"));
        assert_eq!(event.velocity, Some(100));
        assert_eq!(event.semantic.as_deref(), Some("midi_note:C3"));
    }

    #[test]
    fn recorded_key_parser_accepts_note_labels_and_legacy_virtual_keys() {
        assert_eq!(vk_from_recorded_key("z"), Ok(90));
        assert_eq!(vk_from_recorded_key("90"), Ok(90));
    }

    #[test]
    fn non_ableton_replay_timing_stays_capped() {
        let current = RecordedEvent {
            kind: "mousedown".to_string(),
            event_type: None,
            timestamp_ms: 0,
            x: None,
            y: None,
            normalized_x: None,
            normalized_y: None,
            button: Some("left".to_string()),
            key: None,
            note: None,
            velocity: None,
            window_title: Some("Untitled - Notepad".to_string()),
            app_name: Some("Notepad".to_string()),
            window_rect: None,
            element_name: None,
            element_role: None,
            colour_hex: None,
            semantic: None,
        };
        let mut next = current.clone();
        next.timestamp_ms = 5_000;

        assert_eq!(
            replay_event_delay(&current, Some(&next)),
            Duration::from_millis(1_000)
        );
    }
}
