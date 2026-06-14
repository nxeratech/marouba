from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine.executor import Executor
from engine.resolve_adapter import (
    ResolveAdapter,
    capture_events_from_resolve_session,
    captured_workflow,
    hash_resolve_snapshot,
)
from engine.vault import Vault


ROOT = Path(__file__).resolve().parents[1]


class FakeResolve:
    def __init__(self) -> None:
        self.project = FakeProject(self)

    def GetProjectManager(self):
        return FakeProjectManager(self.project)

    def marouba_snapshot(self) -> dict:
        return self.project.snapshot()


class FakeProjectManager:
    def __init__(self, project: "FakeProject") -> None:
        self.project = project

    def GetCurrentProject(self):
        return self.project


class FakeProject:
    def __init__(self, resolve: FakeResolve) -> None:
        self.resolve = resolve
        self.media_pool = FakeMediaPool(self)
        self.timeline = FakeTimeline()

    def GetName(self) -> str:
        return "Marouba Resolve Test"

    def GetMediaPool(self):
        return self.media_pool

    def GetCurrentTimeline(self):
        return self.timeline

    def snapshot(self) -> dict:
        return {
            "project": self.GetName(),
            "media": sorted(self.media_pool.imported),
            "timeline": self.timeline.snapshot(),
        }


class FakeMediaItem:
    def __init__(self, path: str) -> None:
        self.path = path
        self.name = Path(path).name


class FakeMediaPool:
    def __init__(self, project: FakeProject) -> None:
        self.project = project
        self.imported: list[str] = []

    def ImportMedia(self, paths: list[str]):
        self.imported.extend(paths)
        return [FakeMediaItem(path) for path in paths]

    def AppendToTimeline(self, clip_infos: list[dict]):
        items = []
        for clip_info in clip_infos:
            item = FakeTimelineItem(clip_info["mediaPoolItem"], clip_info)
            self.project.timeline.items.append(item)
            items.append(item)
        return items


class FakeTimeline:
    def __init__(self) -> None:
        self.tracks = {"video": 1, "audio": 1}
        self.timecode = "01:00:00:00"
        self.items: list[FakeTimelineItem] = []

    def GetName(self) -> str:
        return "Timeline 1"

    def AddTrack(self, track_type: str, options=None) -> bool:
        self.tracks[track_type] = self.tracks.get(track_type, 0) + 1
        return True

    def SetCurrentTimecode(self, timecode: str) -> bool:
        self.timecode = timecode
        return True

    def GetItemListInTrack(self, _track_type: str, _track_index: int):
        return self.items

    def snapshot(self) -> dict:
        return {
            "tracks": self.tracks,
            "timecode": self.timecode,
            "items": [item.snapshot() for item in self.items],
        }


class FakeTimelineItem:
    def __init__(self, media_item: FakeMediaItem, clip_info: dict) -> None:
        self.media_item = media_item
        self.clip_info = dict(clip_info)
        self.cdl: dict | None = None
        self.graph = FakeGraph()

    def SetCDL(self, cdl: dict) -> bool:
        self.cdl = dict(cdl)
        return True

    def GetNodeGraph(self, _layer_index: int = 1):
        return self.graph

    def snapshot(self) -> dict:
        return {
            "media": self.media_item.path,
            "trackIndex": self.clip_info.get("trackIndex"),
            "recordFrame": self.clip_info.get("recordFrame"),
            "cdl": self.cdl,
            "graph": self.graph.snapshot(),
        }


class FakeGraph:
    def __init__(self) -> None:
        self.luts: dict[int, str] = {}
        self.drx: list[dict] = []
        self.enabled: dict[int, bool] = {}

    def SetLUT(self, node_index: int, lut_path: str) -> bool:
        self.luts[node_index] = lut_path
        return True

    def ApplyGradeFromDRX(self, drx_path: str, grade_mode: int) -> bool:
        self.drx.append({"path": drx_path, "grade_mode": grade_mode})
        return True

    def SetNodeEnabled(self, node_index: int, enabled: bool) -> bool:
        self.enabled[node_index] = enabled
        return True

    def snapshot(self) -> dict:
        return {"luts": self.luts, "drx": self.drx, "enabled": self.enabled}


def edit_grade_route() -> dict:
    return {
        "type": "adapter",
        "adapter": "davinci-resolve",
        "events": [
            {
                "route_tier": "r1",
                "app": "DaVinci Resolve",
                "kind": "timeline_op",
                "action": "import_media",
                "paths": ["{media_path}"],
            },
            {
                "route_tier": "r1",
                "app": "DaVinci Resolve",
                "kind": "timeline_op",
                "action": "append_to_timeline",
                "result_key": "timeline_item_1",
                "clip_infos": [{"mediaPoolItem": "{media_path}", "trackIndex": 1, "recordFrame": 0}],
            },
            {
                "route_tier": "r1",
                "app": "DaVinci Resolve",
                "kind": "grade_node",
                "action": "set_cdl",
                "value_source": "cdl",
                "timeline_item": "timeline_item_1",
                "cdl": {
                    "NodeIndex": "1",
                    "Slope": "1.05 0.98 0.92",
                    "Offset": "0.01 0.00 -0.01",
                    "Power": "0.95 1.00 1.08",
                    "Saturation": "1.15",
                },
            },
            {
                "route_tier": "r2",
                "app": "DaVinci Resolve",
                "kind": "ui_gesture",
                "page": "Color",
            },
        ],
    }


def test_resolve_capture_keeps_timeline_and_grade_as_r1_and_ui_as_gap_fallback() -> None:
    events = capture_events_from_resolve_session(
        [{"action": "append_to_timeline", "clip_infos": []}],
        [
            {
                "action": "set_cdl",
                "value_source": "api",
                "timeline_item": "timeline_item_1",
                "cdl": {"NodeIndex": "1", "Slope": "1 1 1", "Offset": "0 0 0", "Power": "1 1 1", "Saturation": "1"},
            }
        ],
        [{"control": "color-wheel"}],
    )

    assert [event["route_tier"] for event in events] == ["r1", "r1", "r2"]
    assert events[1]["kind"] == "grade_node"
    assert events[1]["value_source"] == "api"
    assert events[2]["kind"] == "ui_gesture"


def test_resolve_refuses_approximated_grade_values() -> None:
    with pytest.raises(RuntimeError, match="refuses approximated"):
        capture_events_from_resolve_session(
            [],
            [{"action": "set_cdl", "capture_source": "approximation", "value_source": "ui", "cdl": {}}],
        )


def test_resolve_replay_applies_exact_timeline_and_grade_api_events() -> None:
    fake = FakeResolve()
    result = ResolveAdapter().execute(edit_grade_route(), {"media_path": "C:/media/clip.mov"}, {}, resolve_app=fake)

    expected = {
        "project": "Marouba Resolve Test",
        "media": ["C:/media/clip.mov"],
        "timeline": {
            "tracks": {"video": 1, "audio": 1},
            "timecode": "01:00:00:00",
            "items": [
                {
                    "media": "C:/media/clip.mov",
                    "trackIndex": 1,
                    "recordFrame": 0,
                    "cdl": {
                        "NodeIndex": "1",
                        "Slope": "1.05 0.98 0.92",
                        "Offset": "0.01 0.00 -0.01",
                        "Power": "0.95 1.00 1.08",
                        "Saturation": "1.15",
                    },
                    "graph": {"luts": {}, "drx": [], "enabled": {}},
                }
            ],
        },
    }
    assert result["success"] is True
    assert result["events_replayed"] == 3
    assert result["project_hash"] == hash_resolve_snapshot(expected)


def test_executor_resolve_adapter_route_does_not_require_pixels(monkeypatch, tmp_path: Path) -> None:
    fake = FakeResolve()
    monkeypatch.setattr(
        "engine.executor.ResolveAdapter",
        lambda: type(
            "InjectedResolveAdapter",
            (),
            {"execute": lambda _self, route, params, workflow: ResolveAdapter().execute(route, params, workflow, fake)},
        )(),
    )

    result = Executor(tmp_path).execute(edit_grade_route(), {"media_path": "C:/media/clip.mov"}, {"app": "DaVinci Resolve"})

    assert result["success"] is True
    assert result["route_type"] == "adapter"
    assert "pixel" not in json.dumps(result).casefold()
    assert "approx" not in json.dumps(result).casefold()


def test_resolve_fake_20_run_soak_meets_threshold() -> None:
    successes = 0
    for index in range(20):
        result = ResolveAdapter().execute(
            edit_grade_route(),
            {"media_path": f"C:/media/clip-{index}.mov"},
            {},
            resolve_app=FakeResolve(),
        )
        successes += int(result["success"])

    assert successes / 20 >= 0.95


def test_captured_resolve_workflow_contains_adapter_route_and_events() -> None:
    events = capture_events_from_resolve_session(
        [{"action": "set_current_timecode", "timecode": "01:00:04:00"}],
        [{"action": "set_node_enabled", "value_source": "api", "timeline_item": "timeline_item_1", "enabled": True}],
    )
    workflow = captured_workflow("Resolve Demo", events)

    assert workflow["routes"][0]["type"] == "adapter"
    assert workflow["routes"][0]["adapter"] == "davinci-resolve"
    assert workflow["signals"]["captured_events"] == events
    assert "visual" not in workflow["fallback_order"]


def test_three_resolve_demo_vaults_load_as_adapter_workflows() -> None:
    roots = sorted((ROOT / "demo-vaults").glob("resolve-*"))

    assert len(roots) >= 3
    for root in roots:
        workflows = Vault(root).list_workflows()
        assert len(workflows) == 1
        route = workflows[0]["routes"][0]
        assert route["type"] == "adapter"
        assert route["adapter"] == "davinci-resolve"
        assert "visual" not in workflows[0]["fallback_order"]
