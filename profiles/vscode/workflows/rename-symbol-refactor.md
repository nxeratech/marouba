---
id: vscode-rename-symbol-refactor
name: VS Code Rename Symbol Refactor
app: VS Code
app_version: latest
author: nxeratech
category: code-refactor
description: Apply command and edit-level events that rename a symbol and verify file end-state.
params: []
tags: [vscode, refactor, extension, adapter, r1]
last_verified: 2026-06-14
created: 2026-06-14
routes:
  - type: adapter
    adapter: vscode
    verify_files: [src/app.ts]
    events:
      - route_tier: r1
        app: VS Code
        kind: command
        action: run_command
        command: editor.action.rename
        args: [{old: makeThing, new: buildThing}]
        source: extension
      - route_tier: r1
        app: VS Code
        kind: edit
        action: apply_edit
        path: src/app.ts
        edits:
          - {start: 16, end: 25, text: buildThing}
          - {start: 39, end: 48, text: buildThing}
        source: extension
  - type: uia
    app_window: Visual Studio Code
    element: Editor
    role: Pane
fallback_order: [adapter, uia, ask]
verification:
  type: workspace_hash
calls: []
depends_on: []
---

# VS Code Rename Symbol Refactor

Replay a local command/edit-level refactor without telemetry or network.
