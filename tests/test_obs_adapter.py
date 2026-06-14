from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine.executor import Executor
from engine.obs_adapter import ObsAdapter, capture_events_from_obs_snapshot, captured_workflow, hash_obs_snapshot
from engine.vault import Vault


ROOT = Path(__file__).resolve().parents[1]


class FakeObsClient:
    def __init__(self) -> None:
        self.scenes: list[dict] = []
        self.inputs: dict[str, dict] = {}
        self.filters: dict[str, list[dict]] = {}
        self.transition = {"transitionName": "Cut", "transitionDuration": 0, "transitionSettings": {}}
        self.calls: list[dict] = []

    def call(self, request_type: str, request_data: dict | None = None) -> dict:
        data = request_data or {}
        self.calls.append({"requestType": request_type, "requestData": data})
        if request_type == "CreateScene":
            self.scenes.append({"sceneName": data["sceneName"]})
            return {}
        if request_type == "SetCurrentProgramScene":
            return {}
        if request_type == "CreateInput":
            self.inputs[data["inputName"]] = {
                "inputName": data["inputName"],
                "inputKind": data["inputKind"],
                "sceneName": data["sceneName"],
                "settings": data.get("inputSettings", {}),
                "volume": {"inputVolumeDb": 0.0, "inputVolumeMul": 1.0},
                "mute": {"inputMuted": False},
            }
            return {"sceneItemId": len(self.inputs)}
        if request_type == "SetInputSettings":
            self.inputs[data["inputName"]]["settings"].update(data.get("inputSettings") or {})
            return {}
        if request_type == "SetInputVolume":
            self.inputs[data["inputName"]]["volume"] = {key: value for key, value in data.items() if key.startswith("inputVolume")}
            return {}
        if request_type == "SetInputMute":
            self.inputs[data["inputName"]]["mute"] = {"inputMuted": data["inputMuted"]}
            return {}
        if request_type == "CreateSourceFilter":
            self.filters.setdefault(data["sourceName"], []).append(
                {
                    "filterName": data["filterName"],
                    "filterKind": data["filterKind"],
                    "filterSettings": data["filterSettings"],
                    "filterEnabled": True,
                }
            )
            return {}
        if request_type == "SetSourceFilterSettings":
            for item in self.filters.get(data["sourceName"], []):
                if item["filterName"] == data["filterName"]:
                    item["filterSettings"].update(data["filterSettings"])
            return {}
        if request_type == "SetSourceFilterEnabled":
            for item in self.filters.get(data["sourceName"], []):
                if item["filterName"] == data["filterName"]:
                    item["filterEnabled"] = data["filterEnabled"]
            return {}
        if request_type == "SetCurrentSceneTransition":
            self.transition["transitionName"] = data["transitionName"]
            return {}
        if request_type == "SetCurrentSceneTransitionDuration":
            self.transition["transitionDuration"] = data["transitionDuration"]
            return {}
        if request_type == "SetCurrentSceneTransitionSettings":
            self.transition["transitionSettings"] = data["transitionSettings"]
            return {}
        if request_type == "GetSceneList":
            return {"scenes": self.scenes}
        if request_type == "GetInputList":
            return {
                "inputs": [
                    {"inputName": value["inputName"], "inputKind": value["inputKind"], "sceneName": value["sceneName"]}
                    for value in self.inputs.values()
                ]
            }
        if request_type == "GetInputSettings":
            return {"inputSettings": self.inputs[data["inputName"]]["settings"]}
        if request_type == "GetInputVolume":
            return self.inputs[data["inputName"]]["volume"]
        if request_type == "GetInputMute":
            return self.inputs[data["inputName"]]["mute"]
        if request_type == "GetSourceFilterList":
            return {"filters": self.filters.get(data["sourceName"], [])}
        if request_type == "GetCurrentSceneTransition":
            return self.transition
        raise RuntimeError(f"Unexpected OBS request: {request_type}")


def obs_route() -> dict:
    return {
        "type": "adapter",
        "adapter": "obs-studio",
        "events": [
            {"route_tier": "r1", "app": "OBS Studio", "kind": "scene", "action": "create_scene", "sceneName": "Demo"},
            {
                "route_tier": "r1",
                "app": "OBS Studio",
                "kind": "source",
                "action": "create_input",
                "sceneName": "Demo",
                "inputName": "Camera",
                "inputKind": "dshow_input",
                "inputSettings": {"device_id": "{device_id}"},
            },
            {
                "route_tier": "r1",
                "app": "OBS Studio",
                "kind": "filter",
                "action": "create_filter",
                "sourceName": "Camera",
                "filterName": "Color Correction",
                "filterKind": "color_filter",
                "filterSettings": {"gamma": 0.05, "contrast": 0.1},
            },
            {
                "route_tier": "r1",
                "app": "OBS Studio",
                "kind": "audio",
                "action": "set_input_volume",
                "inputName": "Camera",
                "inputVolumeDb": -8.0,
            },
            {
                "route_tier": "r1",
                "app": "OBS Studio",
                "kind": "transition",
                "action": "set_current_transition",
                "transitionName": "Fade",
            },
        ],
    }


def test_obs_capture_generates_r1_events_for_scene_source_filter_audio_transition() -> None:
    snapshot = {
        "scenes": [{"sceneName": "Demo"}],
        "inputs": [
            {
                "sceneName": "Demo",
                "inputName": "Camera",
                "inputKind": "dshow_input",
                "settings": {"device_id": "cam-1"},
                "volume": {"inputVolumeDb": -8.0},
                "mute": {"inputMuted": False},
                "filters": [
                    {
                        "filterName": "Color Correction",
                        "filterKind": "color_filter",
                        "filterSettings": {"gamma": 0.05},
                        "filterEnabled": True,
                    }
                ],
            }
        ],
        "transition": {"transitionName": "Fade"},
    }

    events = capture_events_from_obs_snapshot(snapshot)

    assert {event["route_tier"] for event in events} == {"r1"}
    assert [event["kind"] for event in events] == ["scene", "source", "audio", "audio", "filter", "transition"]
    assert events[4]["filterSettings"] == {"gamma": 0.05}


def test_obs_capture_refuses_unreadable_filter_settings() -> None:
    with pytest.raises(RuntimeError, match="filter param unreadable"):
        capture_events_from_obs_snapshot(
            {
                "scenes": [],
                "inputs": [
                    {
                        "sceneName": "Demo",
                        "inputName": "Camera",
                        "inputKind": "dshow_input",
                        "filters": [{"filterName": "Mystery", "filterKind": "unknown", "filterSettings": None}],
                    }
                ],
            }
        )


def test_obs_replay_reconstructs_collection_and_hash() -> None:
    client = FakeObsClient()
    result = ObsAdapter(client=client).execute(obs_route(), {"device_id": "cam-1"}, {})

    expected = {
        "scenes": [{"sceneName": "Demo"}],
        "inputs": [
            {
                "inputName": "Camera",
                "inputKind": "dshow_input",
                "sceneName": "Demo",
                "settings": {"device_id": "cam-1"},
                "volume": {"inputVolumeDb": -8.0},
                "mute": {"inputMuted": False},
                "filters": [
                    {
                        "filterName": "Color Correction",
                        "filterKind": "color_filter",
                        "filterSettings": {"gamma": 0.05, "contrast": 0.1},
                        "filterEnabled": True,
                    }
                ],
            }
        ],
        "transition": {"transitionName": "Fade", "transitionDuration": 0, "transitionSettings": {}},
    }
    assert result["success"] is True
    assert result["events_replayed"] == 5
    assert result["collection_hash"] == hash_obs_snapshot(expected)


def test_executor_obs_adapter_route_does_not_require_pixels(monkeypatch, tmp_path: Path) -> None:
    client = FakeObsClient()
    monkeypatch.setattr("engine.executor.ObsAdapter", lambda: ObsAdapter(client=client))

    result = Executor(tmp_path).execute(obs_route(), {"device_id": "cam-1"}, {"app": "OBS Studio"})

    assert result["success"] is True
    assert result["route_type"] == "adapter"
    assert "pixel" not in json.dumps(result).casefold()
    assert "gesture" not in json.dumps(result).casefold()


def test_obs_fake_20_run_soak_meets_threshold() -> None:
    successes = 0
    for index in range(20):
        result = ObsAdapter(client=FakeObsClient()).execute(obs_route(), {"device_id": f"cam-{index}"}, {})
        successes += int(result["success"])

    assert successes / 20 >= 0.95


def test_captured_obs_workflow_contains_adapter_route_and_events() -> None:
    events = capture_events_from_obs_snapshot({"scenes": [{"sceneName": "Demo"}], "inputs": []})
    workflow = captured_workflow("OBS Demo", events)

    assert workflow["routes"][0]["type"] == "adapter"
    assert workflow["routes"][0]["adapter"] == "obs-studio"
    assert workflow["signals"]["captured_events"] == events
    assert "visual" not in workflow["fallback_order"]


def test_three_obs_demo_vaults_load_as_adapter_workflows() -> None:
    roots = sorted((ROOT / "demo-vaults").glob("obs-*"))

    assert len(roots) >= 3
    for root in roots:
        workflows = Vault(root).list_workflows()
        assert len(workflows) == 1
        route = workflows[0]["routes"][0]
        assert route["type"] == "adapter"
        assert route["adapter"] == "obs-studio"
        assert "visual" not in workflows[0]["fallback_order"]
