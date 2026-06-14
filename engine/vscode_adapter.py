from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any


class VSCodeAdapter:
    id = "vscode"
    mechanism = "local-extension-log"

    def execute(
        self,
        route: dict[str, Any],
        params: dict[str, Any],
        workflow: dict[str, Any],
        workspace_root: str | Path | None = None,
    ) -> dict[str, Any]:
        events = replayable_events(route)
        if not events:
            raise RuntimeError("VS Code adapter route requires r1 extension events")
        root = Path(workspace_root or params.get("workspace_root") or route.get("workspace_root") or ".")

        replayed: list[dict[str, Any]] = []
        for event in events:
            rendered = substitute_slots(event, params)
            action = rendered.get("action")
            if action == "apply_edit":
                apply_edit(root, rendered)
            elif action == "run_command":
                replayed.append({"action": action, "command": rendered["command"], "args": rendered.get("args", [])})
                continue
            elif action == "terminal":
                replayed.append({"action": action, "command_line": rendered["command_line"], "cwd": rendered.get("cwd")})
                continue
            else:
                raise RuntimeError(f"Unsupported VS Code r1 action: {action}")
            replayed.append(rendered)

        snapshot = snapshot_files(root, route.get("verify_files") or changed_files(events))
        return {
            "success": True,
            "route_type": "adapter",
            "adapter": self.id,
            "route_used": "r1:vscode-local-extension",
            "events_replayed": len(events),
            "workspace_hash": hash_workspace_snapshot(snapshot),
            "workspace": snapshot,
            "replayed": replayed,
            "extension_stub": build_extension_stub(),
        }


def replayable_events(route: dict[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for raw_event in route.get("events") or []:
        event = normalize_event(raw_event)
        if event.get("route_tier", "r1") == "r1":
            events.append(event)
    return events


def normalize_event(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError(f"Unsupported VS Code event: {value!r}")
    event = dict(value)
    if event.get("source") in {"telemetry", "network"} or event.get("requires_network") is True:
        raise RuntimeError(f"VS Code adapter refuses telemetry/network-backed event: {event}")
    action = event.get("action")
    if action == "apply_edit":
        require_keys(event, "path", "edits")
        if not isinstance(event["edits"], list) or not event["edits"]:
            raise RuntimeError(f"VS Code apply_edit requires non-empty edits: {event}")
    elif action == "run_command":
        require_keys(event, "command")
    elif action == "terminal":
        require_keys(event, "command_line")
    else:
        raise RuntimeError(f"Unsupported VS Code r1 action: {action}")
    return event


def require_keys(event: dict[str, Any], *keys: str) -> None:
    for key in keys:
        if key not in event:
            raise RuntimeError(f"VS Code event missing {key}: {event}")


def apply_edit(root: Path, event: dict[str, Any]) -> None:
    path = safe_workspace_path(root, str(event["path"]))
    text = path.read_text(encoding=event.get("encoding", "utf-8")) if path.exists() else ""
    for edit in sorted(event["edits"], key=lambda item: int(item.get("start", 0)), reverse=True):
        start = int(edit.get("start", 0))
        end = int(edit.get("end", start))
        replacement = str(edit.get("text", ""))
        if start < 0 or end < start or end > len(text):
            raise RuntimeError(f"VS Code edit range out of bounds for {event['path']}: {edit}")
        text = text[:start] + replacement + text[end:]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding=event.get("encoding", "utf-8"))


def safe_workspace_path(root: Path, relative_path: str) -> Path:
    path = (root / relative_path).resolve()
    root_resolved = root.resolve()
    if root_resolved != path and root_resolved not in path.parents:
        raise RuntimeError(f"VS Code edit path escapes workspace: {relative_path}")
    return path


def changed_files(events: list[dict[str, Any]]) -> list[str]:
    return sorted({str(event["path"]) for event in events if event.get("action") == "apply_edit"})


def snapshot_files(root: Path, paths: list[str]) -> dict[str, Any]:
    files = {}
    for relative in sorted(paths):
        path = safe_workspace_path(root, relative)
        files[relative] = path.read_text(encoding="utf-8") if path.exists() else None
    return {"files": files}


def capture_events_from_vscode_log(log: list[dict[str, Any]]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for entry in log:
        if entry.get("source") in {"telemetry", "network"} or entry.get("requires_network") is True:
            raise RuntimeError(f"VS Code extension log must be local-only, got: {entry}")
        kind = entry.get("kind")
        if kind == "text_edit":
            event = {
                "route_tier": "r1",
                "app": "VS Code",
                "kind": "edit",
                "action": "apply_edit",
                "path": entry["path"],
                "edits": deepcopy(entry["edits"]),
                "source": "extension",
            }
        elif kind == "command":
            event = {
                "route_tier": "r1",
                "app": "VS Code",
                "kind": "command",
                "action": "run_command",
                "command": entry["command"],
                "args": deepcopy(entry.get("args", [])),
                "source": "extension",
            }
        elif kind == "terminal":
            event = {
                "route_tier": "r1",
                "app": "VS Code",
                "kind": "terminal",
                "action": "terminal",
                "command_line": entry["command_line"],
                "cwd": entry.get("cwd"),
                "source": "extension",
            }
        else:
            raise RuntimeError(f"Unsupported VS Code extension log kind: {entry}")
        events.append(normalize_event(event))
    return events


def substitute_slots(value: Any, params: dict[str, Any]) -> Any:
    if isinstance(value, str):
        return value.format(**params)
    if isinstance(value, list):
        return [substitute_slots(item, params) for item in value]
    if isinstance(value, dict):
        return {key: substitute_slots(item, params) for key, item in value.items()}
    return value


def hash_workspace_snapshot(snapshot: dict[str, Any]) -> str:
    canonical = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_extension_stub() -> str:
    return """// Marouba VS Code extension capture hooks, local-only.
vscode.workspace.onDidChangeTextDocument(event => logTextEdits(event));
vscode.commands.registerCommand('marouba.captureCommand', (...args) => logCommand(args));
// Local file logging only. No outbound reporting or remote calls.
"""


def captured_workflow(name: str, events: list[dict[str, Any]]) -> dict[str, Any]:
    workflow_id = slugify(name)
    return {
        "id": workflow_id,
        "name": name,
        "app": "VS Code",
        "description": "VS Code refactor workflow captured from local extension edit, command, and terminal events.",
        "params": [],
        "tags": ["vscode", "adapter", "r1", "extension", "refactor"],
        "author": "nxeratech",
        "created": "2026-06-14",
        "routes": [{"type": "adapter", "adapter": "vscode", "events": events}],
        "fallback_order": ["adapter", "uia", "ask"],
        "verification": {"type": "workspace_hash"},
        "calls": [],
        "depends_on": [],
        "signals": {"captured_events": events},
        "body": f"# {name}\n\nCaptured from VS Code local extension events.\n",
    }


def slugify(value: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in value.casefold()).strip("-") or "vscode-workflow"
