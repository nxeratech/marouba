from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import frontmatter


class Vault:
    """Read and write Marouba's human-readable workflow vault."""

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root) if root else Path(__file__).resolve().parents[1]
        self.vault_dir = self.root / "vault"
        self.workflows_dir = self.vault_dir / "workflows"
        self.runs_dir = self.vault_dir / "runs"
        self.workflows_dir.mkdir(parents=True, exist_ok=True)
        self.runs_dir.mkdir(parents=True, exist_ok=True)

    def load_workflow(self, path_or_id: str | Path) -> dict[str, Any]:
        path = Path(path_or_id)
        if not path.exists():
            workflow = self.find_workflow(str(path_or_id))
            if workflow is None:
                raise FileNotFoundError(f"Workflow not found: {path_or_id}")
            return workflow

        post = frontmatter.load(path)
        data = dict(post.metadata)
        data["body"] = post.content
        data["_path"] = str(path)
        return data

    def save_workflow(self, workflow: dict[str, Any], filename: str | None = None) -> Path:
        data = dict(workflow)
        body = str(data.pop("body", "") or "")
        data.pop("_path", None)
        workflow_id = data.get("id")
        if not filename:
            if not workflow_id:
                raise ValueError("Workflow must include an id when filename is omitted")
            filename = f"{sanitize_workflow_id(str(workflow_id))}.md"
        path = self.workflows_dir / filename
        post = frontmatter.Post(body, **data)
        path.write_text(frontmatter.dumps(post), encoding="utf-8")
        return path

    def list_workflows(self) -> list[dict[str, Any]]:
        workflows = []
        for path in sorted(self.workflows_dir.glob("*.md")):
            workflows.append(self.load_workflow(path))
        return workflows

    def list_vaults(self) -> list[dict[str, Any]]:
        workflows = []
        for path in sorted(self.workflows_dir.rglob("*.md")):
            workflow = self.load_workflow(path)
            workflows.append(
                {
                    "id": workflow.get("id") or path.stem,
                    "name": workflow.get("name") or path.stem,
                    "app": workflow.get("app"),
                    "description": workflow.get("description", ""),
                    "params": workflow.get("params", []),
                    "tags": workflow.get("tags", []),
                    "path": str(path),
                }
            )
        return workflows

    def find_workflow(self, workflow_id_or_name: str) -> dict[str, Any] | None:
        needle = workflow_id_or_name.casefold()
        for workflow in self.list_workflows():
            if str(workflow.get("id", "")).casefold() == needle:
                return workflow
            if str(workflow.get("name", "")).casefold() == needle:
                return workflow
        return None

    def log_run(self, workflow: dict[str, Any] | str, result: dict[str, Any]) -> Path:
        workflow_id = workflow if isinstance(workflow, str) else workflow.get("id", "unknown")
        now = datetime.now(timezone.utc)
        date_prefix = now.strftime("%Y-%m-%d")
        path = self.runs_dir / f"{date_prefix}-{workflow_id}.json"

        payload = {
            "workflow_id": workflow_id,
            "logged_at": now.isoformat(),
            "result": result,
        }
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return path


def sanitize_workflow_id(workflow_id: str) -> str:
    sanitized = re.sub(r"[^a-z0-9\-_]", "", workflow_id.casefold())
    return sanitized or "workflow"
