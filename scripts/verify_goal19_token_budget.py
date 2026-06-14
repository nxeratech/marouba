from __future__ import annotations

import json
import importlib.util
import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.vault import Vault


AUDIT_DIR = ROOT / "audits"
TOKEN_LOG = AUDIT_DIR / "goal19-mcp-token-log.jsonl"
REPORT = AUDIT_DIR / "goal19-token-budget.md"


def main() -> int:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    TOKEN_LOG.write_text("", encoding="utf-8")

    with tempfile.TemporaryDirectory(prefix="marouba-goal19-") as temp_dir:
        root = Path(temp_dir)
        vault = Vault(root)
        artifact = root / "dark-techno-render.txt"
        workflow = dark_techno_workflow(artifact)
        vault.save_workflow(workflow)

        os.environ["MAROUBA_VAULT_PATH"] = str(root / "vault")
        os.environ["MAROUBA_MCP_TOKEN_LOG"] = str(TOKEN_LOG)
        os.environ["MAROUBA_MCP_SESSION"] = "goal19-barry-cold"

        tools = load_mcp_tools()

        discover = tools.search_workflows("dark techno bassline F minor 138bpm", app="Ableton Live", limit=3)
        if not discover or discover[0]["id"] != "dark-techno-bassline":
            raise SystemExit(f"Barry discover failed: {discover}")

        read = tools.read_workflow(discover[0]["id"], depth="summary")
        replay = tools.replay_workflow(
            discover[0]["id"],
            params={"key": "F minor", "bpm": 138},
            no_repair=True,
        )
        if not replay["success"]:
            raise SystemExit(f"Barry replay failed: {replay}")
        rendered = artifact.read_text(encoding="utf-8")
        if rendered != "dark techno bassline | key=F minor | bpm=138":
            raise SystemExit(f"Parameter substitution failed: {rendered!r}")

        rows = [json.loads(line) for line in TOKEN_LOG.read_text(encoding="utf-8").splitlines() if line.strip()]
        report_text = build_report(discover, read, replay, rendered, rows)
        report_tokens = tools.estimate_tokens(report_text)
        mcp_tokens = sum(int(row["total_tokens"]) for row in rows)
        total_tokens = mcp_tokens + report_tokens
        report_text += f"\n- Report output tokens: {report_tokens}\n"
        report_text += f"- MCP tool tokens: {mcp_tokens}\n"
        report_text += f"- Discover -> read -> replay -> report total tokens: {total_tokens}\n"
        report_text += f"- PASS threshold: {total_tokens} < 2000\n"
        REPORT.write_text(report_text, encoding="utf-8")

        if total_tokens >= 2000:
            raise SystemExit(f"Goal 19 token budget exceeded: {total_tokens}")

    print(f"Wrote {TOKEN_LOG}")
    print(f"Wrote {REPORT}")
    return 0


def dark_techno_workflow(artifact: Path) -> dict:
    python = sys.executable
    command = (
        f'"{python}" -c "from pathlib import Path; '
        f'Path(r\'{artifact}\').write_text(\'dark techno bassline | key={{key}} | bpm={{bpm}}\', encoding=\'utf-8\')"'
    )
    return {
        "id": "dark-techno-bassline",
        "name": "Dark Techno Bassline",
        "app": "Ableton Live",
        "description": "Dark techno bassline performance in F minor at 138bpm for Barry cold MCP budget verification.",
        "params": [
            {"name": "key", "type": "string", "required": True},
            {"name": "bpm", "type": "number", "required": True},
        ],
        "tags": ["ableton-live", "dark", "techno", "bassline", "f-minor", "138bpm"],
        "author": "nxeratech",
        "created": "2026-06-14",
        "routes": [{"type": "cli", "command": command}],
        "fallback_order": ["cli", "ask"],
        "verification": {"type": "none"},
        "calls": [],
        "depends_on": [],
        "body": "# Dark Techno Bassline\n\nBudget verification fixture for Barry MCP discovery and replay.\n",
    }


def load_mcp_tools():
    path = ROOT / "mcp" / "tools.py"
    spec = importlib.util.spec_from_file_location("marouba_mcp_tools_goal19", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load MCP tools from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_report(discover: list[dict], read: dict, replay: dict, rendered: str, rows: list[dict]) -> str:
    lines = [
        "# Goal 19 Token Budget Verification",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "Scenario: Barry cold-discovered and ran `dark techno bassline, F minor, 138bpm` through the existing MCP server.",
        "",
        "## Outcome",
        "",
        f"- Discovered workflow: `{discover[0]['id']}` (`{discover[0]['name']}`)",
        f"- Read depth: `{read['depth']}`",
        f"- Replay success: `{replay['success']}`",
        f"- Rendered parameter proof: `{rendered}`",
        "",
        "## MCP Token Log",
        "",
        "| Step | Tool | Input | Output | Total | Status |",
        "| --- | --- | ---: | ---: | ---: | --- |",
    ]
    for index, row in enumerate(rows, start=1):
        lines.append(
            f"| {index} | `{row['tool']}` | {row['input_tokens']} | {row['output_tokens']} | {row['total_tokens']} | {row['status']} |"
        )
    lines.extend(["", "## Budget"])
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
