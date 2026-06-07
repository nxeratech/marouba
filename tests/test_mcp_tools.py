from __future__ import annotations

import importlib.util
import sys
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


def test_mcp_read_workflow_returns_raw_markdown(tmp_path: Path, monkeypatch) -> None:
    vault = Vault(tmp_path)
    saved_path = vault.save_workflow(workflow_dict())
    monkeypatch.setenv("MAROUBA_VAULT_PATH", str(tmp_path / "vault"))

    tools = load_mcp_tools()
    raw = tools.read_workflow("mcp-test-workflow")

    assert raw == saved_path.read_text(encoding="utf-8")
    assert "# MCP Test Workflow" in raw


def test_mcp_replay_workflow_uses_existing_replay_logic(tmp_path: Path, monkeypatch) -> None:
    vault = Vault(tmp_path)
    vault.save_workflow(workflow_dict())
    monkeypatch.setenv("MAROUBA_VAULT_PATH", str(tmp_path / "vault"))

    tools = load_mcp_tools()
    result = tools.replay_workflow("mcp-test-workflow", params={}, no_repair=True)

    print("DEBUG result:", result)
    assert result["success"] is True
    assert result["exit_code"] == 0
    assert "Loading workflow: mcp-test-workflow" in result["stdout"]
