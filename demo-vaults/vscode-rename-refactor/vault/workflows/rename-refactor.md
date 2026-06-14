---
id: rename-refactor
name: Rename Refactor
app: VS Code
description: Demo VS Code adapter vault replaying a command/edit-level rename refactor.
params: []
tags: [vscode, demo, adapter, r1, refactor]
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
fallback_order: [adapter, uia, ask]
verification:
  type: workspace_hash
calls: []
depends_on: []
---

# Rename Refactor

Demo vault for local extension command/edit replay.
