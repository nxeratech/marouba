from __future__ import annotations

from pathlib import Path

from engine.router import Router
from engine.vault import Vault
from scripts.replay import replay_workflow
from scripts.teach import TeachingSession


class FakeExecutor:
    def __init__(self) -> None:
        self.routes = []

    def execute(self, route: dict, params: dict, workflow: dict) -> dict:
        self.routes.append(route)
        return {
            "success": True,
            "route_type": route["type"],
            "output": params.get("output_path"),
            "error": None,
            "duration_ms": 1,
        }


def test_mock_input_events_save_correct_routes(tmp_path: Path) -> None:
    session = TeachingSession("Demo Task", "DemoApp", root=tmp_path, vault=Vault(tmp_path))

    session.capture_action({"type": "ui_click", "window_title": "Demo Window", "element": "Run", "role": "Button"})
    session.capture_action({"type": "shortcut", "keys": ["ctrl", "s"]})
    session.capture_action({"type": "mouse_click", "x": 100, "y": 200, "button": "left"})
    session.capture_action({"type": "http_request", "endpoint": "http://127.0.0.1:8188/prompt", "method": "POST"})
    saved_path = session.save_workflow()

    workflow = Vault(tmp_path).load_workflow(saved_path)
    assert [route["type"] for route in workflow["routes"]] == ["uia", "shortcut", "visual", "api"]
    assert workflow["fallback_order"] == ["api", "uia", "shortcut", "visual", "ask"]
    assert workflow["routes"][0]["element"] == "Run"
    assert workflow["routes"][1]["keys"] == ["ctrl", "s"]
    assert workflow["routes"][2]["coordinates"] == {"x": 100, "y": 200}
    assert saved_path.name == "demo-task.md"


def test_saved_workflow_is_valid_vault_format(tmp_path: Path) -> None:
    session = TeachingSession("Valid Vault Workflow", "DemoApp", root=tmp_path, vault=Vault(tmp_path))
    session.capture_action({"type": "shortcut", "keys": ["ctrl", "enter"]})

    saved_path = session.save_workflow()
    workflow = Vault(tmp_path).find_workflow("valid-vault-workflow")

    assert workflow is not None
    assert workflow["_path"] == str(saved_path)
    assert workflow["id"] == "valid-vault-workflow"
    assert workflow["verification"]["type"] == "none"
    assert workflow["last_verified"]


def test_replay_works_on_saved_taught_workflow(tmp_path: Path) -> None:
    session = TeachingSession("Replayable Workflow", "DemoApp", root=tmp_path, vault=Vault(tmp_path))
    session.capture_action({"type": "shortcut", "keys": ["ctrl", "enter"]})
    session.save_workflow()

    fake_executor = FakeExecutor()
    router = Router({"shortcut": lambda route: True})
    exit_code = replay_workflow(
        "replayable-workflow",
        {"output_path": "/tmp/replayable.txt"},
        root=tmp_path,
        no_repair=True,
        router=router,
        executor=fake_executor,
    )

    assert exit_code == 0
    assert fake_executor.routes[0]["type"] == "shortcut"
