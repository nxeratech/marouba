from __future__ import annotations

import hashlib
import importlib
import json
from copy import deepcopy
from typing import Any


class PhotoshopAdapter:
    id = "photoshop"
    mechanism = "uxp-actionjson"

    def execute(
        self,
        route: dict[str, Any],
        params: dict[str, Any],
        workflow: dict[str, Any],
        photoshop_runtime: Any | None = None,
    ) -> dict[str, Any]:
        events = replayable_events(route)
        if not events:
            raise RuntimeError("Photoshop adapter route requires UXP/ExtendScript action events")

        runtime = photoshop_runtime or PhotoshopRuntime.from_uxp_module()
        rendered_events: list[dict[str, Any]] = []
        gesture_events: list[dict[str, Any]] = []
        for event in events:
            rendered = substitute_slots(event, params)
            rendered_events.append(rendered)
            if rendered.get("route_tier") == "r3":
                runtime.record_gesture_stroke(rendered)
                gesture_events.append(rendered)
                continue

            action = rendered.get("action")
            if action == "set_tool":
                runtime.set_tool(rendered)
            elif action == "layer_op":
                runtime.layer_op(rendered)
            elif action == "apply_filter":
                runtime.apply_filter(rendered)
            elif action == "adjustment":
                runtime.adjustment(rendered)
            elif action == "batch_play":
                runtime.batch_play(rendered)
            else:
                raise RuntimeError(f"Unsupported Photoshop event action: {action}")

        snapshot = runtime.snapshot()
        return {
            "success": True,
            "route_type": "adapter",
            "adapter": self.id,
            "route_used": "r1:photoshop-uxp-actionjson",
            "events_replayed": len(events),
            "semantic_events": len([event for event in events if event.get("route_tier", "r1") == "r1"]),
            "gesture_strokes": len(gesture_events),
            "gesture_policy": "brush strokes remain r3 gesture by design; timing is taste evidence",
            "document_hash": hash_document_snapshot(snapshot),
            "document": snapshot,
            "script": build_uxp_script(rendered_events),
        }


class PhotoshopRuntime:
    def __init__(self, photoshop: Any) -> None:
        self.photoshop = photoshop

    @classmethod
    def from_uxp_module(cls) -> "PhotoshopRuntime":
        try:
            return cls(importlib.import_module("photoshop"))
        except ImportError as exc:
            raise RuntimeError("Photoshop UXP runtime is not available") from exc

    def set_tool(self, event: dict[str, Any]) -> None:
        self.batch_play({"descriptor": {"_obj": "select", "_target": [{"_ref": event["tool_name"]}]}})

    def layer_op(self, event: dict[str, Any]) -> None:
        self.batch_play({"descriptor": event["descriptor"]})

    def apply_filter(self, event: dict[str, Any]) -> None:
        self.batch_play({"descriptor": event["descriptor"]})

    def adjustment(self, event: dict[str, Any]) -> None:
        self.batch_play({"descriptor": event["descriptor"]})

    def batch_play(self, event: dict[str, Any]) -> None:
        action = self.photoshop.action
        core = self.photoshop.core
        descriptor = event.get("descriptor") or event.get("descriptors")
        descriptors = descriptor if isinstance(descriptor, list) else [descriptor]
        core.executeAsModal(lambda: action.batchPlay(descriptors, {"dialogOptions": "silent"}), {"commandName": "Marouba Replay"})

    def record_gesture_stroke(self, event: dict[str, Any]) -> None:
        if hasattr(self.photoshop, "marouba_record_gesture"):
            self.photoshop.marouba_record_gesture(event)

    def snapshot(self) -> dict[str, Any]:
        if hasattr(self.photoshop, "marouba_snapshot"):
            return self.photoshop.marouba_snapshot()
        return {"runtime": "photoshop-uxp"}


def replayable_events(route: dict[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for raw_event in route.get("events") or []:
        events.append(normalize_event(raw_event))
    return events


def normalize_event(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError(f"Unsupported Photoshop event: {value!r}")
    event = dict(value)
    action = event.get("action")
    tier = event.get("route_tier", "r1")
    if action == "set_tool":
        require_keys(event, "tool_name")
    elif action == "layer_op":
        require_keys(event, "operation", "descriptor")
    elif action == "apply_filter":
        require_keys(event, "filter_name", "params", "descriptor")
        require_numeric_params(event, "Photoshop filter")
    elif action == "adjustment":
        require_keys(event, "adjustment_name", "params", "descriptor")
        require_numeric_params(event, "Photoshop adjustment")
    elif action == "batch_play":
        require_keys(event, "descriptor")
    elif action == "brush_stroke":
        require_keys(event, "points", "timing_ms")
        if tier != "r3":
            raise RuntimeError(f"Photoshop brush strokes must be declared r3 gesture evidence: {event}")
    else:
        raise RuntimeError(f"Unsupported Photoshop event action: {action}")
    return event


def require_keys(event: dict[str, Any], *keys: str) -> None:
    for key in keys:
        if key not in event:
            raise RuntimeError(f"Photoshop event missing {key}: {event}")


def require_numeric_params(event: dict[str, Any], label: str) -> None:
    if event.get("value_status") in {"unreadable", "approximate"}:
        raise RuntimeError(f"{label} values must be exact numeric values: {event}")
    params = event.get("params")
    if not isinstance(params, dict) or not params:
        raise RuntimeError(f"{label} requires captured numeric params: {event}")
    for name, value in params.items():
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise RuntimeError(f"{label} param is not numeric ({name}={value!r}): {event}")


def capture_events_from_action_notifications(log: list[dict[str, Any]]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for entry in log:
        kind = entry.get("kind")
        descriptor = deepcopy(entry.get("descriptor", {}))
        if kind == "tool":
            event = {
                "route_tier": "r1",
                "app": "Photoshop",
                "kind": "tool",
                "action": "set_tool",
                "tool_name": entry["tool_name"],
                "descriptor": descriptor,
                "source": "uxp-action-notification",
            }
        elif kind == "layer":
            event = {
                "route_tier": "r1",
                "app": "Photoshop",
                "kind": "layer",
                "action": "layer_op",
                "operation": entry["operation"],
                "layer_id": entry.get("layer_id"),
                "layer_name": entry.get("layer_name"),
                "descriptor": descriptor,
                "source": "uxp-action-notification",
            }
        elif kind == "filter":
            event = {
                "route_tier": "r1",
                "app": "Photoshop",
                "kind": "filter",
                "action": "apply_filter",
                "filter_name": entry["filter_name"],
                "params": deepcopy(entry.get("params", {})),
                "value_status": entry.get("value_status", "exact"),
                "descriptor": descriptor,
                "source": "uxp-action-notification",
            }
        elif kind == "adjustment":
            event = {
                "route_tier": "r1",
                "app": "Photoshop",
                "kind": "adjustment",
                "action": "adjustment",
                "adjustment_name": entry["adjustment_name"],
                "params": deepcopy(entry.get("params", {})),
                "value_status": entry.get("value_status", "exact"),
                "descriptor": descriptor,
                "source": "uxp-action-notification",
            }
        elif kind == "brush_stroke":
            event = {
                "route_tier": "r3",
                "app": "Photoshop",
                "kind": "brush_stroke",
                "action": "brush_stroke",
                "points": deepcopy(entry["points"]),
                "timing_ms": deepcopy(entry["timing_ms"]),
                "source": "gesture-capture",
                "taste_signal": "timing",
            }
        else:
            raise RuntimeError(f"Unsupported Photoshop capture log kind: {entry}")
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


def build_uxp_script(events: list[dict[str, Any]]) -> str:
    descriptors = [event["descriptor"] for event in events if event.get("route_tier", "r1") == "r1" and event.get("descriptor")]
    return "\n".join(
        [
            "const { action, core } = require('photoshop');",
            "await core.executeAsModal(async () => {",
            f"  await action.batchPlay({json.dumps(descriptors, sort_keys=True)}, {{ dialogOptions: 'silent' }});",
            "}, { commandName: 'Marouba Replay' });",
            "",
        ]
    )


def hash_document_snapshot(snapshot: dict[str, Any]) -> str:
    canonical = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def captured_workflow(name: str, events: list[dict[str, Any]]) -> dict[str, Any]:
    workflow_id = slugify(name)
    return {
        "id": workflow_id,
        "name": name,
        "app": "Photoshop",
        "description": "Photoshop layered edit captured from UXP action descriptors, exact filter values, and declared r3 brush gestures.",
        "params": [],
        "tags": ["photoshop", "adapter", "uxp", "actionjson", "layered-edit"],
        "author": "nxeratech",
        "created": "2026-06-14",
        "routes": [{"type": "adapter", "adapter": "photoshop", "events": events}],
        "fallback_order": ["adapter", "gesture", "ask"],
        "verification": {"type": "document_hash"},
        "calls": [],
        "depends_on": [],
        "signals": {"captured_events": events},
        "body": f"# {name}\n\nCaptured from Photoshop UXP action notifications plus declared brush gesture timing.\n",
    }


def slugify(value: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in value.casefold()).strip("-") or "photoshop-workflow"
