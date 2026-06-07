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
from tools import read_workflow as handle_read_workflow
from tools import replay_workflow as handle_replay_workflow


server = FastMCP("Marouba")


@server.tool(name="list_workflows", description="List workflows in the configured Marouba vault.")
def list_workflows() -> list[dict[str, Any]]:
    return handle_list_workflows()


@server.tool(name="read_workflow", description="Read a workflow Markdown file by id, name, or file stem.")
def read_workflow(workflow_id: str) -> str:
    return handle_read_workflow(workflow_id)


@server.tool(name="replay_workflow", description="Replay a Marouba workflow through the existing router and executor.")
def replay_workflow(workflow_id: str, params: dict[str, Any] | None = None, no_repair: bool = True) -> dict[str, Any]:
    return handle_replay_workflow(workflow_id, params=params, no_repair=no_repair)


def main() -> None:
    server.run("stdio")


if __name__ == "__main__":
    main()
