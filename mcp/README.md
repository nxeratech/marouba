# Marouba MCP Server

Marouba exposes a stdio Model Context Protocol server with seven tools:

- `list_workflows` - list workflows from the configured vault
- `search_workflows(query="", app=null, tags=null, limit=10)` - search workflows by id, name, app, description, and tags
- `read_workflow(workflow_id, depth="summary")` - return a depth-gated workflow view; `summary` includes frontmatter plus intent, `full` returns sanitized chunks without raw coordinate streams
- `replay_workflow` - replay a workflow through Marouba's existing router and executor
- `teach_workflow(name, app, actions, description="")` - save a taught sequence workflow from captured action dictionaries
- `compose_workflow(name, app, intent, ..., confirm_save=false)` - preview a composed workflow and save only after explicit confirmation
- `install_workflow(bundle)` - install a signed `.mwf` bundle after Ed25519 verification

## Install

```powershell
cd C:\Share\Marouba
pip install -r requirements.txt
```

The server reads `MAROUBA_VAULT_PATH` when set. If omitted, it falls back to `./vault`.

## Claude Desktop

Add this to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "marouba": {
      "command": "python",
      "args": ["C:\\Share\\Marouba\\mcp\\server.py"],
      "env": {
        "MAROUBA_VAULT_PATH": "C:\\Share\\Marouba\\vault"
      }
    }
  }
}
```

Restart Claude Desktop after editing the config.

## Cursor

Add a stdio MCP server in Cursor settings:

```json
{
  "mcpServers": {
    "marouba": {
      "command": "python",
      "args": ["C:\\Share\\Marouba\\mcp\\server.py"],
      "env": {
        "MAROUBA_VAULT_PATH": "C:\\Share\\Marouba\\vault"
      }
    }
  }
}
```

Restart Cursor or reload MCP servers after saving.
