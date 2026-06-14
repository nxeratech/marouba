from __future__ import annotations

import builtins
import hashlib
import json
from copy import deepcopy
from typing import Any

from engine.osc_transport import OscUdpClient, OscValue


class TouchDesignerAdapter:
    id = "touchdesigner"
    mechanism = "python-api + shared-osc-udp"

    def __init__(self, osc_client: OscUdpClient | None = None, osc_host: str = "127.0.0.1", osc_port: int = 7000) -> None:
        self.osc_client = osc_client or OscUdpClient(host=osc_host, send_port=osc_port)

    def execute(
        self,
        route: dict[str, Any],
        params: dict[str, Any],
        workflow: dict[str, Any],
        td_runtime: Any | None = None,
    ) -> dict[str, Any]:
        events = replayable_events(route)
        if not events:
            raise RuntimeError("TouchDesigner adapter route requires r1 network or OSC events")
        require_network_topology(events)

        runtime = td_runtime or TouchDesignerRuntime.from_builtins()
        sent_osc: list[dict[str, Any]] = []

        for event in events:
            rendered = substitute_slots(event, params)
            action = rendered.get("action")
            if action == "create_operator":
                runtime.create_operator(rendered)
            elif action == "set_param":
                runtime.set_param(rendered)
            elif action == "connect":
                runtime.connect(rendered)
            elif action == "send_osc":
                address = str(rendered["address"])
                args = normalize_osc_args(rendered.get("args", []))
                self.osc_client.send(address, args)
                sent_osc.append({"address": address, "args": args})
            else:
                raise RuntimeError(f"Unsupported TouchDesigner r1 action: {action}")

        snapshot = runtime.snapshot()
        return {
            "success": True,
            "route_type": "adapter",
            "adapter": self.id,
            "route_used": "r1:touchdesigner-python-osc",
            "events_replayed": len(events),
            "network_hash": hash_network_snapshot(snapshot),
            "network": snapshot,
            "sent_osc": sent_osc,
            "script": build_touchdesigner_script(events),
        }


class TouchDesignerRuntime:
    def __init__(self, root: Any, op_func: Any) -> None:
        self.root = root
        self.op = op_func

    @classmethod
    def from_builtins(cls) -> "TouchDesignerRuntime":
        if not hasattr(builtins, "op") or not hasattr(builtins, "root"):
            raise RuntimeError("TouchDesigner Python runtime not available")
        return cls(builtins.root, builtins.op)

    def create_operator(self, event: dict[str, Any]) -> Any:
        parent = self.op(event.get("parent", "/project1")) or self.root
        node = parent.create(event["op_type"], event.get("name"))
        for key, value in (event.get("node") or {}).items():
            setattr(node, key, value)
        return node

    def set_param(self, event: dict[str, Any]) -> None:
        node = self.require_op(event["path"])
        par = node.par[event["param"]]
        par.val = event["value"]

    def connect(self, event: dict[str, Any]) -> None:
        source = self.require_op(event["source"])
        target = self.require_op(event["target"])
        input_index = int(event.get("input_index", 0))
        if hasattr(target, "inputConnectors"):
            target.inputConnectors[input_index].connect(source)
            return
        target.connect_input(input_index, source)

    def require_op(self, path: str) -> Any:
        node = self.op(path)
        if node is None:
            raise RuntimeError(f"TouchDesigner operator not found: {path}")
        return node

    def snapshot(self) -> dict[str, Any]:
        if hasattr(self.root, "marouba_snapshot"):
            return self.root.marouba_snapshot()
        return {"root": getattr(self.root, "path", "/")}


def replayable_events(route: dict[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for raw_event in route.get("events") or []:
        event = normalize_event(raw_event)
        if event.get("route_tier", "r1") == "r1":
            events.append(event)
    return events


def normalize_event(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError(f"Unsupported TouchDesigner event: {value!r}")
    event = dict(value)
    action = event.get("action")
    if action == "create_operator":
        if not event.get("op_type") or not event.get("name"):
            raise RuntimeError(f"TouchDesigner create_operator requires op_type and name: {event}")
    elif action == "set_param":
        if event.get("value_status") in {"approximate", "unreadable"}:
            raise RuntimeError(f"TouchDesigner parameter value is not exact: {event}")
        for key in ("path", "param", "value"):
            if key not in event:
                raise RuntimeError(f"TouchDesigner set_param missing {key}: {event}")
    elif action == "connect":
        for key in ("source", "target"):
            if key not in event:
                raise RuntimeError(f"TouchDesigner connect missing {key}: {event}")
    elif action == "send_osc":
        if not str(event.get("address") or "").startswith("/"):
            raise RuntimeError(f"TouchDesigner OSC event requires absolute address: {event}")
        if "args" not in event:
            raise RuntimeError(f"TouchDesigner OSC event requires exact args: {event}")
    else:
        raise RuntimeError(f"Unsupported TouchDesigner r1 action: {action}")
    return event


def require_network_topology(events: list[dict[str, Any]]) -> None:
    if not any(event.get("action") == "create_operator" for event in events):
        raise RuntimeError("TouchDesigner network topology missing: no create_operator events")


def normalize_osc_args(args: Any) -> list[OscValue]:
    if not isinstance(args, list):
        raise RuntimeError(f"TouchDesigner OSC args must be a list: {args!r}")
    output: list[OscValue] = []
    for value in args:
        if isinstance(value, str):
            output.append(coerce_osc_string(value))
        elif isinstance(value, (int, float, bool)):
            output.append(value)
        else:
            raise RuntimeError(f"Unsupported TouchDesigner OSC arg: {value!r}")
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


def capture_events_from_touchdesigner_network(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for node in snapshot.get("operators", []):
        events.append(
            {
                "route_tier": "r1",
                "app": "TouchDesigner",
                "kind": "network",
                "action": "create_operator",
                "parent": node.get("parent", "/project1"),
                "op_type": node["op_type"],
                "name": node["name"],
                "node": deepcopy(node.get("node", {})),
            }
        )
        for param, value in sorted((node.get("params") or {}).items()):
            if value == "__APPROXIMATE__" or value is None:
                raise RuntimeError(f"TouchDesigner parameter value is not exact: {node['name']}.{param}")
            events.append(
                {
                    "route_tier": "r1",
                    "app": "TouchDesigner",
                    "kind": "parameter",
                    "action": "set_param",
                    "path": node["path"],
                    "param": param,
                    "value": value,
                    "value_status": "exact",
                }
            )
    for connection in snapshot.get("connections", []):
        events.append(
            {
                "route_tier": "r1",
                "app": "TouchDesigner",
                "kind": "network",
                "action": "connect",
                "source": connection["source"],
                "target": connection["target"],
                "input_index": connection.get("input_index", 0),
            }
        )
    return events


def capture_events_from_touchdesigner_osc(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for message in messages:
        event = {
            "route_tier": "r1",
            "app": "TouchDesigner",
            "kind": "osc",
            "action": "send_osc",
            "address": message.get("address"),
            "args": deepcopy(message.get("args")),
        }
        events.append(normalize_event(event))
    return events


def build_touchdesigner_script(events: list[dict[str, Any]]) -> str:
    lines = ["# Run inside TouchDesigner Python", "root_comp = op('/project1') or root", ""]
    for event in events:
        action = event.get("action")
        if action == "create_operator":
            parent = event.get("parent", "/project1")
            lines.append(f"node = (op({parent!r}) or root_comp).create({event['op_type']!r}, {event['name']!r})")
        elif action == "set_param":
            lines.append(f"op({event['path']!r}).par[{event['param']!r}].val = {event['value']!r}")
        elif action == "connect":
            lines.append(
                f"op({event['target']!r}).inputConnectors[{int(event.get('input_index', 0))}].connect(op({event['source']!r}))"
            )
    return "\n".join(lines) + "\n"


def hash_network_snapshot(snapshot: dict[str, Any]) -> str:
    canonical = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def captured_workflow(name: str, events: list[dict[str, Any]]) -> dict[str, Any]:
    workflow_id = slugify(name)
    return {
        "id": workflow_id,
        "name": name,
        "app": "TouchDesigner",
        "description": "TouchDesigner network captured from Python topology and exact parameter evidence.",
        "params": [],
        "tags": ["touchdesigner", "adapter", "r1", "network", "python", "osc"],
        "author": "nxeratech",
        "created": "2026-06-14",
        "routes": [{"type": "adapter", "adapter": "touchdesigner", "events": events}],
        "fallback_order": ["adapter", "ask"],
        "verification": {"type": "network_hash"},
        "calls": [],
        "depends_on": [],
        "signals": {"captured_events": events},
        "body": f"# {name}\n\nCaptured from TouchDesigner Python topology and exact parameter events.\n",
    }


def slugify(value: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in value.casefold()).strip("-") or "touchdesigner-workflow"
