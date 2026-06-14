from __future__ import annotations

import hashlib
import importlib
import json
from copy import deepcopy
from typing import Any


class PremiereAdapter:
    id = "premiere"
    mechanism = "uxp-extendscript-api"

    def execute(
        self,
        route: dict[str, Any],
        params: dict[str, Any],
        workflow: dict[str, Any],
        premiere_runtime: Any | None = None,
    ) -> dict[str, Any]:
        events = replayable_events(route)
        if not events:
            raise RuntimeError("Premiere adapter route requires r1 timeline/effect API events")

        runtime = premiere_runtime or PremiereRuntime.from_module()
        rendered_events: list[dict[str, Any]] = []
        for event in events:
            rendered = substitute_slots(event, params)
            rendered_events.append(rendered)
            action = rendered.get("action")
            if action == "create_sequence":
                runtime.create_sequence(rendered)
            elif action == "add_clip":
                runtime.add_clip(rendered)
            elif action == "move_clip":
                runtime.move_clip(rendered)
            elif action == "set_effect_param":
                runtime.set_effect_param(rendered)
            else:
                raise RuntimeError(f"Unsupported Premiere r1 action: {action}")

        snapshot = runtime.snapshot()
        return {
            "success": True,
            "route_type": "adapter",
            "adapter": self.id,
            "route_used": "r1:premiere-uxp-extendscript",
            "events_replayed": len(events),
            "timeline_hash": hash_timeline_snapshot(snapshot),
            "timeline": snapshot,
            "script": build_extendscript(rendered_events),
        }


class PremiereRuntime:
    def __init__(self, premiere: Any) -> None:
        self.premiere = premiere

    @classmethod
    def from_module(cls) -> "PremiereRuntime":
        try:
            return cls(importlib.import_module("premiere"))
        except ImportError as exc:
            raise RuntimeError("Premiere scripting runtime is not available") from exc

    def create_sequence(self, event: dict[str, Any]) -> None:
        self.premiere.create_sequence(event)

    def add_clip(self, event: dict[str, Any]) -> None:
        self.premiere.add_clip(event)

    def move_clip(self, event: dict[str, Any]) -> None:
        self.premiere.move_clip(event)

    def set_effect_param(self, event: dict[str, Any]) -> None:
        self.premiere.set_effect_param(event)

    def snapshot(self) -> dict[str, Any]:
        if hasattr(self.premiere, "marouba_snapshot"):
            return self.premiere.marouba_snapshot()
        return {"runtime": "premiere-scripting"}


def replayable_events(route: dict[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for raw_event in route.get("events") or []:
        event = normalize_event(raw_event)
        if event.get("route_tier", "r1") == "r1":
            events.append(event)
    return events


def normalize_event(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError(f"Unsupported Premiere event: {value!r}")
    event = dict(value)
    action = event.get("action")
    if action == "create_sequence":
        require_keys(event, "sequence_name", "timebase")
    elif action == "add_clip":
        require_keys(event, "track_type", "track_index", "clip_name", "start", "end")
        require_exact_value(event, "Premiere clip timing")
    elif action == "move_clip":
        require_keys(event, "clip_id", "start", "end")
        require_exact_value(event, "Premiere clip timing")
    elif action == "set_effect_param":
        require_keys(event, "clip_id", "effect_name", "param_name", "value")
        require_exact_value(event, "Premiere effect param")
        require_numeric_or_numeric_array(event["value"], "Premiere effect param")
    else:
        raise RuntimeError(f"Unsupported Premiere event action: {action}")
    return event


def capture_events_from_premiere_session(timeline: dict[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = [
        normalize_event(
            {
                "route_tier": "r1",
                "app": "Premiere Pro",
                "kind": "sequence",
                "action": "create_sequence",
                "sequence_name": timeline["sequence_name"],
                "timebase": timeline["timebase"],
                "frame_size": deepcopy(timeline.get("frame_size", {})),
            }
        )
    ]
    for clip in timeline.get("clips", []):
        event = dict(clip)
        event.update({"route_tier": "r1", "app": "Premiere Pro", "kind": "clip", "action": "add_clip"})
        events.append(normalize_event(event))
        for effect in clip.get("effects", []):
            for param in effect.get("params", []):
                events.append(
                    normalize_event(
                        {
                            "route_tier": "r1",
                            "app": "Premiere Pro",
                            "kind": "effect_param",
                            "action": "set_effect_param",
                            "clip_id": clip["clip_id"],
                            "effect_name": effect["effect_name"],
                            "param_name": param["param_name"],
                            "value": param["value"],
                            "value_status": param.get("value_status", "exact"),
                            "keyframes": deepcopy(param.get("keyframes", [])),
                        }
                    )
                )
    return events


def require_keys(event: dict[str, Any], *keys: str) -> None:
    for key in keys:
        if key not in event:
            raise RuntimeError(f"Premiere event missing {key}: {event}")


def require_exact_value(event: dict[str, Any], label: str) -> None:
    if event.get("value_status") in {"approximate", "unreadable"}:
        raise RuntimeError(f"{label} refuses approximated/unreadable values: {event}")
    for keyframe in event.get("keyframes", []):
        if keyframe.get("value_status") in {"approximate", "unreadable"}:
            raise RuntimeError(f"{label} keyframe values must be exact: {keyframe}")
        require_numeric_or_numeric_array(keyframe.get("value"), f"{label} keyframe")


def require_numeric_or_numeric_array(value: Any, label: str) -> None:
    values = value if isinstance(value, list) else [value]
    if not values or any(not isinstance(item, (int, float)) or isinstance(item, bool) for item in values):
        raise RuntimeError(f"{label} value must be numeric: {value!r}")


def substitute_slots(value: Any, params: dict[str, Any]) -> Any:
    if isinstance(value, str):
        return value.format(**params)
    if isinstance(value, list):
        return [substitute_slots(item, params) for item in value]
    if isinstance(value, dict):
        return {key: substitute_slots(item, params) for key, item in value.items()}
    return value


def build_extendscript(events: list[dict[str, Any]]) -> str:
    lines = ["// Marouba Premiere replay", "app.enableQE();"]
    for event in events:
        action = event.get("action")
        if action == "create_sequence":
            lines.append(f"// create sequence {json.dumps(event['sequence_name'])}")
        elif action == "add_clip":
            lines.append(f"// add clip {json.dumps(event['clip_name'])} at {event['start']}")
        elif action == "set_effect_param":
            lines.append(f"// set {event['effect_name']}.{event['param_name']} = {json.dumps(event['value'])}")
    return "\n".join(lines) + "\n"


def hash_timeline_snapshot(snapshot: dict[str, Any]) -> str:
    canonical = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def captured_workflow(name: str, events: list[dict[str, Any]]) -> dict[str, Any]:
    workflow_id = slugify(name)
    return {
        "id": workflow_id,
        "name": name,
        "app": "Premiere Pro",
        "description": "Premiere timeline and effect workflow captured from API-level sequence, track item, and component parameter evidence.",
        "params": [],
        "tags": ["premiere", "adapter", "r1", "timeline", "effects"],
        "author": "nxeratech",
        "created": "2026-06-14",
        "routes": [{"type": "adapter", "adapter": "premiere", "events": events}],
        "fallback_order": ["adapter", "uia", "ask"],
        "verification": {"type": "timeline_hash"},
        "calls": [],
        "depends_on": [],
        "signals": {"captured_events": events},
        "body": f"# {name}\n\nCaptured from Premiere timeline and effect parameter API evidence.\n",
    }


def slugify(value: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in value.casefold()).strip("-") or "premiere-workflow"
