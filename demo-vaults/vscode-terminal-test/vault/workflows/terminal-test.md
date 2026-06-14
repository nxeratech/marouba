---
id: terminal-test
name: Terminal Test
app: VS Code
description: Demo VS Code adapter vault capturing local terminal usage with an edit.
params: []
tags: [vscode, demo, adapter, r1, terminal]
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
fallback_order: [adapter, uia, ask]
verification:
  type: workspace_hash
calls: []
depends_on: []
---

# Terminal Test

Demo vault for local terminal evidence, without telemetry or network.
