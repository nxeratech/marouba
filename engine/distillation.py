from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from engine.vault import Vault


ModelFn = Callable[[dict[str, Any]], dict[str, Any]]


def ai_distillation_enabled() -> bool:
    value = os.environ.get("MAROUBA_AI_DISTILLATION", "")
    return value.strip().casefold() in {"1", "true", "yes", "on"}


def distill_after_session(
    vault: Vault,
    workflow: dict[str, Any],
    model: ModelFn | None = None,
) -> dict[str, Any]:
    workflow_id = str(workflow.get("id") or "").strip()
    if not workflow_id:
        return {"status": "skipped", "reason": "workflow_id_missing"}
    if not ai_distillation_enabled():
        return {"status": "skipped", "reason": "ai_distillation_off"}

    signals_path = find_signals_file(vault, workflow_id)
    if signals_path is None:
        return {"status": "skipped", "reason": "signals_missing", "workflow_id": workflow_id}

    payload = {
        "workflow_summary": workflow_summary_only(workflow),
        "signals": read_signals(signals_path),
    }
    model = model or command_model_from_env()
    if model is None:
        return {"status": "skipped", "reason": "model_unavailable", "workflow_id": workflow_id}

    annotations = model(payload)
    if not isinstance(annotations, dict):
        raise TypeError("AI distillation model must return a JSON object")

    output_path = annotation_path(vault, workflow_id)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    body = {
        "workflow_id": workflow_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "signals_path": str(signals_path),
            "inputs": ["signals", "workflow_summary"],
        },
        "annotations": annotations,
    }
    output_path.write_text(json.dumps(body, indent=2, sort_keys=True), encoding="utf-8")
    return {"status": "annotated", "workflow_id": workflow_id, "path": str(output_path)}


def workflow_summary_only(workflow: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": workflow.get("id"),
        "name": workflow.get("name"),
        "app": workflow.get("app"),
        "description": workflow.get("description", ""),
        "params": workflow.get("params", []),
        "tags": workflow.get("tags", []),
        "fallback_order": workflow.get("fallback_order", []),
        "verification": workflow.get("verification", {"type": "none"}),
        "route_count": len(workflow.get("routes", []) or []),
        "step_count": len(workflow.get("steps", []) or []),
    }


def find_signals_file(vault: Vault, workflow_id: str) -> Path | None:
    for suffix in (".json", ".jsonl"):
        path = vault.signals_dir / f"{workflow_id}{suffix}"
        if path.exists():
            return path
    return None


def read_signals(path: Path) -> Any:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    return json.loads(text)


def annotation_path(vault: Vault, workflow_id: str) -> Path:
    return vault.vault_dir / "annotations" / f"{workflow_id}.patterns.json"


def command_model_from_env() -> ModelFn | None:
    command = os.environ.get("MAROUBA_AI_DISTILLATION_COMMAND", "").strip()
    if not command:
        return None

    def run(payload: dict[str, Any]) -> dict[str, Any]:
        completed = subprocess.run(
            command,
            input=json.dumps(payload),
            shell=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip()
            raise RuntimeError(f"AI distillation command failed: {detail}")
        return json.loads(completed.stdout or "{}")

    return run
