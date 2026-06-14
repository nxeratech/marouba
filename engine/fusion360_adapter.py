from __future__ import annotations

import hashlib
import importlib
import json
from copy import deepcopy
from typing import Any


class Fusion360Adapter:
    id = "fusion360"
    mechanism = "python-api-design-timeline"

    def execute(
        self,
        route: dict[str, Any],
        params: dict[str, Any],
        workflow: dict[str, Any],
        fusion_runtime: Any | None = None,
    ) -> dict[str, Any]:
        events = replayable_events(route)
        if not events:
            raise RuntimeError("Fusion 360 adapter route requires r1 feature timeline events")

        runtime = fusion_runtime or Fusion360Runtime.from_adsk()
        rendered_events: list[dict[str, Any]] = []
        for event in events:
            rendered = substitute_slots(event, params)
            rendered_events.append(rendered)
            action = rendered.get("action")
            if action == "create_sketch":
                runtime.create_sketch(rendered)
            elif action == "add_profile":
                runtime.add_profile(rendered)
            elif action == "extrude":
                runtime.extrude(rendered)
            elif action == "fillet":
                runtime.fillet(rendered)
            elif action == "set_parameter":
                runtime.set_parameter(rendered)
            else:
                raise RuntimeError(f"Unsupported Fusion 360 r1 action: {action}")

        snapshot = runtime.snapshot()
        return {
            "success": True,
            "route_type": "adapter",
            "adapter": self.id,
            "route_used": "r1:fusion360-python-timeline",
            "events_replayed": len(events),
            "timeline_hash": hash_design_snapshot(snapshot),
            "design": snapshot,
            "python_script": build_python_script(rendered_events),
        }


class Fusion360Runtime:
    def __init__(self, adsk_core: Any, adsk_fusion: Any) -> None:
        self.adsk_core = adsk_core
        self.adsk_fusion = adsk_fusion

    @classmethod
    def from_adsk(cls) -> "Fusion360Runtime":
        try:
            adsk_core = importlib.import_module("adsk.core")
            adsk_fusion = importlib.import_module("adsk.fusion")
            return cls(adsk_core, adsk_fusion)
        except ImportError as exc:
            raise RuntimeError("Fusion 360 Python API runtime is not available") from exc

    def create_sketch(self, event: dict[str, Any]) -> None:
        raise RuntimeError("Fusion 360 live runtime bridge not installed")

    def add_profile(self, event: dict[str, Any]) -> None:
        raise RuntimeError("Fusion 360 live runtime bridge not installed")

    def extrude(self, event: dict[str, Any]) -> None:
        raise RuntimeError("Fusion 360 live runtime bridge not installed")

    def fillet(self, event: dict[str, Any]) -> None:
        raise RuntimeError("Fusion 360 live runtime bridge not installed")

    def set_parameter(self, event: dict[str, Any]) -> None:
        raise RuntimeError("Fusion 360 live runtime bridge not installed")

    def snapshot(self) -> dict[str, Any]:
        return {"runtime": "fusion360-python"}


def replayable_events(route: dict[str, Any]) -> list[dict[str, Any]]:
    events = [normalize_event(raw_event) for raw_event in route.get("events") or []]
    validate_timeline_order(events)
    return [event for event in events if event.get("route_tier", "r1") == "r1"]


def normalize_event(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError(f"Unsupported Fusion 360 event: {value!r}")
    event = dict(value)
    require_keys(event, "action", "timeline_index", "feature_id", "parameters")
    if event.get("capture_source") in {"uia", "pixels", "approximation"}:
        raise RuntimeError(f"Fusion 360 feature history must come from API timeline evidence: {event}")
    if event.get("value_status") in {"approximate", "unreadable"}:
        raise RuntimeError(f"Fusion 360 feature history approximated: {event}")
    if not isinstance(event["parameters"], dict) or not event["parameters"]:
        raise RuntimeError(f"Fusion 360 feature event requires exact parameters: {event}")
    validate_parameters(event["parameters"])

    action = event["action"]
    if action == "create_sketch":
        require_keys(event, "plane")
    elif action == "add_profile":
        require_keys(event, "sketch_id", "profile_type")
    elif action == "extrude":
        require_keys(event, "profile_id", "operation")
    elif action == "fillet":
        require_keys(event, "edge_refs")
    elif action == "set_parameter":
        require_keys(event, "parameter_name", "expression")
    else:
        raise RuntimeError(f"Unsupported Fusion 360 r1 action: {action}")
    return event


def validate_timeline_order(events: list[dict[str, Any]]) -> None:
    indices = [int(event["timeline_index"]) for event in events]
    if indices != sorted(indices):
        raise RuntimeError(f"Fusion 360 timeline order wrong: {indices}")
    if indices != list(range(len(indices))):
        raise RuntimeError(f"Fusion 360 timeline indices must be contiguous from zero: {indices}")


def validate_parameters(value: Any) -> None:
    if isinstance(value, dict):
        for item in value.values():
            validate_parameters(item)
        return
    if isinstance(value, list):
        if not value:
            raise RuntimeError("Fusion 360 feature parameter lists must not be empty")
        for item in value:
            validate_parameters(item)
        return
    if isinstance(value, (int, float, str)) and not isinstance(value, bool):
        return
    raise RuntimeError(f"Fusion 360 feature parameter is not exact/replayable: {value!r}")


def capture_events_from_design_timeline(timeline: list[dict[str, Any]]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for index, entry in enumerate(timeline):
        event = deepcopy(entry)
        event.update(
            {
                "route_tier": "r1",
                "app": "Fusion 360",
                "kind": "feature",
                "timeline_index": entry.get("timeline_index", index),
                "capture_source": entry.get("capture_source", "design-timeline"),
            }
        )
        events.append(normalize_event(event))
    validate_timeline_order(events)
    return events


def require_keys(event: dict[str, Any], *keys: str) -> None:
    for key in keys:
        if key not in event:
            raise RuntimeError(f"Fusion 360 event missing {key}: {event}")


def substitute_slots(value: Any, params: dict[str, Any]) -> Any:
    if isinstance(value, str):
        return value.format(**params)
    if isinstance(value, list):
        return [substitute_slots(item, params) for item in value]
    if isinstance(value, dict):
        return {key: substitute_slots(item, params) for key, item in value.items()}
    return value


def build_python_script(events: list[dict[str, Any]]) -> str:
    lines = ["# Marouba Fusion 360 replay", "import adsk.core, adsk.fusion", ""]
    for event in events:
        lines.append(f"# timeline[{event['timeline_index']}] {event['action']} {json.dumps(event['feature_id'])}")
    return "\n".join(lines) + "\n"


def hash_design_snapshot(snapshot: dict[str, Any]) -> str:
    canonical = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def captured_workflow(name: str, events: list[dict[str, Any]]) -> dict[str, Any]:
    workflow_id = slugify(name)
    return {
        "id": workflow_id,
        "name": name,
        "app": "Fusion 360",
        "description": "Fusion 360 parametric modeling workflow mirrored from exact design timeline feature evidence.",
        "params": [],
        "tags": ["fusion360", "adapter", "r1", "timeline", "parametric-cad"],
        "author": "nxeratech",
        "created": "2026-06-14",
        "routes": [{"type": "adapter", "adapter": "fusion360", "events": events}],
        "fallback_order": ["adapter", "uia", "ask"],
        "verification": {"type": "timeline_feature_hash"},
        "calls": [],
        "depends_on": [],
        "signals": {"captured_events": events},
        "body": f"# {name}\n\nCaptured from Fusion 360 design timeline feature evidence.\n",
    }


def slugify(value: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in value.casefold()).strip("-") or "fusion360-workflow"
