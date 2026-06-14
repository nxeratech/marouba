from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine.executor import Executor
from engine.reaper_adapter import ReaperAdapter, capture_events_from_reaper_project, captured_workflow, hash_project_snapshot
from engine.vault import Vault


ROOT = Path(__file__).resolve().parents[1]


class FakeReaperRuntime:
    def __init__(self) -> None:
        self.actions: list[int] = []
        self.tracks: list[dict] = []

    def run_action(self, event: dict) -> None:
        self.actions.append(int(event["command_id"]))

    def insert_track(self, event: dict) -> dict:
        track = {
            "track_index": int(event["track_index"]),
            "name": event.get("name"),
            "volume": event.get("volume"),
            "pan": event.get("pan", 0.0),
            "items": [],
            "fx": [],
            "envelopes": {},
        }
        while len(self.tracks) <= track["track_index"]:
            self.tracks.append({"track_index": len(self.tracks), "items": [], "fx": [], "envelopes": {}})
        self.tracks[track["track_index"]] = track
        return track

    def add_media_item(self, event: dict) -> dict:
        item = {
            "position": event["position"],
            "length": event["length"],
            "name": event.get("name"),
            "source_path": event.get("source_path"),
        }
        self.tracks[int(event["track_index"])]["items"].append(item)
        return item

    def add_fx(self, event: dict) -> int:
        fx = {"fx_index": int(event.get("fx_index", len(self.tracks[int(event["track_index"])]["fx"]))), "fx_name": event["fx_name"], "params": []}
        self.tracks[int(event["track_index"])]["fx"].append(fx)
        return fx["fx_index"]

    def set_fx_param(self, event: dict) -> None:
        track = self.tracks[int(event["track_index"])]
        fx = track["fx"][int(event["fx_index"])]
        fx["params"].append(
            {
                "param_index": int(event["param_index"]),
                "param_name": event.get("param_name"),
                "value": float(event["value"]),
                "value_status": "exact",
            }
        )

    def insert_envelope_point(self, event: dict) -> None:
        track = self.tracks[int(event["track_index"])]
        env = track["envelopes"].setdefault(event["envelope_name"], [])
        env.append(
            {
                "time": float(event["time"]),
                "value": float(event["value"]),
                "shape": int(event.get("shape", 0)),
                "tension": float(event.get("tension", 0)),
                "value_status": "exact",
            }
        )

    def snapshot(self) -> dict:
        tracks = []
        for track in self.tracks:
            copy = dict(track)
            copy["envelopes"] = [
                {"name": name, "points": points}
                for name, points in sorted(track.get("envelopes", {}).items())
            ]
            tracks.append(copy)
        return {"actions": self.actions, "tracks": tracks}


def reaper_route() -> dict:
    return {
        "type": "adapter",
        "adapter": "reaper",
        "events": [
            {"route_tier": "r1", "app": "REAPER", "kind": "action", "action": "run_action", "command_id": 40001},
            {
                "route_tier": "r1",
                "app": "REAPER",
                "kind": "track",
                "action": "insert_track",
                "track_index": 0,
                "name": "Marouba Bass",
                "volume": 0.82,
                "pan": 0.0,
            },
            {
                "route_tier": "r1",
                "app": "REAPER",
                "kind": "item",
                "action": "add_media_item",
                "track_index": 0,
                "position": 0.0,
                "length": 4.0,
                "name": "bass-loop",
            },
            {
                "route_tier": "r1",
                "app": "REAPER",
                "kind": "fx",
                "action": "add_fx",
                "track_index": 0,
                "fx_index": 0,
                "fx_name": "ReaEQ",
            },
            {
                "route_tier": "r1",
                "app": "REAPER",
                "kind": "fx_param",
                "action": "set_fx_param",
                "track_index": 0,
                "fx_index": 0,
                "param_index": 0,
                "param_name": "Band 1 Frequency",
                "value": "{freq}",
                "value_status": "exact",
            },
            {
                "route_tier": "r1",
                "app": "REAPER",
                "kind": "envelope",
                "action": "insert_envelope_point",
                "track_index": 0,
                "envelope_name": "Volume",
                "time": 4.0,
                "value": 1.0,
                "shape": 0,
                "tension": 0.0,
                "value_status": "exact",
            },
        ],
    }


def project_snapshot() -> dict:
    return {
        "actions": [{"command_id": 40001}],
        "tracks": [
            {
                "track_index": 0,
                "name": "Marouba Bass",
                "volume": 0.82,
                "pan": 0.0,
                "items": [{"position": 0.0, "length": 4.0, "name": "bass-loop"}],
                "fx": [
                    {
                        "fx_index": 0,
                        "fx_name": "ReaEQ",
                        "params": [
                            {
                                "param_index": 0,
                                "param_name": "Band 1 Frequency",
                                "value": 0.42,
                                "min": 0.0,
                                "max": 1.0,
                                "value_status": "exact",
                            }
                        ],
                    }
                ],
                "envelopes": [
                    {
                        "name": "Volume",
                        "points": [{"time": 4.0, "value": 1.0, "shape": 0, "tension": 0.0, "value_status": "exact"}],
                    }
                ],
            }
        ],
    }


def test_reaper_capture_generates_action_item_fx_param_and_envelope_events() -> None:
    events = capture_events_from_reaper_project(project_snapshot())

    assert [event["action"] for event in events] == [
        "run_action",
        "insert_track",
        "add_media_item",
        "add_fx",
        "set_fx_param",
        "insert_envelope_point",
    ]
    assert {event["route_tier"] for event in events} == {"r1"}
    assert events[4]["value"] == 0.42
    assert events[4]["value_status"] == "exact"


def test_reaper_refuses_unread_fx_param_when_reascript_exposes_it() -> None:
    snapshot = project_snapshot()
    snapshot["tracks"][0]["fx"][0]["params"][0]["value_status"] = "unreadable"

    with pytest.raises(RuntimeError, match="FX param unread"):
        capture_events_from_reaper_project(snapshot)


def test_reaper_replay_matches_project_state_hash() -> None:
    runtime = FakeReaperRuntime()
    result = ReaperAdapter().execute(reaper_route(), {"freq": 0.42}, {}, reaper_runtime=runtime)

    expected = {
        "actions": [40001],
        "tracks": [
            {
                "track_index": 0,
                "name": "Marouba Bass",
                "volume": 0.82,
                "pan": 0.0,
                "items": [{"position": 0.0, "length": 4.0, "name": "bass-loop", "source_path": None}],
                "fx": [
                    {
                        "fx_index": 0,
                        "fx_name": "ReaEQ",
                        "params": [
                            {
                                "param_index": 0,
                                "param_name": "Band 1 Frequency",
                                "value": 0.42,
                                "value_status": "exact",
                            }
                        ],
                    }
                ],
                "envelopes": [
                    {
                        "name": "Volume",
                        "points": [{"time": 4.0, "value": 1.0, "shape": 0, "tension": 0.0, "value_status": "exact"}],
                    }
                ],
            }
        ],
    }
    assert result["success"] is True
    assert result["project_hash"] == hash_project_snapshot(expected)
    assert "TrackFX_SetParam" in result["script"]


def test_executor_reaper_adapter_route_does_not_require_pixels(monkeypatch, tmp_path: Path) -> None:
    runtime = FakeReaperRuntime()
    monkeypatch.setattr(
        "engine.executor.ReaperAdapter",
        lambda: type(
            "InjectedReaperAdapter",
            (),
            {"execute": lambda _self, route, params, workflow: ReaperAdapter().execute(route, params, workflow, runtime)},
        )(),
    )

    result = Executor(tmp_path).execute(reaper_route(), {"freq": 0.42}, {"app": "REAPER"})

    assert result["success"] is True
    assert result["route_type"] == "adapter"
    assert "pixel" not in json.dumps(result).casefold()
    assert "gesture" not in json.dumps(result).casefold()


def test_reaper_fake_20_run_soak_meets_threshold() -> None:
    successes = 0
    for index in range(20):
        result = ReaperAdapter().execute(reaper_route(), {"freq": index / 20}, {}, reaper_runtime=FakeReaperRuntime())
        successes += int(result["success"])

    assert successes / 20 >= 0.95


def test_captured_reaper_workflow_contains_adapter_route_and_events() -> None:
    events = capture_events_from_reaper_project(project_snapshot())
    workflow = captured_workflow("REAPER Demo", events)

    assert workflow["routes"][0]["type"] == "adapter"
    assert workflow["routes"][0]["adapter"] == "reaper"
    assert workflow["signals"]["captured_events"] == events
    assert "visual" not in workflow["fallback_order"]


def test_three_reaper_demo_vaults_load_as_adapter_workflows() -> None:
    roots = sorted((ROOT / "demo-vaults").glob("reaper-*"))

    assert len(roots) >= 3
    for root in roots:
        workflows = Vault(root).list_workflows()
        assert len(workflows) == 1
        route = workflows[0]["routes"][0]
        assert route["type"] == "adapter"
        assert route["adapter"] == "reaper"
        assert "visual" not in workflows[0]["fallback_order"]
