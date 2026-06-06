from __future__ import annotations

import json
from pathlib import Path

from engine.vault import Vault


def make_vault(tmp_path: Path) -> Vault:
    return Vault(tmp_path)


def workflow_dict() -> dict:
    return {
        "id": "test-workflow-001",
        "name": "Test Workflow",
        "app": "ComfyUI",
        "routes": [{"type": "api", "endpoint": "http://127.0.0.1:8188/prompt"}],
        "fallback_order": ["api", "ask"],
        "verification": {"type": "file_exists", "path": "{output_path}"},
        "calls": [],
        "depends_on": [],
        "body": "# Test Workflow\n\nA saved workflow.",
    }


def test_load_workflow_from_markdown(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)
    saved_path = vault.save_workflow(workflow_dict())

    loaded = vault.load_workflow(saved_path)

    assert loaded["id"] == "test-workflow-001"
    assert loaded["name"] == "Test Workflow"
    assert loaded["body"].startswith("# Test Workflow")


def test_save_workflow_dict(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)

    saved_path = vault.save_workflow(workflow_dict())

    assert saved_path.exists()
    assert saved_path.name == "test-workflow-001.md"


def test_list_workflows(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)
    vault.save_workflow(workflow_dict())

    workflows = vault.list_workflows()

    assert [workflow["id"] for workflow in workflows] == ["test-workflow-001"]


def test_find_workflow_by_id_or_name(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)
    vault.save_workflow(workflow_dict())

    assert vault.find_workflow("test-workflow-001")["name"] == "Test Workflow"
    assert vault.find_workflow("test workflow")["id"] == "test-workflow-001"


def test_log_run(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)
    workflow = workflow_dict()

    log_path = vault.log_run(workflow, {"success": True, "output": "/tmp/test.png"})

    assert log_path.exists()
    payload = json.loads(log_path.read_text(encoding="utf-8"))
    assert payload["workflow_id"] == "test-workflow-001"
    assert payload["result"]["success"] is True
