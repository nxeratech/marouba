from __future__ import annotations

import json
from pathlib import Path

from engine.distillation import distill_after_session
from engine.vault import Vault
from scripts.replay import replay_workflow


def workflow_dict() -> dict:
    return {
        "id": "distill-test",
        "name": "Distill Test",
        "app": "Ableton Live",
        "description": "A workflow used for distillation tests.",
        "params": [{"name": "bpm", "type": "number"}],
        "tags": ["ableton", "test"],
        "routes": [{"type": "cli", "command": "echo secret-route-detail"}],
        "fallback_order": ["cli", "ask"],
        "verification": {"type": "none"},
        "body": "# Distill Test\n\nRaw body should not reach AI.",
    }


def test_ai_off_is_mechanical_noop(tmp_path: Path, monkeypatch) -> None:
    vault = Vault(tmp_path)
    workflow = workflow_dict()
    vault.save_workflow(workflow)
    (vault.signals_dir / "distill-test.json").write_text('{"moves": 2}', encoding="utf-8")
    monkeypatch.delenv("MAROUBA_AI_DISTILLATION", raising=False)

    calls = []
    result = distill_after_session(vault, workflow, model=lambda payload: calls.append(payload) or {})

    assert result == {"status": "skipped", "reason": "ai_distillation_off"}
    assert calls == []
    assert not (vault.vault_dir / "annotations").exists()


def test_ai_on_reads_only_signals_and_workflow_summary_then_writes_annotations(
    tmp_path: Path, monkeypatch
) -> None:
    vault = Vault(tmp_path)
    workflow = workflow_dict()
    vault.save_workflow(workflow)
    (vault.signals_dir / "distill-test.json").write_text(
        json.dumps({"repeat_gaps_ms": [120, 118], "route_success": ["cli"]}),
        encoding="utf-8",
    )
    monkeypatch.setenv("MAROUBA_AI_DISTILLATION", "on")

    seen = []

    def fake_model(payload: dict) -> dict:
        seen.append(payload)
        return {"patterns": [{"name": "steady repeated gap", "confidence": 0.91}]}

    result = distill_after_session(vault, workflow, model=fake_model)

    assert result["status"] == "annotated"
    assert len(seen) == 1
    assert set(seen[0]) == {"workflow_summary", "signals"}
    assert seen[0]["signals"] == {"repeat_gaps_ms": [120, 118], "route_success": ["cli"]}
    assert seen[0]["workflow_summary"] == {
        "id": "distill-test",
        "name": "Distill Test",
        "app": "Ableton Live",
        "description": "A workflow used for distillation tests.",
        "params": [{"name": "bpm", "type": "number"}],
        "tags": ["ableton", "test"],
        "fallback_order": ["cli", "ask"],
        "verification": {"type": "none"},
        "route_count": 1,
        "step_count": 0,
    }
    assert "secret-route-detail" not in json.dumps(seen[0], sort_keys=True)
    assert "Raw body should not reach AI" not in json.dumps(seen[0], sort_keys=True)

    annotation = json.loads(Path(result["path"]).read_text(encoding="utf-8"))
    assert annotation["source"]["inputs"] == ["signals", "workflow_summary"]
    assert annotation["annotations"]["patterns"][0]["name"] == "steady repeated gap"


def test_replay_runs_post_session_distillation_when_enabled(tmp_path: Path, monkeypatch) -> None:
    vault = Vault(tmp_path)
    workflow = workflow_dict()
    output = tmp_path / "replay.txt"
    workflow["routes"] = [
        {
            "type": "cli",
            "command": f'"{__import__("sys").executable}" -c "from pathlib import Path; Path(r\'{output}\').write_text(\'ok\', encoding=\'utf-8\')"',
        }
    ]
    vault.save_workflow(workflow)
    (vault.signals_dir / "distill-test.json").write_text('{"tempo": "steady"}', encoding="utf-8")
    model_output = tmp_path / "model-output.json"
    model_script = tmp_path / "model.py"
    model_script.write_text(
        (
            "import json, pathlib, sys\n"
            "payload = json.loads(sys.stdin.read())\n"
            f"pathlib.Path(r'{model_output}').write_text(json.dumps(payload, sort_keys=True), encoding='utf-8')\n"
            "print(json.dumps({'patterns': [{'name': 'replay-distilled'}]}))\n"
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("MAROUBA_AI_DISTILLATION", "on")
    monkeypatch.setenv("MAROUBA_AI_DISTILLATION_COMMAND", f'"{__import__("sys").executable}" "{model_script}"')

    exit_code = replay_workflow("distill-test", {}, root=tmp_path, no_repair=True)

    assert exit_code == 0
    assert output.read_text(encoding="utf-8") == "ok"
    annotation_path = vault.vault_dir / "annotations" / "distill-test.patterns.json"
    annotation = json.loads(annotation_path.read_text(encoding="utf-8"))
    assert annotation["annotations"]["patterns"][0]["name"] == "replay-distilled"
    model_payload = json.loads(model_output.read_text(encoding="utf-8"))
    assert set(model_payload) == {"signals", "workflow_summary"}
