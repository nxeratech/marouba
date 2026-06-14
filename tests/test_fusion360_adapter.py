from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine.executor import Executor
from engine.fusion360_adapter import Fusion360Adapter, capture_events_from_design_timeline, captured_workflow, hash_design_snapshot
from engine.vault import Vault


ROOT = Path(__file__).resolve().parents[1]


class FakeFusionRuntime:
    def __init__(self) -> None:
        self.timeline: list[dict] = []
        self.features: list[dict] = []

    def create_sketch(self, event: dict) -> None:
        self._append(event, {"type": "sketch", "plane": event["plane"], "parameters": event["parameters"]})

    def add_profile(self, event: dict) -> None:
        self._append(event, {"type": "profile", "sketch_id": event["sketch_id"], "profile_type": event["profile_type"], "parameters": event["parameters"]})

    def extrude(self, event: dict) -> None:
        self._append(event, {"type": "extrude", "profile_id": event["profile_id"], "operation": event["operation"], "parameters": event["parameters"]})

    def fillet(self, event: dict) -> None:
        self._append(event, {"type": "fillet", "edge_refs": event["edge_refs"], "parameters": event["parameters"]})

    def set_parameter(self, event: dict) -> None:
        self._append(event, {"type": "parameter", "parameter_name": event["parameter_name"], "expression": event["expression"], "parameters": event["parameters"]})

    def _append(self, event: dict, feature: dict) -> None:
        entry = {"timeline_index": event["timeline_index"], "feature_id": event["feature_id"], **feature}
        self.timeline.append({"timeline_index": event["timeline_index"], "feature_id": event["feature_id"], "action": event["action"]})
        self.features.append(entry)

    def snapshot(self) -> dict:
        return {"timeline": self.timeline, "features": self.features}


def design_timeline() -> list[dict]:
    return [
        {"action": "create_sketch", "feature_id": "sketch_base", "plane": "XY", "parameters": {"plane": "XY"}},
        {
            "action": "add_profile",
            "feature_id": "profile_rect",
            "sketch_id": "sketch_base",
            "profile_type": "rectangle",
            "parameters": {"corner_a": [0, 0], "corner_b": [80, 40]},
        },
        {"action": "extrude", "feature_id": "extrude_body", "profile_id": "profile_rect", "operation": "new_body", "parameters": {"distance": 12}},
        {"action": "fillet", "feature_id": "fillet_edges", "edge_refs": ["top_edges"], "parameters": {"radius": 2}},
    ]


def fusion_route() -> dict:
    return {"type": "adapter", "adapter": "fusion360", "events": capture_events_from_design_timeline(design_timeline())}


def test_fusion_capture_mirrors_feature_timeline_in_order() -> None:
    events = capture_events_from_design_timeline(design_timeline())

    assert [event["timeline_index"] for event in events] == [0, 1, 2, 3]
    assert [event["action"] for event in events] == ["create_sketch", "add_profile", "extrude", "fillet"]
    assert events[2]["parameters"]["distance"] == 12


def test_fusion_refuses_approximated_feature_history() -> None:
    timeline = design_timeline()
    timeline[2]["value_status"] = "approximate"

    with pytest.raises(RuntimeError, match="approximated"):
        capture_events_from_design_timeline(timeline)


def test_fusion_refuses_wrong_timeline_order() -> None:
    timeline = design_timeline()
    timeline[0]["timeline_index"] = 1
    timeline[1]["timeline_index"] = 0

    with pytest.raises(RuntimeError, match="timeline order wrong"):
        capture_events_from_design_timeline(timeline)


def test_fusion_replay_rebuilds_timeline_and_feature_hash() -> None:
    runtime = FakeFusionRuntime()
    result = Fusion360Adapter().execute(fusion_route(), {}, {}, fusion_runtime=runtime)

    expected = {
        "timeline": [
            {"timeline_index": 0, "feature_id": "sketch_base", "action": "create_sketch"},
            {"timeline_index": 1, "feature_id": "profile_rect", "action": "add_profile"},
            {"timeline_index": 2, "feature_id": "extrude_body", "action": "extrude"},
            {"timeline_index": 3, "feature_id": "fillet_edges", "action": "fillet"},
        ],
        "features": [
            {"timeline_index": 0, "feature_id": "sketch_base", "type": "sketch", "plane": "XY", "parameters": {"plane": "XY"}},
            {"timeline_index": 1, "feature_id": "profile_rect", "type": "profile", "sketch_id": "sketch_base", "profile_type": "rectangle", "parameters": {"corner_a": [0, 0], "corner_b": [80, 40]}},
            {"timeline_index": 2, "feature_id": "extrude_body", "type": "extrude", "profile_id": "profile_rect", "operation": "new_body", "parameters": {"distance": 12}},
            {"timeline_index": 3, "feature_id": "fillet_edges", "type": "fillet", "edge_refs": ["top_edges"], "parameters": {"radius": 2}},
        ],
    }
    assert result["success"] is True
    assert result["timeline_hash"] == hash_design_snapshot(expected)
    assert "timeline[2] extrude" in result["python_script"]


def test_executor_fusion_adapter_route_does_not_require_pixels(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "engine.executor.Fusion360Adapter",
        lambda: type(
            "InjectedFusionAdapter",
            (),
            {"execute": lambda _self, route, params, workflow: Fusion360Adapter().execute(route, params, workflow, FakeFusionRuntime())},
        )(),
    )

    result = Executor(tmp_path).execute(fusion_route(), {}, {"app": "Fusion 360"})

    assert result["success"] is True
    assert result["route_type"] == "adapter"
    assert "pixel" not in json.dumps(result).casefold()


def test_fusion_fake_20_run_soak_meets_threshold() -> None:
    successes = 0
    for _ in range(20):
        result = Fusion360Adapter().execute(fusion_route(), {}, {}, fusion_runtime=FakeFusionRuntime())
        successes += int(result["success"])

    assert successes / 20 >= 0.95


def test_captured_fusion_workflow_contains_adapter_route_and_events() -> None:
    events = capture_events_from_design_timeline(design_timeline())
    workflow = captured_workflow("Fusion Demo", events)

    assert workflow["routes"][0]["type"] == "adapter"
    assert workflow["routes"][0]["adapter"] == "fusion360"
    assert workflow["signals"]["captured_events"] == events


def test_three_fusion_demo_vaults_load_as_adapter_workflows() -> None:
    roots = sorted((ROOT / "demo-vaults").glob("fusion360-*"))

    assert len(roots) >= 3
    for root in roots:
        workflows = Vault(root).list_workflows()
        assert len(workflows) == 1
        assert workflows[0]["routes"][0]["adapter"] == "fusion360"
