from __future__ import annotations

import hashlib
import importlib
import json
from copy import deepcopy
from typing import Any


class ReaperAdapter:
    id = "reaper"
    mechanism = "reascript-api"

    def execute(
        self,
        route: dict[str, Any],
        params: dict[str, Any],
        workflow: dict[str, Any],
        reaper_runtime: Any | None = None,
    ) -> dict[str, Any]:
        events = replayable_events(route)
        if not events:
            raise RuntimeError("REAPER adapter route requires r1 ReaScript events")

        runtime = reaper_runtime or ReaperRuntime.from_python_module()
        rendered_events: list[dict[str, Any]] = []
        for event in events:
            rendered = substitute_slots(event, params)
            rendered_events.append(rendered)
            action = rendered.get("action")
            if action == "run_action":
                runtime.run_action(rendered)
            elif action == "insert_track":
                runtime.insert_track(rendered)
            elif action == "add_media_item":
                runtime.add_media_item(rendered)
            elif action == "add_fx":
                runtime.add_fx(rendered)
            elif action == "set_fx_param":
                runtime.set_fx_param(rendered)
            elif action == "insert_envelope_point":
                runtime.insert_envelope_point(rendered)
            else:
                raise RuntimeError(f"Unsupported REAPER r1 action: {action}")

        snapshot = runtime.snapshot()
        return {
            "success": True,
            "route_type": "adapter",
            "adapter": self.id,
            "route_used": "r1:reaper-reascript",
            "events_replayed": len(events),
            "project_hash": hash_project_snapshot(snapshot),
            "project": snapshot,
            "script": build_reascript_lua(rendered_events),
        }


class ReaperRuntime:
    def __init__(self, reaper: Any) -> None:
        self.reaper = reaper

    @classmethod
    def from_python_module(cls) -> "ReaperRuntime":
        try:
            return cls(importlib.import_module("reaper_python"))
        except ImportError as exc:
            raise RuntimeError("REAPER Python ReaScript runtime is not available") from exc

    def run_action(self, event: dict[str, Any]) -> None:
        self.reaper.RPR_Main_OnCommand(int(event["command_id"]), 0)

    def insert_track(self, event: dict[str, Any]) -> Any:
        index = int(event["track_index"])
        self.reaper.RPR_InsertTrackAtIndex(index, bool(event.get("want_defaults", False)))
        track = self.reaper.RPR_GetTrack(0, index)
        if event.get("name"):
            self.reaper.RPR_GetSetMediaTrackInfo_String(track, "P_NAME", str(event["name"]), True)
        if "volume" in event:
            self.reaper.RPR_SetMediaTrackInfo_Value(track, "D_VOL", float(event["volume"]))
        if "pan" in event:
            self.reaper.RPR_SetMediaTrackInfo_Value(track, "D_PAN", float(event["pan"]))
        return track

    def add_media_item(self, event: dict[str, Any]) -> Any:
        track = self.track(event)
        item = self.reaper.RPR_AddMediaItemToTrack(track)
        self.reaper.RPR_SetMediaItemInfo_Value(item, "D_POSITION", float(event.get("position", 0)))
        self.reaper.RPR_SetMediaItemInfo_Value(item, "D_LENGTH", float(event.get("length", 0)))
        if event.get("name") and hasattr(self.reaper, "RPR_GetSetMediaItemInfo_String"):
            self.reaper.RPR_GetSetMediaItemInfo_String(item, "P_NOTES", str(event["name"]), True)
        return item

    def add_fx(self, event: dict[str, Any]) -> int:
        track = self.track(event)
        return int(self.reaper.RPR_TrackFX_AddByName(track, str(event["fx_name"]), False, int(event.get("instantiate", -1))))

    def set_fx_param(self, event: dict[str, Any]) -> None:
        track = self.track(event)
        self.reaper.RPR_TrackFX_SetParam(track, int(event["fx_index"]), int(event["param_index"]), float(event["value"]))

    def insert_envelope_point(self, event: dict[str, Any]) -> None:
        track = self.track(event)
        envelope = self.reaper.RPR_GetTrackEnvelopeByName(track, str(event["envelope_name"]))
        ok = self.reaper.RPR_InsertEnvelopePoint(
            envelope,
            float(event["time"]),
            float(event["value"]),
            int(event.get("shape", 0)),
            float(event.get("tension", 0)),
            bool(event.get("selected", False)),
            bool(event.get("no_sort", True)),
        )
        if isinstance(ok, tuple):
            ok = ok[0]
        if not ok:
            raise RuntimeError(f"REAPER InsertEnvelopePoint failed: {event}")
        self.reaper.RPR_Envelope_SortPoints(envelope)

    def track(self, event: dict[str, Any]) -> Any:
        return self.reaper.RPR_GetTrack(0, int(event["track_index"]))

    def snapshot(self) -> dict[str, Any]:
        if hasattr(self.reaper, "marouba_snapshot"):
            return self.reaper.marouba_snapshot()
        return {"runtime": "reaper_python"}


def replayable_events(route: dict[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for raw_event in route.get("events") or []:
        event = normalize_event(raw_event)
        if event.get("route_tier", "r1") == "r1":
            events.append(event)
    return events


def normalize_event(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError(f"Unsupported REAPER event: {value!r}")
    event = dict(value)
    action = event.get("action")
    if action == "run_action":
        require_keys(event, "command_id")
    elif action == "insert_track":
        require_keys(event, "track_index")
    elif action == "add_media_item":
        require_keys(event, "track_index", "position", "length")
    elif action == "add_fx":
        require_keys(event, "track_index", "fx_name")
    elif action == "set_fx_param":
        require_keys(event, "track_index", "fx_index", "param_index", "value")
        if event.get("value_status") in {"unreadable", "approximate"}:
            raise RuntimeError(f"REAPER FX param value is not exact/readable: {event}")
    elif action == "insert_envelope_point":
        require_keys(event, "track_index", "envelope_name", "time", "value")
        if event.get("value_status") in {"unreadable", "approximate"}:
            raise RuntimeError(f"REAPER envelope value is not exact/readable: {event}")
    else:
        raise RuntimeError(f"Unsupported REAPER r1 action: {action}")
    return event


def require_keys(event: dict[str, Any], *keys: str) -> None:
    for key in keys:
        if key not in event:
            raise RuntimeError(f"REAPER event missing {key}: {event}")


def substitute_slots(value: Any, params: dict[str, Any]) -> Any:
    if isinstance(value, str):
        return value.format(**params)
    if isinstance(value, list):
        return [substitute_slots(item, params) for item in value]
    if isinstance(value, dict):
        return {key: substitute_slots(item, params) for key, item in value.items()}
    return value


def capture_events_from_reaper_project(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for action in snapshot.get("actions", []):
        events.append(
            {
                "route_tier": "r1",
                "app": "REAPER",
                "kind": "action",
                "action": "run_action",
                "command_id": action["command_id"],
            }
        )
    for track in snapshot.get("tracks", []):
        events.append(
            {
                "route_tier": "r1",
                "app": "REAPER",
                "kind": "track",
                "action": "insert_track",
                "track_index": track["track_index"],
                "name": track.get("name"),
                "volume": track.get("volume"),
                "pan": track.get("pan"),
                "want_defaults": False,
            }
        )
        for item in track.get("items", []):
            events.append(
                {
                    "route_tier": "r1",
                    "app": "REAPER",
                    "kind": "item",
                    "action": "add_media_item",
                    "track_index": track["track_index"],
                    "position": item["position"],
                    "length": item["length"],
                    "name": item.get("name"),
                    "source_path": item.get("source_path"),
                }
            )
        for fx in track.get("fx", []):
            events.append(
                {
                    "route_tier": "r1",
                    "app": "REAPER",
                    "kind": "fx",
                    "action": "add_fx",
                    "track_index": track["track_index"],
                    "fx_index": fx["fx_index"],
                    "fx_name": fx["fx_name"],
                }
            )
            for param in fx.get("params", []):
                if param.get("value_status") in {"unreadable", "approximate"} or "value" not in param:
                    raise RuntimeError(f"REAPER FX param unread where ReaScript exposes it: {param}")
                events.append(
                    {
                        "route_tier": "r1",
                        "app": "REAPER",
                        "kind": "fx_param",
                        "action": "set_fx_param",
                        "track_index": track["track_index"],
                        "fx_index": fx["fx_index"],
                        "param_index": param["param_index"],
                        "param_name": param.get("param_name"),
                        "value": param["value"],
                        "min": param.get("min"),
                        "max": param.get("max"),
                        "value_status": "exact",
                    }
                )
        for envelope in track.get("envelopes", []):
            for point in envelope.get("points", []):
                if point.get("value_status") in {"unreadable", "approximate"}:
                    raise RuntimeError(f"REAPER envelope value is not exact/readable: {point}")
                events.append(
                    {
                        "route_tier": "r1",
                        "app": "REAPER",
                        "kind": "envelope",
                        "action": "insert_envelope_point",
                        "track_index": track["track_index"],
                        "envelope_name": envelope["name"],
                        "time": point["time"],
                        "value": point["value"],
                        "shape": point.get("shape", 0),
                        "tension": point.get("tension", 0),
                        "value_status": "exact",
                    }
                )
    return events


def build_reascript_lua(events: list[dict[str, Any]]) -> str:
    lines = ["reaper.Undo_BeginBlock()", ""]
    for event in events:
        action = event.get("action")
        if action == "run_action":
            lines.append(f"reaper.Main_OnCommand({int(event['command_id'])}, 0)")
        elif action == "insert_track":
            lines.append(f"reaper.InsertTrackAtIndex({int(event['track_index'])}, false)")
        elif action == "add_media_item":
            lines.append(f"-- add media item on track {int(event['track_index'])} at {event['position']}")
        elif action == "add_fx":
            lines.append(
                f"reaper.TrackFX_AddByName(reaper.GetTrack(0, {int(event['track_index'])}), {json.dumps(event['fx_name'])}, false, -1)"
            )
        elif action == "set_fx_param":
            lines.append(
                f"reaper.TrackFX_SetParam(reaper.GetTrack(0, {int(event['track_index'])}), {int(event['fx_index'])}, {int(event['param_index'])}, {float(event['value'])})"
            )
        elif action == "insert_envelope_point":
            lines.append(f"-- insert envelope point {event['envelope_name']} at {event['time']} value {event['value']}")
    lines.extend(["", "reaper.Undo_EndBlock('Marouba replay', -1)"])
    return "\n".join(lines) + "\n"


def hash_project_snapshot(snapshot: dict[str, Any]) -> str:
    canonical = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def captured_workflow(name: str, events: list[dict[str, Any]]) -> dict[str, Any]:
    workflow_id = slugify(name)
    return {
        "id": workflow_id,
        "name": name,
        "app": "REAPER",
        "description": "REAPER arrange and mix workflow captured from ReaScript action, item, FX parameter, and envelope evidence.",
        "params": [],
        "tags": ["reaper", "adapter", "r1", "reascript", "daw"],
        "author": "nxeratech",
        "created": "2026-06-14",
        "routes": [{"type": "adapter", "adapter": "reaper", "events": events}],
        "fallback_order": ["adapter", "ask"],
        "verification": {"type": "project_hash"},
        "calls": [],
        "depends_on": [],
        "signals": {"captured_events": events},
        "body": f"# {name}\n\nCaptured from REAPER ReaScript project evidence.\n",
    }


def slugify(value: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in value.casefold()).strip("-") or "reaper-workflow"
