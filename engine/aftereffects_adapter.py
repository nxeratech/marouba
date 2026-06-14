from __future__ import annotations

import hashlib
import importlib
import json
from copy import deepcopy
from typing import Any


class AfterEffectsAdapter:
    id = "after-effects"
    mechanism = "extendscript-api"

    def execute(
        self,
        route: dict[str, Any],
        params: dict[str, Any],
        workflow: dict[str, Any],
        ae_runtime: Any | None = None,
    ) -> dict[str, Any]:
        events = replayable_events(route)
        if not events:
            raise RuntimeError("After Effects adapter route requires r1 comp/keyframe/effect API events")

        runtime = ae_runtime or AfterEffectsRuntime.from_module()
        rendered_events: list[dict[str, Any]] = []
        for event in events:
            rendered = substitute_slots(event, params)
            rendered_events.append(rendered)
            action = rendered.get("action")
            if action == "create_comp":
                runtime.create_comp(rendered)
            elif action == "add_layer":
                runtime.add_layer(rendered)
            elif action == "add_effect":
                runtime.add_effect(rendered)
            elif action == "set_keyframe":
                runtime.set_keyframe(rendered)
            elif action == "set_expression":
                runtime.set_expression(rendered)
            else:
                raise RuntimeError(f"Unsupported After Effects r1 action: {action}")

        snapshot = runtime.snapshot()
        return {
            "success": True,
            "route_type": "adapter",
            "adapter": self.id,
            "route_used": "r1:after-effects-extendscript",
            "events_replayed": len(events),
            "comp_hash": hash_comp_snapshot(snapshot),
            "comp": snapshot,
            "script": build_extendscript(rendered_events),
        }


class AfterEffectsRuntime:
    def __init__(self, ae: Any) -> None:
        self.ae = ae

    @classmethod
    def from_module(cls) -> "AfterEffectsRuntime":
        try:
            return cls(importlib.import_module("aftereffects"))
        except ImportError as exc:
            raise RuntimeError("After Effects scripting runtime is not available") from exc

    def create_comp(self, event: dict[str, Any]) -> None:
        self.ae.create_comp(event)

    def add_layer(self, event: dict[str, Any]) -> None:
        self.ae.add_layer(event)

    def add_effect(self, event: dict[str, Any]) -> None:
        self.ae.add_effect(event)

    def set_keyframe(self, event: dict[str, Any]) -> None:
        self.ae.set_keyframe(event)

    def set_expression(self, event: dict[str, Any]) -> None:
        self.ae.set_expression(event)

    def snapshot(self) -> dict[str, Any]:
        if hasattr(self.ae, "marouba_snapshot"):
            return self.ae.marouba_snapshot()
        return {"runtime": "after-effects-extendscript"}


def replayable_events(route: dict[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for raw_event in route.get("events") or []:
        event = normalize_event(raw_event)
        if event.get("route_tier", "r1") == "r1":
            events.append(event)
    return events


def normalize_event(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError(f"Unsupported After Effects event: {value!r}")
    event = dict(value)
    action = event.get("action")
    if action == "create_comp":
        require_keys(event, "comp_name", "width", "height", "duration", "frame_rate")
    elif action == "add_layer":
        require_keys(event, "layer_id", "layer_name", "layer_type")
    elif action == "add_effect":
        require_keys(event, "layer_id", "effect_name", "match_name")
    elif action == "set_keyframe":
        require_keys(event, "layer_id", "property_path", "time", "value")
        require_exact_value(event, "After Effects keyframe")
        require_numeric_or_numeric_array(event["value"], "After Effects keyframe")
    elif action == "set_expression":
        require_keys(event, "layer_id", "property_path", "expression")
    else:
        raise RuntimeError(f"Unsupported After Effects event action: {action}")
    return event


def capture_events_from_ae_project(comp: dict[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = [
        normalize_event(
            {
                "route_tier": "r1",
                "app": "After Effects",
                "kind": "comp",
                "action": "create_comp",
                "comp_name": comp["comp_name"],
                "width": comp["width"],
                "height": comp["height"],
                "duration": comp["duration"],
                "frame_rate": comp["frame_rate"],
            }
        )
    ]
    for layer in comp.get("layers", []):
        events.append(
            normalize_event(
                {
                    "route_tier": "r1",
                    "app": "After Effects",
                    "kind": "layer",
                    "action": "add_layer",
                    "layer_id": layer["layer_id"],
                    "layer_name": layer["layer_name"],
                    "layer_type": layer["layer_type"],
                }
            )
        )
        for effect in layer.get("effects", []):
            events.append(
                normalize_event(
                    {
                        "route_tier": "r1",
                        "app": "After Effects",
                        "kind": "effect",
                        "action": "add_effect",
                        "layer_id": layer["layer_id"],
                        "effect_name": effect["effect_name"],
                        "match_name": effect["match_name"],
                    }
                )
            )
        for keyframe in layer.get("keyframes", []):
            event = dict(keyframe)
            event.update({"route_tier": "r1", "app": "After Effects", "kind": "keyframe", "action": "set_keyframe", "layer_id": layer["layer_id"]})
            events.append(normalize_event(event))
        for expression in layer.get("expressions", []):
            event = dict(expression)
            event.update({"route_tier": "r1", "app": "After Effects", "kind": "expression", "action": "set_expression", "layer_id": layer["layer_id"]})
            events.append(normalize_event(event))
    return events


def require_keys(event: dict[str, Any], *keys: str) -> None:
    for key in keys:
        if key not in event:
            raise RuntimeError(f"After Effects event missing {key}: {event}")


def require_exact_value(event: dict[str, Any], label: str) -> None:
    if event.get("value_status") in {"approximate", "unreadable"}:
        raise RuntimeError(f"{label} values must be exact, never approximated: {event}")


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
    lines = ["// Marouba After Effects replay", "app.beginUndoGroup('Marouba Replay');"]
    for event in events:
        action = event.get("action")
        if action == "create_comp":
            lines.append(f"// create comp {json.dumps(event['comp_name'])}")
        elif action == "add_effect":
            lines.append(f"// add effect {json.dumps(event['match_name'])}")
        elif action == "set_keyframe":
            lines.append(f"// setValueAtTime {event['property_path']} {event['time']} {json.dumps(event['value'])}")
        elif action == "set_expression":
            lines.append(f"// expression {event['property_path']}")
    lines.append("app.endUndoGroup();")
    return "\n".join(lines) + "\n"


def hash_comp_snapshot(snapshot: dict[str, Any]) -> str:
    canonical = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def captured_workflow(name: str, events: list[dict[str, Any]]) -> dict[str, Any]:
    workflow_id = slugify(name)
    return {
        "id": workflow_id,
        "name": name,
        "app": "After Effects",
        "description": "After Effects comp workflow captured from exact layer, effect, keyframe, and expression API evidence.",
        "params": [],
        "tags": ["after-effects", "adapter", "r1", "keyframes", "expressions"],
        "author": "nxeratech",
        "created": "2026-06-14",
        "routes": [{"type": "adapter", "adapter": "after-effects", "events": events}],
        "fallback_order": ["adapter", "uia", "ask"],
        "verification": {"type": "comp_hash"},
        "calls": [],
        "depends_on": [],
        "signals": {"captured_events": events},
        "body": f"# {name}\n\nCaptured from After Effects scripting API comp, effect, keyframe, and expression evidence.\n",
    }


def slugify(value: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in value.casefold()).strip("-") or "after-effects-workflow"
