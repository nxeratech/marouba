from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

from engine.osc_transport import OscUdpClient, OscValue


class ResolumeAdapter:
    id = "resolume"
    mechanism = "shared-osc-udp"

    def __init__(self, client: OscUdpClient | None = None, host: str = "127.0.0.1", send_port: int = 7000) -> None:
        self.client = client or OscUdpClient(host=host, send_port=send_port)

    def execute(self, route: dict[str, Any], params: dict[str, Any], workflow: dict[str, Any]) -> dict[str, Any]:
        events = replayable_events(route)
        if not events:
            raise RuntimeError("Resolume adapter route requires r1 OSC events")

        sent: list[dict[str, Any]] = []
        for event in events:
            rendered = substitute_slots(event, params)
            address = str(rendered["address"])
            args = normalize_args(rendered.get("args", []))
            self.client.send(address, args)
            sent.append({"address": address, "args": args, "semantic": rendered.get("semantic")})

        return {
            "success": True,
            "route_type": "adapter",
            "adapter": self.id,
            "route_used": "r1:shared-osc-udp",
            "events_replayed": len(events),
            "osc_hash": hash_osc_events(sent),
            "sent": sent,
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
        raise RuntimeError(f"Unsupported Resolume OSC event: {value!r}")
    event = dict(value)
    if not str(event.get("address") or "").startswith("/"):
        raise RuntimeError(f"Resolume OSC event requires absolute address: {event}")
    if "args" not in event:
        raise RuntimeError(f"Resolume OSC event requires exact args: {event}")
    if event.get("value_status") == "unreadable":
        raise RuntimeError(f"Resolume OSC value unreadable for exposed parameter: {event}")
    return event


def normalize_args(args: Any) -> list[OscValue]:
    if not isinstance(args, list):
        raise RuntimeError(f"Resolume OSC args must be a list: {args!r}")
    output: list[OscValue] = []
    for value in args:
        if isinstance(value, str):
            output.append(coerce_osc_string(value))
            continue
        if isinstance(value, (str, int, float, bool)):
            output.append(value)
            continue
        raise RuntimeError(f"Unsupported Resolume OSC arg: {value!r}")
    return output


def coerce_osc_string(value: str) -> OscValue:
    try:
        if value.strip().isdigit() or (value.startswith("-") and value[1:].isdigit()):
            return int(value)
        return float(value)
    except ValueError:
        return value


def substitute_slots(value: Any, params: dict[str, Any]) -> Any:
    if isinstance(value, str):
        return value.format(**params)
    if isinstance(value, list):
        return [substitute_slots(item, params) for item in value]
    if isinstance(value, dict):
        return {key: substitute_slots(item, params) for key, item in value.items()}
    return value


def capture_events_from_resolume_osc(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for message in messages:
        event = {
            "route_tier": "r1",
            "app": "Resolume",
            "kind": "osc",
            "semantic": message.get("semantic") or classify_resolume_address(str(message.get("address", ""))),
            "address": message.get("address"),
            "args": deepcopy(message.get("args")),
        }
        events.append(normalize_event(event))
    return events


def classify_resolume_address(address: str) -> str:
    lowered = address.casefold()
    if "/clip" in lowered or "/connect" in lowered:
        return "clip_trigger"
    if "/effect" in lowered or "/video/effects" in lowered or "/audio/effects" in lowered:
        return "effect_param"
    if "/layer" in lowered:
        return "layer_param"
    if "/composition" in lowered:
        return "composition_param"
    return "osc_param"


def hash_osc_events(events: list[dict[str, Any]]) -> str:
    canonical = json.dumps(events, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def captured_workflow(name: str, events: list[dict[str, Any]]) -> dict[str, Any]:
    workflow_id = slugify(name)
    return {
        "id": workflow_id,
        "name": name,
        "app": "Resolume",
        "description": "Resolume VJ workflow captured from exact native OSC messages.",
        "params": [],
        "tags": ["resolume", "adapter", "r1", "osc"],
        "author": "nxeratech",
        "created": "2026-06-14",
        "routes": [{"type": "adapter", "adapter": "resolume", "events": events}],
        "fallback_order": ["adapter", "ask"],
        "verification": {"type": "osc_hash"},
        "calls": [],
        "depends_on": [],
        "signals": {"captured_events": events},
        "body": f"# {name}\n\nCaptured from Resolume native OSC messages.\n",
    }


def slugify(value: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in value.casefold()).strip("-") or "resolume-workflow"
