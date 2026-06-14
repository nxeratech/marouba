from __future__ import annotations

import json
import time
import urllib.request
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


class ComfyUIHttpClient(Protocol):
    def post_prompt(self, payload: dict[str, Any]) -> dict[str, Any]:
        ...

    def get_history(self, prompt_id: str) -> dict[str, Any]:
        ...


@dataclass
class UrllibComfyUIClient:
    api_base: str = "http://127.0.0.1:8188"

    def post_prompt(self, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self.api_base.rstrip("/") + "/prompt",
            data=body,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8") or "{}")

    def get_history(self, prompt_id: str) -> dict[str, Any]:
        with urllib.request.urlopen(self.api_base.rstrip("/") + f"/history/{prompt_id}", timeout=10) as response:
            return json.loads(response.read().decode("utf-8") or "{}")


class ComfyUIAdapter:
    id = "comfyui"
    mechanism = "http-api + websocket"

    def __init__(self, client: ComfyUIHttpClient | None = None, api_base: str = "http://127.0.0.1:8188") -> None:
        self.client = client or UrllibComfyUIClient(api_base)

    def execute(self, route: dict[str, Any], params: dict[str, Any], workflow: dict[str, Any]) -> dict[str, Any]:
        graph = route.get("graph") or route.get("workflow_graph")
        if graph is None and route.get("graph_template"):
            graph = json.loads(Path(str(route["graph_template"])).read_text(encoding="utf-8"))
        if graph is None:
            raise RuntimeError("ComfyUI adapter route requires graph, workflow_graph, or graph_template")

        rendered_graph = substitute_slots(graph, params)
        payload = {"prompt": rendered_graph}
        if route.get("client_id"):
            payload["client_id"] = substitute_slots(route["client_id"], params)

        response = self.client.post_prompt(payload)
        prompt_id = response.get("prompt_id")
        if not prompt_id:
            raise RuntimeError(f"ComfyUI /prompt did not return prompt_id: {response}")

        if route.get("wait_for_history", True):
            wait_for_history(self.client, str(prompt_id), float(workflow.get("verification", {}).get("timeout_seconds", 120)))

        return {
            "success": True,
            "route_type": "adapter",
            "adapter": self.id,
            "route_used": "r1:comfyui-http-api",
            "prompt_id": prompt_id,
            "graph": rendered_graph,
        }


def substitute_slots(value: Any, params: dict[str, Any]) -> Any:
    if isinstance(value, str):
        return value.format(**params)
    if isinstance(value, list):
        return [substitute_slots(item, params) for item in value]
    if isinstance(value, dict):
        return {key: substitute_slots(item, params) for key, item in value.items()}
    return value


def wait_for_history(client: ComfyUIHttpClient, prompt_id: str, timeout_seconds: float) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        history = client.get_history(prompt_id)
        if prompt_id in history:
            return history[prompt_id]
        time.sleep(0.1)
    raise TimeoutError(f"Timed out waiting for ComfyUI prompt {prompt_id}")


def normalize_prompt_graph(value: dict[str, Any]) -> dict[str, Any]:
    graph = value.get("prompt", value)
    return deepcopy(graph)


def capture_events_from_graphs(
    before: dict[str, Any],
    after: dict[str, Any],
    websocket_events: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    before_graph = normalize_prompt_graph(before)
    after_graph = normalize_prompt_graph(after)
    events: list[dict[str, Any]] = []

    for node_id in sorted(set(after_graph) - set(before_graph), key=str):
        events.append(node_event("node_added", node_id, after_graph[node_id]))
    for node_id in sorted(set(before_graph) - set(after_graph), key=str):
        events.append(node_event("node_removed", node_id, before_graph[node_id]))
    for node_id in sorted(set(before_graph) & set(after_graph), key=str):
        events.extend(diff_node(node_id, before_graph[node_id], after_graph[node_id]))

    events.extend(queue_events_from_websocket(websocket_events or []))
    return events


def node_event(kind: str, node_id: str, node: dict[str, Any]) -> dict[str, Any]:
    return {
        "route_tier": "r1",
        "app": "ComfyUI",
        "kind": kind,
        "node_id": str(node_id),
        "class_type": node.get("class_type"),
        "value": node,
    }


def diff_node(node_id: str, before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    if before.get("class_type") != after.get("class_type"):
        events.append(
            {
                "route_tier": "r1",
                "app": "ComfyUI",
                "kind": "node_class_changed",
                "node_id": str(node_id),
                "before": before.get("class_type"),
                "after": after.get("class_type"),
            }
        )
    before_inputs = before.get("inputs", {}) or {}
    after_inputs = after.get("inputs", {}) or {}
    for key in sorted(set(before_inputs) | set(after_inputs)):
        if before_inputs.get(key) != after_inputs.get(key):
            events.append(
                {
                    "route_tier": "r1",
                    "app": "ComfyUI",
                    "kind": "param_changed",
                    "node_id": str(node_id),
                    "class_type": after.get("class_type") or before.get("class_type"),
                    "param": key,
                    "before": before_inputs.get(key),
                    "after": after_inputs.get(key),
                }
            )
    return events


def queue_events_from_websocket(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    seen_prompt_ids: set[str] = set()
    for event in events:
        event_type = str(event.get("type") or event.get("event") or "")
        data = event.get("data") if isinstance(event.get("data"), dict) else event
        prompt_id = str(data.get("prompt_id") or data.get("id") or "")
        if event_type not in {"execution_start", "executing", "execution_success", "execution_error", "status", "queued"}:
            continue
        kind = "queue_event"
        taste_signal = False
        if event_type in {"execution_start", "queued"}:
            kind = "queue_start"
        if event_type in {"execution_success", "execution_error"}:
            kind = "queue_complete"
        if prompt_id and prompt_id in seen_prompt_ids and event_type in {"execution_start", "queued"}:
            kind = "queue_requeue"
            taste_signal = True
        if prompt_id:
            seen_prompt_ids.add(prompt_id)
        output.append(
            {
                "route_tier": "r1",
                "app": "ComfyUI",
                "kind": kind,
                "prompt_id": prompt_id or None,
                "taste_signal": taste_signal,
                "raw_type": event_type,
            }
        )
    return output


def captured_workflow(name: str, graph: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
    workflow_id = slugify(name)
    return {
        "id": workflow_id,
        "name": name,
        "app": "ComfyUI",
        "description": "ComfyUI graph captured from node-level API evidence.",
        "params": [],
        "tags": ["comfyui", "adapter", "r1", "node-graph"],
        "author": "nxeratech",
        "created": "2026-06-14",
        "routes": [
            {
                "type": "adapter",
                "adapter": "comfyui",
                "graph": normalize_prompt_graph(graph),
                "wait_for_history": True,
            }
        ],
        "fallback_order": ["adapter", "api", "ask"],
        "verification": {"type": "none"},
        "calls": [],
        "depends_on": [],
        "signals": {"captured_events": events},
        "body": f"# {name}\n\nCaptured from ComfyUI workflow graph JSON and websocket queue events.\n",
    }


def slugify(value: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in value.casefold()).strip("-") or "comfyui-workflow"
