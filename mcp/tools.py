from __future__ import annotations

import contextlib
import io
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.executor import Executor
from engine.router import Router
from engine.vault import Vault
from scripts.replay import replay_workflow as run_replay_workflow


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


def list_workflows() -> list[dict[str, Any]]:
    """List workflows in the configured Marouba vault."""

    return vault().list_vaults()


def read_workflow(workflow_id: str) -> str:
    """Return the raw Markdown for a workflow by id, name, or file stem."""

    target = workflow_id.casefold()
    workflows_dir = vault().workflows_dir
    for path in sorted(workflows_dir.rglob("*.md")):
        workflow = vault().load_workflow(path)
        candidates = {
            str(workflow.get("id", "")).casefold(),
            str(workflow.get("name", "")).casefold(),
            path.stem.casefold(),
            path.name.casefold(),
        }
        if target in candidates:
            return path.read_text(encoding="utf-8")
    raise FileNotFoundError(f"Workflow not found: {workflow_id}")


def replay_workflow(
    workflow_id: str,
    params: dict[str, Any] | None = None,
    no_repair: bool = True,
) -> dict[str, Any]:
    """Replay a workflow through Marouba's existing router and executor."""

    params = params or {}
    stdout = io.StringIO()
    stderr = io.StringIO()
    root = configured_root()
    vault_path = configured_vault_path()
    workflow_paths = sorted(str(path) for path in (vault_path / "workflows").rglob("*.md"))
    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr), silence_process_stdio():
            exit_code = run_replay_workflow(
                workflow_id,
                params,
                root=root,
                no_repair=no_repair,
                router=Router({"cli": mcp_cli_available}),
                executor=Executor(root),
            )
    except Exception as exc:
        return {
            "success": False,
            "exit_code": 1,
            "error": repr(exc),
            "steps": [],
            "stdout": stdout.getvalue(),
            "stderr": stderr.getvalue(),
            "root": str(root),
            "vault_path": str(vault_path),
            "workflow_paths": workflow_paths,
        }

    output = stdout.getvalue()
    error_output = stderr.getvalue()
    steps = extract_replay_steps(output)
    error = ""
    if exit_code != 0:
        error = error_output.strip() or last_replay_error(output) or f"Replay exited with code {exit_code}"

    return {
        "success": exit_code == 0,
        "exit_code": exit_code,
        "error": error,
        "steps": steps,
        "stdout": output,
        "stderr": error_output,
        "root": str(root),
        "vault_path": str(vault_path),
        "workflow_paths": workflow_paths,
    }


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


def extract_replay_steps(output: str) -> list[str]:
    steps = []
    for line in output.splitlines():
        if line.startswith("[Marouba] Route order:"):
            steps.append(line)
        elif line.startswith("[Marouba] Trying route:"):
            steps.append(line)
        elif line.startswith("[Marouba] Step "):
            steps.append(line)
        elif line.startswith("[Marouba] Route failed:"):
            steps.append(line)
        elif line.startswith("[Marouba] Step failed:"):
            steps.append(line)
        elif line.startswith("[Marouba] All routes failed."):
            steps.append(line)
    return steps


def last_replay_error(output: str) -> str:
    for line in reversed(output.splitlines()):
        if "failed" in line.casefold() or "not found" in line.casefold():
            return line
    return ""


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
