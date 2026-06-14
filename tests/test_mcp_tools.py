from __future__ import annotations

import importlib.util
import sys
import zipfile
from pathlib import Path

from engine.vault import Vault


ROOT = Path(__file__).resolve().parents[1]
MCP_TOOLS_PATH = ROOT / "mcp" / "tools.py"


def load_mcp_tools():
    spec = importlib.util.spec_from_file_location("marouba_mcp_tools", MCP_TOOLS_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def workflow_dict() -> dict:
    return {
        "id": "mcp-test-workflow",
        "name": "MCP Test Workflow",
        "app": "TestApp",
        "description": "A workflow used by the MCP tests.",
        "params": [{"name": "output_path", "type": "string", "required": False}],
        "tags": ["mcp", "test"],
        "author": "nxeratech",
        "created": "2026-06-07",
        "routes": [{"type": "cli", "command": f"{sys.executable} --version"}],
        "fallback_order": ["cli", "ask"],
        "verification": {"type": "none"},
        "steps": [
            {
                "id": "step_001",
                "type": "click",
                "intent": "Click the test button.",
                "routes": [
                    {
                        "type": "gesture",
                        "events": [
                            {
                                "kind": "mousedown",
                                "x": 10,
                                "y": 20,
                                "normalized_x": 0.1,
                                "normalized_y": 0.2,
                            }
                        ],
                    }
                ],
            }
        ],
        "calls": [],
        "depends_on": [],
        "body": "# MCP Test Workflow\n\nRaw workflow body.",
    }


def test_mcp_list_workflows_reads_vault_frontmatter(tmp_path: Path, monkeypatch) -> None:
    vault = Vault(tmp_path)
    vault.save_workflow(workflow_dict())
    monkeypatch.setenv("MAROUBA_VAULT_PATH", str(tmp_path / "vault"))

    tools = load_mcp_tools()
    workflows = tools.list_workflows()

    assert workflows == [
        {
            "id": "mcp-test-workflow",
            "name": "MCP Test Workflow",
            "app": "TestApp",
            "description": "A workflow used by the MCP tests.",
            "params": [{"name": "output_path", "type": "string", "required": False}],
            "tags": ["mcp", "test"],
            "path": str(tmp_path / "vault" / "workflows" / "mcp-test-workflow.md"),
        }
    ]


def test_mcp_read_workflow_summary_is_depth_gated(tmp_path: Path, monkeypatch) -> None:
    vault = Vault(tmp_path)
    vault.save_workflow(workflow_dict())
    monkeypatch.setenv("MAROUBA_VAULT_PATH", str(tmp_path / "vault"))

    tools = load_mcp_tools()
    payload = tools.read_workflow("mcp-test-workflow")

    assert payload["id"] == "mcp-test-workflow"
    assert payload["depth"] == "summary"
    assert "description: A workflow used by the MCP tests." in payload["content"]
    assert "intent: A workflow used by the MCP tests." in payload["content"]
    assert "events" not in payload["content"]
    assert len(payload["content"].split()) <= 400


def test_mcp_read_workflow_full_chunks_without_raw_coordinate_streams(
    tmp_path: Path, monkeypatch
) -> None:
    vault = Vault(tmp_path)
    vault.save_workflow(workflow_dict())
    monkeypatch.setenv("MAROUBA_VAULT_PATH", str(tmp_path / "vault"))

    tools = load_mcp_tools()
    payload = tools.read_workflow("mcp-test-workflow", depth="full")
    text = "\n".join(chunk["text"] for chunk in payload["chunks"])

    assert payload["depth"] == "full"
    assert '{"events_omitted":"1 raw gesture events","type":"gesture"}' in text
    assert "normalized_x" not in text
    assert '"x":10' not in text


def test_mcp_replay_workflow_uses_existing_replay_logic(tmp_path: Path, monkeypatch) -> None:
    vault = Vault(tmp_path)
    vault.save_workflow(workflow_dict())
    monkeypatch.setenv("MAROUBA_VAULT_PATH", str(tmp_path / "vault"))

    tools = load_mcp_tools()
    result = tools.replay_workflow("mcp-test-workflow", params={}, no_repair=True)

    assert result["success"] is True
    assert result["exit_code"] == 0
    assert "Loading workflow: mcp-test-workflow" in result["stdout"]


def test_mcp_server_exposes_all_seven_tools() -> None:
    server_module = load_mcp_server()

    for name in [
        "list_workflows",
        "search_workflows",
        "read_workflow",
        "replay_workflow",
        "teach_workflow",
        "compose_workflow",
        "install_workflow",
    ]:
        assert callable(getattr(server_module, name))


def test_mcp_search_teach_and_compose_confirmation(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MAROUBA_VAULT_PATH", str(tmp_path / "vault"))
    tools = load_mcp_tools()

    taught = tools.teach_workflow(
        name="Teach Browser Save",
        app="TestApp",
        actions=[{"type": "cli", "command": f"{sys.executable} --version"}],
        description="A taught workflow.",
    )
    assert taught["status"] == "saved"

    matches = tools.search_workflows("browser save", app="TestApp")
    assert [match["id"] for match in matches] == ["teach-browser-save"]

    preview = tools.compose_workflow(
        name="Composed Param Replay",
        app="TestApp",
        intent="Preview only.",
        routes=[{"type": "cli", "command": f"{sys.executable} --version"}],
    )
    assert preview["status"] == "needs_confirmation"
    assert not (tmp_path / "vault" / "workflows" / "composed-param-replay.md").exists()

    saved = tools.compose_workflow(
        name="Composed Param Replay",
        app="TestApp",
        intent="Save after confirmation.",
        routes=[{"type": "cli", "command": f"{sys.executable} --version"}],
        confirm_save=True,
    )
    assert saved["status"] == "saved"
    assert (tmp_path / "vault" / "workflows" / "composed-param-replay.md").exists()


def test_mcp_replay_substitutes_parameter_slots(tmp_path: Path, monkeypatch) -> None:
    vault = Vault(tmp_path)
    output_path = tmp_path / "params.json"
    workflow = workflow_dict()
    workflow.update(
        {
            "id": "param-slot-replay",
            "name": "Param Slot Replay",
            "params": [
                {"name": "key", "type": "string", "required": True},
                {"name": "bpm", "type": "number", "required": True},
            ],
            "routes": [
                {
                    "type": "cli",
                    "command": (
                        f'"{sys.executable}" -c "import pathlib; '
                        f'pathlib.Path(r\'{output_path}\').write_text(\'{{key}}|{{bpm}}\', encoding=\'utf-8\')"'
                    ),
                }
            ],
            "fallback_order": ["cli", "ask"],
            "steps": [],
        }
    )
    vault.save_workflow(workflow)
    monkeypatch.setenv("MAROUBA_VAULT_PATH", str(tmp_path / "vault"))

    tools = load_mcp_tools()
    result = tools.replay_workflow("param-slot-replay", params={"key": "F minor", "bpm": 138}, no_repair=True)

    assert result["success"] is True
    assert output_path.read_text(encoding="utf-8") == "F minor|138"


def test_mcp_install_workflow_refuses_unsigned_pack(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MAROUBA_VAULT_PATH", str(tmp_path / "vault"))
    bundle = tmp_path / "unsigned.mwf"
    with zipfile.ZipFile(bundle, "w") as archive:
        archive.writestr("workflow.md", "---\nid: unsigned\nname: Unsigned\n---\n")
        archive.writestr("manifest.json", "{}")

    tools = load_mcp_tools()
    result = tools.install_workflow(str(bundle))

    assert result["ok"] is False
    assert result["status"] == "refused"
    assert "missing workflow.md, workflow.sig, or manifest.json" in result["error"].lower()


def load_mcp_server():
    server_path = ROOT / "mcp" / "server.py"
    spec = importlib.util.spec_from_file_location("marouba_mcp_server", server_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
