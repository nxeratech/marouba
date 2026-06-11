from __future__ import annotations

from engine import executor as executor_module
from engine.executor import Executor


class HealthyCompanion:
    def __init__(self) -> None:
        self.payloads = []

    def health(self) -> bool:
        return True

    def click_uia(self, payload: dict) -> dict:
        self.payloads.append(payload)
        return {"ok": True}


class DownCompanion:
    def health(self) -> bool:
        return False


def test_executor_calls_companion_for_uia_route(tmp_path) -> None:
    executor = Executor(tmp_path)
    companion = HealthyCompanion()
    executor.companion = companion

    result = executor.execute(
        {"type": "uia", "app_window": "ComfyUI", "element": "Queue Prompt", "role": "Button"},
        {"output_path": "/tmp/out.png"},
        {"verification": {"type": "none"}},
    )

    assert result["success"] is True
    assert result["output"] == "/tmp/out.png"
    assert companion.payloads == [
        {"window_title": "ComfyUI", "name": "Queue Prompt", "role": "Button"}
    ]


def test_executor_falls_back_to_pywinauto_stub_when_companion_unavailable(monkeypatch, tmp_path) -> None:
    executor = Executor(tmp_path)
    executor.companion = DownCompanion()
    monkeypatch.setattr(executor_module.importlib.util, "find_spec", lambda name: None)

    result = executor.execute(
        {"type": "uia", "app_window": "ComfyUI", "element": "Queue Prompt", "role": "Button"},
        {},
        {"verification": {"type": "none"}},
    )

    assert result["success"] is False
    assert "Companion is not running and pywinauto is unavailable" in result["error"]

class AbletonCompanion:
    def __init__(self) -> None:
        self.payloads = []

    def health(self) -> bool:
        return True

    def ableton_execute(self, payload: dict) -> dict:
        self.payloads.append(payload)
        return {"ok": True, "output": {"route": "api", "action": "set_parameter"}}


def test_executor_routes_ableton_api_through_companion(tmp_path) -> None:
    executor = Executor(tmp_path)
    companion = AbletonCompanion()
    executor.companion = companion

    result = executor.execute(
        {
            "type": "api",
            "api": "ableton_lom",
            "action": "set_parameter",
            "target": "track:1/device:Auto Filter",
            "param": "Frequency",
            "value": 0.73,
        },
        {},
        {"id": "ableton-test", "name": "Ableton Test", "app": "Ableton Live"},
    )

    assert result["success"] is True
    assert result["route_type"] == "api"
    assert companion.payloads[0]["route"]["api"] == "ableton_lom"
    assert companion.payloads[0]["workflow"]["app"] == "Ableton Live"

