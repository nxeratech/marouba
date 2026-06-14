from __future__ import annotations

import base64
import hashlib
import json
import uuid
from copy import deepcopy
from typing import Any, Protocol


class ObsClient(Protocol):
    def call(self, request_type: str, request_data: dict[str, Any] | None = None) -> dict[str, Any]:
        ...


class ObsWebSocketClient:
    def __init__(self, url: str = "ws://127.0.0.1:4455", password: str | None = None) -> None:
        self.url = url
        self.password = password

    def call(self, request_type: str, request_data: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            import websocket
        except ImportError as exc:
            raise RuntimeError("websocket-client is required for live obs-websocket replay") from exc

        ws = websocket.create_connection(self.url, subprotocols=["obswebsocket.json"], timeout=10)
        try:
            hello = json.loads(ws.recv())
            identify = {"rpcVersion": int(hello["d"].get("rpcVersion", 1))}
            auth = hello["d"].get("authentication")
            if auth:
                if self.password is None:
                    raise RuntimeError("obs-websocket requires a password but none was configured")
                identify["authentication"] = obs_auth(self.password, auth["salt"], auth["challenge"])
            ws.send(json.dumps({"op": 1, "d": identify}))
            identified = json.loads(ws.recv())
            if identified.get("op") != 2:
                raise RuntimeError(f"obs-websocket identify failed: {identified}")

            request_id = str(uuid.uuid4())
            ws.send(
                json.dumps(
                    {
                        "op": 6,
                        "d": {
                            "requestType": request_type,
                            "requestId": request_id,
                            "requestData": request_data or {},
                        },
                    }
                )
            )
            response = json.loads(ws.recv())
        finally:
            ws.close()

        payload = response.get("d", {})
        status = payload.get("requestStatus") or {}
        if not status.get("result", False):
            raise RuntimeError(status.get("comment") or f"obs-websocket request failed: {request_type}")
        return payload.get("responseData") or {}


class ObsAdapter:
    id = "obs-studio"
    mechanism = "obs-websocket"

    def __init__(self, client: ObsClient | None = None, url: str = "ws://127.0.0.1:4455", password: str | None = None) -> None:
        self.client = client or ObsWebSocketClient(url, password)

    def execute(self, route: dict[str, Any], params: dict[str, Any], workflow: dict[str, Any]) -> dict[str, Any]:
        events = replayable_events(route)
        if not events:
            raise RuntimeError("OBS adapter route requires r1 obs-websocket events")

        calls: list[dict[str, Any]] = []
        for event in events:
            rendered = substitute_slots(event, params)
            request_type, request_data = obs_request_for_event(rendered)
            response = self.client.call(request_type, request_data)
            calls.append({"requestType": request_type, "requestData": request_data, "response": response})

        snapshot = snapshot_collection(self.client)
        return {
            "success": True,
            "route_type": "adapter",
            "adapter": self.id,
            "route_used": "r1:obs-websocket",
            "events_replayed": len(events),
            "collection_hash": hash_obs_snapshot(snapshot),
            "snapshot": snapshot,
            "calls": calls,
        }


def obs_auth(password: str, salt: str, challenge: str) -> str:
    secret = base64.b64encode(hashlib.sha256((password + salt).encode("utf-8")).digest()).decode("ascii")
    return base64.b64encode(hashlib.sha256((secret + challenge).encode("utf-8")).digest()).decode("ascii")


def replayable_events(route: dict[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for raw_event in route.get("events") or []:
        event = normalize_event(raw_event)
        if event.get("route_tier", "r1") != "r1":
            continue
        events.append(event)
    return events


def normalize_event(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError(f"Unsupported OBS event: {value!r}")
    event = dict(value)
    if event.get("kind") == "filter" and event.get("action") in {"create_filter", "set_filter_settings"}:
        settings = event.get("filterSettings", event.get("settings"))
        if settings is None:
            raise RuntimeError(f"OBS filter event missing exact filterSettings: {event}")
        if event.get("settings_status") == "unreadable":
            raise RuntimeError(f"OBS filter settings are marked unreadable despite obs-websocket exposure: {event}")
    return event


def obs_request_for_event(event: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    action = str(event.get("action"))
    if action == "create_scene":
        return "CreateScene", pick(event, "sceneName")
    if action == "set_current_program_scene":
        return "SetCurrentProgramScene", pick(event, "sceneName")
    if action == "create_input":
        return "CreateInput", pick(event, "sceneName", "inputName", "inputKind", "inputSettings", "sceneItemEnabled")
    if action == "set_input_settings":
        return "SetInputSettings", pick(event, "inputName", "inputSettings", "overlay")
    if action == "set_input_volume":
        return "SetInputVolume", pick(event, "inputName", "inputVolumeMul", "inputVolumeDb")
    if action == "set_input_mute":
        return "SetInputMute", pick(event, "inputName", "inputMuted")
    if action == "create_filter":
        return "CreateSourceFilter", {
            "sourceName": event["sourceName"],
            "filterName": event["filterName"],
            "filterKind": event["filterKind"],
            "filterSettings": event.get("filterSettings") or event.get("settings"),
        }
    if action == "set_filter_settings":
        return "SetSourceFilterSettings", {
            "sourceName": event["sourceName"],
            "filterName": event["filterName"],
            "filterSettings": event.get("filterSettings") or event.get("settings"),
            "overlay": event.get("overlay", True),
        }
    if action == "set_filter_enabled":
        return "SetSourceFilterEnabled", pick(event, "sourceName", "filterName", "filterEnabled")
    if action == "set_current_transition":
        return "SetCurrentSceneTransition", pick(event, "transitionName")
    if action == "set_transition_duration":
        return "SetCurrentSceneTransitionDuration", pick(event, "transitionDuration")
    if action == "set_transition_settings":
        return "SetCurrentSceneTransitionSettings", pick(event, "transitionSettings", "overlay")
    if action == "set_scene_item_transform":
        return "SetSceneItemTransform", pick(event, "sceneName", "sceneItemId", "sceneItemTransform")
    if action == "set_scene_item_enabled":
        return "SetSceneItemEnabled", pick(event, "sceneName", "sceneItemId", "sceneItemEnabled")
    raise RuntimeError(f"Unsupported OBS r1 action: {action}")


def pick(source: dict[str, Any], *keys: str) -> dict[str, Any]:
    return {key: source[key] for key in keys if key in source}


def substitute_slots(value: Any, params: dict[str, Any]) -> Any:
    if isinstance(value, str):
        return value.format(**params)
    if isinstance(value, list):
        return [substitute_slots(item, params) for item in value]
    if isinstance(value, dict):
        return {key: substitute_slots(item, params) for key, item in value.items()}
    return value


def snapshot_collection(client: ObsClient) -> dict[str, Any]:
    scenes = client.call("GetSceneList").get("scenes", [])
    inputs = client.call("GetInputList").get("inputs", [])
    transition = client.call("GetCurrentSceneTransition")
    result = {"scenes": scenes, "inputs": [], "transition": transition}
    for input_info in inputs:
        input_name = input_info.get("inputName")
        if not input_name:
            continue
        item = deepcopy(input_info)
        item["settings"] = client.call("GetInputSettings", {"inputName": input_name}).get("inputSettings", {})
        item["volume"] = client.call("GetInputVolume", {"inputName": input_name})
        item["mute"] = client.call("GetInputMute", {"inputName": input_name})
        filters = client.call("GetSourceFilterList", {"sourceName": input_name}).get("filters", [])
        for filter_info in filters:
            if filter_info.get("filterSettings") is None:
                raise RuntimeError(f"OBS filter settings unreadable for {input_name}: {filter_info.get('filterName')}")
        item["filters"] = filters
        result["inputs"].append(item)
    return result


def capture_events_from_obs_snapshot(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for scene in snapshot.get("scenes", []):
        events.append(
            {
                "route_tier": "r1",
                "app": "OBS Studio",
                "kind": "scene",
                "action": "create_scene",
                "sceneName": scene["sceneName"],
            }
        )
    for input_info in snapshot.get("inputs", []):
        input_name = input_info["inputName"]
        events.append(
            {
                "route_tier": "r1",
                "app": "OBS Studio",
                "kind": "source",
                "action": "create_input",
                "sceneName": input_info["sceneName"],
                "inputName": input_name,
                "inputKind": input_info["inputKind"],
                "inputSettings": input_info.get("settings", {}),
                "sceneItemEnabled": input_info.get("sceneItemEnabled", True),
            }
        )
        volume = input_info.get("volume") or {}
        if volume:
            events.append(
                {
                    "route_tier": "r1",
                    "app": "OBS Studio",
                    "kind": "audio",
                    "action": "set_input_volume",
                    "inputName": input_name,
                    **volume,
                }
            )
        mute = input_info.get("mute") or {}
        if "inputMuted" in mute:
            events.append(
                {
                    "route_tier": "r1",
                    "app": "OBS Studio",
                    "kind": "audio",
                    "action": "set_input_mute",
                    "inputName": input_name,
                    "inputMuted": mute["inputMuted"],
                }
            )
        for filter_info in input_info.get("filters", []):
            if filter_info.get("filterSettings") is None:
                raise RuntimeError(f"OBS filter param unreadable despite obs-websocket exposure: {filter_info}")
            events.append(
                {
                    "route_tier": "r1",
                    "app": "OBS Studio",
                    "kind": "filter",
                    "action": "create_filter",
                    "sourceName": input_name,
                    "filterName": filter_info["filterName"],
                    "filterKind": filter_info["filterKind"],
                    "filterSettings": filter_info["filterSettings"],
                    "filterEnabled": filter_info.get("filterEnabled", True),
                }
            )
    transition = snapshot.get("transition") or {}
    if transition.get("transitionName"):
        events.append(
            {
                "route_tier": "r1",
                "app": "OBS Studio",
                "kind": "transition",
                "action": "set_current_transition",
                "transitionName": transition["transitionName"],
            }
        )
    return events


def hash_obs_snapshot(snapshot: dict[str, Any]) -> str:
    canonical = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def captured_workflow(name: str, events: list[dict[str, Any]]) -> dict[str, Any]:
    workflow_id = slugify(name)
    return {
        "id": workflow_id,
        "name": name,
        "app": "OBS Studio",
        "description": "OBS collection captured from obs-websocket scenes, sources, filters, transitions, and audio settings.",
        "params": [],
        "tags": ["obs", "adapter", "r1", "obs-websocket"],
        "author": "nxeratech",
        "created": "2026-06-14",
        "routes": [{"type": "adapter", "adapter": "obs-studio", "events": events}],
        "fallback_order": ["adapter", "ask"],
        "verification": {"type": "collection_hash"},
        "calls": [],
        "depends_on": [],
        "signals": {"captured_events": events},
        "body": f"# {name}\n\nCaptured from obs-websocket collection evidence.\n",
    }


def slugify(value: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in value.casefold()).strip("-") or "obs-workflow"
