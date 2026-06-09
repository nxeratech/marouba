# Marouba MCP Server — Spec
**Version: v2**
**Date: 09 June 2026**
**Build target: C:\Share\Marouba\mcp\**

---

## Vision Anchor

The vault is the product. The MCP server is the interface that makes the vault callable by any agent — Barry, Claude Desktop, OpenClaw, n8n, or any HTTP-capable tool. The MCP server does not define what Marouba does. It exposes what the vault already contains to the agent layer.

The current proof-of-concept app is MS Paint. Ableton Live is the Phase 8 target. The MCP server is app-agnostic — it calls whatever workflow is in the vault regardless of target app.

Read `marouba-vision-and-codex-brief-v2.md` for full context before building.

---

## What This Is

A Model Context Protocol server that exposes the Marouba vault to any MCP-compatible agent. Claude Desktop, Cursor, Windsurf, or any agent that speaks MCP can list, read, and execute vault workflows without knowing anything about the underlying engine.

One connection. All workflows available as callable tools.

---

## Why MCP (Not REST)

REST requires the agent to be told about the endpoint, auth, and schema out-of-band. MCP is self-describing — the agent discovers available tools at connection time. "Works with Claude Desktop out of the box" is a one-line install. That's the demo story.

---

## Server Location

```
C:\Share\Marouba\mcp\
  server.py          ← MCP server entry point
  tools.py           ← tool definitions + handlers
  README.md          ← install instructions for Claude Desktop / Cursor
```

Runs as a local process. No cloud. No auth needed for local use (companion token optional for remote).

---

## Transport

**stdio** — standard MCP transport. Claude Desktop spawns the process and communicates over stdin/stdout. Zero config for the user beyond adding it to `claude_desktop_config.json`.

---

## Tools Exposed (v1 — 3 tools)

### 1. `list_workflows`

**Description:** List all saved Marouba workflow files. Returns workflow names, app targets, and one-line descriptions parsed from the vault frontmatter.

**Input:** none

**Output:**
```json
[
  {
    "name": "ms-paint/apple-sketch",
    "app": "MS Paint",
    "description": "Draws an apple shape with circle, fill, and pencil stalk.",
    "params": []
  },
  {
    "name": "comfyui/portrait_upscale",
    "app": "ComfyUI",
    "description": "Upscales a portrait image with face detail pass. Params: input_path, scale.",
    "params": ["input_path", "scale"]
  }
]
```

---

### 2. `read_workflow`

**Description:** Read the full contents of a vault workflow file. Returns the raw Markdown so the agent can understand intent, style, decision rules, and parameter slots before executing.

**Input:**
```json
{ "name": "ms-paint/apple-sketch" }
```

**Output:** Full Markdown content of the workflow file.

**Why this exists:** Lets the agent understand what the workflow does before calling replay. Critical for natural language matching. Also lets the agent explain to the user what is about to happen.

---

### 3. `replay_workflow`

**Description:** Execute a saved workflow. Marouba opens the target app (if not already open), resolves each step via the cheapest available route, and runs the full sequence.

**Input:**
```json
{
  "name": "ms-paint/apple-sketch",
  "params": {}
}
```

**Output:**
```json
{
  "status": "completed",
  "steps_total": 12,
  "steps_completed": 12,
  "steps_repaired": 0,
  "run_id": "run_20260609_143022",
  "log_path": "vault/runs/run_20260609_143022.json"
}
```

Error case:
```json
{
  "status": "failed",
  "step_failed": 4,
  "step_description": "Fill canvas region green",
  "error": "UIA element not found — app layout may have changed",
  "repair_available": true
}
```

---

## Vault Frontmatter Standard (Required for MCP)

Every workflow `.md` file needs a frontmatter block for `list_workflows` to parse.

```markdown
---
id: "apple-sketch"
name: "Apple Sketch"
app: "MS Paint"
description: "Draws an apple — circle body, green fill, brown pencil stalk."
params: []
tags: ["ms-paint", "recorded", "gesture"]
author: nxeratech
created: 2026-06-09
---
```

This standard is documented in VAULT_SPEC.md.

---

## Install — Claude Desktop

User adds this to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "marouba": {
      "command": "python",
      "args": ["C:\\Share\\Marouba\\mcp\\server.py"],
      "env": {
        "MAROUBA_VAULT_PATH": "C:\\Users\\Dave\\AppData\\Local\\Marouba\\vault\\workflows"
      }
    }
  }
}
```

Restart Claude Desktop. Marouba tools appear automatically.

---

## Install — Cursor / Windsurf

Same server, different config format per editor. Both support stdio MCP servers. README.md in `mcp/` covers both.

---

## What the Agent Interaction Looks Like

**Current (Paint proof-of-concept):**

User: "Replay my apple sketch"

Agent internally:
1. Calls `list_workflows` — sees `ms-paint/apple-sketch`
2. Calls `read_workflow("ms-paint/apple-sketch")` — confirms it matches intent
3. Calls `replay_workflow("ms-paint/apple-sketch", {})`
4. Returns: "Done — apple drawn in Paint. 12 steps executed, 0 repairs needed."

**Phase 8 target (Ableton):**

User: "Make me a dark techno bassline, F minor, 138bpm"

Agent internally:
1. Calls `list_workflows` — sees `ableton/dark_bassline` with tags `[techno, dark, bassline]`
2. Calls `read_workflow("ableton/dark_bassline")` — reads the Markdown, confirms it matches
3. Calls `replay_workflow("ableton/dark_bassline", {"key": "Fm", "bpm": 138, "steps": 16})`
4. Returns: "Done — bassline in Ableton. 12 steps executed, 0 repairs needed."

Note: Ableton profile is Phase 8. Do not build Ableton-specific logic now. The MCP server is app-agnostic — it calls whatever is in the vault.

---

## Build Scope

- `mcp/server.py` — stdio MCP server, registers 3 tools
- `mcp/tools.py` — handlers for list/read/replay, calls existing engine
- Update `engine/vault.py` — add `list_vaults()` that parses frontmatter
- Update `VAULT_SPEC.md` — document required frontmatter block
- Update existing profile `.md` files — add frontmatter to all seed workflows
- `mcp/README.md` — Claude Desktop + Cursor install instructions
- Add `mcp` section to main `README.md`
- Tests — 3 new tests: list returns expected workflows, read returns content, replay calls executor

**Note:** MCP server is already built as of 08 June 2026. This spec is the reference document. Do not rebuild from scratch — extend and verify against this spec only.

---

## v2 Additions (Post-Launch)

- `teach_workflow` tool — agent watches you work, saves to vault
- `search_workflows` tool — semantic search across vault by description/tags
- Remote MCP over SSE — vault accessible from non-local agents (cloud sync tier)
- Marketplace integration — `install_workflow(bundle_url)` installs signed .mwf

---

*Spec by Claude / NXeraTech*
*Updated: 09 June 2026*
