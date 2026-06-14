from __future__ import annotations

import hashlib
import importlib
import json
from copy import deepcopy
from typing import Any


class BlenderAdapter:
    id = "blender"
    mechanism = "bpy handlers + operator log"

    def execute(
        self,
        route: dict[str, Any],
        params: dict[str, Any],
        workflow: dict[str, Any],
        bpy_module: Any | None = None,
    ) -> dict[str, Any]:
        events = replayable_events(route)
        if not events:
            raise RuntimeError("Blender adapter route requires r1 operator or datablock events")

        bpy = bpy_module or importlib.import_module("bpy")
        if route.get("clear_scene", True):
            clear_scene(bpy)

        for event in events:
            rendered = substitute_slots(event, params)
            kind = rendered.get("kind", "operator")
            if kind == "operator":
                call_bpy_operator(bpy, str(rendered["operator"]), rendered.get("params") or {})
            elif kind == "datablock_changed":
                apply_datablock_change(bpy, rendered)
            else:
                raise RuntimeError(f"Unsupported Blender r1 event kind: {kind}")

        scene_hash = hash_bpy_scene(bpy)
        return {
            "success": True,
            "route_type": "adapter",
            "adapter": self.id,
            "route_used": "r1:blender-bpy",
            "events_replayed": len(events),
            "scene_hash": scene_hash,
            "script": build_bpy_script(events),
        }


def replayable_events(route: dict[str, Any]) -> list[dict[str, Any]]:
    raw_events = route.get("events") or route.get("operators") or []
    events: list[dict[str, Any]] = []
    for raw_event in raw_events:
        event = normalize_operator_event(raw_event)
        if event.get("route_tier", "r1") != "r1":
            continue
        if event.get("kind", "operator") in {"viewport_gesture", "gesture"}:
            continue
        events.append(event)
    return events


def normalize_operator_event(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        return {"route_tier": "r1", "app": "Blender", "kind": "operator", "operator": value, "params": {}}
    if not isinstance(value, dict):
        raise RuntimeError(f"Unsupported Blender event: {value!r}")
    event = dict(value)
    if "operator" in event and "kind" not in event:
        event["kind"] = "operator"
    if event.get("kind") == "operator":
        if not event.get("operator"):
            raise RuntimeError(f"Blender operator event missing operator: {event}")
        params = event.get("params")
        if params is None:
            event["params"] = {}
        elif not isinstance(params, dict):
            raise RuntimeError(f"Blender operator params must be an object: {event}")
    return event


def substitute_slots(value: Any, params: dict[str, Any]) -> Any:
    if isinstance(value, str):
        return value.format(**params)
    if isinstance(value, list):
        return [substitute_slots(item, params) for item in value]
    if isinstance(value, dict):
        return {key: substitute_slots(item, params) for key, item in value.items()}
    return value


def clear_scene(bpy: Any) -> None:
    if hasattr(bpy, "marouba_clear_scene"):
        bpy.marouba_clear_scene()
        return

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def call_bpy_operator(bpy: Any, operator: str, params: dict[str, Any]) -> Any:
    group_name, _, op_name = operator.partition(".")
    if not group_name or not op_name:
        raise RuntimeError(f"Blender operator must be in bpy.ops group.name form: {operator}")
    group = getattr(bpy.ops, group_name)
    operation = getattr(group, op_name)
    return operation(**params)


def apply_datablock_change(bpy: Any, event: dict[str, Any]) -> None:
    if hasattr(bpy, "marouba_apply_datablock_change"):
        bpy.marouba_apply_datablock_change(event)
        return

    target = str(event.get("datablock") or event.get("target") or "")
    path = str(event.get("path") or "")
    if not target or not path:
        raise RuntimeError(f"Blender datablock change requires datablock/target and path: {event}")
    if not target.startswith("object:"):
        raise RuntimeError(f"Unsupported Blender datablock target: {target}")

    object_name = target.split(":", 1)[1]
    obj = bpy.data.objects[object_name]
    assign_path(obj, path.split("."), event.get("value"))


def assign_path(root: Any, parts: list[str], value: Any) -> None:
    if not parts:
        raise RuntimeError("Cannot assign empty Blender datablock path")
    current = root
    for part in parts[:-1]:
        current = get_child(current, part)
    leaf = parts[-1]
    if isinstance(current, dict):
        current[leaf] = value
    else:
        setattr(current, leaf, value)


def get_child(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        return value[key]
    try:
        return value[key]
    except Exception:
        return getattr(value, key)


def build_bpy_script(events: list[dict[str, Any]]) -> str:
    lines = [
        "import bpy",
        "",
        "bpy.ops.object.select_all(action='SELECT')",
        "bpy.ops.object.delete()",
        "",
    ]
    for event in events:
        kind = event.get("kind", "operator")
        if kind == "operator":
            params = json.dumps(event.get("params") or {}, sort_keys=True)
            lines.append(f"bpy.ops.{event['operator']}(**{params})")
        elif kind == "datablock_changed":
            lines.append(f"# datablock change: {json.dumps(event, sort_keys=True)}")
    return "\n".join(lines) + "\n"


def capture_events_from_blender_session(
    operator_log: list[dict[str, Any]],
    before_snapshot: dict[str, Any],
    after_snapshot: dict[str, Any],
    viewport_events: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for entry in operator_log:
        event = normalize_operator_event(
            {
                "route_tier": "r1",
                "app": "Blender",
                "kind": "operator",
                "operator": entry.get("operator"),
                "params": deepcopy(entry.get("params") or {}),
            }
        )
        events.append(event)

    events.extend(diff_datablocks(before_snapshot, after_snapshot))

    for viewport_event in viewport_events or []:
        demoted = dict(viewport_event)
        demoted.update({"route_tier": "r3", "app": "Blender", "kind": "viewport_gesture"})
        events.append(demoted)
    return events


def diff_datablocks(before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    before_flat = flatten_snapshot(before)
    after_flat = flatten_snapshot(after)
    for path in sorted(set(before_flat) | set(after_flat)):
        if before_flat.get(path) == after_flat.get(path):
            continue
        target, _, attr_path = path.partition(".")
        events.append(
            {
                "route_tier": "r1",
                "app": "Blender",
                "kind": "datablock_changed",
                "datablock": target,
                "path": attr_path,
                "before": before_flat.get(path),
                "value": after_flat.get(path),
            }
        )
    return events


def flatten_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    flat: dict[str, Any] = {}

    def walk(prefix: str, value: Any) -> None:
        if isinstance(value, dict):
            for key in sorted(value):
                walk(f"{prefix}.{key}" if prefix else str(key), value[key])
        elif isinstance(value, list):
            for index, item in enumerate(value):
                walk(f"{prefix}.{index}", item)
        else:
            flat[prefix] = value

    objects = snapshot.get("objects", snapshot)
    for name, value in sorted(objects.items()):
        walk(f"object:{name}", value)
    return flat


def hash_bpy_scene(bpy: Any) -> str:
    if hasattr(bpy, "marouba_scene_snapshot"):
        return hash_scene_snapshot(bpy.marouba_scene_snapshot())
    return hash_scene_snapshot(snapshot_bpy_scene(bpy))


def hash_scene_snapshot(snapshot: dict[str, Any]) -> str:
    canonical = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def snapshot_bpy_scene(bpy: Any) -> dict[str, Any]:
    objects: dict[str, Any] = {}
    for obj in sorted(bpy.data.objects, key=lambda item: item.name):
        item: dict[str, Any] = {
            "name": obj.name,
            "type": obj.type,
            "location": [round(float(value), 6) for value in getattr(obj, "location", [])],
            "modifiers": [],
        }
        for modifier in getattr(obj, "modifiers", []):
            item["modifiers"].append({"name": modifier.name, "type": modifier.type})
        mesh = getattr(obj, "data", None)
        if mesh is not None and hasattr(mesh, "vertices"):
            item["mesh"] = {
                "vertices": [
                    [round(float(coord), 6) for coord in vertex.co]
                    for vertex in mesh.vertices
                ],
                "polygons": [list(poly.vertices) for poly in mesh.polygons],
            }
        objects[obj.name] = item
    return {"objects": objects}
