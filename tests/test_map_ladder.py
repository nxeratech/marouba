from __future__ import annotations

import json
from pathlib import Path

from engine.router import Router
from engine.vault import Vault
from scripts.replay import replay_workflow


class PlannedExecutor:
    def __init__(self, outcomes: dict[str, bool]) -> None:
        self.outcomes = outcomes
        self.routes: list[str] = []

    def execute(self, route: dict, params: dict, workflow: dict) -> dict:
        route_type = route["type"]
        self.routes.append(route_type)
        success = self.outcomes.get(route_type, False)
        return {
            "success": success,
            "route_type": route_type,
            "map_route": route.get("map_route"),
            "output": params.get("output_path") if success else None,
            "error": None if success else f"{route_type} failed deliberately",
            "duration_ms": 1,
        }


def map_workflow(routes: list[dict], fallback_order: list[str]) -> dict:
    return {
        "id": "map-ladder-test",
        "name": "MAP Ladder Test",
        "app": "TestApp",
        "description": "MAP ladder replay test.",
        "params": [],
        "tags": ["map", "test"],
        "author": "nxeratech",
        "created": "2026-06-10",
        "routes": routes,
        "fallback_order": fallback_order,
        "verification": {"type": "none"},
        "body": "# MAP Ladder Test\n",
    }


def save_and_replay(tmp_path: Path, workflow: dict, executor: PlannedExecutor) -> int:
    vault = Vault(tmp_path)
    vault.save_workflow(workflow)
    route_types = {route["type"] for route in workflow["routes"]}
    router = Router({route_type: (lambda _route: True) for route_type in route_types})
    return replay_workflow(
        workflow["id"],
        {"output_path": str(tmp_path / "out.txt")},
        root=tmp_path,
        no_repair=True,
        router=router,
        executor=executor,
    )


def latest_run_result(tmp_path: Path) -> dict:
    run_path = next((tmp_path / "vault" / "runs").glob("*-map-ladder-test.json"))
    return json.loads(run_path.read_text(encoding="utf-8"))["result"]


def test_map_r1_adapter_success_executes_first() -> None:
    workflow = map_workflow(
        [{"type": "adapter", "adapter": "stub"}, {"type": "uia", "element": "Run"}],
        ["adapter", "uia", "ask"],
    )
    router = Router({"adapter": lambda _route: True, "uia": lambda _route: True})

    order = router.route_order(workflow)

    assert [(route["type"], route["map_route"]) for route in order] == [
        ("adapter", "r1"),
        ("uia", "r2"),
        ("ask", "r4"),
    ]


def test_r1_to_r2_fallback_logs_repair_event(tmp_path: Path) -> None:
    workflow = map_workflow(
        [{"type": "adapter", "adapter": "stub"}, {"type": "uia", "element": "Run"}],
        ["adapter", "uia", "ask"],
    )
    executor = PlannedExecutor({"adapter": False, "uia": True})

    exit_code = save_and_replay(tmp_path, workflow, executor)
    result = latest_run_result(tmp_path)

    assert exit_code == 0
    assert executor.routes == ["adapter", "uia"]
    assert result["success"] is True
    assert result["repair_events"] == [
        {
            "repair_event": True,
            "event_type": "fallback",
            "from_route": "adapter",
            "from_map_route": "r1",
            "to_route": "uia",
            "to_map_route": "r2",
            "reason": "adapter failed deliberately",
        }
    ]


def test_r2_to_r3_fallback_logs_repair_event(tmp_path: Path) -> None:
    workflow = map_workflow(
        [{"type": "uia", "element": "Run"}, {"type": "gesture", "events": [{"kind": "mousedown"}]}],
        ["uia", "gesture", "ask"],
    )
    executor = PlannedExecutor({"uia": False, "gesture": True})

    exit_code = save_and_replay(tmp_path, workflow, executor)
    result = latest_run_result(tmp_path)

    assert exit_code == 0
    assert executor.routes == ["uia", "gesture"]
    assert result["repair_events"][0]["from_map_route"] == "r2"
    assert result["repair_events"][0]["to_map_route"] == "r3"


def test_three_consecutive_repairs_pause_replay(tmp_path: Path) -> None:
    workflow = map_workflow(
        [
            {"type": "adapter", "adapter": "stub"},
            {"type": "uia", "element": "Run"},
            {"type": "shortcut", "keys": ["ctrl", "s"]},
            {"type": "gesture", "events": [{"kind": "mousedown"}]},
        ],
        ["adapter", "uia", "shortcut", "gesture", "ask"],
    )
    executor = PlannedExecutor({"adapter": False, "uia": False, "shortcut": False, "gesture": True})

    exit_code = save_and_replay(tmp_path, workflow, executor)
    result = latest_run_result(tmp_path)

    assert exit_code == 1
    assert executor.routes == ["adapter", "uia", "shortcut"]
    assert result["paused"] is True
    assert len(result["repair_events"]) == 3


def test_r4_routes_are_unreachable_without_explicit_repair_mode() -> None:
    workflow = map_workflow(
        [{"type": "visual", "coordinates": {"x": 10, "y": 20}}],
        ["visual", "ask"],
    )
    router = Router({"visual": lambda _route: True})

    normal_order = router.route_order(workflow)
    repair_order = router.route_order(workflow, allow_repair_routes=True)

    assert [route["type"] for route in normal_order] == ["ask"]
    assert [(route["type"], route["map_route"]) for route in repair_order] == [("visual", "r4"), ("ask", "r4")]