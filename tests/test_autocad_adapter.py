from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine.autocad_adapter import AutoCADAdapter, capture_events_from_command_stream, captured_workflow, hash_drawing_snapshot
from engine.executor import Executor
from engine.vault import Vault


ROOT = Path(__file__).resolve().parents[1]


class FakeAutoCADRuntime:
    def __init__(self) -> None:
        self.commands: list[dict] = []
        self.entities: list[dict] = []

    def run_command(self, event: dict) -> None:
        self.commands.append({"command": event["command"], "parameters": event["parameters"]})
        command = event["command"].casefold()
        params = event["parameters"]
        if command == "line":
            self.entities.append({"type": "LINE", "start": params[0], "end": params[1]})
        elif command == "circle":
            self.entities.append({"type": "CIRCLE", "center": params[0], "radius": params[1]})
        elif command == "rectang":
            self.entities.append({"type": "LWPOLYLINE", "corner_a": params[0], "corner_b": params[1]})
        elif command == "text":
            self.entities.append({"type": "TEXT", "point": params[0], "height": params[1], "rotation": params[2], "text": params[3]})

    def snapshot(self) -> dict:
        return {"commands": self.commands, "entities": self.entities}


def command_stream() -> list[dict]:
    return [
        {"command": "LINE", "parameters": [[0, 0, 0], [100, 0, 0], ""], "source": "dotnet-command-stream"},
        {"command": "CIRCLE", "parameters": [[50, 50, 0], 25], "source": "dotnet-command-stream"},
    ]


def autocad_route() -> dict:
    return {"type": "adapter", "adapter": "autocad", "events": capture_events_from_command_stream(command_stream())}


def test_autocad_capture_generates_command_level_r1_events_with_exact_params() -> None:
    events = capture_events_from_command_stream(command_stream())

    assert [event["command"] for event in events] == ["LINE", "CIRCLE"]
    assert {event["route_tier"] for event in events} == {"r1"}
    assert events[0]["parameters"][0] == [0, 0, 0]
    assert events[1]["parameters"][1] == 25


def test_autocad_refuses_commands_without_parameters() -> None:
    with pytest.raises(RuntimeError, match="without parameters"):
        capture_events_from_command_stream([{"command": "LINE", "parameters": []}])


def test_autocad_refuses_ui_or_pixel_captured_commands_as_r1() -> None:
    with pytest.raises(RuntimeError, match="command stream/API evidence"):
        capture_events_from_command_stream([{"command": "CIRCLE", "parameters": [[0, 0, 0], 4], "capture_source": "pixels"}])


def test_autocad_replay_produces_identical_entity_snapshot_hash() -> None:
    runtime = FakeAutoCADRuntime()
    result = AutoCADAdapter().execute(autocad_route(), {}, {}, autocad_runtime=runtime)

    expected = {
        "commands": [
            {"command": "LINE", "parameters": [[0, 0, 0], [100, 0, 0], ""]},
            {"command": "CIRCLE", "parameters": [[50, 50, 0], 25]},
        ],
        "entities": [
            {"type": "LINE", "start": [0, 0, 0], "end": [100, 0, 0]},
            {"type": "CIRCLE", "center": [50, 50, 0], "radius": 25},
        ],
    }
    assert result["success"] is True
    assert result["dwg_hash"] == hash_drawing_snapshot(expected)
    assert "(command \"_.LINE\"" in result["autolisp"]


def test_executor_autocad_adapter_route_does_not_require_pixels(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "engine.executor.AutoCADAdapter",
        lambda: type(
            "InjectedAutoCADAdapter",
            (),
            {"execute": lambda _self, route, params, workflow: AutoCADAdapter().execute(route, params, workflow, FakeAutoCADRuntime())},
        )(),
    )

    result = Executor(tmp_path).execute(autocad_route(), {}, {"app": "AutoCAD"})

    assert result["success"] is True
    assert result["route_type"] == "adapter"
    assert "pixel" not in json.dumps(result).casefold()


def test_autocad_fake_20_run_soak_meets_threshold() -> None:
    successes = 0
    for _ in range(20):
        result = AutoCADAdapter().execute(autocad_route(), {}, {}, autocad_runtime=FakeAutoCADRuntime())
        successes += int(result["success"])

    assert successes / 20 >= 0.95


def test_captured_autocad_workflow_contains_adapter_route_and_events() -> None:
    events = capture_events_from_command_stream(command_stream())
    workflow = captured_workflow("AutoCAD Demo", events)

    assert workflow["routes"][0]["type"] == "adapter"
    assert workflow["routes"][0]["adapter"] == "autocad"
    assert workflow["signals"]["captured_events"] == events


def test_three_autocad_demo_vaults_load_as_adapter_workflows() -> None:
    roots = sorted((ROOT / "demo-vaults").glob("autocad-*"))

    assert len(roots) >= 3
    for root in roots:
        workflows = Vault(root).list_workflows()
        assert len(workflows) == 1
        assert workflows[0]["routes"][0]["adapter"] == "autocad"
