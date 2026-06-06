from __future__ import annotations

from pathlib import Path

from engine.repairer import Repairer
from engine.vault import Vault


def workflow_dict() -> dict:
    return {
        "id": "repair-test-001",
        "name": "Repair Test",
        "app": "ComfyUI",
        "routes": [{"type": "api", "endpoint": "http://127.0.0.1:8188/prompt"}],
        "fallback_order": ["api", "ask"],
        "verification": {"type": "file_exists", "path": "{output_path}"},
        "calls": [],
        "depends_on": [],
        "body": "# Repair Test\n",
    }


def test_repair_loop_asks_once_updates_vault_and_does_not_ask_again(tmp_path: Path) -> None:
    vault = Vault(tmp_path)
    workflow = workflow_dict()
    vault.save_workflow(workflow)
    failures = [{"route_type": "api", "error": "connection refused", "success": False}]
    prompts = []

    repairer = Repairer(vault, input_fn=lambda prompt: prompts.append(prompt) or "")
    first_result = repairer.repair(workflow, {"output_path": "/tmp/repaired.png"}, failures, step_label="X")

    assert first_result["success"] is True
    assert first_result["repair"] == "recorded"
    assert len(prompts) == 1
    assert prompts[0] == "Step X failed. Please perform the action manually, then press Enter."

    saved = vault.find_workflow("repair-test-001")
    assert saved is not None
    assert saved["fallback_order"][0] == "manual_repair"
    assert saved["routes"][0]["type"] == "manual_repair"

    second_prompts = []
    second_repairer = Repairer(vault, input_fn=lambda prompt: second_prompts.append(prompt) or "")
    second_result = second_repairer.repair(saved, {"output_path": "/tmp/repaired.png"}, failures, step_label="X")

    assert second_result["success"] is True
    assert second_result["repair"] == "already_recorded"
    assert second_prompts == []
