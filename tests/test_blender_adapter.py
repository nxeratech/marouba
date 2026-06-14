from __future__ import annotations

import json
from pathlib import Path

from engine.blender_adapter import (
    BlenderAdapter,
    capture_events_from_blender_session,
    hash_scene_snapshot,
)
from engine.executor import Executor
from engine.vault import Vault


ROOT = Path(__file__).resolve().parents[1]


class FakeOperatorGroup:
    def __init__(self, fake: FakeBpy, group: str) -> None:
        self.fake = fake
        self.group = group

    def __getattr__(self, name: str):
        def call(**params):
            self.fake.call_operator(f"{self.group}.{name}", params)
            return {"FINISHED"}

        return call


class FakeOps:
    def __init__(self, fake: FakeBpy) -> None:
        self.object = FakeOperatorGroup(fake, "object")
        self.mesh = FakeOperatorGroup(fake, "mesh")


class FakeBpy:
    def __init__(self) -> None:
        self.ops = FakeOps(self)
        self.objects: dict[str, dict] = {}
        self.active_object: str | None = None

    def marouba_clear_scene(self) -> None:
        self.objects.clear()
        self.active_object = None

    def marouba_apply_datablock_change(self, event: dict) -> None:
        name = str(event["datablock"]).split(":", 1)[1]
        parts = str(event["path"]).split(".")
        current = self.objects[name]
        for part in parts[:-1]:
            current = current.setdefault(part, {})
        current[parts[-1]] = event["value"]

    def marouba_scene_snapshot(self) -> dict:
        return {"objects": self.objects}

    def call_operator(self, operator: str, params: dict) -> None:
        if operator == "mesh.primitive_cube_add":
            name = str(params.get("name") or "Cube")
            self.objects[name] = {
                "type": "MESH",
                "mesh": {"shape": "cube", "size": params.get("size", 2)},
                "location": params.get("location", [0, 0, 0]),
                "modifiers": {},
                "operator_params": {"mesh.primitive_cube_add": params},
            }
            self.active_object = name
            return
        if operator == "object.modifier_add":
            if not self.active_object:
                raise RuntimeError("No active object for modifier_add")
            modifier_type = str(params["type"])
            modifier_name = str(params.get("name") or modifier_type.title())
            self.objects[self.active_object]["modifiers"][modifier_name] = {"type": modifier_type}
            return
        if operator == "object.shade_smooth":
            if self.active_object:
                self.objects[self.active_object]["shade_smooth"] = True
            return
        raise RuntimeError(f"Unexpected fake bpy operator: {operator}")


def simple_blender_route() -> dict:
    return {
        "type": "adapter",
        "adapter": "blender",
        "events": [
            {
                "route_tier": "r1",
                "app": "Blender",
                "kind": "operator",
                "operator": "mesh.primitive_cube_add",
                "params": {"name": "BassCube", "size": "{size}", "location": [0, 0, 0]},
            },
            {
                "route_tier": "r1",
                "app": "Blender",
                "kind": "operator",
                "operator": "object.modifier_add",
                "params": {"type": "BEVEL", "name": "Bevel"},
            },
            {
                "route_tier": "r1",
                "app": "Blender",
                "kind": "datablock_changed",
                "datablock": "object:BassCube",
                "path": "modifiers.Bevel.width",
                "value": 0.12,
            },
            {
                "route_tier": "r3",
                "app": "Blender",
                "kind": "viewport_gesture",
                "screen_delta": [22, -4],
            },
        ],
    }


def test_blender_capture_marks_operator_and_datablock_as_r1_and_viewport_as_r3() -> None:
    events = capture_events_from_blender_session(
        [
            {"operator": "mesh.primitive_cube_add", "params": {"size": 2}},
            {"operator": "object.modifier_add", "params": {"type": "BEVEL"}},
        ],
        {"objects": {"Cube": {"modifiers": {}}}},
        {"objects": {"Cube": {"modifiers": {"Bevel": {"type": "BEVEL", "width": 0.12}}}}},
        [{"screen_delta": [4, 1]}],
    )

    r1_events = [event for event in events if event["route_tier"] == "r1"]
    r3_events = [event for event in events if event["route_tier"] == "r3"]
    assert [event["operator"] for event in r1_events if event["kind"] == "operator"] == [
        "mesh.primitive_cube_add",
        "object.modifier_add",
    ]
    assert any(event["kind"] == "datablock_changed" for event in r1_events)
    assert len(r3_events) == 1
    assert r3_events[0]["kind"] == "viewport_gesture"


def test_blender_replay_preserves_operator_params_and_hashes_scene() -> None:
    fake_bpy = FakeBpy()
    route = simple_blender_route()

    result = BlenderAdapter().execute(route, {"size": 3}, {"id": "blender-demo"}, bpy_module=fake_bpy)

    expected_snapshot = {
        "objects": {
            "BassCube": {
                "type": "MESH",
                "mesh": {"shape": "cube", "size": "3"},
                "location": [0, 0, 0],
                "modifiers": {"Bevel": {"type": "BEVEL", "width": 0.12}},
                "operator_params": {"mesh.primitive_cube_add": {"name": "BassCube", "size": "3", "location": [0, 0, 0]}},
            }
        }
    }
    assert result["success"] is True
    assert result["events_replayed"] == 3
    assert result["scene_hash"] == hash_scene_snapshot(expected_snapshot)
    assert "viewport" not in result["script"].casefold()


def test_executor_blender_adapter_route_does_not_require_browser_pixels(monkeypatch, tmp_path: Path) -> None:
    fake_bpy = FakeBpy()
    monkeypatch.setattr(
        "engine.executor.BlenderAdapter",
        lambda: type(
            "InjectedBlenderAdapter",
            (),
            {"execute": lambda _self, route, params, workflow: BlenderAdapter().execute(route, params, workflow, fake_bpy)},
        )(),
    )

    result = Executor(tmp_path).execute(simple_blender_route(), {"size": 2}, {"id": "blender", "app": "Blender"})

    assert result["success"] is True
    assert result["route_type"] == "adapter"
    assert "pixel" not in json.dumps(result).casefold()
    assert "snapshot" not in json.dumps(result).casefold()


def test_blender_fake_20_run_soak_meets_threshold() -> None:
    successes = 0
    for index in range(20):
        fake_bpy = FakeBpy()
        result = BlenderAdapter().execute(simple_blender_route(), {"size": 2 + index}, {}, bpy_module=fake_bpy)
        successes += int(result["success"])

    assert successes / 20 >= 0.95


def test_three_blender_demo_vaults_load_as_adapter_workflows() -> None:
    roots = sorted((ROOT / "demo-vaults").glob("blender-*"))

    assert len(roots) >= 3
    for root in roots:
        workflows = Vault(root).list_workflows()
        assert len(workflows) == 1
        route = workflows[0]["routes"][0]
        assert route["type"] == "adapter"
        assert route["adapter"] == "blender"
        assert "visual" not in workflows[0]["fallback_order"]
