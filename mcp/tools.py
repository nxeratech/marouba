from __future__ import annotations

import contextlib
import io
import json
import os
import re
import shutil
import sys
import textwrap
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, TypeVar

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.executor import Executor
from engine.router import Router
from engine.vault import Vault
from marketplace.installer import InstallError, install_bundle
from scripts.replay import replay_workflow as run_replay_workflow

T = TypeVar("T")
MCP_TOKEN_LOG_VERSION = 1


def configured_vault_path() -> Path:
    return Path(os.environ.get("MAROUBA_VAULT_PATH", "./vault")).expanduser().resolve()


def configured_root() -> Path:
    vault_path = configured_vault_path()
    return vault_path.parent if vault_path.name == "vault" else ROOT


def vault() -> Vault:
    root = configured_root()
    instance = Vault(root)
    instance.vault_dir = configured_vault_path()
    instance.workflows_dir = instance.vault_dir / "workflows"
    instance.runs_dir = instance.vault_dir / "runs"
    instance.workflows_dir.mkdir(parents=True, exist_ok=True)
    instance.runs_dir.mkdir(parents=True, exist_ok=True)
    return instance


def token_log_path() -> Path:
    configured = os.environ.get("MAROUBA_MCP_TOKEN_LOG")
    if configured:
        path = Path(configured).expanduser().resolve()
    else:
        path = configured_vault_path() / "runs" / "mcp_token_usage.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def instrument_mcp_call(tool: str, args: dict[str, Any], call: Callable[[], T]) -> T:
    started = time.perf_counter()
    status = "ok"
    result: Any = None
    error: str | None = None
    try:
        result = call()
        return result
    except Exception as exc:
        status = "error"
        error = str(exc)
        raise
    finally:
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        log_mcp_token_usage(tool, args, result, status=status, error=error, elapsed_ms=elapsed_ms)


def log_mcp_token_usage(
    tool: str,
    args: dict[str, Any],
    result: Any,
    status: str,
    error: str | None,
    elapsed_ms: int,
) -> None:
    request_text = stable_json({"tool": tool, "arguments": args})
    response_text = stable_json({"result": result if error is None else {"error": error}})
    input_tokens = estimate_tokens(request_text)
    output_tokens = estimate_tokens(response_text)
    record = {
        "version": MCP_TOKEN_LOG_VERSION,
        "logged_at": datetime.now(timezone.utc).isoformat(),
        "session": os.environ.get("MAROUBA_MCP_SESSION", "default"),
        "tool": tool,
        "status": status,
        "elapsed_ms": elapsed_ms,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "estimator": "regex_json_v1",
    }
    if error:
        record["error"] = error
    try:
        with token_log_path().open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
    except OSError:
        pass


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))


def estimate_tokens(value: Any) -> int:
    text = value if isinstance(value, str) else stable_json(value)
    return len(re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE))


def list_workflows() -> list[dict[str, Any]]:
    """List workflows in the configured Marouba vault."""

    return instrument_mcp_call("list_workflows", {}, lambda: vault().list_vaults())


def search_workflows(query: str = "", app: str | None = None, tags: list[str] | None = None, limit: int = 10) -> list[dict[str, Any]]:
    """Search workflows by id, name, app, description, and tags."""

    return instrument_mcp_call(
        "search_workflows",
        {"query": query, "app": app, "tags": tags, "limit": limit},
        lambda: search_workflows_impl(query=query, app=app, tags=tags, limit=limit),
    )


def teach_workflow(
    name: str,
    app: str,
    actions: list[dict[str, Any]],
    description: str = "",
) -> dict[str, Any]:
    """Create and save a taught sequence workflow from captured action dictionaries."""

    return instrument_mcp_call(
        "teach_workflow",
        {"name": name, "app": app, "actions": actions, "description": description},
        lambda: teach_workflow_impl(name=name, app=app, actions=actions, description=description),
    )


def compose_workflow(
    name: str,
    app: str,
    intent: str,
    routes: list[dict[str, Any]] | None = None,
    params: list[dict[str, Any]] | None = None,
    tags: list[str] | None = None,
    confirm_save: bool = False,
) -> dict[str, Any]:
    """Compose a workflow preview; save only when confirm_save is true."""

    return instrument_mcp_call(
        "compose_workflow",
        {
            "name": name,
            "app": app,
            "intent": intent,
            "routes": routes,
            "params": params,
            "tags": tags,
            "confirm_save": confirm_save,
        },
        lambda: compose_workflow_impl(
            name=name,
            app=app,
            intent=intent,
            routes=routes,
            params=params,
            tags=tags,
            confirm_save=confirm_save,
        ),
    )


def install_workflow(bundle: str) -> dict[str, Any]:
    """Install a signed .mwf workflow bundle after Ed25519 verification."""

    return instrument_mcp_call("install_workflow", {"bundle": bundle}, lambda: install_workflow_impl(bundle))


def read_workflow(workflow_id: str, depth: str = "summary") -> dict[str, Any]:
    """Return a depth-gated workflow view by id, name, or file stem."""

    return instrument_mcp_call(
        "read_workflow",
        {"workflow_id": workflow_id, "depth": depth},
        lambda: read_workflow_impl(workflow_id, depth),
    )


def replay_workflow(
    workflow_id: str,
    params: dict[str, Any] | None = None,
    no_repair: bool = True,
) -> dict[str, Any]:
    """Replay a workflow through Marouba's existing router and executor."""

    return instrument_mcp_call(
        "replay_workflow",
        {"workflow_id": workflow_id, "params": params or {}, "no_repair": no_repair},
        lambda: replay_workflow_impl(workflow_id, params=params, no_repair=no_repair),
    )


def search_workflows_impl(query: str = "", app: str | None = None, tags: list[str] | None = None, limit: int = 10) -> list[dict[str, Any]]:
    query_terms = [term.casefold() for term in str(query or "").split() if term.strip()]
    wanted_tags = {tag.casefold() for tag in (tags or []) if str(tag).strip()}
    app_term = str(app or "").casefold().strip()
    results = []
    for workflow in vault().list_vaults():
        haystack_parts = [
            workflow.get("id"),
            workflow.get("name"),
            workflow.get("app"),
            workflow.get("description"),
            " ".join(str(tag) for tag in workflow.get("tags", [])),
        ]
        haystack = " ".join(str(part or "") for part in haystack_parts).casefold()
        workflow_tags = {str(tag).casefold() for tag in workflow.get("tags", [])}
        if query_terms and not all(term in haystack for term in query_terms):
            continue
        if app_term and app_term not in str(workflow.get("app") or "").casefold():
            continue
        if wanted_tags and not wanted_tags.issubset(workflow_tags):
            continue
        score = sum(haystack.count(term) for term in query_terms) if query_terms else 1
        results.append({**workflow, "score": score})

    results.sort(key=lambda item: (-int(item.get("score", 0)), str(item.get("name") or "")))
    return results[: max(1, int(limit or 10))]


def teach_workflow_impl(
    name: str,
    app: str,
    actions: list[dict[str, Any]],
    description: str = "",
) -> dict[str, Any]:
    workflow = workflow_from_actions(name=name, app=app, actions=actions, description=description, tags=["taught", slugify(app)])
    path = vault().save_workflow(workflow)
    return {"status": "saved", "id": workflow["id"], "path": str(path), "workflow": workflow_summary(workflow)}


def compose_workflow_impl(
    name: str,
    app: str,
    intent: str,
    routes: list[dict[str, Any]] | None = None,
    params: list[dict[str, Any]] | None = None,
    tags: list[str] | None = None,
    confirm_save: bool = False,
) -> dict[str, Any]:
    workflow = {
        "id": slugify(name),
        "name": name,
        "app": app,
        "description": intent,
        "params": params or [],
        "tags": tags or ["composed", slugify(app)],
        "author": "nxeratech",
        "created": date.today().isoformat(),
        "routes": routes or [],
        "fallback_order": fallback_order(routes or []),
        "verification": {"type": "none"},
        "calls": [],
        "depends_on": [],
        "body": f"# {name}\n\n{intent}\n",
    }
    if not confirm_save:
        return {
            "status": "needs_confirmation",
            "message": "Review the workflow preview, then call compose_workflow again with confirm_save=true to save.",
            "workflow": workflow,
        }
    path = vault().save_workflow(workflow)
    return {"status": "saved", "id": workflow["id"], "path": str(path), "workflow": workflow_summary(workflow)}


def install_workflow_impl(bundle: str) -> dict[str, Any]:
    try:
        path = install_bundle(bundle, configured_root())
    except InstallError as error:
        return {"status": "refused", "ok": False, "error": str(error)}
    except Exception as error:
        return {"status": "failed", "ok": False, "error": str(error)}
    return {"status": "installed", "ok": True, "path": str(path)}


def read_workflow_impl(workflow_id: str, depth: str = "summary") -> dict[str, Any]:
    depth = normalize_workflow_depth(depth)
    target = workflow_id.casefold()
    workflows_dir = vault().workflows_dir
    for path in sorted(workflows_dir.rglob("*.md")):
        if path.name.endswith(".steps.md"):
            continue
        workflow = vault().load_workflow(path)
        candidates = {
            str(workflow.get("id", "")).casefold(),
            str(workflow.get("name", "")).casefold(),
            path.stem.casefold(),
            path.name.casefold(),
        }
        if target in candidates:
            return workflow_read_payload(path, workflow, depth, workflow_source_text(path))
    raise FileNotFoundError(f"Workflow not found: {workflow_id}")


def replay_workflow_impl(
    workflow_id: str,
    params: dict[str, Any] | None = None,
    no_repair: bool = True,
) -> dict[str, Any]:
    params = params or {}
    stdout = io.StringIO()
    stderr = io.StringIO()
    root = configured_root()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr), silence_process_stdio():
        exit_code = run_replay_workflow(
            workflow_id,
            params,
            root=root,
            no_repair=no_repair,
            router=Router({"cli": mcp_cli_available}),
            executor=Executor(root),
        )

    return {
        "success": exit_code == 0,
        "exit_code": exit_code,
        "stdout": stdout.getvalue(),
        "stderr": stderr.getvalue(),
    }


def workflow_from_actions(
    name: str,
    app: str,
    actions: list[dict[str, Any]],
    description: str = "",
    tags: list[str] | None = None,
) -> dict[str, Any]:
    routes = [route for action in actions if (route := action_to_route(action))]
    today = date.today().isoformat()
    return {
        "id": slugify(name),
        "name": name,
        "app": app,
        "mode": "sequence",
        "description": description or f"Taught workflow for {app}.",
        "params": [],
        "tags": tags or ["taught", slugify(app)],
        "author": "nxeratech",
        "created": today,
        "last_verified": today,
        "routes": routes,
        "fallback_order": fallback_order(routes),
        "verification": {"type": "none"},
        "calls": [],
        "depends_on": [],
        "body": f"# {name}\n\n{description or 'Captured by Marouba Teach mode.'}\n",
    }


def action_to_route(action: dict[str, Any]) -> dict[str, Any] | None:
    action_type = str(action.get("type") or action.get("action") or "").strip()
    if action_type in {"ui_click", "uia"}:
        return {
            "type": "uia",
            "app_window": action.get("window_title") or action.get("app_window"),
            "element": action.get("element") or action.get("name"),
            "role": action.get("role") or action.get("control_type"),
        }
    if action_type in {"shortcut", "hotkey"}:
        return {"type": "shortcut", "keys": action.get("keys") or action.get("sequence") or action.get("hotkey")}
    if action_type in {"text", "keyboard"}:
        return {"type": "keyboard", "text": action.get("text") or "", "interval": action.get("interval", 0.04)}
    if action_type in {"mouse_click", "visual"}:
        coordinates = action.get("coordinates") or {"x": action.get("x", 0), "y": action.get("y", 0)}
        return {"type": "visual", "coordinates": coordinates, "button": action.get("button", "left")}
    if action_type in {"http_request", "api"}:
        return {
            "type": "api",
            "endpoint": action.get("endpoint"),
            "method": action.get("method", "GET"),
            "payload_template": action.get("payload_template"),
        }
    if action_type == "cli":
        return {"type": "cli", "command": action.get("command"), "wait_seconds": action.get("wait_seconds", 0)}
    return None


def fallback_order(routes: list[dict[str, Any]]) -> list[str]:
    preferred = ["api", "cli", "uia", "shortcut", "keyboard", "visual", "gesture"]
    seen = {route.get("type") for route in routes}
    order = [route_type for route_type in preferred if route_type in seen]
    return order + ["ask"]


def workflow_summary(workflow: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": workflow.get("id"),
        "name": workflow.get("name"),
        "app": workflow.get("app"),
        "description": workflow.get("description", ""),
        "routes": len(workflow.get("routes", [])),
        "fallback_order": workflow.get("fallback_order", []),
    }


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(value).casefold()).strip("-")
    return slug or "workflow"


def normalize_workflow_depth(depth: str) -> str:
    normalized = str(depth or "summary").strip().casefold()
    if normalized not in {"summary", "full"}:
        raise ValueError("depth must be 'summary' or 'full'")
    return normalized


def workflow_read_payload(path: Path, workflow: dict[str, Any], depth: str, source_text: str) -> dict[str, Any]:
    workflow_id = str(workflow.get("id") or path.stem)
    frontmatter = raw_frontmatter(source_text)
    intent = workflow_intent(workflow, source_text)
    if depth == "summary":
        content = f"---\n{frontmatter.strip()}\n---\n\nintent: {intent}\n"
        return {
            "id": workflow_id,
            "depth": "summary",
            "content": compact_words(content, 360),
            "chunks": [],
            "omitted": ["steps", "raw gesture event streams"],
        }

    content = sanitized_workflow_markdown(workflow, frontmatter, intent)
    chunks = chunk_text(content, 2000)
    return {
        "id": workflow_id,
        "depth": "full",
        "content": "",
        "chunks": [{"index": index + 1, "text": chunk} for index, chunk in enumerate(chunks)],
        "omitted": ["raw gesture event streams", "raw coordinate streams"],
    }


def workflow_source_text(path: Path) -> str:
    content = path.read_text(encoding="utf-8")
    sidecar = path.with_name(f"{path.stem}.steps.md")
    if sidecar.exists():
        content = f"{content.rstrip()}\n\n{sidecar.read_text(encoding='utf-8')}"
    return content


def raw_frontmatter(content: str) -> str:
    parts = content.split("---", 2)
    if len(parts) >= 3 and not parts[0].strip():
        return parts[1]
    return ""


def workflow_intent(workflow: dict[str, Any], source_text: str) -> str:
    description = str(workflow.get("description") or "").strip()
    if description:
        return description
    for line in source_text.splitlines():
        text = line.strip().lstrip("#").strip()
        if text and text != "---" and not text.startswith(("vault_spec_version:", "id:")):
            return text
    return "Replay recorded workflow."


def sanitized_workflow_markdown(workflow: dict[str, Any], frontmatter: str, intent: str) -> str:
    lines = [
        "---",
        frontmatter.strip(),
        "---",
        "",
        f"# {workflow.get('name') or workflow.get('id') or 'Workflow'}",
        "",
        f"Intent: {intent}",
        "",
        "## Steps",
    ]
    steps = workflow.get("steps") or []
    if not isinstance(steps, list) or not steps:
        lines.append("No structured steps declared.")
        return "\n".join(lines) + "\n"

    for index, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            continue
        step_id = step.get("id") or f"step_{index:03d}"
        lines.extend(
            [
                "",
                f"### Step {index:03d} - {step_id}",
                f"type: {step.get('type') or 'unknown'}",
                f"intent: {step.get('intent') or ''}",
            ]
        )
        routes = step.get("routes") or []
        if isinstance(routes, list):
            lines.append("routes:")
            for route in routes:
                if not isinstance(route, dict):
                    continue
                sanitized = sanitize_route(route)
                lines.append(f"  - {json.dumps(sanitized, separators=(',', ':'), sort_keys=True)}")
    return "\n".join(lines) + "\n"


def sanitize_route(route: dict[str, Any]) -> dict[str, Any]:
    sanitized = {}
    for key, value in route.items():
        if key in {"events", "x", "y", "normalized_x", "normalized_y", "coordinates", "window_rect"}:
            continue
        sanitized[key] = value
    if "events" in route:
        events = route.get("events")
        count = len(events) if isinstance(events, list) else 0
        sanitized["events_omitted"] = f"{count} raw gesture events"
    return sanitized


def compact_words(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + " ..."


def chunk_text(text: str, chunk_size: int) -> list[str]:
    return [
        "\n".join(textwrap.wrap(chunk, width=120, replace_whitespace=False))
        for chunk in (text[index : index + chunk_size] for index in range(0, len(text), chunk_size))
        if chunk
    ]


def mcp_cli_available(route: dict[str, Any]) -> bool:
    command = str(route.get("command", "")).strip()
    if not command:
        return False
    executable = first_command_token(command)
    if not executable:
        return False
    executable_path = Path(executable)
    if executable_path.is_absolute() or executable_path.parent != Path("."):
        return executable_path.exists()
    return shutil.which(executable) is not None


def first_command_token(command: str) -> str:
    match = re.match(r'''^\s*(?:"([^"]+)"|'([^']+)'|(\S+))''', command)
    if not match:
        return ""
    return next(group for group in match.groups() if group)


@contextlib.contextmanager
def silence_process_stdio():
    stdout_fd = os.dup(1)
    stderr_fd = os.dup(2)
    with open(os.devnull, "w", encoding="utf-8") as devnull:
        try:
            os.dup2(devnull.fileno(), 1)
            os.dup2(devnull.fileno(), 2)
            yield
        finally:
            os.dup2(stdout_fd, 1)
            os.dup2(stderr_fd, 2)
            os.close(stdout_fd)
            os.close(stderr_fd)
