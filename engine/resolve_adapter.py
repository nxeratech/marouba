from __future__ import annotations

import hashlib
import importlib
import json
from copy import deepcopy
from typing import Any


class ResolveAdapter:
    id = "davinci-resolve"
    mechanism = "python-scripting-api"

    def execute(
        self,
        route: dict[str, Any],
        params: dict[str, Any],
        workflow: dict[str, Any],
        resolve_app: Any | None = None,
    ) -> dict[str, Any]:
        events = replayable_events(route)
        if not events:
            raise RuntimeError("DaVinci Resolve adapter route requires r1 API timeline or grade events")

        resolve = resolve_app or get_resolve()
        project = current_project(resolve)
        timeline = current_timeline(project)
        context = ResolveReplayContext(resolve=resolve, project=project, timeline=timeline)

        for event in events:
            rendered = substitute_slots(event, params)
            replay_event(context, rendered)

        state = snapshot_resolve_context(context)
        return {
            "success": True,
            "route_type": "adapter",
            "adapter": self.id,
            "route_used": "r1:resolve-python-api",
            "events_replayed": len(events),
            "project_hash": hash_resolve_snapshot(state),
            "state": state,
        }


class ResolveReplayContext:
    def __init__(self, resolve: Any, project: Any, timeline: Any) -> None:
        self.resolve = resolve
        self.project = project
        self.timeline = timeline
        self.media_pool = project.GetMediaPool()
        self.media_items: dict[str, Any] = {}
        self.timeline_items: dict[str, Any] = {}


def get_resolve() -> Any:
    module = importlib.import_module("DaVinciResolveScript")
    resolve = module.scriptapp("Resolve")
    if resolve is None:
        raise RuntimeError("DaVinci Resolve scripting API did not return a Resolve app")
    return resolve


def current_project(resolve: Any) -> Any:
    project_manager = resolve.GetProjectManager()
    project = project_manager.GetCurrentProject()
    if project is None:
        raise RuntimeError("DaVinci Resolve has no current project")
    return project


def current_timeline(project: Any) -> Any:
    timeline = project.GetCurrentTimeline()
    if timeline is None:
        raise RuntimeError("DaVinci Resolve project has no current timeline")
    return timeline


def replayable_events(route: dict[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for raw_event in route.get("events") or []:
        event = normalize_event(raw_event)
        if event.get("route_tier", "r1") != "r1":
            continue
        if event.get("kind") in {"ui_gesture", "gesture", "visual"}:
            continue
        events.append(event)
    return events


def normalize_event(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError(f"Unsupported DaVinci Resolve event: {value!r}")
    event = dict(value)
    kind = event.get("kind")
    if kind not in {"timeline_op", "grade_node"}:
        return event
    if event.get("capture_source") == "approximation":
        raise RuntimeError(f"Resolve {kind} refuses approximated grade/timeline values: {event}")
    if kind == "grade_node" and event.get("value_source") not in {"api", "drx", "lut", "cdl"}:
        raise RuntimeError(f"Resolve grade_node requires exact api/drx/lut/cdl value_source: {event}")
    return event


def replay_event(context: ResolveReplayContext, event: dict[str, Any]) -> None:
    kind = event.get("kind")
    action = event.get("action")
    if kind == "timeline_op":
        replay_timeline_op(context, event, str(action))
        return
    if kind == "grade_node":
        replay_grade_node(context, event, str(action))
        return
    raise RuntimeError(f"Unsupported Resolve r1 event kind: {kind}")


def replay_timeline_op(context: ResolveReplayContext, event: dict[str, Any], action: str) -> None:
    if action == "add_track":
        ok = context.timeline.AddTrack(event["track_type"], event.get("options") or event.get("sub_track_type", ""))
        require_ok(ok, event)
        return
    if action == "set_current_timecode":
        require_ok(context.timeline.SetCurrentTimecode(event["timecode"]), event)
        return
    if action == "import_media":
        items = context.media_pool.ImportMedia(event["paths"])
        require_ok(bool(items), event)
        for path, item in zip(event["paths"], items):
            context.media_items[str(path)] = item
        return
    if action == "append_to_timeline":
        clip_infos = resolve_clip_infos(context, event["clip_infos"])
        appended = context.media_pool.AppendToTimeline(clip_infos)
        require_ok(bool(appended), event)
        for index, item in enumerate(appended):
            key = str(event.get("result_key") or f"timeline_item_{len(context.timeline_items) + index + 1}")
            context.timeline_items[key] = item
        return
    raise RuntimeError(f"Unsupported Resolve timeline action: {action}")


def resolve_clip_infos(context: ResolveReplayContext, clip_infos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    resolved = deepcopy(clip_infos)
    for clip_info in resolved:
        media_pool_item = clip_info.get("mediaPoolItem")
        if isinstance(media_pool_item, str) and media_pool_item in context.media_items:
            clip_info["mediaPoolItem"] = context.media_items[media_pool_item]
    return resolved


def replay_grade_node(context: ResolveReplayContext, event: dict[str, Any], action: str) -> None:
    timeline_item = resolve_timeline_item(context, event)
    if action == "set_cdl":
        require_ok(timeline_item.SetCDL(event["cdl"]), event)
        return

    graph = timeline_item.GetNodeGraph(int(event.get("layer_index", 1)))
    node_index = int(event.get("node_index", 1))
    if action == "set_lut":
        require_ok(graph.SetLUT(node_index, event["lut_path"]), event)
        return
    if action == "apply_grade_from_drx":
        require_ok(graph.ApplyGradeFromDRX(event["drx_path"], int(event.get("grade_mode", 0))), event)
        return
    if action == "set_node_enabled":
        require_ok(graph.SetNodeEnabled(node_index, bool(event["enabled"])), event)
        return
    raise RuntimeError(f"Unsupported Resolve grade action: {action}")


def resolve_timeline_item(context: ResolveReplayContext, event: dict[str, Any]) -> Any:
    key = str(event.get("timeline_item") or event.get("timeline_item_key") or "timeline_item_1")
    if key not in context.timeline_items and hasattr(context.timeline, "GetItemListInTrack"):
        track_type = str(event.get("track_type", "video"))
        track_index = int(event.get("track_index", 1))
        items = context.timeline.GetItemListInTrack(track_type, track_index)
        if items:
            context.timeline_items[key] = items[int(event.get("item_index", 0))]
    if key not in context.timeline_items:
        raise RuntimeError(f"Resolve timeline item not available for grade event: {key}")
    return context.timeline_items[key]


def require_ok(ok: Any, event: dict[str, Any]) -> None:
    if not ok:
        raise RuntimeError(f"DaVinci Resolve API call failed for event: {event}")


def substitute_slots(value: Any, params: dict[str, Any]) -> Any:
    if isinstance(value, str):
        return value.format(**params)
    if isinstance(value, list):
        return [substitute_slots(item, params) for item in value]
    if isinstance(value, dict):
        return {key: substitute_slots(item, params) for key, item in value.items()}
    return value


def capture_events_from_resolve_session(
    timeline_events: list[dict[str, Any]],
    grade_events: list[dict[str, Any]],
    ui_events: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for entry in timeline_events:
        event = dict(entry)
        event.update({"route_tier": "r1", "app": "DaVinci Resolve", "kind": "timeline_op"})
        events.append(normalize_event(event))
    for entry in grade_events:
        event = dict(entry)
        event.update({"route_tier": "r1", "app": "DaVinci Resolve", "kind": "grade_node"})
        events.append(normalize_event(event))
    for entry in ui_events or []:
        event = dict(entry)
        event.update({"route_tier": entry.get("route_tier", "r2"), "app": "DaVinci Resolve", "kind": "ui_gesture"})
        events.append(event)
    return events


def snapshot_resolve_context(context: ResolveReplayContext) -> dict[str, Any]:
    if hasattr(context.resolve, "marouba_snapshot"):
        return context.resolve.marouba_snapshot()
    return {
        "project": safe_call(context.project, "GetName"),
        "timeline": safe_call(context.timeline, "GetName"),
        "timeline_items": sorted(context.timeline_items),
    }


def safe_call(target: Any, name: str) -> Any:
    method = getattr(target, name, None)
    if method is None:
        return None
    try:
        return method()
    except Exception:
        return None


def hash_resolve_snapshot(snapshot: dict[str, Any]) -> str:
    canonical = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def captured_workflow(name: str, events: list[dict[str, Any]]) -> dict[str, Any]:
    workflow_id = slugify(name)
    return {
        "id": workflow_id,
        "name": name,
        "app": "DaVinci Resolve",
        "description": "Resolve edit and grade workflow captured from Python scripting API evidence.",
        "params": [],
        "tags": ["davinci-resolve", "adapter", "r1", "timeline", "grade"],
        "author": "nxeratech",
        "created": "2026-06-14",
        "routes": [{"type": "adapter", "adapter": "davinci-resolve", "events": events}],
        "fallback_order": ["adapter", "uia", "ask"],
        "verification": {"type": "project_hash"},
        "calls": [],
        "depends_on": [],
        "signals": {"captured_events": events},
        "body": f"# {name}\n\nCaptured from Resolve timeline and grade scripting API events.\n",
    }


def slugify(value: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in value.casefold()).strip("-") or "resolve-workflow"
