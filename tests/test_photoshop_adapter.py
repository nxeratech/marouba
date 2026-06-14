from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine.executor import Executor
from engine.photoshop_adapter import (
    PhotoshopAdapter,
    capture_events_from_action_notifications,
    captured_workflow,
    hash_document_snapshot,
)
from engine.vault import Vault


ROOT = Path(__file__).resolve().parents[1]


class FakePhotoshopRuntime:
    def __init__(self) -> None:
        self.tool: str | None = None
        self.layers: list[dict] = []
        self.filters: list[dict] = []
        self.adjustments: list[dict] = []
        self.gesture_strokes: list[dict] = []
        self.descriptors: list[dict] = []

    def set_tool(self, event: dict) -> None:
        self.tool = event["tool_name"]
        self.descriptors.append(event.get("descriptor", {"_obj": "select"}))

    def layer_op(self, event: dict) -> None:
        if event["operation"] == "make":
            self.layers.append({"layer_id": event.get("layer_id"), "name": event.get("layer_name"), "opacity": event.get("opacity", 100)})
        elif event["operation"] == "rename":
            self.layers[-1]["name"] = event["layer_name"]
        self.descriptors.append(event["descriptor"])

    def apply_filter(self, event: dict) -> None:
        self.filters.append({"filter_name": event["filter_name"], "params": event["params"], "value_status": "exact"})
        self.descriptors.append(event["descriptor"])

    def adjustment(self, event: dict) -> None:
        self.adjustments.append({"adjustment_name": event["adjustment_name"], "params": event["params"], "value_status": "exact"})
        self.descriptors.append(event["descriptor"])

    def batch_play(self, event: dict) -> None:
        self.descriptors.append(event["descriptor"])

    def record_gesture_stroke(self, event: dict) -> None:
        self.gesture_strokes.append({"points": event["points"], "timing_ms": event["timing_ms"]})

    def snapshot(self) -> dict:
        return {
            "tool": self.tool,
            "layers": self.layers,
            "filters": self.filters,
            "adjustments": self.adjustments,
            "gesture_strokes": self.gesture_strokes,
        }


def layered_edit_log() -> list[dict]:
    return [
        {
            "kind": "tool",
            "tool_name": "moveTool",
            "descriptor": {"_obj": "select", "_target": [{"_ref": "moveTool"}]},
        },
        {
            "kind": "layer",
            "operation": "make",
            "layer_id": 7,
            "layer_name": "Glow Pass",
            "descriptor": {"_obj": "make", "_target": [{"_ref": "layer"}], "layerID": 7},
        },
        {
            "kind": "filter",
            "filter_name": "gaussianBlur",
            "params": {"radius": 4.5},
            "descriptor": {"_obj": "gaussianBlur", "radius": {"_unit": "pixelsUnit", "_value": 4.5}},
        },
        {
            "kind": "adjustment",
            "adjustment_name": "brightnessContrast",
            "params": {"brightness": 12, "contrast": 18},
            "descriptor": {"_obj": "brightnessEvent", "brightness": 12, "center": 18},
        },
        {
            "kind": "brush_stroke",
            "points": [{"x": 10, "y": 20}, {"x": 30, "y": 45}],
            "timing_ms": [0, 92],
        },
    ]


def photoshop_route() -> dict:
    return {"type": "adapter", "adapter": "photoshop", "events": capture_events_from_action_notifications(layered_edit_log())}


def test_photoshop_capture_marks_semantic_events_r1_and_brush_strokes_r3() -> None:
    events = capture_events_from_action_notifications(layered_edit_log())

    assert [event["action"] for event in events] == ["set_tool", "layer_op", "apply_filter", "adjustment", "brush_stroke"]
    assert [event["route_tier"] for event in events] == ["r1", "r1", "r1", "r1", "r3"]
    assert events[2]["params"]["radius"] == 4.5
    assert events[4]["taste_signal"] == "timing"


def test_photoshop_refuses_filter_dialog_values_that_are_not_numeric() -> None:
    log = layered_edit_log()
    log[2]["params"] = {"radius": "medium"}

    with pytest.raises(RuntimeError, match="param is not numeric"):
        capture_events_from_action_notifications(log)


def test_photoshop_refuses_approximate_filter_values() -> None:
    log = layered_edit_log()
    log[2]["value_status"] = "approximate"

    with pytest.raises(RuntimeError, match="exact numeric"):
        capture_events_from_action_notifications(log)


def test_photoshop_replay_reproduces_layer_stack_and_filter_values() -> None:
    runtime = FakePhotoshopRuntime()
    result = PhotoshopAdapter().execute(photoshop_route(), {}, {}, photoshop_runtime=runtime)

    expected = {
        "tool": "moveTool",
        "layers": [{"layer_id": 7, "name": "Glow Pass", "opacity": 100}],
        "filters": [{"filter_name": "gaussianBlur", "params": {"radius": 4.5}, "value_status": "exact"}],
        "adjustments": [{"adjustment_name": "brightnessContrast", "params": {"brightness": 12, "contrast": 18}, "value_status": "exact"}],
        "gesture_strokes": [{"points": [{"x": 10, "y": 20}, {"x": 30, "y": 45}], "timing_ms": [0, 92]}],
    }
    assert result["success"] is True
    assert result["gesture_strokes"] == 1
    assert result["document_hash"] == hash_document_snapshot(expected)
    assert "batchPlay" in result["script"]


def test_executor_photoshop_adapter_route_uses_semantic_adapter(monkeypatch, tmp_path: Path) -> None:
    runtime = FakePhotoshopRuntime()
    monkeypatch.setattr(
        "engine.executor.PhotoshopAdapter",
        lambda: type(
            "InjectedPhotoshopAdapter",
            (),
            {"execute": lambda _self, route, params, workflow: PhotoshopAdapter().execute(route, params, workflow, runtime)},
        )(),
    )

    result = Executor(tmp_path).execute(photoshop_route(), {}, {"app": "Photoshop"})

    assert result["success"] is True
    assert result["route_type"] == "adapter"
    assert "gaussianBlur" in json.dumps(result)


def test_photoshop_fake_20_run_soak_meets_threshold() -> None:
    successes = 0
    for _ in range(20):
        result = PhotoshopAdapter().execute(photoshop_route(), {}, {}, photoshop_runtime=FakePhotoshopRuntime())
        successes += int(result["success"])

    assert successes / 20 >= 0.95


def test_captured_photoshop_workflow_contains_adapter_route_and_gesture_fallback() -> None:
    events = capture_events_from_action_notifications(layered_edit_log())
    workflow = captured_workflow("Photoshop Layered Edit", events)

    assert workflow["routes"][0]["type"] == "adapter"
    assert workflow["routes"][0]["adapter"] == "photoshop"
    assert workflow["signals"]["captured_events"] == events
    assert "gesture" in workflow["fallback_order"]


def test_three_photoshop_demo_vaults_load_as_adapter_workflows() -> None:
    roots = sorted((ROOT / "demo-vaults").glob("photoshop-*"))

    assert len(roots) >= 3
    for root in roots:
        workflows = Vault(root).list_workflows()
        assert len(workflows) == 1
        route = workflows[0]["routes"][0]
        assert route["type"] == "adapter"
        assert route["adapter"] == "photoshop"
        assert "gesture" in workflows[0]["fallback_order"]
