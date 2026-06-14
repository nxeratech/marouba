from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine.aftereffects_adapter import AfterEffectsAdapter, capture_events_from_ae_project, captured_workflow as ae_workflow, hash_comp_snapshot
from engine.executor import Executor
from engine.premiere_adapter import PremiereAdapter, capture_events_from_premiere_session, captured_workflow as premiere_workflow, hash_timeline_snapshot
from engine.vault import Vault


ROOT = Path(__file__).resolve().parents[1]


class FakePremiereRuntime:
    def __init__(self) -> None:
        self.sequence: dict | None = None
        self.clips: list[dict] = []
        self.effects: list[dict] = []

    def create_sequence(self, event: dict) -> None:
        self.sequence = {"sequence_name": event["sequence_name"], "timebase": event["timebase"]}

    def add_clip(self, event: dict) -> None:
        self.clips.append({key: event[key] for key in ("track_type", "track_index", "clip_id", "clip_name", "start", "end")})

    def move_clip(self, event: dict) -> None:
        for clip in self.clips:
            if clip["clip_id"] == event["clip_id"]:
                clip["start"] = event["start"]
                clip["end"] = event["end"]

    def set_effect_param(self, event: dict) -> None:
        self.effects.append(
            {
                "clip_id": event["clip_id"],
                "effect_name": event["effect_name"],
                "param_name": event["param_name"],
                "value": event["value"],
                "keyframes": event.get("keyframes", []),
            }
        )

    def snapshot(self) -> dict:
        return {"sequence": self.sequence, "clips": self.clips, "effects": self.effects}


class FakeAfterEffectsRuntime:
    def __init__(self) -> None:
        self.comp: dict | None = None
        self.layers: list[dict] = []
        self.effects: list[dict] = []
        self.keyframes: list[dict] = []
        self.expressions: list[dict] = []

    def create_comp(self, event: dict) -> None:
        self.comp = {key: event[key] for key in ("comp_name", "width", "height", "duration", "frame_rate")}

    def add_layer(self, event: dict) -> None:
        self.layers.append({key: event[key] for key in ("layer_id", "layer_name", "layer_type")})

    def add_effect(self, event: dict) -> None:
        self.effects.append({key: event[key] for key in ("layer_id", "effect_name", "match_name")})

    def set_keyframe(self, event: dict) -> None:
        self.keyframes.append({key: event[key] for key in ("layer_id", "property_path", "time", "value")})

    def set_expression(self, event: dict) -> None:
        self.expressions.append({key: event[key] for key in ("layer_id", "property_path", "expression")})

    def snapshot(self) -> dict:
        return {"comp": self.comp, "layers": self.layers, "effects": self.effects, "keyframes": self.keyframes, "expressions": self.expressions}


def premiere_session() -> dict:
    return {
        "sequence_name": "Marouba Cut",
        "timebase": 25,
        "clips": [
            {
                "track_type": "video",
                "track_index": 0,
                "clip_id": "clip_1",
                "clip_name": "bassline-shot.mov",
                "start": 0.0,
                "end": 4.0,
                "effects": [
                    {
                        "effect_name": "Transform",
                        "params": [
                            {
                                "param_name": "Scale",
                                "value": 100,
                                "value_status": "exact",
                                "keyframes": [
                                    {"time": 0.0, "value": 100, "value_status": "exact"},
                                    {"time": 2.0, "value": 118, "value_status": "exact"},
                                ],
                            }
                        ],
                    }
                ],
            }
        ],
    }


def ae_project() -> dict:
    return {
        "comp_name": "Marouba Motion",
        "width": 1920,
        "height": 1080,
        "duration": 6,
        "frame_rate": 25,
        "layers": [
            {
                "layer_id": "layer_1",
                "layer_name": "Bass Title",
                "layer_type": "text",
                "effects": [{"effect_name": "Glow", "match_name": "ADBE Glow"}],
                "keyframes": [{"property_path": "Transform/Position", "time": 0.0, "value": [960, 540], "value_status": "exact"}],
                "expressions": [{"property_path": "Transform/Opacity", "expression": "50 + Math.sin(time * 4) * 25"}],
            }
        ],
    }


def test_premiere_capture_and_replay_matches_timeline_state() -> None:
    events = capture_events_from_premiere_session(premiere_session())
    runtime = FakePremiereRuntime()
    result = PremiereAdapter().execute({"type": "adapter", "adapter": "premiere", "events": events}, {}, {}, premiere_runtime=runtime)

    expected = {
        "sequence": {"sequence_name": "Marouba Cut", "timebase": 25},
        "clips": [{"track_type": "video", "track_index": 0, "clip_id": "clip_1", "clip_name": "bassline-shot.mov", "start": 0.0, "end": 4.0}],
        "effects": [{"clip_id": "clip_1", "effect_name": "Transform", "param_name": "Scale", "value": 100, "keyframes": premiere_session()["clips"][0]["effects"][0]["params"][0]["keyframes"]}],
    }
    assert result["success"] is True
    assert result["timeline_hash"] == hash_timeline_snapshot(expected)
    assert "set Transform.Scale" in result["script"]


def test_premiere_refuses_approximated_keyframe_values() -> None:
    session = premiere_session()
    session["clips"][0]["effects"][0]["params"][0]["keyframes"][1]["value_status"] = "approximate"

    with pytest.raises(RuntimeError, match="keyframe values must be exact"):
        capture_events_from_premiere_session(session)


def test_after_effects_capture_and_replay_matches_comp_state() -> None:
    events = capture_events_from_ae_project(ae_project())
    runtime = FakeAfterEffectsRuntime()
    result = AfterEffectsAdapter().execute({"type": "adapter", "adapter": "after-effects", "events": events}, {}, {}, ae_runtime=runtime)

    expected = {
        "comp": {"comp_name": "Marouba Motion", "width": 1920, "height": 1080, "duration": 6, "frame_rate": 25},
        "layers": [{"layer_id": "layer_1", "layer_name": "Bass Title", "layer_type": "text"}],
        "effects": [{"layer_id": "layer_1", "effect_name": "Glow", "match_name": "ADBE Glow"}],
        "keyframes": [{"layer_id": "layer_1", "property_path": "Transform/Position", "time": 0.0, "value": [960, 540]}],
        "expressions": [{"layer_id": "layer_1", "property_path": "Transform/Opacity", "expression": "50 + Math.sin(time * 4) * 25"}],
    }
    assert result["success"] is True
    assert result["comp_hash"] == hash_comp_snapshot(expected)
    assert "setValueAtTime" in result["script"]


def test_after_effects_refuses_approximated_keyframe_values() -> None:
    project = ae_project()
    project["layers"][0]["keyframes"][0]["value_status"] = "approximate"

    with pytest.raises(RuntimeError, match="must be exact"):
        capture_events_from_ae_project(project)


def test_executor_routes_premiere_and_after_effects_without_pixels(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "engine.executor.PremiereAdapter",
        lambda: type("InjectedPremiere", (), {"execute": lambda _self, route, params, workflow: PremiereAdapter().execute(route, params, workflow, FakePremiereRuntime())})(),
    )
    monkeypatch.setattr(
        "engine.executor.AfterEffectsAdapter",
        lambda: type("InjectedAE", (), {"execute": lambda _self, route, params, workflow: AfterEffectsAdapter().execute(route, params, workflow, FakeAfterEffectsRuntime())})(),
    )

    prem = Executor(tmp_path).execute({"type": "adapter", "adapter": "premiere", "events": capture_events_from_premiere_session(premiere_session())}, {}, {})
    ae = Executor(tmp_path).execute({"type": "adapter", "adapter": "after-effects", "events": capture_events_from_ae_project(ae_project())}, {}, {})

    assert prem["success"] is True
    assert ae["success"] is True
    assert "pixel" not in json.dumps([prem, ae]).casefold()


def test_adobe_video_fake_20_run_soaks_meet_threshold() -> None:
    prem_successes = 0
    ae_successes = 0
    for _ in range(20):
        prem_successes += int(PremiereAdapter().execute({"type": "adapter", "adapter": "premiere", "events": capture_events_from_premiere_session(premiere_session())}, {}, {}, FakePremiereRuntime())["success"])
        ae_successes += int(AfterEffectsAdapter().execute({"type": "adapter", "adapter": "after-effects", "events": capture_events_from_ae_project(ae_project())}, {}, {}, FakeAfterEffectsRuntime())["success"])

    assert prem_successes / 20 >= 0.95
    assert ae_successes / 20 >= 0.95


def test_captured_workflows_and_demo_vaults_load() -> None:
    prem_wf = premiere_workflow("Premiere Demo", capture_events_from_premiere_session(premiere_session()))
    ae_wf = ae_workflow("AE Demo", capture_events_from_ae_project(ae_project()))
    assert prem_wf["routes"][0]["adapter"] == "premiere"
    assert ae_wf["routes"][0]["adapter"] == "after-effects"

    for pattern, adapter in [("premiere-*", "premiere"), ("after-effects-*", "after-effects")]:
        roots = sorted((ROOT / "demo-vaults").glob(pattern))
        assert len(roots) >= 3
        for root in roots:
            workflows = Vault(root).list_workflows()
            assert len(workflows) == 1
            assert workflows[0]["routes"][0]["adapter"] == adapter
