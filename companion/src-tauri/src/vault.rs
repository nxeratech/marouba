use super::*;

pub(crate) fn vault_workflows_dir() -> PathBuf {
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

pub(crate) fn list_saved_workflows() -> (Value, u16) {
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
        if is_steps_sidecar(&path) {
            continue;
        }
        if let Some(workflow) = workflow_summary_from_path(path) {
            workflows.push(workflow);
        }
    }

    workflows.sort_by(|left, right| left.name.cmp(&right.name));
    (json!(workflows), 200)
}

pub(crate) fn workflow_summary_from_path(path: PathBuf) -> Option<VaultWorkflowSummary> {
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

pub(crate) fn parse_gesture_workflow(name: &str) -> Option<Vec<RecordedEvent>> {
    let content = workflow_content(name)?;
    let frontmatter = frontmatter_block(&content)?;
    if workflow_version(frontmatter)
        .ok()
        .is_some_and(|version| version == 2 || version == 3)
    {
        let mut events = Vec::new();
        for step in parse_v2_workflow_steps(name).unwrap_or_default() {
            if let Some(route_events) = step.gesture_events() {
                events.extend(route_events);
            }
        }
        if !events.is_empty() {
            return Some(events);
        }
    }
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

#[derive(Clone, Debug)]
pub(crate) struct VaultReplayStep {
    pub id: String,
    pub step_type: String,
    pub intent: String,
    pub value: Value,
}

impl VaultReplayStep {
    pub(crate) fn gesture_events(&self) -> Option<Vec<RecordedEvent>> {
        let routes = self.value.get("routes")?.as_array()?;
        for route in routes {
            if route.get("type").and_then(Value::as_str) == Some("gesture") {
                return serde_json::from_value(route.get("events")?.clone()).ok();
            }
        }
        None
    }
}

pub(crate) fn parse_v2_workflow_steps(name: &str) -> Option<Vec<VaultReplayStep>> {
    let content = workflow_content(name)?;
    parse_workflow_steps_from_content(&content).ok()
}

pub(crate) fn workflow_version_error(name: &str) -> Option<String> {
    let content = workflow_content(name)?;
    let frontmatter = frontmatter_block(&content)?;
    workflow_version(frontmatter).err()
}

pub(crate) fn parse_workflow_steps_from_content(
    content: &str,
) -> Result<Vec<VaultReplayStep>, String> {
    let frontmatter =
        frontmatter_block(content).ok_or_else(|| "workflow frontmatter is missing".to_string())?;
    let version = workflow_version(frontmatter)?;
    if version != 2 && version != 3 {
        return Ok(Vec::new());
    }

    let mut steps = Vec::new();
    let mut in_block = false;
    let mut block = Vec::new();

    for line in content.lines() {
        let trimmed = line.trim();
        if trimmed.starts_with("```") {
            if in_block {
                if let Ok(value) = parse_step_value(&block.join("\n")) {
                    let id = value
                        .get("id")
                        .and_then(Value::as_str)
                        .unwrap_or("step")
                        .to_string();
                    let step_type = value
                        .get("type")
                        .and_then(Value::as_str)
                        .unwrap_or("legacy_gesture_sequence")
                        .to_string();
                    let intent = value
                        .get("intent")
                        .and_then(Value::as_str)
                        .unwrap_or("")
                        .to_string();
                    steps.push(VaultReplayStep {
                        id,
                        step_type,
                        intent,
                        value,
                    });
                }
                block.clear();
                in_block = false;
            } else if trimmed == "```yaml" || trimmed == "```json" {
                in_block = true;
            }
            continue;
        }
        if in_block {
            block.push(line.to_string());
        }
    }

    Ok(steps)
}

pub(crate) fn parse_workflow_app_name(name: &str) -> Option<String> {
    let content = workflow_content(name)?;
    let frontmatter = frontmatter_block(&content)?;
    yaml_scalar_field(frontmatter, "app")
}

fn workflow_version(frontmatter: &str) -> Result<u16, String> {
    let Some(raw) = yaml_scalar_field(frontmatter, "vault_spec_version") else {
        return Ok(1);
    };
    let version = raw.parse::<u16>().map_err(|_| {
        format!("Unsupported vault_spec_version {raw}; supported versions are 1, 2, 3")
    })?;
    match version {
        1 | 2 | 3 => Ok(version),
        _ => Err(format!(
            "Unsupported vault_spec_version {version}; supported versions are 1, 2, 3"
        )),
    }
}

fn parse_step_value(block: &str) -> Result<Value, String> {
    serde_json::from_str::<Value>(block)
        .or_else(|_| serde_yaml::from_str::<Value>(block))
        .map_err(|error| error.to_string())
}
fn workflow_content(name: &str) -> Option<String> {
    let path = vault_workflows_dir().join(format!("{name}.md"));
    let mut content = std::fs::read_to_string(&path).ok()?;
    let sidecar = steps_sidecar_path(&path);
    if let Ok(steps) = std::fs::read_to_string(sidecar) {
        content.push_str("\n\n");
        content.push_str(&steps);
    }
    Some(content)
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

pub(crate) fn delete_saved_workflow(payload: ReplayWorkflowRequest) -> (Value, u16) {
    let name = match safe_workflow_name(&payload.name) {
        Ok(name) => name,
        Err(error) => return (json!({"status": "failed", "error": error}), 400),
    };
    let path = vault_workflows_dir().join(format!("{name}.md"));
    match std::fs::remove_file(&path) {
        Ok(_) => {
            let sidecar = steps_sidecar_path(&path);
            let _ = std::fs::remove_file(sidecar);
            let _ = regenerate_vault_index_and_graph();
            (json!({"status": "deleted", "name": name}), 200)
        }
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

pub(crate) fn safe_workflow_name(value: &str) -> Result<String, String> {
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

pub(crate) fn regenerate_vault_index_and_graph() -> Result<(), String> {
    let vault = vault_dir();
    let workflows_dir = vault.join("workflows");
    let elements_dir = vault.join("elements");
    let runs_dir = vault.join("runs");
    std::fs::create_dir_all(&workflows_dir).map_err(|error| error.to_string())?;
    std::fs::create_dir_all(&elements_dir).map_err(|error| error.to_string())?;
    std::fs::create_dir_all(&runs_dir).map_err(|error| error.to_string())?;
    std::fs::create_dir_all(vault.join("signals")).map_err(|error| error.to_string())?;

    let mut index_lines = Vec::new();
    let mut nodes = Vec::new();
    let mut links = Vec::new();
    let mut element_ids = std::collections::BTreeSet::new();
    let entries = std::fs::read_dir(&workflows_dir).map_err(|error| error.to_string())?;
    for entry in entries.flatten() {
        let path = entry.path();
        if !path.is_file()
            || path.extension().and_then(|value| value.to_str()) != Some("md")
            || is_steps_sidecar(&path)
        {
            continue;
        }
        let Some(content) = std::fs::read_to_string(&path).ok() else {
            continue;
        };
        let Some(frontmatter) = frontmatter_block(&content) else {
            continue;
        };
        let workflow_id = yaml_scalar_field(frontmatter, "id").unwrap_or_else(|| {
            path.file_stem()
                .and_then(|v| v.to_str())
                .unwrap_or("workflow")
                .to_string()
        });
        let app = yaml_scalar_field(frontmatter, "app").unwrap_or_else(|| "Unknown".to_string());
        let description = yaml_scalar_field(frontmatter, "description").unwrap_or_else(|| {
            content
                .lines()
                .find(|line| {
                    !line.trim().is_empty() && !line.starts_with("---") && !line.starts_with('#')
                })
                .unwrap_or("Replay recorded workflow.")
                .trim()
                .to_string()
        });
        let tags = yaml_inline_list_field(frontmatter, "tags");
        index_lines.push(bounded_index_line(&workflow_id, &app, &tags, &description));
        nodes.push(json!({
            "id": format!("workflow:{workflow_id}"),
            "type": "workflow",
            "path": relative_slash_path(&vault, &path),
            "steps_path": relative_slash_path(&vault, &steps_sidecar_path(&path)),
            "app": app,
            "tags": tags,
            "intent": description
        }));
        for element in std::iter::once(app).chain(tags.into_iter()) {
            if element.trim().is_empty() {
                continue;
            }
            let slug = slugify_element(&element);
            let element_id = format!("element:{slug}");
            element_ids.insert(slug);
            links.push(json!({"from": format!("workflow:{workflow_id}"), "to": element_id, "type": "uses"}));
        }
        if let Ok(run_entries) = std::fs::read_dir(&runs_dir) {
            for run_entry in run_entries.flatten() {
                let run_path = run_entry.path();
                let Some(file_name) = run_path.file_name().and_then(|value| value.to_str()) else {
                    continue;
                };
                if file_name.ends_with(&format!("-{workflow_id}.json")) {
                    let run_id = format!(
                        "run:{}",
                        run_path
                            .file_stem()
                            .and_then(|v| v.to_str())
                            .unwrap_or(file_name)
                    );
                    nodes.push(json!({"id": run_id, "type": "run", "path": relative_slash_path(&vault, &run_path)}));
                    links.push(json!({"from": format!("workflow:{workflow_id}"), "to": run_id, "type": "ran"}));
                }
            }
        }
    }
    for slug in element_ids {
        let path = elements_dir.join(format!("{slug}.md"));
        let _ = std::fs::write(&path, format!("# {slug}\n"));
        nodes.push(json!({"id": format!("element:{slug}"), "type": "element", "path": relative_slash_path(&vault, &path)}));
    }
    std::fs::write(
        vault.join("index.md"),
        index_lines.join("\n") + if index_lines.is_empty() { "" } else { "\n" },
    )
    .map_err(|error| error.to_string())?;
    std::fs::write(
        vault.join("graph.json"),
        serde_json::to_string_pretty(&json!({"nodes": nodes, "links": links}))
            .map_err(|error| error.to_string())?,
    )
    .map_err(|error| error.to_string())?;
    Ok(())
}

pub(crate) fn steps_sidecar_path(path: &PathBuf) -> PathBuf {
    if is_steps_sidecar(path) {
        return path.clone();
    }
    path.with_file_name(format!(
        "{}.steps.md",
        path.file_stem()
            .and_then(|value| value.to_str())
            .unwrap_or("workflow")
    ))
}

pub(crate) fn hide_steps_sidecar(path: &PathBuf) {
    #[cfg(target_os = "windows")]
    {
        let mut command = Command::new("attrib.exe");
        command.arg("+h").arg(path);
        let _ = no_window_command(&mut command).status();
    }
    #[cfg(not(target_os = "windows"))]
    {
        let _ = path;
    }
}

fn is_steps_sidecar(path: &PathBuf) -> bool {
    path.file_name()
        .and_then(|value| value.to_str())
        .is_some_and(|name| name.ends_with(".steps.md"))
}

fn yaml_inline_list_field(frontmatter: &str, field: &str) -> Vec<String> {
    let Some(raw) = yaml_scalar_field(frontmatter, field) else {
        return Vec::new();
    };
    if let Ok(values) = serde_json::from_str::<Vec<String>>(&raw) {
        return values;
    }
    raw.trim_matches(['[', ']'])
        .split(',')
        .map(|value| {
            value
                .trim()
                .trim_matches('"')
                .trim_matches('\'')
                .to_string()
        })
        .filter(|value| !value.is_empty())
        .collect()
}

fn bounded_index_line(workflow_id: &str, app: &str, tags: &[String], intent: &str) -> String {
    let tags_text = if tags.is_empty() {
        "-".to_string()
    } else {
        tags.iter().take(4).cloned().collect::<Vec<_>>().join(",")
    };
    let prefix = format!("[[workflows/{workflow_id}|{workflow_id}]] · {app} · {tags_text} ·");
    let mut words: Vec<&str> = intent.split_whitespace().collect();
    while !words.is_empty()
        && format!("{} {}", prefix, words.join(" "))
            .split_whitespace()
            .count()
            > 40
    {
        words.pop();
    }
    format!("{} {}", prefix, words.join(" "))
}

fn slugify_element(value: &str) -> String {
    let slug = value
        .to_ascii_lowercase()
        .chars()
        .map(|ch| {
            if ch.is_ascii_alphanumeric() || ch == '-' || ch == '_' {
                ch
            } else {
                '-'
            }
        })
        .collect::<String>()
        .trim_matches('-')
        .to_string();
    if slug.is_empty() {
        "element".to_string()
    } else {
        slug
    }
}

fn relative_slash_path(root: &PathBuf, path: &PathBuf) -> String {
    path.strip_prefix(root)
        .unwrap_or(path)
        .to_string_lossy()
        .replace('\\', "/")
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
    match output {
        Ok(output) if output.status.success() => {
            let value = String::from_utf8_lossy(&output.stdout).trim().to_string();
            if value.is_empty() {
                format!("{modified:?}")
            } else {
                value
            }
        }
        _ => format!("{modified:?}"),
    }
}
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_v3_api_uia_gesture_routes_and_signals() {
        let content = include_str!("../../../tests/fixtures/vault_v3_api_uia_gesture.md");
        let steps = parse_workflow_steps_from_content(content).expect("v3 workflow parses");
        assert_eq!(steps.len(), 1);
        let routes = steps[0]
            .value
            .get("routes")
            .and_then(Value::as_array)
            .unwrap();
        assert_eq!(routes[0].get("type").and_then(Value::as_str), Some("api"));
        assert_eq!(routes[1].get("type").and_then(Value::as_str), Some("uia"));
        assert_eq!(
            routes[2].get("type").and_then(Value::as_str),
            Some("gesture")
        );
        assert_eq!(
            steps[0]
                .value
                .get("signals")
                .and_then(|signals| signals.get("dwell_before_ms"))
                .and_then(Value::as_i64),
            Some(1200)
        );
    }

    #[test]
    fn unknown_vault_version_errors_cleanly() {
        let content = "---\nvault_spec_version: 99\nid: future\n---\n";
        let error = parse_workflow_steps_from_content(content).unwrap_err();
        assert!(error.contains("Unsupported vault_spec_version 99"));
    }

    #[test]
    fn missing_vault_version_is_legacy_v1() {
        let content = "---\nid: legacy\n---\n";
        let steps = parse_workflow_steps_from_content(content).expect("legacy version accepted");
        assert!(steps.is_empty());
    }
}
