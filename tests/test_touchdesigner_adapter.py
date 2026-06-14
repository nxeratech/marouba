from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine.executor import Executor
from engine.touchdesigner_adapter import (
    TouchDesignerAdapter,
    capture_events_from_touchdesigner_network,
    capture_events_from_touchdesigner_osc,
    captured_workflow,
    hash_network_snapshot,
)
from engine.vault import Vault


ROOT = Path(__file__).resolve().parents[1]


class FakeOscClient:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    def send(self, address: str, args: list | None = None) -> None:
        self.sent.append({"address": address, "args": args or []})


class FakePar:
    def __init__(self) -> None:
        self.val = None


class FakeParCollection:
    def __init__(self) -> None:
        self.values: dict[str, FakePar] = {}

    def __getitem__(self, key: str) -> FakePar:
        self.values.setdefault(key, FakePar())
        return self.values[key]


class FakeConnector:
    def __init__(self, node: "FakeNode", index: int) -> None:
        self.node = node
        self.index = index

    def connect(self, source: "FakeNode") -> None:
        self.node.inputs[self.index] = source.path


class FakeNode:
    def __init__(self, runtime: "FakeTouchDesignerRuntime", path: str, op_type: str, name: str) -> None:
        self.runtime = runtime
        self.path = path
        self.op_type = op_type
        self.name = name
        self.par = FakeParCollection()
        self.inputs: dict[int, str] = {}
        self.inputConnectors = [FakeConnector(self, index) for index in range(4)]
        self.nodeX = 0
        self.nodeY = 0

    def create(self, op_type: str, name: str):
        return self.runtime.create_child(self.path, op_type, name)

    def connect_input(self, index: int, source: "FakeNode") -> None:
        self.inputs[index] = source.path


class FakeTouchDesignerRuntime:
    def __init__(self) -> None:
        self.nodes: dict[str, FakeNode] = {}
        self.root = self.create_child("", "baseCOMP", "project1")

    def op(self, path: str):
        return self.nodes.get(path)

    def create_child(self, parent_path: str, op_type: str, name: str) -> FakeNode:
        path = f"{parent_path}/{name}" if parent_path else f"/{name}"
        node = FakeNode(self, path, op_type, name)
        self.nodes[path] = node
        return node

    def create_operator(self, event: dict):
        parent = self.op(event.get("parent", "/project1")) or self.root
        node = parent.create(event["op_type"], event["name"])
        for key, value in (event.get("node") or {}).items():
            setattr(node, key, value)
        return node

    def set_param(self, event: dict) -> None:
        self.nodes[event["path"]].par[event["param"]].val = event["value"]

    def connect(self, event: dict) -> None:
        self.nodes[event["target"]].connect_input(int(event.get("input_index", 0)), self.nodes[event["source"]])

    def snapshot(self) -> dict:
        operators = []
        connections = []
        for path, node in sorted(self.nodes.items()):
            if path == "/project1":
                continue
            operators.append(
                {
                    "path": path,
                    "parent": path.rsplit("/", 1)[0],
                    "name": node.name,
                    "op_type": node.op_type,
                    "node": {"nodeX": node.nodeX, "nodeY": node.nodeY},
                    "params": {key: par.val for key, par in sorted(node.par.values.items())},
                }
            )
            for index, source in sorted(node.inputs.items()):
                connections.append({"source": source, "target": path, "input_index": index})
        return {"operators": operators, "connections": connections}


def touchdesigner_route() -> dict:
    return {
        "type": "adapter",
        "adapter": "touchdesigner",
        "events": [
            {
                "route_tier": "r1",
                "app": "TouchDesigner",
                "kind": "network",
                "action": "create_operator",
                "parent": "/project1",
                "op_type": "noiseTOP",
                "name": "marouba_noise",
                "node": {"nodeX": 0, "nodeY": 0},
            },
            {
                "route_tier": "r1",
                "app": "TouchDesigner",
                "kind": "parameter",
                "action": "set_param",
                "path": "/project1/marouba_noise",
                "param": "period",
                "value": "{period}",
                "value_status": "exact",
            },
            {
                "route_tier": "r1",
                "app": "TouchDesigner",
                "kind": "network",
                "action": "create_operator",
                "parent": "/project1",
                "op_type": "levelTOP",
                "name": "marouba_level",
                "node": {"nodeX": 180, "nodeY": 0},
            },
            {
                "route_tier": "r1",
                "app": "TouchDesigner",
                "kind": "parameter",
                "action": "set_param",
                "path": "/project1/marouba_level",
                "param": "opacity",
                "value": 0.72,
                "value_status": "exact",
            },
            {
                "route_tier": "r1",
                "app": "TouchDesigner",
                "kind": "network",
                "action": "connect",
                "source": "/project1/marouba_noise",
                "target": "/project1/marouba_level",
                "input_index": 0,
            },
            {
                "route_tier": "r1",
                "app": "TouchDesigner",
                "kind": "osc",
                "action": "send_osc",
                "address": "/marouba/period",
                "args": ["{period}"],
            },
        ],
    }


def test_touchdesigner_capture_requires_full_topology_and_exact_params() -> None:
    events = capture_events_from_touchdesigner_network(
        {
            "operators": [
                {
                    "path": "/project1/noise1",
                    "parent": "/project1",
                    "op_type": "noiseTOP",
                    "name": "noise1",
                    "params": {"period": 3.5},
                },
                {
                    "path": "/project1/level1",
                    "parent": "/project1",
                    "op_type": "levelTOP",
                    "name": "level1",
                    "params": {"opacity": 0.72},
                },
            ],
            "connections": [{"source": "/project1/noise1", "target": "/project1/level1", "input_index": 0}],
        }
    )

    assert [event["action"] for event in events] == [
        "create_operator",
        "set_param",
        "create_operator",
        "set_param",
        "connect",
    ]
    assert {event["route_tier"] for event in events} == {"r1"}


def test_touchdesigner_refuses_approximate_parameter_values() -> None:
    with pytest.raises(RuntimeError, match="not exact"):
        capture_events_from_touchdesigner_network(
            {
                "operators": [
                    {
                        "path": "/project1/noise1",
                        "parent": "/project1",
                        "op_type": "noiseTOP",
                        "name": "noise1",
                        "params": {"period": "__APPROXIMATE__"},
                    }
                ],
            }
        )


def test_touchdesigner_refuses_missing_network_topology() -> None:
    with pytest.raises(RuntimeError, match="topology missing"):
        TouchDesignerAdapter(osc_client=FakeOscClient()).execute(
            {
                "type": "adapter",
                "adapter": "touchdesigner",
                "events": [
                    {
                        "route_tier": "r1",
                        "app": "TouchDesigner",
                        "kind": "parameter",
                        "action": "set_param",
                        "path": "/project1/noise1",
                        "param": "period",
                        "value": 3.5,
                        "value_status": "exact",
                    }
                ],
            },
            {},
            {},
            td_runtime=FakeTouchDesignerRuntime(),
        )


def test_touchdesigner_osc_capture_keeps_exact_address_and_args() -> None:
    events = capture_events_from_touchdesigner_osc([{"address": "/marouba/gain", "args": [0.5, "scene"]}])

    assert events == [
        {
            "route_tier": "r1",
            "app": "TouchDesigner",
            "kind": "osc",
            "action": "send_osc",
            "address": "/marouba/gain",
            "args": [0.5, "scene"],
        }
    ]


def test_touchdesigner_replay_rebuilds_identical_network_and_sends_osc() -> None:
    runtime = FakeTouchDesignerRuntime()
    osc = FakeOscClient()
    result = TouchDesignerAdapter(osc_client=osc).execute(
        touchdesigner_route(),
        {"period": 3.5},
        {},
        td_runtime=runtime,
    )

    expected = {
        "operators": [
            {
                "path": "/project1/marouba_level",
                "parent": "/project1",
                "name": "marouba_level",
                "op_type": "levelTOP",
                "node": {"nodeX": 180, "nodeY": 0},
                "params": {"opacity": 0.72},
            },
            {
                "path": "/project1/marouba_noise",
                "parent": "/project1",
                "name": "marouba_noise",
                "op_type": "noiseTOP",
                "node": {"nodeX": 0, "nodeY": 0},
                "params": {"period": "3.5"},
            },
        ],
        "connections": [{"source": "/project1/marouba_noise", "target": "/project1/marouba_level", "input_index": 0}],
    }
    assert result["success"] is True
    assert result["network_hash"] == hash_network_snapshot(expected)
    assert osc.sent == [{"address": "/marouba/period", "args": [3.5]}]


def test_executor_touchdesigner_adapter_route_does_not_require_pixels(monkeypatch, tmp_path: Path) -> None:
    runtime = FakeTouchDesignerRuntime()
    osc = FakeOscClient()
    monkeypatch.setattr(
        "engine.executor.TouchDesignerAdapter",
        lambda: type(
            "InjectedTouchDesignerAdapter",
            (),
            {
                "execute": lambda _self, route, params, workflow: TouchDesignerAdapter(osc_client=osc).execute(
                    route, params, workflow, runtime
                )
            },
        )(),
    )

    result = Executor(tmp_path).execute(touchdesigner_route(), {"period": 3.5}, {"app": "TouchDesigner"})

    assert result["success"] is True
    assert result["route_type"] == "adapter"
    assert "pixel" not in json.dumps(result).casefold()
    assert "gesture" not in json.dumps(result).casefold()


def test_touchdesigner_fake_20_run_soak_meets_threshold() -> None:
    successes = 0
    for index in range(20):
        result = TouchDesignerAdapter(osc_client=FakeOscClient()).execute(
            touchdesigner_route(),
            {"period": 1.0 + index},
            {},
            td_runtime=FakeTouchDesignerRuntime(),
        )
        successes += int(result["success"])

    assert successes / 20 >= 0.95


def test_captured_touchdesigner_workflow_contains_adapter_route_and_events() -> None:
    events = capture_events_from_touchdesigner_network(
        {
            "operators": [
                {
                    "path": "/project1/noise1",
                    "parent": "/project1",
                    "op_type": "noiseTOP",
                    "name": "noise1",
                    "params": {"period": 3.5},
                }
            ]
        }
    )
    workflow = captured_workflow("TouchDesigner Demo", events)

    assert workflow["routes"][0]["type"] == "adapter"
    assert workflow["routes"][0]["adapter"] == "touchdesigner"
    assert workflow["signals"]["captured_events"] == events
    assert "visual" not in workflow["fallback_order"]


def test_three_touchdesigner_demo_vaults_load_as_adapter_workflows() -> None:
    roots = sorted((ROOT / "demo-vaults").glob("touchdesigner-*"))

    assert len(roots) >= 3
    for root in roots:
        workflows = Vault(root).list_workflows()
        assert len(workflows) == 1
        route = workflows[0]["routes"][0]
        assert route["type"] == "adapter"
        assert route["adapter"] == "touchdesigner"
        assert "visual" not in workflows[0]["fallback_order"]
