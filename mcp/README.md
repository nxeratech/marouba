# Marouba MCP Server

Marouba exposes a stdio Model Context Protocol server with three tools:

- `list_workflows` - list workflows from the configured vault
- `read_workflow` - return the raw Markdown for one workflow
- `replay_workflow` - replay a workflow through Marouba's existing router and executor

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
