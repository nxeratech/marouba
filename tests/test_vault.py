from __future__ import annotations

import json
from pathlib import Path

from engine.vault import Vault, VaultVersionError


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

def v3_workflow_markdown() -> str:
    return (Path(__file__).resolve().parent / "fixtures" / "vault_v3_api_uia_gesture.md").read_text(encoding="utf-8")


def test_v3_workflow_with_api_uia_gesture_routes_parses(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)
    path = vault.workflows_dir / "v3-api-route.md"
    path.write_text(v3_workflow_markdown(), encoding="utf-8")

    workflow = vault.load_workflow(path)

    assert workflow["vault_spec_version"] == 3
    assert len(workflow["steps"]) == 1
    routes = workflow["steps"][0]["routes"]
    assert [route["type"] for route in routes] == ["api", "uia", "gesture"]
    assert routes[0] == {
        "type": "api",
        "api": "ableton_lom",
        "target": "track:1/device:Auto Filter",
        "device": "Auto Filter",
        "param": "Frequency",
        "value": 0.73,
        "display_value": "3.42 kHz",
    }
    assert workflow["steps"][0]["signals"]["dwell_before_ms"] == 1200


def test_v2_workflow_load_does_not_mutate_original_bytes(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)
    path = vault.workflows_dir / "v2-legacy.md"
    original = """---
vault_spec_version: 2
id: v2-legacy
name: V2 Legacy
app: Paint
routes: []
fallback_order: [gesture, ask]
verification: {"type":"none"}
---

# V2 Legacy

## Steps

### Step 001 - Gesture

```yaml
{"id":"step_001","type":"legacy_gesture_sequence","intent":"Replay.","routes":[{"type":"gesture","events":[]}]}
```
"""
    path.write_text(original, encoding="utf-8")
    before = path.read_bytes()

    workflow = vault.load_workflow(path)

    assert workflow["vault_spec_version"] == 2
    assert path.read_bytes() == before


def test_unknown_vault_version_refused_with_readable_error(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)
    path = vault.workflows_dir / "future.md"
    path.write_text("---\nvault_spec_version: 99\nid: future\n---\n", encoding="utf-8")

    try:
        vault.load_workflow(path)
    except VaultVersionError as error:
        assert "Unsupported vault_spec_version 99" in str(error)
        assert "supported versions are 1, 2, 3" in str(error)
    else:
        raise AssertionError("future vault version should be refused")


def test_migrator_writes_v3_copy_without_mutating_original(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)
    source = vault.save_workflow(workflow_dict())
    before = source.read_bytes()

    migrated = vault.migrate_workflow_to_v3(source)

    assert migrated != source
    assert migrated.name == "test-workflow-001-v3.md"
    assert source.read_bytes() == before
    loaded = vault.load_workflow(migrated)
    assert loaded["vault_spec_version"] == 3
