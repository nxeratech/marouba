from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

from mcp.server.fastmcp import FastMCP

MCP_DIR = Path(__file__).resolve().parent
ROOT = MCP_DIR.parent
if str(MCP_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_DIR))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import list_workflows as handle_list_workflows
from tools import search_workflows as handle_search_workflows
from tools import read_workflow as handle_read_workflow
from tools import replay_workflow as handle_replay_workflow
from tools import teach_workflow as handle_teach_workflow
from tools import compose_workflow as handle_compose_workflow
from tools import install_workflow as handle_install_workflow


server = FastMCP("Marouba")


@server.tool(name="list_workflows", description="List workflows in the configured Marouba vault.")
def list_workflows() -> list[dict[str, Any]]:
    return handle_list_workflows()


@server.tool(name="search_workflows", description="Search workflows by id, name, app, description, and tags.")
def search_workflows(
    query: str = "",
    app: str | None = None,
    tags: list[str] | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    return handle_search_workflows(query=query, app=app, tags=tags, limit=limit)


@server.tool(name="read_workflow", description="Read a depth-gated workflow view by id, name, or file stem.")
def read_workflow(workflow_id: str, depth: str = "summary") -> dict[str, Any]:
    return handle_read_workflow(workflow_id, depth=depth)


@server.tool(name="replay_workflow", description="Replay a Marouba workflow through the existing router and executor.")
def replay_workflow(workflow_id: str, params: dict[str, Any] | None = None, no_repair: bool = True) -> dict[str, Any]:
    return handle_replay_workflow(workflow_id, params=params, no_repair=no_repair)


@server.tool(name="teach_workflow", description="Save a taught workflow from captured action dictionaries.")
def teach_workflow(
    name: str,
    app: str,
    actions: list[dict[str, Any]],
    description: str = "",
) -> dict[str, Any]:
    return handle_teach_workflow(name=name, app=app, actions=actions, description=description)


@server.tool(name="compose_workflow", description="Compose a workflow; saves only when confirm_save is true.")
def compose_workflow(
    name: str,
    app: str,
    intent: str,
    routes: list[dict[str, Any]] | None = None,
    params: list[dict[str, Any]] | None = None,
    tags: list[str] | None = None,
    confirm_save: bool = False,
) -> dict[str, Any]:
    return handle_compose_workflow(
        name=name,
        app=app,
        intent=intent,
        routes=routes,
        params=params,
        tags=tags,
        confirm_save=confirm_save,
    )


@server.tool(name="install_workflow", description="Install a signed .mwf workflow bundle after Ed25519 verification.")
def install_workflow(bundle: str) -> dict[str, Any]:
    return handle_install_workflow(bundle)


def main() -> None:
    server.run("stdio")


if __name__ == "__main__":
    main()
