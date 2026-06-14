---
id: import-cleanup
name: Import Cleanup
app: VS Code
description: Demo VS Code adapter vault applying local extension edits after an organize imports command.
params: []
tags: [vscode, demo, adapter, r1, command]
routes:
  - type: adapter
    adapter: vscode
    verify_files: [src/index.ts]
    events:
      - route_tier: r1
        app: VS Code
        kind: command
        action: run_command
        command: editor.action.organizeImports
        args: []
        source: extension
      - route_tier: r1
        app: VS Code
        kind: edit
        action: apply_edit
        path: src/index.ts
        edits:
          - {start: 0, end: 22, text: ""}
        source: extension
fallback_order: [adapter, uia, ask]
verification:
  type: workspace_hash
calls: []
depends_on: []
---

# Import Cleanup

Demo vault for command/edit-level import cleanup.
