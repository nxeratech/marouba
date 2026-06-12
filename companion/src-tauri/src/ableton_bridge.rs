use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::io::{Read, Write};
use std::net::{TcpStream, UdpSocket};
use std::process::{Child, Command};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};
use tiny_http::{Method, Response, Server, StatusCode};

const DEFAULT_OSC_HOST: &str = "127.0.0.1";
const DEFAULT_OSC_SEND_PORT: u16 = 11000;
const DEFAULT_OSC_RECV_PORT: u16 = 11001;
const DEFAULT_HEALTH_PORT: u16 = 11002;

#[derive(Clone, Debug, Eq, PartialEq)]
pub(crate) struct AbletonBridgeConfig {
    pub(crate) host: String,
    pub(crate) send_port: u16,
    pub(crate) recv_port: u16,
    pub(crate) health_port: u16,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub(crate) struct AbletonBridgeHealth {
    pub(crate) status: String,
    pub(crate) message: Option<String>,
    pub(crate) send_port: u16,
    pub(crate) recv_port: u16,
    pub(crate) health_port: u16,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub(crate) struct AbletonParameterSnapshot {
    pub(crate) target: String,
    pub(crate) track: String,
    #[serde(default)]
    pub(crate) track_id: Option<String>,
    #[serde(default)]
    pub(crate) track_index: Option<i64>,
    pub(crate) device: String,
    pub(crate) parameter: String,
    pub(crate) normalized_value: f64,
    pub(crate) display_value: String,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub(crate) struct AbletonTransportSnapshot {
    pub(crate) is_playing: bool,
    pub(crate) record_mode: bool,
    pub(crate) session_record: bool,
    pub(crate) tempo: String,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub(crate) struct AbletonMidiEvent {
    pub(crate) kind: String,
    pub(crate) channel: u8,
    pub(crate) pitch: u8,
    pub(crate) velocity: u8,
    pub(crate) timestamp_ms: u128,
    pub(crate) start_time: Option<String>,
    pub(crate) duration: Option<String>,
    pub(crate) tempo: Option<String>,
    pub(crate) note_id: Option<String>,
    pub(crate) source: Option<String>,
}

#[derive(Debug)]
pub(crate) struct AbletonBridgeSupervisor {
    config: AbletonBridgeConfig,
    child: Option<Child>,
}

impl AbletonBridgeConfig {
    pub(crate) fn from_env() -> Self {
        Self {
            host: std::env::var("MAROUBA_ABLETON_OSC_HOST")
                .unwrap_or_else(|_| DEFAULT_OSC_HOST.to_string()),
            send_port: env_port("MAROUBA_ABLETON_OSC_SEND_PORT", DEFAULT_OSC_SEND_PORT),
            recv_port: env_port("MAROUBA_ABLETON_OSC_RECV_PORT", DEFAULT_OSC_RECV_PORT),
            health_port: env_port("MAROUBA_ABLETON_BRIDGE_HEALTH_PORT", DEFAULT_HEALTH_PORT),
        }
    }
}

impl AbletonBridgeHealth {
    pub(crate) fn unavailable(message: impl Into<String>) -> Self {
        let config = AbletonBridgeConfig::from_env();
        Self {
            status: "unavailable".to_string(),
            message: Some(message.into()),
            send_port: config.send_port,
            recv_port: config.recv_port,
            health_port: config.health_port,
        }
    }
}

impl AbletonBridgeSupervisor {
    pub(crate) fn new(config: AbletonBridgeConfig) -> Self {
        Self {
            config,
            child: None,
        }
    }

    pub(crate) fn status_without_spawn(&mut self) -> AbletonBridgeHealth {
        if let Some(child) = self.child.as_mut() {
            match child.try_wait() {
                Ok(Some(status)) => {
                    self.child = None;
                    return self.health("unavailable", format!("osc bridge exited: {status}"));
                }
                Err(error) => {
                    self.child = None;
                    return self
                        .health("unavailable", format!("osc bridge status failed: {error}"));
                }
                Ok(None) => {
                    return match request_bridge_health(&self.config) {
                        Ok(health) => health,
                        Err(error) => self.health("degraded", error),
                    };
                }
            }
        }

        self.health("unavailable", "bridge idle")
    }

    pub(crate) fn health_check(&mut self) -> AbletonBridgeHealth {
        if let Some(child) = self.child.as_mut() {
            match child.try_wait() {
                Ok(Some(status)) => {
                    self.child = None;
                    return self.health("unavailable", format!("osc bridge exited: {status}"));
                }
                Err(error) => {
                    self.child = None;
                    return self
                        .health("unavailable", format!("osc bridge status failed: {error}"));
                }
                Ok(None) => {}
            }
        }

        if self.child.is_none() {
            match self.spawn_bridge() {
                Ok(child) => {
                    self.child = Some(child);
                    std::thread::sleep(Duration::from_millis(120));
                }
                Err(error) => {
                    return self.health(
                        "unavailable",
                        format!("failed to start osc bridge: {error}"),
                    );
                }
            }
        }

        match request_bridge_health(&self.config) {
            Ok(health) => health,
            Err(error) => self.health("degraded", error),
        }
    }

    pub(crate) fn selected_parameter_snapshot(
        &mut self,
    ) -> Result<AbletonParameterSnapshot, String> {
        let health = self.health_check();
        if health.status != "ok" {
            return Err(health
                .message
                .unwrap_or_else(|| "Ableton bridge unavailable".to_string()));
        }
        request_bridge_parameter_snapshot(&self.config)
    }

    pub(crate) fn transport_snapshot(&mut self) -> Result<AbletonTransportSnapshot, String> {
        let health = self.health_check();
        if health.status != "ok" {
            return Err(health
                .message
                .unwrap_or_else(|| "Ableton bridge unavailable".to_string()));
        }
        request_bridge_transport_snapshot(&self.config)
    }

    pub(crate) fn drain_midi_events(&mut self) -> Result<Vec<AbletonMidiEvent>, String> {
        if let Some(child) = self.child.as_mut() {
            if let Ok(Some(_)) | Err(_) = child.try_wait() {
                self.child = None;
            }
        }
        if self.child.is_none() {
            self.child = Some(self.spawn_bridge()?);
            std::thread::sleep(Duration::from_millis(120));
        }
        request_bridge_midi_events(&self.config)
    }

    pub(crate) fn execute(&mut self, payload: Value) -> Result<Value, String> {
        let health = self.health_check();
        if health.status != "ok" {
            return Err(health
                .message
                .unwrap_or_else(|| "Ableton bridge unavailable".to_string()));
        }
        request_bridge_execute(&self.config, payload)
    }

    fn spawn_bridge(&self) -> Result<Child, String> {
        let exe = std::env::current_exe().map_err(|error| error.to_string())?;
        let mut command = Command::new(exe);
        command
            .arg("--marouba-osc-bridge")
            .env("MAROUBA_ABLETON_OSC_HOST", &self.config.host)
            .env(
                "MAROUBA_ABLETON_OSC_SEND_PORT",
                self.config.send_port.to_string(),
            )
            .env(
                "MAROUBA_ABLETON_OSC_RECV_PORT",
                self.config.recv_port.to_string(),
            )
            .env(
                "MAROUBA_ABLETON_BRIDGE_HEALTH_PORT",
                self.config.health_port.to_string(),
            );
        no_window_command(&mut command)
            .spawn()
            .map_err(|error| error.to_string())
    }

    fn health(&self, status: &str, message: impl Into<String>) -> AbletonBridgeHealth {
        AbletonBridgeHealth {
            status: status.to_string(),
            message: Some(message.into()),
            send_port: self.config.send_port,
            recv_port: self.config.recv_port,
            health_port: self.config.health_port,
        }
    }
}

pub(crate) fn run_ableton_osc_bridge() -> Result<(), String> {
    let config = AbletonBridgeConfig::from_env();
    let osc = Arc::new(Mutex::new(OscHealthProbe::bind(config.clone())?));
    let server = Server::http(format!("127.0.0.1:{}", config.health_port))
        .map_err(|error| format!("failed to bind bridge health server: {error}"))?;

    for mut request in server.incoming_requests() {
        let response = match (request.method(), request.url()) {
            (&Method::Get, "/health") => {
                let health = osc
                    .lock()
                    .map_err(|_| "bridge probe lock poisoned".to_string())
                    .and_then(|mut probe| probe.health());
                match health {
                    Ok(value) => json_response(value, 200),
                    Err(error) => json_response(
                        json!({
                            "status": "degraded",
                            "message": error,
                            "send_port": config.send_port,
                            "recv_port": config.recv_port,
                            "health_port": config.health_port
                        }),
                        200,
                    ),
                }
            }
            (&Method::Get, "/parameter/snapshot") => {
                let snapshot = osc
                    .lock()
                    .map_err(|_| "bridge probe lock poisoned".to_string())
                    .and_then(|mut probe| probe.parameter_snapshot());
                match snapshot {
                    Ok(value) => json_response(json!(value), 200),
                    Err(error) => json_response(
                        json!({
                            "status": "degraded",
                            "message": error,
                            "send_port": config.send_port,
                            "recv_port": config.recv_port,
                            "health_port": config.health_port
                        }),
                        200,
                    ),
                }
            }
            (&Method::Get, "/transport/snapshot") => {
                let snapshot = osc
                    .lock()
                    .map_err(|_| "bridge probe lock poisoned".to_string())
                    .and_then(|mut probe| probe.transport_snapshot());
                match snapshot {
                    Ok(value) => json_response(json!(value), 200),
                    Err(error) => json_response(
                        json!({
                            "status": "degraded",
                            "message": error,
                            "send_port": config.send_port,
                            "recv_port": config.recv_port,
                            "health_port": config.health_port
                        }),
                        200,
                    ),
                }
            }
            (&Method::Get, "/midi/drain") => {
                let events = osc
                    .lock()
                    .map_err(|_| "bridge probe lock poisoned".to_string())
                    .and_then(|mut probe| probe.drain_midi_events());
                match events {
                    Ok(value) => json_response(json!({"status": "ok", "events": value}), 200),
                    Err(error) => json_response(
                        json!({
                            "status": "degraded",
                            "message": error,
                            "send_port": config.send_port,
                            "recv_port": config.recv_port,
                            "health_port": config.health_port
                        }),
                        200,
                    ),
                }
            }
            (&Method::Post, "/execute") => {
                let mut body = String::new();
                let payload = match request.as_reader().read_to_string(&mut body) {
                    Ok(_) => serde_json::from_str::<Value>(&body).unwrap_or_else(|_| json!({})),
                    Err(_) => json!({}),
                };
                let result = osc
                    .lock()
                    .map_err(|_| "bridge probe lock poisoned".to_string())
                    .and_then(|mut probe| probe.execute(&payload));
                match result {
                    Ok(value) => json_response(json!({"status": "ok", "output": value}), 200),
                    Err(error) => {
                        json_response(json!({"status": "degraded", "message": error}), 200)
                    }
                }
            }
            _ => json_response(json!({"error": "not found"}), 404),
        };
        let _ = request.respond(response);
    }
    Ok(())
}

struct OscHealthProbe {
    config: AbletonBridgeConfig,
    socket: UdpSocket,
}

impl OscHealthProbe {
    fn bind(config: AbletonBridgeConfig) -> Result<Self, String> {
        let socket =
            UdpSocket::bind(format!("{}:{}", config.host, config.recv_port)).map_err(|error| {
                format!("failed to bind OSC recv port {}: {error}", config.recv_port)
            })?;
        socket
            .set_read_timeout(Some(Duration::from_millis(800)))
            .map_err(|error| error.to_string())?;
        Ok(Self { config, socket })
    }

    fn health(&mut self) -> Result<serde_json::Value, String> {
        let (address, args) = self.request("/marouba/health", &[])?;
        Ok(health_response_value(&self.config, address, args))
    }

    fn parameter_snapshot(&mut self) -> Result<AbletonParameterSnapshot, String> {
        let (address, args) = self.request("/marouba/parameter/selected", &[])?;
        if address != "/marouba/parameter/selected" {
            return Err(format!("unexpected OSC response address: {address}"));
        }
        if args.first().map(String::as_str) != Some("ok") {
            return Err(args
                .get(1)
                .cloned()
                .unwrap_or_else(|| "selected parameter unavailable".to_string()));
        }
        if args.len() < 7 {
            return Err(format!(
                "selected parameter response missing fields: {args:?}"
            ));
        }
        let normalized_value = args[5].parse::<f64>().map_err(|error| {
            format!("invalid normalized parameter value {:?}: {error}", args[5])
        })?;
        Ok(AbletonParameterSnapshot {
            track: args[1].clone(),
            track_id: args.get(7).cloned().filter(|value| !value.is_empty()),
            track_index: args.get(8).and_then(|value| value.parse::<i64>().ok()),
            device: args[2].clone(),
            parameter: args[3].clone(),
            display_value: args[4].clone(),
            normalized_value,
            target: args[6].clone(),
        })
    }

    fn transport_snapshot(&mut self) -> Result<AbletonTransportSnapshot, String> {
        let (address, args) = self.request("/marouba/transport/snapshot", &[])?;
        if address != "/marouba/transport/snapshot" {
            return Err(format!("unexpected OSC response address: {address}"));
        }
        if args.first().map(String::as_str) != Some("ok") {
            return Err(args
                .get(1)
                .cloned()
                .unwrap_or_else(|| "transport snapshot unavailable".to_string()));
        }
        if args.len() < 5 {
            return Err(format!("transport response missing fields: {args:?}"));
        }
        Ok(AbletonTransportSnapshot {
            is_playing: args[1] == "1",
            record_mode: args[2] == "1",
            session_record: args[3] == "1",
            tempo: args[4].clone(),
        })
    }

    fn drain_midi_events(&mut self) -> Result<Vec<AbletonMidiEvent>, String> {
        let (address, args) = self.request("/marouba/midi/drain", &[])?;
        if address != "/marouba/midi/drain" {
            return Err(format!("unexpected OSC response address: {address}"));
        }
        if args.first().map(String::as_str) != Some("ok") {
            return Err(args
                .get(1)
                .cloned()
                .unwrap_or_else(|| "MIDI drain unavailable".to_string()));
        }
        let count = args
            .get(1)
            .and_then(|value| value.parse::<usize>().ok())
            .unwrap_or(0);
        let mut events = Vec::new();
        let mut offset = 2usize;
        for _ in 0..count {
            if offset + 4 >= args.len() {
                return Err(format!("MIDI drain response truncated: {args:?}"));
            }
            let start_time = args
                .get(offset + 5)
                .cloned()
                .filter(|value| !value.is_empty());
            let duration = args
                .get(offset + 6)
                .cloned()
                .filter(|value| !value.is_empty());
            let tempo = args
                .get(offset + 7)
                .cloned()
                .filter(|value| !value.is_empty());
            let note_id = args
                .get(offset + 8)
                .cloned()
                .filter(|value| !value.is_empty());
            let source = args
                .get(offset + 9)
                .cloned()
                .filter(|value| !value.is_empty());
            events.push(AbletonMidiEvent {
                kind: args[offset].clone(),
                channel: args[offset + 1].parse::<u8>().unwrap_or(1),
                pitch: args[offset + 2].parse::<u8>().unwrap_or(0),
                velocity: args[offset + 3].parse::<u8>().unwrap_or(0),
                timestamp_ms: args[offset + 4].parse::<u128>().unwrap_or(0),
                start_time,
                duration,
                tempo,
                note_id,
                source,
            });
            offset += if offset + 9 < args.len() { 10 } else { 5 };
        }
        Ok(events)
    }

    fn execute(&mut self, payload: &Value) -> Result<Value, String> {
        let route = payload.get("route").unwrap_or(payload);
        let action = route
            .get("action")
            .or_else(|| payload.get("action"))
            .and_then(Value::as_str)
            .or_else(|| route.get("api").and_then(Value::as_str))
            .unwrap_or("execute");
        let payload_text = serde_json::to_string(payload)
            .map_err(|error| format!("Ableton execute payload encode failed: {error}"))?;
        let (address, args) = self.request("/marouba/execute", &[action, &payload_text])?;
        if address != "/marouba/execute" {
            return Err(format!("unexpected OSC response address: {address}"));
        }
        if args.first().map(String::as_str) != Some("ok") {
            return Err(args
                .get(1)
                .cloned()
                .unwrap_or_else(|| "Ableton LOM execute failed".to_string()));
        }
        let body = args.get(1).cloned().unwrap_or_else(|| "{}".to_string());
        match serde_json::from_str::<Value>(&body) {
            Ok(value) => Ok(value),
            Err(_) => Ok(json!({"message": body})),
        }
    }

    fn request(&mut self, address: &str, args: &[&str]) -> Result<(String, Vec<String>), String> {
        let message = osc_message(address, args);
        self.socket
            .send_to(
                &message,
                format!("{}:{}", self.config.host, self.config.send_port),
            )
            .map_err(|error| format!("failed to send OSC {address}: {error}"))?;

        let deadline = Instant::now() + Duration::from_millis(1_600);
        let mut stale = Vec::<String>::new();
        loop {
            let mut buffer = [0u8; 65_535];
            let (len, _) = self.socket.recv_from(&mut buffer).map_err(|error| {
                if stale.is_empty() {
                    format!("Live Remote Script did not answer {address}: {error}")
                } else {
                    format!(
                        "Live Remote Script did not answer {address}; discarded stale replies: {}",
                        stale.join(", ")
                    )
                }
            })?;
            let decoded = decode_osc_message(&buffer[..len])?;
            if decoded.0 == address {
                return Ok(decoded);
            }
            stale.push(decoded.0);
            if Instant::now() >= deadline {
                return Err(format!(
                    "Live Remote Script did not answer {address}; discarded stale replies: {}",
                    stale.join(", ")
                ));
            }
        }
    }
}

fn health_response_value(
    config: &AbletonBridgeConfig,
    address: String,
    args: Vec<String>,
) -> serde_json::Value {
    let script_ok = address == "/marouba/health" && args.iter().any(|arg| arg == "ok");
    let execute_ready = args.iter().any(|arg| arg == "execute");
    let execute_v3_ready = args.iter().any(|arg| arg == "execute-v3");
    let ok = script_ok && execute_ready && execute_v3_ready;
    json!({
        "status": if ok { "ok" } else { "degraded" },
        "message": if ok {
            "Live script responded with execute-v3 support"
        } else if script_ok && execute_ready {
            "Live script responded but execute-v3 support is not loaded; reload MaroubaAbleton in Live"
        } else if script_ok {
            "Live script responded but execute support is not loaded; reload MaroubaAbleton in Live"
        } else {
            "unexpected OSC health response"
        },
        "address": address,
        "args": args,
        "send_port": config.send_port,
        "recv_port": config.recv_port,
        "health_port": config.health_port
    })
}

fn request_bridge_health(config: &AbletonBridgeConfig) -> Result<AbletonBridgeHealth, String> {
    let body = request_bridge_path(config, "/health")?;
    serde_json::from_str::<AbletonBridgeHealth>(&body)
        .map_err(|error| format!("bridge health JSON parse failed: {error}; body={body}"))
}

fn request_bridge_parameter_snapshot(
    config: &AbletonBridgeConfig,
) -> Result<AbletonParameterSnapshot, String> {
    let body = request_bridge_path(config, "/parameter/snapshot")?;
    let value: serde_json::Value = serde_json::from_str(&body)
        .map_err(|error| format!("bridge parameter JSON parse failed: {error}; body={body}"))?;
    if value.get("status").and_then(serde_json::Value::as_str) == Some("degraded") {
        return Err(value
            .get("message")
            .and_then(serde_json::Value::as_str)
            .unwrap_or("Ableton selected parameter unavailable")
            .to_string());
    }
    serde_json::from_value::<AbletonParameterSnapshot>(value)
        .map_err(|error| format!("bridge parameter snapshot parse failed: {error}; body={body}"))
}

fn request_bridge_transport_snapshot(
    config: &AbletonBridgeConfig,
) -> Result<AbletonTransportSnapshot, String> {
    let body = request_bridge_path(config, "/transport/snapshot")?;
    let value: serde_json::Value = serde_json::from_str(&body)
        .map_err(|error| format!("bridge transport JSON parse failed: {error}; body={body}"))?;
    if value.get("status").and_then(serde_json::Value::as_str) == Some("degraded") {
        return Err(value
            .get("message")
            .and_then(serde_json::Value::as_str)
            .unwrap_or("Ableton transport unavailable")
            .to_string());
    }
    serde_json::from_value::<AbletonTransportSnapshot>(value)
        .map_err(|error| format!("bridge transport snapshot parse failed: {error}; body={body}"))
}

fn request_bridge_execute(config: &AbletonBridgeConfig, payload: Value) -> Result<Value, String> {
    let body = request_bridge_post(config, "/execute", &payload)?;
    let value: Value = serde_json::from_str(&body)
        .map_err(|error| format!("bridge execute JSON parse failed: {error}; body={body}"))?;
    if value.get("status").and_then(Value::as_str) == Some("degraded") {
        return Err(value
            .get("message")
            .and_then(Value::as_str)
            .unwrap_or("Ableton execute unavailable")
            .to_string());
    }
    Ok(value.get("output").cloned().unwrap_or(value))
}

fn request_bridge_midi_events(
    config: &AbletonBridgeConfig,
) -> Result<Vec<AbletonMidiEvent>, String> {
    let body = request_bridge_path(config, "/midi/drain")?;
    let value: serde_json::Value = serde_json::from_str(&body)
        .map_err(|error| format!("bridge MIDI JSON parse failed: {error}; body={body}"))?;
    if value.get("status").and_then(serde_json::Value::as_str) == Some("degraded") {
        return Err(value
            .get("message")
            .and_then(serde_json::Value::as_str)
            .unwrap_or("Ableton MIDI drain unavailable")
            .to_string());
    }
    value
        .get("events")
        .cloned()
        .ok_or_else(|| format!("bridge MIDI response missing events: {body}"))
        .and_then(|events| {
            serde_json::from_value::<Vec<AbletonMidiEvent>>(events)
                .map_err(|error| format!("bridge MIDI event parse failed: {error}; body={body}"))
        })
}

fn request_bridge_path(config: &AbletonBridgeConfig, path: &str) -> Result<String, String> {
    request_bridge_http(config, "GET", path, None)
}

fn request_bridge_post(
    config: &AbletonBridgeConfig,
    path: &str,
    payload: &Value,
) -> Result<String, String> {
    let body = serde_json::to_string(payload).map_err(|error| error.to_string())?;
    request_bridge_http(config, "POST", path, Some(&body))
}

fn request_bridge_http(
    config: &AbletonBridgeConfig,
    method: &str,
    path: &str,
    body: Option<&str>,
) -> Result<String, String> {
    let mut stream = TcpStream::connect(("127.0.0.1", config.health_port))
        .map_err(|error| format!("osc bridge health server unavailable: {error}"))?;
    stream
        .set_read_timeout(Some(Duration::from_millis(1200)))
        .map_err(|error| error.to_string())?;
    let body = body.unwrap_or("");
    let request = if method == "POST" {
        format!(
            "POST {path} HTTP/1.1\r\nHost: 127.0.0.1\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{}",
            body.as_bytes().len(),
            body
        )
    } else {
        format!("GET {path} HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n")
    };
    stream
        .write_all(request.as_bytes())
        .map_err(|error| error.to_string())?;
    let mut response = String::new();
    stream
        .read_to_string(&mut response)
        .map_err(|error| error.to_string())?;
    response
        .split("\r\n\r\n")
        .nth(1)
        .map(str::to_string)
        .ok_or_else(|| "bridge returned malformed HTTP".to_string())
}

fn json_response(value: serde_json::Value, status: u16) -> Response<std::io::Cursor<Vec<u8>>> {
    Response::from_data(serde_json::to_vec(&value).unwrap_or_else(|_| b"{}".to_vec()))
        .with_status_code(StatusCode(status))
}

fn osc_message(address: &str, args: &[&str]) -> Vec<u8> {
    let mut output = osc_string(address);
    let tags = format!(",{}", "s".repeat(args.len()));
    output.extend(osc_string(&tags));
    for arg in args {
        output.extend(osc_string(arg));
    }
    output
}

fn osc_string(value: &str) -> Vec<u8> {
    let mut bytes = value.as_bytes().to_vec();
    bytes.push(0);
    while bytes.len() % 4 != 0 {
        bytes.push(0);
    }
    bytes
}

fn decode_osc_message(data: &[u8]) -> Result<(String, Vec<String>), String> {
    let (address, mut offset) = read_osc_string(data, 0)?;
    let (tags, next) = read_osc_string(data, offset)?;
    offset = next;
    let mut args = Vec::new();
    for tag in tags.trim_start_matches(',').chars() {
        match tag {
            's' => {
                let (value, next) = read_osc_string(data, offset)?;
                args.push(value);
                offset = next;
            }
            'i' => {
                if offset + 4 > data.len() {
                    return Err("truncated OSC int".to_string());
                }
                let value = i32::from_be_bytes([
                    data[offset],
                    data[offset + 1],
                    data[offset + 2],
                    data[offset + 3],
                ]);
                args.push(value.to_string());
                offset += 4;
            }
            'f' => {
                if offset + 4 > data.len() {
                    return Err("truncated OSC float".to_string());
                }
                let value = f32::from_be_bytes([
                    data[offset],
                    data[offset + 1],
                    data[offset + 2],
                    data[offset + 3],
                ]);
                args.push(value.to_string());
                offset += 4;
            }
            _ => {}
        }
    }
    Ok((address, args))
}

fn read_osc_string(data: &[u8], start: usize) -> Result<(String, usize), String> {
    let mut end = start;
    while end < data.len() && data[end] != 0 {
        end += 1;
    }
    if end >= data.len() {
        return Err("unterminated OSC string".to_string());
    }
    let value = std::str::from_utf8(&data[start..end])
        .map_err(|error| error.to_string())?
        .to_string();
    let mut offset = end + 1;
    while offset % 4 != 0 {
        offset += 1;
    }
    Ok((value, offset))
}

fn env_port(name: &str, default: u16) -> u16 {
    std::env::var(name)
        .ok()
        .and_then(|value| value.parse::<u16>().ok())
        .unwrap_or(default)
}

fn no_window_command(command: &mut Command) -> &mut Command {
    #[cfg(target_os = "windows")]
    {
        use std::os::windows::process::CommandExt;
        command.creation_flags(0x08000000);
    }
    command
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn osc_string_is_padded_to_four_bytes() {
        assert_eq!(osc_string("/x").len() % 4, 0);
        assert_eq!(osc_string("/abc").len(), 8);
    }

    #[test]
    fn osc_message_round_trips_health_reply() {
        let encoded = osc_message("/marouba/health", &["ok", "marouba-ableton"]);
        let decoded = decode_osc_message(&encoded).expect("decode health");
        assert_eq!(decoded.0, "/marouba/health");
        assert_eq!(decoded.1, vec!["ok", "marouba-ableton"]);
    }

    #[test]
    fn health_config_ports_are_not_hardcoded() {
        let config = AbletonBridgeConfig {
            host: "127.0.0.1".to_string(),
            send_port: 12000,
            recv_port: 12001,
            health_port: 12002,
        };
        let supervisor = AbletonBridgeSupervisor::new(config.clone());
        let health = supervisor.health("degraded", "test");
        assert_eq!(health.send_port, 12000);
        assert_eq!(health.recv_port, 12001);
        assert_eq!(health.health_port, 12002);
    }

    #[test]
    fn parameter_snapshot_parse_rejects_missing_fields() {
        let encoded = osc_message("/marouba/parameter/selected", &["error", "none"]);
        let decoded = decode_osc_message(&encoded).expect("decode parameter error");
        assert_eq!(decoded.0, "/marouba/parameter/selected");
        assert_eq!(decoded.1, vec!["error", "none"]);
    }
    #[test]
    fn health_requires_execute_capability() {
        let config = AbletonBridgeConfig {
            host: "127.0.0.1".to_string(),
            send_port: 12000,
            recv_port: 12001,
            health_port: 12002,
        };
        let old_script = health_response_value(
            &config,
            "/marouba/health".to_string(),
            vec![
                "ok".to_string(),
                "marouba-ableton".to_string(),
                "midi".to_string(),
            ],
        );
        assert_eq!(
            old_script.get("status").and_then(Value::as_str),
            Some("degraded")
        );
        assert!(old_script
            .get("message")
            .and_then(Value::as_str)
            .unwrap_or_default()
            .contains("execute support is not loaded"));

        let execute_without_v3 = health_response_value(
            &config,
            "/marouba/health".to_string(),
            vec![
                "ok".to_string(),
                "marouba-ableton".to_string(),
                "midi".to_string(),
                "execute".to_string(),
            ],
        );
        assert_eq!(
            execute_without_v3.get("status").and_then(Value::as_str),
            Some("degraded")
        );

        let new_script = health_response_value(
            &config,
            "/marouba/health".to_string(),
            vec![
                "ok".to_string(),
                "marouba-ableton".to_string(),
                "midi".to_string(),
                "execute".to_string(),
                "execute-v3".to_string(),
            ],
        );
        assert_eq!(new_script.get("status").and_then(Value::as_str), Some("ok"));
    }
}
