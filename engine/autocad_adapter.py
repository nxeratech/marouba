from __future__ import annotations

import hashlib
import importlib
import json
from copy import deepcopy
from typing import Any


class AutoCADAdapter:
    id = "autocad"
    mechanism = "com-dotnet-autolisp"

    def execute(
        self,
        route: dict[str, Any],
        params: dict[str, Any],
        workflow: dict[str, Any],
        autocad_runtime: Any | None = None,
    ) -> dict[str, Any]:
        events = replayable_events(route)
        if not events:
            raise RuntimeError("AutoCAD adapter route requires r1 command stream events")

        runtime = autocad_runtime or AutoCADRuntime.from_com()
        rendered_events: list[dict[str, Any]] = []
        for event in events:
            rendered = substitute_slots(event, params)
            rendered_events.append(rendered)
            if rendered.get("action") != "run_command":
                raise RuntimeError(f"Unsupported AutoCAD r1 action: {rendered.get('action')}")
            runtime.run_command(rendered)

        snapshot = runtime.snapshot()
        return {
            "success": True,
            "route_type": "adapter",
            "adapter": self.id,
            "route_used": "r1:autocad-command-stream",
            "events_replayed": len(events),
            "dwg_hash": hash_drawing_snapshot(snapshot),
            "drawing": snapshot,
            "autolisp": build_autolisp(rendered_events),
        }


class AutoCADRuntime:
    def __init__(self, autocad: Any) -> None:
        self.autocad = autocad

    @classmethod
    def from_com(cls) -> "AutoCADRuntime":
        try:
            win32com = importlib.import_module("win32com.client")
            return cls(win32com.Dispatch("AutoCAD.Application"))
        except ImportError as exc:
            raise RuntimeError("AutoCAD COM runtime requires pywin32") from exc

    def run_command(self, event: dict[str, Any]) -> None:
        command_line = command_to_autocad_line(event["command"], event["parameters"])
        self.autocad.ActiveDocument.SendCommand(command_line)

    def snapshot(self) -> dict[str, Any]:
        if hasattr(self.autocad, "marouba_snapshot"):
            return self.autocad.marouba_snapshot()
        return {"runtime": "autocad-com"}


def replayable_events(route: dict[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for raw_event in route.get("events") or []:
        event = normalize_event(raw_event)
        if event.get("route_tier", "r1") == "r1":
            events.append(event)
    return events


def normalize_event(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError(f"Unsupported AutoCAD event: {value!r}")
    event = dict(value)
    require_keys(event, "action", "command", "parameters")
    if event["action"] != "run_command":
        raise RuntimeError(f"Unsupported AutoCAD event action: {event['action']}")
    if event.get("capture_source") in {"uia", "pixels", "approximation"}:
        raise RuntimeError(f"AutoCAD r1 command events must come from command stream/API evidence: {event}")
    if not isinstance(event["parameters"], list) or not event["parameters"]:
        raise RuntimeError(f"AutoCAD command captured without parameters: {event}")
    for param in event["parameters"]:
        validate_parameter(param)
    return event


def validate_parameter(param: Any) -> None:
    if isinstance(param, (int, float, str)) and not isinstance(param, bool):
        return
    if isinstance(param, list) and param and all(isinstance(item, (int, float)) and not isinstance(item, bool) for item in param):
        return
    raise RuntimeError(f"AutoCAD command parameter is not exact/replayable: {param!r}")


def capture_events_from_command_stream(command_stream: list[dict[str, Any]]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for entry in command_stream:
        event = {
            "route_tier": "r1",
            "app": "AutoCAD",
            "kind": "command",
            "action": "run_command",
            "command": entry["command"],
            "parameters": deepcopy(entry.get("parameters", [])),
            "source": entry.get("source", "command-stream"),
            "capture_source": entry.get("capture_source", "command-stream"),
        }
        events.append(normalize_event(event))
    return events


def require_keys(event: dict[str, Any], *keys: str) -> None:
    for key in keys:
        if key not in event:
            raise RuntimeError(f"AutoCAD event missing {key}: {event}")


def substitute_slots(value: Any, params: dict[str, Any]) -> Any:
    if isinstance(value, str):
        return value.format(**params)
    if isinstance(value, list):
        return [substitute_slots(item, params) for item in value]
    if isinstance(value, dict):
        return {key: substitute_slots(item, params) for key, item in value.items()}
    return value


def command_to_autocad_line(command: str, parameters: list[Any]) -> str:
    parts = [f"_.{command}"]
    for param in parameters:
        if isinstance(param, list):
            parts.append(",".join(format_number(value) for value in param))
        else:
            parts.append(str(param))
    return " ".join(parts) + " \n"


def build_autolisp(events: list[dict[str, Any]]) -> str:
    lines = ["(defun c:MAROUBA-REPLAY ( / )"]
    for event in events:
        args = " ".join(to_lisp_atom(param) for param in event["parameters"])
        lines.append(f"  (command \"_.{event['command']}\" {args})")
    lines.extend(["  (princ)", ")", ""])
    return "\n".join(lines)


def to_lisp_atom(value: Any) -> str:
    if isinstance(value, list):
        return f"'({ ' '.join(format_number(item) for item in value) })"
    if isinstance(value, str):
        return json.dumps(value)
    return format_number(value)


def format_number(value: Any) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def hash_drawing_snapshot(snapshot: dict[str, Any]) -> str:
    canonical = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def captured_workflow(name: str, events: list[dict[str, Any]]) -> dict[str, Any]:
    workflow_id = slugify(name)
    return {
        "id": workflow_id,
        "name": name,
        "app": "AutoCAD",
        "description": "AutoCAD drawing workflow captured from exact command stream parameters and replayed through COM/AutoLISP.",
        "params": [],
        "tags": ["autocad", "adapter", "r1", "command-stream", "dwg"],
        "author": "nxeratech",
        "created": "2026-06-14",
        "routes": [{"type": "adapter", "adapter": "autocad", "events": events}],
        "fallback_order": ["adapter", "uia", "ask"],
        "verification": {"type": "dwg_entity_hash"},
        "calls": [],
        "depends_on": [],
        "signals": {"captured_events": events},
        "body": f"# {name}\n\nCaptured from AutoCAD command stream evidence with exact parameters.\n",
    }


def slugify(value: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in value.casefold()).strip("-") or "autocad-workflow"
