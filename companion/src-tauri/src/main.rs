use serde::{Deserialize, Serialize};
use serde_json::json;
use std::io::Read;
use std::path::PathBuf;
use std::thread;
use tiny_http::{Header, Method, Response, Server, StatusCode};
use rand::{distributions::Alphanumeric, Rng};

#[cfg(target_os = "windows")]
use windows::Win32::Foundation::HWND;
#[cfg(target_os = "windows")]
use windows::Win32::UI::WindowsAndMessaging::{GetForegroundWindow, GetWindowTextW};

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

#[derive(Debug, Serialize)]
struct WindowInfo {
    title: String,
    app_name: String,
}

fn main() {
    let token = load_or_create_token();
    thread::spawn(move || start_http_api(token));

    tauri::Builder::default()
        .setup(|app| {
            let _tray = tauri::tray::TrayIconBuilder::new()
                .tooltip("Marouba Companion")
                .build(app)?;
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running Marouba Companion");
}

fn start_http_api(token: String) {
    let server = Server::http("127.0.0.1:7842").expect("failed to bind companion API");
    for mut request in server.incoming_requests() {
        if !is_authorized(&request, &token) {
            let _ = request.respond(json_response(json!({"error": "unauthorized"}), 401));
            continue;
        }
        let method = request.method().clone();
        let url = request.url().to_string();
        let response = match (method, url.as_str()) {
            (Method::Get, "/health") => json_response(json!({"status": "ok"}), 200),
            (Method::Get, "/window") => json_response(json!(active_window()), 200),
            (Method::Post, "/uia/find") => {
                let payload: UiaRequest = read_json(&mut request);
                json_response(find_uia(payload), 501)
            }
            (Method::Post, "/uia/click") => {
                let payload: UiaRequest = read_json(&mut request);
                json_response(click_uia(payload), 501)
            }
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

fn json_response(value: serde_json::Value, status: u16) -> Response<std::io::Cursor<Vec<u8>>> {
    let body = serde_json::to_vec(&value).unwrap_or_else(|_| b"{}".to_vec());
    let header = Header::from_bytes("Content-Type", "application/json").unwrap();
    Response::from_data(body)
        .with_status_code(StatusCode(status))
        .with_header(header)
}

fn find_uia(payload: UiaRequest) -> serde_json::Value {
    json!({
        "ok": false,
        "found": false,
        "name": payload.name,
        "role": payload.role,
        "window_title": payload.window_title,
        "error": "UIA not implemented on this platform"
    })
}

fn click_uia(payload: UiaRequest) -> serde_json::Value {
    json!({
        "ok": false,
        "clicked": false,
        "name": payload.name,
        "role": payload.role,
        "window_title": payload.window_title,
        "error": "UIA not implemented on this platform"
    })
}

fn screenshot(payload: ScreenshotRequest) -> serde_json::Value {
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

fn active_window() -> WindowInfo {
    WindowInfo {
        title: active_window_title(),
        app_name: "unknown".to_string(),
    }
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
