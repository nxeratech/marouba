---
id: vscode-terminal-test-run
name: VS Code Terminal Test Run
app: VS Code
app_version: latest
author: nxeratech
category: code-test
description: Capture local terminal usage alongside a small edit.
params: []
tags: [vscode, terminal, extension, adapter, r1]
last_verified: 2026-06-14
created: 2026-06-14
routes:
  - type: adapter
    adapter: vscode
    verify_files: [README.md]
    events:
      - route_tier: r1
        app: VS Code
        kind: edit
        action: apply_edit
        path: README.md
        edits:
          - {start: 0, end: 0, text: "Verified\n"}
        source: extension
      - route_tier: r1
        app: VS Code
        kind: terminal
        action: terminal
        command_line: "npm test"
        cwd: .
        source: extension
  - type: uia
    app_window: Visual Studio Code
    element: Terminal
    role: Pane
fallback_order: [adapter, uia, ask]
verification:
  type: workspace_hash
calls: []
depends_on: []
---

# VS Code Terminal Test Run

Replay local edit and terminal evidence captured by the extension.
