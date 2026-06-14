# Goal 28 VS Code Adapter Audit

Date: 2026-06-14

## API Sources

The VS Code extension API exposes the local editor surfaces Marouba needs:

- `workspace.onDidChangeTextDocument` emits detailed document edit events.
- `commands.executeCommand(...)` can replay command identifiers and arguments.
- `workspace.applyEdit(...)` applies text/resource edits and is used for deterministic replay.
- `window.createTerminal(...)` and terminal APIs cover local terminal usage evidence.

The API also exposes telemetry helpers such as `env.createTelemetryLogger(...)`, but the VS Code adapter forbids telemetry and network-backed capture.

Source: [VS Code API reference](https://code.visualstudio.com/api/references/vscode-api).

## r1 Boundary

r1 capture stores:

- local extension text edits with file path, ranges, inserted text, and source document version
- command IDs and serializable arguments
- terminal command lines/cwd recorded locally
- file end-state hash for replay verification

## Declared Failures

- Telemetry-backed events are hard failures.
- Network-backed extension events are hard failures.
- Replay must verify file end-state, not editor pixels.

## Remaining Machine Proof

The committed tests use a temp workspace and fake extension logs. Full PASS still requires Dave's machine:

- install/load the local Marouba VS Code extension
- record a real refactor session
- replay in a clean workspace
- confirm diff clean
- run 20 cold replays with at least 95 percent success
