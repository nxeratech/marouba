from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine.executor import Executor
from engine.vault import Vault
from engine.vscode_adapter import VSCodeAdapter, capture_events_from_vscode_log, captured_workflow, hash_workspace_snapshot


ROOT = Path(__file__).resolve().parents[1]


def vscode_route() -> dict:
    return {
        "type": "adapter",
        "adapter": "vscode",
        "verify_files": ["src/app.ts"],
        "events": [
            {
                "route_tier": "r1",
                "app": "VS Code",
                "kind": "command",
                "action": "run_command",
                "command": "editor.action.rename",
                "args": [{"old": "makeThing", "new": "buildThing"}],
                "source": "extension",
            },
            {
                "route_tier": "r1",
                "app": "VS Code",
                "kind": "edit",
                "action": "apply_edit",
                "path": "src/app.ts",
                "edits": [
                    {"start": 16, "end": 25, "text": "buildThing"},
                    {"start": 39, "end": 48, "text": "buildThing"},
                ],
                "source": "extension",
            },
            {
                "route_tier": "r1",
                "app": "VS Code",
                "kind": "terminal",
                "action": "terminal",
                "command_line": "npm test",
                "cwd": ".",
                "source": "extension",
            },
        ],
    }


def seed_workspace(tmp_path: Path) -> Path:
    root = tmp_path / "workspace"
    source = root / "src" / "app.ts"
    source.parent.mkdir(parents=True)
    source.write_text("export function makeThing() {\n  return makeThing.name;\n}\n", encoding="utf-8")
    return root


def test_vscode_capture_generates_command_edit_and_terminal_r1_events() -> None:
    events = capture_events_from_vscode_log(
        [
            {"kind": "command", "command": "editor.action.rename", "args": [{"old": "makeThing", "new": "buildThing"}]},
            {"kind": "text_edit", "path": "src/app.ts", "edits": [{"start": 0, "end": 4, "text": "type"}]},
            {"kind": "terminal", "command_line": "npm test", "cwd": "."},
        ]
    )

    assert [event["action"] for event in events] == ["run_command", "apply_edit", "terminal"]
    assert {event["route_tier"] for event in events} == {"r1"}
    assert {event["source"] for event in events} == {"extension"}


def test_vscode_refuses_telemetry_or_network_backed_extension_events() -> None:
    with pytest.raises(RuntimeError, match="local-only"):
        capture_events_from_vscode_log([{"kind": "command", "command": "x", "source": "telemetry"}])

    with pytest.raises(RuntimeError, match="local-only"):
        capture_events_from_vscode_log([{"kind": "terminal", "command_line": "curl example.com", "requires_network": True}])


def test_vscode_replay_reproduces_file_end_state(tmp_path: Path) -> None:
    workspace = seed_workspace(tmp_path)

    result = VSCodeAdapter().execute(vscode_route(), {}, {}, workspace_root=workspace)

    expected_text = "export function buildThing() {\n  return buildThing.name;\n}\n"
    expected = {"files": {"src/app.ts": expected_text}}
    assert (workspace / "src" / "app.ts").read_text(encoding="utf-8") == expected_text
    assert result["success"] is True
    assert result["workspace_hash"] == hash_workspace_snapshot(expected)
    assert "createTelemetryLogger" not in result["extension_stub"]
    assert "fetch" not in result["extension_stub"]


def test_executor_vscode_adapter_route_does_not_require_pixels(monkeypatch, tmp_path: Path) -> None:
    workspace = seed_workspace(tmp_path)
    monkeypatch.setattr(
        "engine.executor.VSCodeAdapter",
        lambda: type(
            "InjectedVSCodeAdapter",
            (),
            {"execute": lambda _self, route, params, workflow: VSCodeAdapter().execute(route, params, workflow, workspace)},
        )(),
    )

    result = Executor(tmp_path).execute(vscode_route(), {}, {"app": "VS Code"})

    assert result["success"] is True
    assert result["route_type"] == "adapter"
    assert "pixel" not in json.dumps(result).casefold()
    output = json.loads(result["output"])
    assert {event.get("source") for event in output["replayed"] if isinstance(event, dict)} <= {"extension", None}


def test_vscode_fake_20_run_soak_meets_threshold(tmp_path: Path) -> None:
    successes = 0
    for index in range(20):
        workspace = seed_workspace(tmp_path / f"run-{index}")
        result = VSCodeAdapter().execute(vscode_route(), {}, {}, workspace_root=workspace)
        successes += int(result["success"])

    assert successes / 20 >= 0.95


def test_captured_vscode_workflow_contains_adapter_route_and_events() -> None:
    events = capture_events_from_vscode_log(
        [{"kind": "text_edit", "path": "src/app.ts", "edits": [{"start": 0, "end": 0, "text": "// hi\n"}]}]
    )
    workflow = captured_workflow("VS Code Demo", events)

    assert workflow["routes"][0]["type"] == "adapter"
    assert workflow["routes"][0]["adapter"] == "vscode"
    assert workflow["signals"]["captured_events"] == events
    assert "visual" not in workflow["fallback_order"]


def test_three_vscode_demo_vaults_load_as_adapter_workflows() -> None:
    roots = sorted((ROOT / "demo-vaults").glob("vscode-*"))

    assert len(roots) >= 3
    for root in roots:
        workflows = Vault(root).list_workflows()
        assert len(workflows) == 1
        route = workflows[0]["routes"][0]
        assert route["type"] == "adapter"
        assert route["adapter"] == "vscode"
        assert "visual" not in workflows[0]["fallback_order"]
