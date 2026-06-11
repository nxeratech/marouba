from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import frontmatter
import yaml


CURRENT_VAULT_SPEC_VERSION = 3
SUPPORTED_VAULT_SPEC_VERSIONS = {1, 2, 3}


class VaultVersionError(ValueError):
    pass


class Vault:
    """Read and write Marouba's human-readable workflow vault."""

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root) if root else Path(__file__).resolve().parents[1]
        self.vault_dir = self.root / "vault"
        self.workflows_dir = self.vault_dir / "workflows"
        self.elements_dir = self.vault_dir / "elements"
        self.runs_dir = self.vault_dir / "runs"
        self.signals_dir = self.vault_dir / "signals"
        self.workflows_dir.mkdir(parents=True, exist_ok=True)
        self.elements_dir.mkdir(parents=True, exist_ok=True)
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self.signals_dir.mkdir(parents=True, exist_ok=True)

    def load_workflow(self, path_or_id: str | Path) -> dict[str, Any]:
        path = Path(path_or_id)
        if not path.exists():
            workflow = self.find_workflow(str(path_or_id))
            if workflow is None:
                raise FileNotFoundError(f"Workflow not found: {path_or_id}")
            return workflow

        post = frontmatter.load(path)
        data = dict(post.metadata)
        sidecar = steps_sidecar_path(path)
        sidecar_body = sidecar.read_text(encoding="utf-8") if sidecar.exists() else ""
        data["body"] = post.content if not sidecar_body else f"{post.content.rstrip()}\n\n{sidecar_body}".strip() + "\n"
        data["_path"] = str(path)
        version = validate_vault_spec_version(data.get("vault_spec_version"))
        data["vault_spec_version"] = version
        normalize_gesture_routes(data)
        steps = parse_workflow_steps(sidecar_body or post.content)
        if steps:
            data["steps"] = normalize_steps(steps, version)
            if "routes" not in data and data["steps"]:
                first_routes = data["steps"][0].get("routes")
                if isinstance(first_routes, list):
                    data["routes"] = first_routes
        return data

    def save_workflow(self, workflow: dict[str, Any], filename: str | None = None) -> Path:
        data = dict(workflow)
        body = str(data.pop("body", "") or "")
        data.pop("_path", None)
        steps = data.pop("steps", None)
        workflow_id = data.get("id")
        if not filename:
            if not workflow_id:
                raise ValueError("Workflow must include an id when filename is omitted")
            filename = f"{sanitize_workflow_id(str(workflow_id))}.md"
        path = self.workflows_dir / filename
        human_body, steps_body = split_human_and_steps_body(body)
        if steps:
            steps_body = write_workflow_steps_markdown(normalize_steps(steps, int(data.get("vault_spec_version") or 1)))
        post = frontmatter.Post(human_body, **data)
        path.write_text(frontmatter.dumps(post), encoding="utf-8")
        sidecar = steps_sidecar_path(path)
        if steps_body.strip():
            sidecar.write_text(steps_body, encoding="utf-8")
        elif sidecar.exists():
            sidecar.unlink()
        self.regenerate_index_and_graph()
        return path

    def migrate_workflow_to_v3(self, path_or_id: str | Path, filename: str | None = None) -> Path:
        source_path = Path(path_or_id)
        workflow = self.load_workflow(path_or_id)
        migrated = dict(workflow)
        migrated["vault_spec_version"] = CURRENT_VAULT_SPEC_VERSION
        migrated.setdefault("compat", {})["legacy_gesture_routes"] = True
        if "steps" in migrated:
            migrated["steps"] = normalize_steps(migrated["steps"], CURRENT_VAULT_SPEC_VERSION)
            migrated["body"] = write_workflow_steps_markdown(migrated["steps"])
        if filename is None:
            stem = source_path.stem if source_path.exists() else sanitize_workflow_id(str(workflow.get("id", "workflow")))
            filename = f"{stem}-v3.md"
        return self.save_workflow(migrated, filename=filename)

    def list_workflows(self) -> list[dict[str, Any]]:
        workflows = []
        for path in sorted(self.workflows_dir.glob("*.md")):
            if is_steps_sidecar(path):
                continue
            workflows.append(self.load_workflow(path))
        return workflows

    def list_vaults(self) -> list[dict[str, Any]]:
        workflows = []
        for path in sorted(self.workflows_dir.rglob("*.md")):
            if is_steps_sidecar(path):
                continue
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
        self.regenerate_index_and_graph()
        return path

    def regenerate_index_and_graph(self) -> None:
        workflows = []
        for path in sorted(self.workflows_dir.glob("*.md")):
            if is_steps_sidecar(path):
                continue
            try:
                workflow = self.load_workflow(path)
            except Exception:
                continue
            workflows.append((path, workflow))

        lines = []
        nodes = []
        links = []
        element_paths: dict[str, Path] = {}
        run_nodes = []
        for path, workflow in workflows:
            workflow_id = str(workflow.get("id") or path.stem)
            app = str(workflow.get("app") or "Unknown")
            tags = workflow.get("tags") or []
            if not isinstance(tags, list):
                tags = [str(tags)]
            intent = one_line_intent(workflow)
            line = bounded_index_line(workflow_id, app, tags, intent)
            lines.append(line)
            nodes.append(
                {
                    "id": f"workflow:{workflow_id}",
                    "type": "workflow",
                    "path": slash_path(path.relative_to(self.vault_dir)),
                    "steps_path": slash_path(steps_sidecar_path(path).relative_to(self.vault_dir)),
                    "app": app,
                    "tags": tags,
                    "intent": intent,
                }
            )
            for element in [app, *tags]:
                if not str(element).strip():
                    continue
                element_id = f"element:{slugify_element(str(element))}"
                element_path = self.elements_dir / f"{slugify_element(str(element))}.md"
                element_paths[element_id] = element_path
                links.append({"from": f"workflow:{workflow_id}", "to": element_id, "type": "uses"})
            for run_path in sorted(self.runs_dir.glob(f"*-{workflow_id}.json")):
                run_id = f"run:{run_path.stem}"
                run_nodes.append({"id": run_id, "type": "run", "path": slash_path(run_path.relative_to(self.vault_dir))})
                links.append({"from": f"workflow:{workflow_id}", "to": run_id, "type": "ran"})

        for element_id, element_path in sorted(element_paths.items()):
            label = element_id.split(":", 1)[1]
            element_path.write_text(f"# {label}\n", encoding="utf-8")
            nodes.append({"id": element_id, "type": "element", "path": slash_path(element_path.relative_to(self.vault_dir))})
        nodes.extend(run_nodes)
        self.vault_dir.mkdir(parents=True, exist_ok=True)
        (self.vault_dir / "index.md").write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        (self.vault_dir / "graph.json").write_text(
            json.dumps({"nodes": nodes, "links": links}, indent=2, sort_keys=True),
            encoding="utf-8",
        )


def sanitize_workflow_id(workflow_id: str) -> str:
    sanitized = re.sub(r"[^a-z0-9\-_]", "", workflow_id.casefold())
    return sanitized or "workflow"


def is_steps_sidecar(path: Path) -> bool:
    return path.name.endswith(".steps.md")


def steps_sidecar_path(path: Path) -> Path:
    if is_steps_sidecar(path):
        return path
    return path.with_name(f"{path.stem}.steps.md")


def split_human_and_steps_body(body: str) -> tuple[str, str]:
    match = re.search(r"(?m)^## Steps\b", body)
    if not match:
        return body, ""
    return body[: match.start()].rstrip() + "\n", body[match.start() :].strip() + "\n"


def one_line_intent(workflow: dict[str, Any]) -> str:
    description = str(workflow.get("description") or "").strip()
    if description:
        return " ".join(description.split())
    body = re.sub(r"```.*?```", "", str(workflow.get("body") or ""), flags=re.S)
    body = re.sub(r"#+\s*", "", body)
    return " ".join(body.split())[:160] or "Replay recorded workflow."


def bounded_index_line(workflow_id: str, app: str, tags: list[Any], intent: str) -> str:
    tags_text = ",".join(str(tag) for tag in tags[:4]) or "-"
    prefix = f"[[workflows/{workflow_id}|{workflow_id}]] · {app} · {tags_text} ·"
    words = intent.split()
    while words and len(f"{prefix} {' '.join(words)}".split()) > 40:
        words.pop()
    return f"{prefix} {' '.join(words) if words else intent.split()[0] if intent.split() else 'workflow'}"


def slugify_element(value: str) -> str:
    slug = re.sub(r"[^a-z0-9\-_]+", "-", value.casefold()).strip("-")
    return slug or "element"


def slash_path(path: Path) -> str:
    return path.as_posix()


def validate_vault_spec_version(value: Any) -> int:
    if value is None:
        return 1
    try:
        version = int(value)
    except (TypeError, ValueError) as exc:
        raise VaultVersionError(f"Unsupported vault_spec_version {value!r}; supported versions are 1, 2, 3") from exc
    if version not in SUPPORTED_VAULT_SPEC_VERSIONS:
        raise VaultVersionError(f"Unsupported vault_spec_version {version}; supported versions are 1, 2, 3")
    return version


def normalize_gesture_routes(workflow: dict[str, Any]) -> None:
    routes = workflow.get("routes")
    if not isinstance(routes, list):
        return
    for route in routes:
        if isinstance(route, dict) and "events" in route and "type" not in route:
            route["type"] = "gesture"


def parse_workflow_steps(body: str) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    in_block = False
    block: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            if in_block:
                parsed = parse_step_block("\n".join(block))
                if isinstance(parsed, dict):
                    steps.append(parsed)
                block = []
                in_block = False
            elif stripped in {"```yaml", "```json"}:
                in_block = True
            continue
        if in_block:
            block.append(line)
    return steps


def parse_step_block(block: str) -> Any:
    try:
        return json.loads(block)
    except json.JSONDecodeError:
        return yaml.safe_load(block)


def normalize_steps(steps: list[dict[str, Any]], version: int) -> list[dict[str, Any]]:
    normalized = []
    for step in steps:
        step_copy = dict(step)
        routes = step_copy.get("routes")
        if isinstance(routes, list):
            for route in routes:
                if isinstance(route, dict) and "events" in route and "type" not in route:
                    route["type"] = "gesture"
        if version >= 3:
            step_copy.setdefault("signals", default_signals())
        normalized.append(step_copy)
    return normalized


def default_signals() -> dict[str, Any]:
    return {"dwell_before_ms": None, "revisit_of": None, "undo_cluster": None}


def write_workflow_steps_markdown(steps: list[dict[str, Any]]) -> str:
    parts = ["## Steps"]
    for index, step in enumerate(steps, start=1):
        intent = step.get("intent") or "Replay recorded step."
        parts.append(f"### Step {index:03} - {intent}\n")
        parts.append("```yaml")
        parts.append(json.dumps(step, indent=2, sort_keys=True))
        parts.append("```")
    return "\n\n".join(parts).strip() + "\n"
