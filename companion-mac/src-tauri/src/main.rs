use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::io::Read;
use std::path::PathBuf;
use std::process::Command;
use std::thread;
use tiny_http::{Header, Method, Response, Server, StatusCode};
use rand::{distributions::Alphanumeric, Rng};

#[derive(Debug, Deserialize, Serialize)]
struct BridgeRequest {
    name: Option<String>,
    role: Option<String>,
    window_title: Option<String>,
    x: Option<i32>,
    y: Option<i32>,
}

#[derive(Debug, Deserialize, Serialize)]
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
                .tooltip("Marouba Companion Mac")
                .build(app)?;
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running Marouba Companion Mac");
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
            (Method::Get, "/window") => json_response(bridge("window", json!({})), 200),
            (Method::Post, "/uia/find") => {
                let payload: BridgeRequest = read_json(&mut request);
                json_response(bridge("find", json!(payload)), 200)
            }
            (Method::Post, "/uia/click") => {
                let payload: BridgeRequest = read_json(&mut request);
                json_response(bridge("click", json!(payload)), 200)
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
    let home = std::env::var("HOME")
        .or_else(|_| std::env::var("USERPROFILE"))
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

fn bridge(command: &str, payload: Value) -> Value {
    let script = std::env::current_exe()
        .ok()
        .and_then(|path| path.parent().map(|parent| parent.join("uia_bridge.py")))
        .unwrap_or_else(|| std::path::PathBuf::from("uia_bridge.py"));

    let output = Command::new("python3")
        .arg(script)
        .arg(command)
        .arg(payload.to_string())
        .output();

    match output {
        Ok(result) if result.status.success() => {
            serde_json::from_slice(&result.stdout).unwrap_or_else(|_| json!({"ok": false, "error": "invalid bridge json"}))
        }
        Ok(result) => json!({
            "ok": false,
            "error": String::from_utf8_lossy(&result.stderr).to_string()
        }),
        Err(error) => json!({"ok": false, "error": error.to_string()}),
    }
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

fn json_response(value: Value, status: u16) -> Response<std::io::Cursor<Vec<u8>>> {
    let body = serde_json::to_vec(&value).unwrap_or_else(|_| b"{}".to_vec());
    let header = Header::from_bytes("Content-Type", "application/json").unwrap();
    Response::from_data(body)
        .with_status_code(StatusCode(status))
        .with_header(header)
}
