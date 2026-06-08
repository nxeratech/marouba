#![windows_subsystem = "windows"]

use rand::{distributions::Alphanumeric, Rng};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::HashSet;
use std::path::PathBuf;
use std::process::Command;
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};
use tauri::image::Image;
use tauri::menu::{Menu, MenuItem};
use tauri::tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent};
use tauri::{AppHandle, Manager};
use tiny_http::{Header, Method, Response, Server, StatusCode};

#[cfg(target_os = "windows")]
use windows::core::PCWSTR;
#[cfg(target_os = "windows")]
use windows::core::VARIANT;
#[cfg(target_os = "windows")]
use windows::Win32::Foundation::{BOOL, HWND, LPARAM, POINT, RECT, WPARAM};
#[cfg(target_os = "windows")]
use windows::Win32::System::Com::{
    CoCreateInstance, CoInitializeEx, CLSCTX_INPROC_SERVER, COINIT_MULTITHREADED,
};
#[cfg(target_os = "windows")]
use windows::Win32::Graphics::Gdi::{
    BitBlt, CreateCompatibleBitmap, CreateCompatibleDC, DeleteDC, DeleteObject, GetDC, GetPixel,
    ReleaseDC, SelectObject, SRCCOPY,
};
#[cfg(target_os = "windows")]
use windows::Win32::UI::Accessibility::{
    CUIAutomation, IUIAutomation, IUIAutomationElement, TreeScope_Subtree, UIA_NamePropertyId,
};
#[cfg(target_os = "windows")]
use windows::Win32::UI::Input::KeyboardAndMouse::{
    mouse_event, GetAsyncKeyState, SendInput, INPUT, INPUT_0, INPUT_KEYBOARD,
    INPUT_MOUSE, KEYBDINPUT, KEYBD_EVENT_FLAGS, KEYEVENTF_KEYUP, MOUSEEVENTF_LEFTDOWN,
    MOUSEEVENTF_LEFTUP, MOUSEEVENTF_MOVE, MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP,
    MOUSEINPUT, VIRTUAL_KEY, VK_BACK, VK_CONTROL, VK_ESCAPE, VK_LBUTTON, VK_MENU, VK_RBUTTON,
    VK_RETURN, VK_TAB,
};
#[cfg(target_os = "windows")]
use windows::Win32::UI::Shell::ShellExecuteW;
#[cfg(target_os = "windows")]
use windows::Win32::UI::WindowsAndMessaging::{
    EnumWindows, GetCursorPos, GetForegroundWindow, GetWindowRect, GetWindowTextW,
    IsWindowVisible, SendMessageW, SetCursorPos, SetForegroundWindow, SW_SHOWNORMAL, WM_SETFOCUS,
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
    timestamp_ms: u128,
    x: Option<i32>,
    y: Option<i32>,
    normalized_x: Option<f64>,
    normalized_y: Option<f64>,
    button: Option<String>,
    key: Option<String>,
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

    builder = builder.icon(Image::new(include_bytes!("../icons/tray_icon_rgba.bin"), 32, 32));
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
fn delete_step(index: usize, state: tauri::State<Arc<Mutex<AppState>>>) -> Result<RecordingStatus, String> {
    let mut guard = state.lock().map_err(|_| "recording state is unavailable".to_string())?;
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
    let guard = state.lock().map_err(|_| "recording state is unavailable".to_string())?;
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
    let mut guard = state.lock().map_err(|_| "recording state is unavailable".to_string())?;
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
        let mut guard = state.lock().map_err(|_| "recording state is unavailable".to_string())?;
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
    let mut guard = state.lock().map_err(|_| "recording state is unavailable".to_string())?;
    guard.recording = false;
    let before_count = guard.events.len();
    guard.events.retain(|event| !is_marouba_event(event));
    let event_count = guard.events.len();
    let removed_count = before_count.saturating_sub(event_count);
    if removed_count > 0 {
        push_log(&mut guard, format!("Filtered {removed_count} Marouba control steps"));
    }
    push_log(&mut guard, format!("Recording stopped: {event_count} steps"));
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
            active_window: WindowInfo { title: "unknown".to_string(), app_name: "unknown".to_string() },
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
                    timestamp_ms: started.elapsed().as_millis(),
                    x: None,
                    y: None,
                    normalized_x: None,
                    normalized_y: None,
                    button: None,
                    key: None,
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
            if last_pos != Some((x, y)) {
                last_pos = Some((x, y));
                if should_record_mousemove(last_mousemove_pos, x, y) {
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

            #[cfg(target_os = "windows")]
            let left = key_is_down(VK_LBUTTON.0 as i32);
            #[cfg(not(target_os = "windows"))]
            let left = false;
            if left != last_left {
                last_left = left;
                push_event(
                    &state,
                    mouse_event_record(
                        if left { "mousedown" } else { "mouseup" },
                        x,
                        y,
                        Some("left".to_string()),
                        started.elapsed().as_millis(),
                        &window,
                        &current_app_name,
                    ),
                );
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
                    push_event(
                        &state,
                        RecordedEvent {
                            kind: "keydown".to_string(),
                            timestamp_ms: started.elapsed().as_millis(),
                            x: None,
                            y: None,
                            normalized_x: None,
                            normalized_y: None,
                            button: None,
                            key: Some(vk.to_string()),
                            window_title: Some(window.title.clone()),
                            app_name: Some(current_app_name.clone()),
                            window_rect: active_window_rect(),
                            element_name: None,
                            element_role: None,
                            colour_hex: None,
                            semantic: None,
                        },
                    );
                }
            }
        }
        for vk in last_keys.difference(&current_keys) {
            push_event(
                &state,
                RecordedEvent {
                    kind: "keyup".to_string(),
                    timestamp_ms: started.elapsed().as_millis(),
                    x: None,
                    y: None,
                    normalized_x: None,
                    normalized_y: None,
                    button: None,
                    key: Some(vk.to_string()),
                    window_title: Some(window.title.clone()),
                    app_name: Some(current_app_name.clone()),
                    window_rect: active_window_rect(),
                    element_name: None,
                    element_role: None,
                    colour_hex: None,
                    semantic: None,
                },
            );
        }
        last_keys = current_keys;
        thread::sleep(Duration::from_millis(45));
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

fn should_record_mousemove(previous: Option<(i32, i32)>, x: i32, y: i32) -> bool {
    match previous {
        None => true,
        Some((previous_x, previous_y)) => {
            let dx = (x - previous_x) as f64;
            let dy = (y - previous_y) as f64;
            (dx * dx + dy * dy).sqrt() > 8.0
        }
    }
}

fn push_log(state: &mut AppState, label: String) {
    state.last_actions.insert(0, label);
    state.last_actions.truncate(5);
}

fn event_label(event: &RecordedEvent) -> String {
    match event.kind.as_str() {
        "mousemove" => format!("Mouse move {}, {}", event.x.unwrap_or(0), event.y.unwrap_or(0)),
        "mousedown" | "mouseup" => format!("{} {} {}, {}", event.kind, event.button.as_deref().unwrap_or("left"), event.x.unwrap_or(0), event.y.unwrap_or(0)),
        "keydown" | "keyup" => format!("{} {}", event.kind, event.key.as_deref().unwrap_or("?")),
        "focus" => format!("Focus {}", event.window_title.as_deref().unwrap_or("unknown")),
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
        timestamp_ms,
        x: Some(x),
        y: Some(y),
        normalized_x,
        normalized_y,
        button,
        key: None,
        window_title: Some(window.title.clone()),
        app_name: Some(app_name),
        window_rect: rect,
        element_name: None,
        element_role: None,
        colour_hex: None,
        semantic: None,
    };
    if kind == "mousedown" {
        if let Ok((element, _)) = find_uia_element(&UiaRequest {
            name: None,
            role: None,
            window_title: None,
            x: Some(x),
            y: Some(y),
        }) {
            let body = element_json(&element, event.window_title.as_deref().unwrap_or(""), &UiaRequest {
                name: None,
                role: None,
                window_title: None,
                x: Some(x),
                y: Some(y),
            });
            event.element_name = body.get("name").and_then(Value::as_str).map(str::to_string);
            event.element_role = body.get("control_type").map(Value::to_string);
        }
        let paint_window = is_ms_paint_event(&event) || title_is_ms_paint(&window.title);
        let in_colour_bar = normalized_y
            .map(|value| value < 0.16 && value > 0.09)
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
                window.title,
                current_app_name
            );
        }
    }
    event
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
    command
        .current_dir(marouba_root_dir())
        .args(["scripts/replay.py", "--workflow", &name, "--params", "{}"]);
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
    if let Some(app_name) = parse_workflow_app_name(name) {
        push_unique_window(&mut candidates, app_name);
    }
    for event in events {
        if let Some(title) = event.window_title.as_ref() {
            push_unique_window(&mut candidates, title.clone());
        }
    }
    candidates.sort_by_key(|title| if is_known_creative_window(title) { 0 } else { 1 });
    candidates
}

fn push_unique_window(candidates: &mut Vec<String>, title: String) {
    let trimmed = title.trim();
    if trimmed.is_empty() {
        return;
    }
    if !candidates.iter().any(|candidate| candidate.eq_ignore_ascii_case(trimmed)) {
        candidates.push(trimmed.to_string());
    }
}

fn is_known_creative_window(title: &str) -> bool {
    let lower = title.to_ascii_lowercase();
    ["paint", "photoshop", "ableton", "blender", "comfyui", "chrome", "edge"]
        .iter()
        .any(|needle| lower.contains(needle))
}

#[cfg(target_os = "windows")]
fn ensure_target_window_ready(candidates: &[String]) -> Result<String, String> {
    if let Ok(window_title) = focus_first_available_window(candidates) {
        return Ok(window_title);
    }
    let app = launchable_app_for_targets(candidates)
        .ok_or_else(|| format!("Could not launch the target app. Please open it manually."))?;
    launch_app(&app)?;
    for _ in 0..6 {
        thread::sleep(Duration::from_millis(500));
        if let Ok(window_title) = focus_first_available_window(candidates) {
            return Ok(window_title);
        }
    }
    Err(format!("Could not launch {}. Please open it manually.", app.display_name))
}

#[cfg(not(target_os = "windows"))]
fn ensure_target_window_ready(candidates: &[String]) -> Result<String, String> {
    focus_first_available_window(candidates)
}

#[cfg(target_os = "windows")]
struct LaunchableApp {
    display_name: &'static str,
    executable: &'static str,
}

#[cfg(target_os = "windows")]
fn launchable_app_for_targets(candidates: &[String]) -> Option<LaunchableApp> {
    candidates.iter().find_map(|candidate| {
        let lower = candidate.to_ascii_lowercase();
        if lower.contains("paint") {
            Some(LaunchableApp {
                display_name: "Paint",
                executable: "mspaint.exe",
            })
        } else {
            None
        }
    })
}

#[cfg(target_os = "windows")]
fn launch_app(app: &LaunchableApp) -> Result<(), String> {
    shell_execute(app.executable).map_err(|error| {
        format!(
            "Could not launch {}. Please open it manually. ({error})",
            app.display_name
        )
    })
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
        if SetForegroundWindow(hwnd).as_bool() {
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
    let mut search = WindowSearch { needles, hwnd: None };
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
    if name.is_empty() || !name.chars().all(|ch| ch.is_ascii_alphanumeric() || ch == '-' || ch == '_') {
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
    request.headers().iter().any(|header| {
        header.field.equiv("Authorization") && header.value.as_str() == expected
    })
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
    let allow_methods = Header::from_bytes(
        "Access-Control-Allow-Methods",
        "GET, POST, OPTIONS",
    )
    .unwrap();
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
    // BlockInput removed — caused system lockout on replay failure.
    let mut replay_rect = active_window_rect();
    write_debug_log(&format!("replay_mouse called, events count: {}", payload.events.len()));
    let mut replayed = 0usize;
    let mut skipped_colour_mouseup = false;
    if replay_payload_targets_ms_paint(&payload) {
        match prepare_ms_paint_replay_tool(&payload) {
            Ok(rect) => replay_rect = Some(rect),
            Err(error) => {
                return (
                    json!({
                        "ok": false,
                        "replayed": replayed,
                        "target_window": payload.target_window,
                        "error": error
                    }),
                    500,
                );
            }
        }
    }
    for event in payload.events.iter().filter(|event| {
        matches!(event.kind.as_str(), "mousemove" | "mousedown" | "mouseup")
    }) {
        if skipped_colour_mouseup && event.kind == "mouseup" {
            skipped_colour_mouseup = false;
            continue;
        }
        if is_colour_select_event(event) {
            if let Some(colour_hex) = event.colour_hex.as_deref() {
                write_debug_log(&format!("colour_select: hex={colour_hex}"));
                match replay_ms_paint_colour_select(colour_hex) {
                    Ok(()) => {
                        skipped_colour_mouseup = true;
                        replayed += 1;
                        continue;
                    }
                    Err(error) => {
                        return (
                            json!({
                                "ok": false,
                                "replayed": replayed,
                                "target_window": payload.target_window,
                                "error": error
                            }),
                            500,
                        );
                    }
                }
            }
        }
        let (x, y) = resolve_replay_point(event, replay_rect.as_ref());
        write_debug_log(&format!(
            "event: {} {:?} {:?} -> screen {},{}",
            event.kind,
            event.normalized_x,
            event.normalized_y,
            x,
            y
        ));
        unsafe {
            let _ = SetCursorPos(x, y);
            match (event.kind.as_str(), event.button.as_deref().unwrap_or("left")) {
                ("mousemove", _) => mouse_event(MOUSEEVENTF_MOVE, 0, 0, 0, 0),
                ("mousedown", "right") => mouse_event(MOUSEEVENTF_RIGHTDOWN, x, y, 0, 0),
                ("mouseup", "right") => mouse_event(MOUSEEVENTF_RIGHTUP, x, y, 0, 0),
                ("mousedown", _) => mouse_event(MOUSEEVENTF_LEFTDOWN, x, y, 0, 0),
                ("mouseup", _) => mouse_event(MOUSEEVENTF_LEFTUP, x, y, 0, 0),
                _ => {}
            }
        }
        replayed += 1;
        thread::sleep(Duration::from_millis(20));
    }
    (json!({"ok": true, "replayed": replayed, "target_window": payload.target_window}), 200)
}

#[cfg(not(target_os = "windows"))]
fn replay_mouse(payload: MouseReplayRequest) -> (Value, u16) {
    (json!({"ok": false, "replayed": 0, "target_window": payload.target_window, "error": "mouse replay not implemented on this platform"}), 501)
}

fn resolve_replay_point(event: &RecordedEvent, rect: Option<&WindowRect>) -> (i32, i32) {
    let replay_rect = rect.or(event.window_rect.as_ref());
    if let (Some(rect), Some(nx), Some(ny)) = (replay_rect, event.normalized_x, event.normalized_y) {
        let x = rect.left + (nx.clamp(0.0, 1.0) * rect.width as f64).round() as i32;
        let y = rect.top + (ny.clamp(0.0, 1.0) * rect.height as f64).round() as i32;
        return (x, y);
    }
    (event.x.unwrap_or(0), event.y.unwrap_or(0))
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
        .open(r"C:\Share\Marouba\companion\replay-debug.log")
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
        eprintln!("[Marouba] Raw COLORREF sampled at ({x}, {y}): 0x{:08X}", colour.0);
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
        let _ = SendMessageW(hwnd, WM_SETFOCUS, WPARAM(0), LPARAM(0));
    }
    write_debug_log("WM_SETFOCUS sent");
    thread::sleep(Duration::from_millis(300));
    send_key(VK_ESCAPE)?;
    write_debug_log("sent key: VK_ESCAPE");
    thread::sleep(Duration::from_millis(200));
    send_key(VK_ESCAPE)?;
    write_debug_log("sent key: VK_ESCAPE");
    thread::sleep(Duration::from_millis(200));
    let (click_x, click_y) = click_window_normalized(&rect, 0.168, 0.138, "Paint pencil tool")?;
    write_debug_log(&format!("canvas click sent at {click_x},{click_y}"));
    thread::sleep(Duration::from_millis(300));
    Ok(rect)
}

#[cfg(target_os = "windows")]
fn find_paint_window(payload: &MouseReplayRequest) -> Option<(HWND, WindowRect)> {
    let mut candidates = Vec::new();
    if let Some(target) = payload.target_window.as_deref().filter(|value| title_is_ms_paint(value)) {
        candidates.push(target.to_string());
    }
    if let Some(app) = payload.workflow_app.as_deref().filter(|value| title_is_ms_paint(value)) {
        candidates.push(app.to_string());
    }
    if let Some(title) = first_valid_event_window_title(&payload.events)
        .filter(|value| title_is_ms_paint(value))
    {
        candidates.push(title);
    }
    for event in &payload.events {
        if let Some(title) = event.window_title.as_deref().filter(|value| title_is_ms_paint(value)) {
            if !candidates.iter().any(|candidate| candidate.eq_ignore_ascii_case(title)) {
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
fn click_window_normalized(rect: &WindowRect, normalized_x: f64, normalized_y: f64, label: &str) -> Result<(i32, i32), String> {
    let x = rect.left + (normalized_x.clamp(0.0, 1.0) * rect.width as f64).round() as i32;
    let y = rect.top + (normalized_y.clamp(0.0, 1.0) * rect.height as f64).round() as i32;
    unsafe {
        SetCursorPos(x, y).map_err(|error| format!("failed to move cursor to {label}: {error}"))?;
    }
    send_mouse_click()?;
    Ok((x, y))
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
    let red = u8::from_str_radix(&hex[0..2], 16).map_err(|_| format!("invalid red value in '{value}'"))?;
    let green = u8::from_str_radix(&hex[2..4], 16).map_err(|_| format!("invalid green value in '{value}'"))?;
    let blue = u8::from_str_radix(&hex[4..6], 16).map_err(|_| format!("invalid blue value in '{value}'"))?;
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
fn send_mouse_click() -> Result<(), String> {
    let down = INPUT {
        r#type: INPUT_MOUSE,
        Anonymous: INPUT_0 {
            mi: MOUSEINPUT {
                dx: 0,
                dy: 0,
                mouseData: 0,
                dwFlags: MOUSEEVENTF_LEFTDOWN,
                time: 0,
                dwExtraInfo: 0,
            },
        },
    };
    let up = INPUT {
        r#type: INPUT_MOUSE,
        Anonymous: INPUT_0 {
            mi: MOUSEINPUT {
                dx: 0,
                dy: 0,
                mouseData: 0,
                dwFlags: MOUSEEVENTF_LEFTUP,
                time: 0,
                dwExtraInfo: 0,
            },
        },
    };
    let sent = unsafe { SendInput(&[down, up], std::mem::size_of::<INPUT>() as i32) };
    if sent == 2 {
        Ok(())
    } else {
        Err("SendInput failed while clicking Paint canvas center".to_string())
    }
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
                    mouse_event(MOUSEEVENTF_LEFTDOWN, point.x, point.y, 0, 0);
                    mouse_event(MOUSEEVENTF_LEFTUP, point.x, point.y, 0, 0);
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
        let automation = create_uia().map_err(|error| format!("failed to start UIAutomation: {error}"))?;
        let window_title = active_window_title();

        if let (Some(x), Some(y)) = (payload.x, payload.y) {
            return automation
                .ElementFromPoint(POINT { x, y })
                .map(|element| (element, window_title))
                .map_err(|error| format!("no UIA element at ({x}, {y}): {error}"));
        }

        let hwnd = GetForegroundWindow();
        if hwnd.0.is_null() {
            return Err("no active window".to_string());
        }

        let root = automation
            .ElementFromHandle(hwnd)
            .map_err(|error| format!("failed to read active window UIA tree: {error}"))?;

        if let Some(name) = payload.name.as_ref().filter(|value| !value.trim().is_empty()) {
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
        let control_type = element.CurrentControlType().map(|value| value.0).unwrap_or(0);
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
    if lower.contains("paint") {
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
            Err(format!("ShellExecuteW failed with code {}", result.0 as isize))
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
    if std::env::var("ANTHROPIC_API_KEY").ok().filter(|value| !value.trim().is_empty()).is_none() {
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
        .map(|values| values.iter().filter_map(Value::as_str).map(slugify).collect())
        .unwrap_or_else(|| vec!["tray".to_string(), "recorded".to_string()]);
    Some(WorkflowMetadata { description, tags })
}

fn fallback_metadata(name: &str, events: &[RecordedEvent]) -> WorkflowMetadata {
    let apps: HashSet<String> = events.iter().filter_map(|event| event.app_name.clone()).collect();
    WorkflowMetadata {
        description: format!("Tray-recorded workflow '{}' with {} captured events.", name, events.len()),
        tags: vec![
            "tray".to_string(),
            "recorded".to_string(),
            apps.iter().next().map(|value| slugify(value)).unwrap_or_else(|| "workflow".to_string()),
        ],
    }
}

fn write_workflow(name: &str, events: &[RecordedEvent], metadata: WorkflowMetadata) -> Result<PathBuf, String> {
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
    for event in events.iter().filter(|event| !is_empty_unknown_system_event(event)) {
        if let Some(app_name) = event.app_name.as_deref().map(str::trim) {
            if !app_name.is_empty() && !app_name.eq_ignore_ascii_case("unknown") {
                return app_name.to_string();
            }
        }
    }
    for event in events.iter().filter(|event| !is_empty_unknown_system_event(event)) {
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
    if slug.is_empty() { "workflow".to_string() } else { slug }
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
