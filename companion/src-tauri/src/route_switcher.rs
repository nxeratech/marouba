#![allow(dead_code)]

use crate::classifier::EventType;
use crate::RecordedEvent;
use serde::Deserialize;
use std::collections::HashMap;
use std::fs;
use std::path::{Path, PathBuf};

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum Route {
    UIA,
    KeyboardShortcut(String),
    Coordinates,
    Api(String),
    NullAdapterGesture(String),
}

#[derive(Clone, Debug, Deserialize)]
pub struct AppProfile {
    pub app_name: String,
    pub title_fragment: String,
    #[serde(default)]
    pub adapter: Option<String>,
    #[serde(default)]
    pub tier: Option<String>,
    #[serde(default)]
    pub mechanism: Option<String>,
    pub supported_routes: HashMap<String, Vec<String>>,
    pub known_shortcuts: HashMap<String, String>,
    pub ui_density: String,
    pub coordinate_tolerance_px: i32,
}

pub fn select_route(event_type: &EventType, app_profile: &AppProfile) -> Route {
    if let Some(adapter) = null_adapter_id(app_profile) {
        return Route::NullAdapterGesture(adapter);
    }
    let key = event_type_key(event_type);
    let routes = app_profile
        .supported_routes
        .get(key)
        .map(Vec::as_slice)
        .unwrap_or(&[]);

    if let Some(endpoint) = first_route(routes, "api") {
        return Route::Api(endpoint);
    }
    if first_route(routes, "uia").is_some() {
        return Route::UIA;
    }
    if let Some(shortcut) = shortcut_for_event_type(event_type, app_profile) {
        return Route::KeyboardShortcut(shortcut);
    }
    Route::Coordinates
}

pub fn select_route_for_event(
    event_type: &EventType,
    event: &RecordedEvent,
    app_profile: Option<&AppProfile>,
) -> Route {
    let Some(app_profile) = app_profile else {
        return Route::Coordinates;
    };
    if let Some(adapter) = null_adapter_id(app_profile) {
        return Route::NullAdapterGesture(adapter);
    }
    let key = event_type_key(event_type);
    let routes = app_profile
        .supported_routes
        .get(key)
        .map(Vec::as_slice)
        .unwrap_or(&[]);

    if let Some(endpoint) = first_route(routes, "api") {
        return Route::Api(endpoint);
    }
    if event_has_element_name(event) && first_route(routes, "uia").is_some() {
        return Route::UIA;
    }
    if let Some(shortcut) = shortcut_for_event(event_type, event, app_profile) {
        return Route::KeyboardShortcut(shortcut);
    }
    Route::Coordinates
}

pub fn load_app_profile(window_title: &str) -> Option<AppProfile> {
    profile_dirs()
        .into_iter()
        .flat_map(|dir| profile_files(&dir))
        .filter_map(|path| load_profile_file(&path).ok())
        .find(|profile| {
            !profile.title_fragment.trim().is_empty()
                && window_title
                    .to_ascii_lowercase()
                    .contains(&profile.title_fragment.to_ascii_lowercase())
        })
}

fn null_adapter_id(app_profile: &AppProfile) -> Option<String> {
    let adapter = app_profile.adapter.as_deref().unwrap_or("");
    let tier = app_profile.tier.as_deref().unwrap_or("");
    let mechanism = app_profile.mechanism.as_deref().unwrap_or("");
    let paint_title = app_profile
        .title_fragment
        .to_ascii_lowercase()
        .contains("paint")
        || app_profile.app_name.to_ascii_lowercase().contains("paint");
    if paint_title
        && adapter.eq_ignore_ascii_case("ms-paint")
        && tier.eq_ignore_ascii_case("T3")
        && mechanism.to_ascii_lowercase().contains("null")
    {
        Some(adapter.to_string())
    } else {
        None
    }
}
fn load_profile_file(path: &Path) -> Result<AppProfile, String> {
    let content = fs::read_to_string(path).map_err(|error| format!("{error}"))?;
    let frontmatter = frontmatter_block(&content)
        .ok_or_else(|| format!("profile has no frontmatter: {}", path.display()))?;
    serde_yaml::from_str(frontmatter).map_err(|error| format!("{error}"))
}

fn frontmatter_block(content: &str) -> Option<&str> {
    let rest = content.strip_prefix("---")?;
    let end = rest.find("---")?;
    Some(&rest[..end])
}

fn profile_dirs() -> Vec<PathBuf> {
    let mut dirs = Vec::new();
    if let Ok(exe) = std::env::current_exe() {
        if let Some(parent) = exe.parent() {
            dirs.push(parent.join("profiles"));
            dirs.push(parent.join("..").join("profiles"));
            dirs.push(parent.join("..").join("..").join("profiles"));
            dirs.push(parent.join("..").join("..").join("..").join("profiles"));
            dirs.push(
                parent
                    .join("..")
                    .join("..")
                    .join("..")
                    .join("..")
                    .join("profiles"),
            );
        }
    }
    dirs.push(PathBuf::from(r"C:\Share\Marouba\profiles"));
    dirs.push(PathBuf::from("profiles"));
    dirs
}

fn profile_files(dir: &Path) -> Vec<PathBuf> {
    let Ok(entries) = fs::read_dir(dir) else {
        return Vec::new();
    };
    entries
        .filter_map(Result::ok)
        .map(|entry| entry.path())
        .filter(|path| path.extension().and_then(|value| value.to_str()) == Some("md"))
        .collect()
}

fn first_route(routes: &[String], wanted: &str) -> Option<String> {
    routes
        .iter()
        .find(|route| route.eq_ignore_ascii_case(wanted))
        .cloned()
}

fn event_has_element_name(event: &RecordedEvent) -> bool {
    event
        .element_name
        .as_deref()
        .map(str::trim)
        .map(|value| !value.is_empty())
        .unwrap_or(false)
}

fn shortcut_for_event(
    event_type: &EventType,
    event: &RecordedEvent,
    app_profile: &AppProfile,
) -> Option<String> {
    shortcut_action_for_event(event)
        .and_then(|action| app_profile.known_shortcuts.get(action).cloned())
        .or_else(|| shortcut_for_event_type(event_type, app_profile))
}

fn shortcut_for_event_type(event_type: &EventType, app_profile: &AppProfile) -> Option<String> {
    match event_type {
        EventType::KeyboardShortcut => app_profile
            .known_shortcuts
            .get("keyboard_shortcut")
            .cloned(),
        EventType::TextInput => app_profile.known_shortcuts.get("text_input").cloned(),
        _ => None,
    }
}

fn shortcut_action_for_event(event: &RecordedEvent) -> Option<&'static str> {
    let name = event.element_name.as_deref()?.to_ascii_lowercase();
    if name.contains("search") {
        return Some("search_browser");
    }
    if name.contains("save") {
        return Some("save_file");
    }
    if name.contains("undo") {
        return Some("undo");
    }
    if name.contains("redo") {
        return Some("redo");
    }
    None
}

pub fn event_type_key(event_type: &EventType) -> &'static str {
    match event_type {
        EventType::ToolbarClick => "toolbar_click",
        EventType::CanvasStroke => "canvas_stroke",
        EventType::ShapeDrag => "shape_drag",
        EventType::FillClick => "fill_click",
        EventType::DoubleClick => "double_click",
        EventType::DragToTarget => "drag_to_target",
        EventType::TextInput => "text_input",
        EventType::KeyboardShortcut => "keyboard_shortcut",
        EventType::ParameterDrag => "parameter_drag",
        EventType::MidiNoteEntry => "midi_note_entry",
        EventType::BrowserScroll => "browser_scroll",
        EventType::FocusChange => "focus_change",
        EventType::MouseMoveIdle => "mouse_move_idle",
        EventType::Unknown => "unknown",
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::WindowRect;

    fn profile() -> AppProfile {
        AppProfile {
            app_name: "Test App".to_string(),
            title_fragment: "Test".to_string(),
            supported_routes: HashMap::from([
                (
                    "toolbar_click".to_string(),
                    vec!["uia".to_string(), "gesture".to_string()],
                ),
                (
                    "keyboard_shortcut".to_string(),
                    vec!["shortcut".to_string(), "gesture".to_string()],
                ),
            ]),
            known_shortcuts: HashMap::from([(
                "keyboard_shortcut".to_string(),
                "Ctrl+S".to_string(),
            )]),
            adapter: None,
            tier: None,
            mechanism: None,
            ui_density: "medium".to_string(),
            coordinate_tolerance_px: 6,
        }
    }

    fn paint_null_profile() -> AppProfile {
        AppProfile {
            app_name: "MS Paint".to_string(),
            title_fragment: "Paint".to_string(),
            adapter: Some("ms-paint".to_string()),
            tier: Some("T3".to_string()),
            mechanism: Some("null-adapter + gesture".to_string()),
            supported_routes: HashMap::from([(
                "toolbar_click".to_string(),
                vec!["gesture".to_string()],
            )]),
            known_shortcuts: HashMap::new(),
            ui_density: "medium".to_string(),
            coordinate_tolerance_px: 6,
        }
    }
    fn event_with_name(name: Option<&str>) -> RecordedEvent {
        RecordedEvent {
            kind: "mousedown".to_string(),
            event_type: None,
            timestamp_ms: 1,
            x: Some(10),
            y: Some(10),
            normalized_x: Some(0.1),
            normalized_y: Some(0.1),
            button: Some("left".to_string()),
            key: None,
            note: None,
            velocity: None,
            midi_pitch: None,
            midi_channel: None,
            midi_start_beats: None,
            midi_duration_beats: None,
            midi_tempo: None,
            midi_source: None,
            midi_note_id: None,
            window_title: Some("Test".to_string()),
            app_name: Some("Test App".to_string()),
            window_rect: Some(WindowRect {
                left: 0,
                top: 0,
                width: 100,
                height: 100,
            }),
            element_name: name.map(str::to_string),
            element_role: None,
            colour_hex: None,
            semantic: None,
            parameter_value_raw: None,
            parameter_value_normalized: None,
            parameter_value_capture_method: None,
            api_target: None,
            api_device: None,
            api_param: None,
        }
    }

    #[test]
    fn paint_t3_null_adapter_routes_named_toolbar_clicks_to_gesture() {
        let event = event_with_name(Some("Tools"));
        let route = select_route_for_event(
            &EventType::ToolbarClick,
            &event,
            Some(&paint_null_profile()),
        );
        assert_eq!(route, Route::NullAdapterGesture("ms-paint".to_string()));
    }
    #[test]
    fn route_switcher_uia_preferred_when_element_named() {
        let event = event_with_name(Some("Save"));
        let route = select_route_for_event(&EventType::ToolbarClick, &event, Some(&profile()));
        assert_eq!(route, Route::UIA);
    }

    #[test]
    fn route_switcher_coordinates_fallback_when_no_profile() {
        let event = event_with_name(Some("Save"));
        let route = select_route_for_event(&EventType::ToolbarClick, &event, None);
        assert_eq!(route, Route::Coordinates);
    }

    #[test]
    fn route_switcher_keyboard_shortcut_used_when_declared() {
        let event = event_with_name(None);
        let route = select_route_for_event(&EventType::KeyboardShortcut, &event, Some(&profile()));
        assert_eq!(route, Route::KeyboardShortcut("Ctrl+S".to_string()));
    }
}
