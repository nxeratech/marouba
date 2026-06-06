# Marouba — Day 1 Codex Brief
**NXeraTech / Dave Reilly**
**Date: 05 June 2026**
**Phase: 1a — Prove the vault format**

---

## Context

Marouba is an open source memory and replay engine for desktop workflows.
The user teaches it a task once. It remembers every possible route to complete it.
It replays automatically. When something breaks, it repairs itself and never asks again.

**The vault — not the agent — is the product.**

Full vision and scope: `Z:\Marouba\Scope Docs\marouba-scope-v2.md`
Read it before starting.

---

## Your Job Today (Phase 1a)

Prove the vault format works. Nothing more.

No companion app. No UI. No Windows integration yet.
Just a Python script that:
1. Executes one workflow via ComfyUI API
2. Saves that workflow to the vault as a Markdown file
3. Can replay it from the vault file cold

**If the vault format is solid at the end of today, Phase 1a is done.**

---

## Project Setup

```
Project path: Z:\Marouba\
WSL path: /mnt/z/Marouba/ (or create at /home/claw/marouba/)
Python: 3.11+ (WSL Ubuntu)
No Node, no Flutter, no frontend — pure Python today
```

Create this folder structure:

```
marouba/
  engine/
    __init__.py
    vault.py          ← vault read/write
    router.py         ← route resolver (stub for now)
    executor.py       ← executes a route
    repairer.py       ← repair loop (stub for now)
  profiles/
    comfyui/
      comfyui-profile.md    ← app profile
    photoshop/
      (empty for now)
  vault/
    workflows/
      (generated here)
    elements/
      (generated here)
    snapshots/
      (generated here)
    runs/
      (generated here)
  scripts/
    teach.py          ← record a workflow manually
    replay.py         ← replay a workflow from vault
    repair.py         ← stub for now
  tests/
    test_vault.py
    test_router.py
  requirements.txt
  README.md
```

---

## Step 1 — Vault Format

Define the vault format in `engine/vault.py`.

A workflow file looks like this:

```yaml
---
id: comfyui-generate-image-001
name: ComfyUI Generate Image
app: ComfyUI
app_version: latest
author: nxeratech
category: image-generation
tags: [comfyui, generate, image]
last_verified: 2026-06-05
created: 2026-06-05
routes:
  - type: api
    endpoint: http://127.0.0.1:8188/prompt
    method: POST
    payload_template: prompts/comfyui-basic.json
  - type: cli
    command: "python comfyui_client.py --prompt {prompt} --output {output_path}"
  - type: uia
    element: queue-prompt-button
    app_window: ComfyUI
  - type: visual
    snapshot: snapshots/comfyui-queue-button.png
fallback_order: [api, cli, uia, visual, ask]
verification:
  type: file_exists
  path: "{output_path}"
  timeout_seconds: 120
calls: []
depends_on: []
---

## What This Workflow Does

Generates an image using ComfyUI by queuing a prompt via the API.
Falls back to CLI client, then UIA button click, then visual scan if API is unavailable.

## Steps

1. Load workflow JSON from payload template
2. Substitute {prompt} and {output_path} variables
3. POST to ComfyUI /prompt endpoint
4. Poll /history/{prompt_id} until complete
5. Verify output file exists at output_path
6. Return output_path on success

## Notes

- ComfyUI must be running on port 8188
- Output lands in ComfyUI output folder by default
- API route is fastest — use it unless ComfyUI API is disabled
```

`vault.py` must:
- Load a workflow .md file and parse the frontmatter + body
- Save a new workflow .md file from a dict
- List all workflows in the vault
- Find a workflow by id or name
- Log each run to `vault/runs/` as JSON

Use `python-frontmatter` for parsing. Add to requirements.txt.

---

## Step 2 — Route Router

Define `engine/router.py`.

Takes a workflow and resolves which route to try first:

```python
class Router:
    def resolve(self, workflow: Workflow) -> list[Route]:
        """
        Returns routes in priority order based on:
        - fallback_order in workflow frontmatter
        - availability check (is ComfyUI running? is app open?)
        """
        pass

    def check_available(self, route: Route) -> bool:
        """
        Quick availability check before attempting a route:
        - api: ping the endpoint
        - cli: check command exists
        - uia: check app window is open (stub for now)
        - visual: check snapshot file exists
        """
        pass
```

For Phase 1a: implement `api` and `cli` availability checks only. Stub `uia` and `visual` as always-unavailable.

---

## Step 3 — Executor

Define `engine/executor.py`.

Executes a single route and returns success/failure + output:

```python
class Executor:
    def execute(self, route: Route, params: dict) -> ExecutionResult:
        """
        Executes the route. Returns:
        - success: bool
        - output: any (file path, response, etc.)
        - error: str if failed
        - duration_ms: int
        """
        pass
```

For Phase 1a: implement `api` executor only.

The API executor for ComfyUI:
1. Load the payload template JSON
2. Substitute variables (prompt, output_path, seed)
3. POST to ComfyUI /prompt
4. Poll /history/{prompt_id} every 2 seconds
5. Return output file path when complete or error after timeout

---

## Step 4 — The Replay Script

`scripts/replay.py` — the thing that proves Phase 1a works.

```
python scripts/replay.py --workflow comfyui-generate-image-001 \
  --params '{"prompt": "a red fox in a forest", "output_path": "/tmp/test.png"}'
```

It must:
1. Load the workflow from vault
2. Ask the router for the route order
3. Try each route via the executor
4. On success: log the run to vault/runs/, print output path
5. On failure: print which routes failed and why

No repair loop yet. Just try routes in order, fail gracefully.

---

## Step 5 — ComfyUI App Profile

Create `profiles/comfyui/comfyui-profile.md`:

```yaml
---
app: ComfyUI
app_version: latest
platform: windows
default_port: 8188
api_base: http://127.0.0.1:8188
endpoints:
  queue_prompt: POST /prompt
  get_history: GET /history/{prompt_id}
  get_queue: GET /queue
  interrupt: POST /interrupt
uia_window_title: "ComfyUI"
install_paths:
  - C:\Users\Dave\Documents\ComfyUI\
  - C:\ComfyUI\
output_folder: output/
---

## ComfyUI App Profile

ComfyUI is a node-based stable diffusion interface with a full REST API.
The API route is always preferred — it's faster and more reliable than UIA.

## Route Notes

### API Route
Full REST API available at http://127.0.0.1:8188 when ComfyUI is running.
Queue a prompt with POST /prompt, poll /history/{id} for completion.

### CLI Route
ComfyUI has no official CLI but a simple Python client can be scripted.
Use the API under the hood via requests.

### UIA Route
Window title: "ComfyUI" in browser (Electron wrapper or browser tab).
Queue Prompt button: look for button with text "Queue Prompt".

### Visual Route
Snapshot: snapshots/comfyui-queue-button.png
Region: bottom-right quadrant of ComfyUI window.
```

---

## Step 6 — Tests

Write tests in `tests/`:

`test_vault.py`:
- Load a workflow from a .md file → parse correctly
- Save a workflow dict → valid .md file created
- List workflows → returns all .md files in vault/workflows/
- Log a run → JSON file created in vault/runs/

`test_router.py`:
- Given a workflow with api + cli routes, api available → returns api first
- Given a workflow with api + cli routes, api unavailable → returns cli first
- All routes unavailable → returns ask route

Run: `python -m pytest tests/ -v`
All tests must pass before build is complete.

---

## Step 7 — README

Write `README.md`:

```markdown
# Marouba

An open source memory and replay engine for desktop workflows.

Teach it once. It remembers every route. It repairs itself.

## What It Does

- **Teach:** Record a workflow once. Saved to the vault as human-readable Markdown.
- **Replay:** Run any workflow by name. Uses the cheapest available route automatically.
- **Repair:** When a route breaks, Marouba tries fallbacks. If all fail, asks once, updates vault, never asks again.

## Quick Start

\`\`\`bash
pip install -r requirements.txt
python scripts/replay.py --workflow comfyui-generate-image-001 \
  --params '{"prompt": "a red fox in a forest", "output_path": "/tmp/test.png"}'
\`\`\`

## The Vault

Workflows are stored as human-readable Markdown files in vault/workflows/.
Each file contains: routes, fallback order, verification rules, run history.
The vault is yours — inspect it, edit it, share it.

## Status

Phase 1a — vault format + ComfyUI API route. Active development.
```

---

## Deliverables Checklist

- [ ] Folder structure created at Z:\Marouba\
- [ ] `engine/vault.py` — load, save, list, log runs
- [ ] `engine/router.py` — resolve route order, api + cli availability checks
- [ ] `engine/executor.py` — api executor for ComfyUI working
- [ ] `profiles/comfyui/comfyui-profile.md` — complete
- [ ] `vault/workflows/comfyui-generate-image-001.md` — first real workflow
- [ ] `scripts/replay.py` — runs end to end
- [ ] `tests/test_vault.py` + `tests/test_router.py` — all passing
- [ ] `README.md` — written
- [ ] `requirements.txt` — complete

---

## Definition of Done for Phase 1a

Run this command on a machine with ComfyUI running:

```bash
python scripts/replay.py --workflow comfyui-generate-image-001 \
  --params '{"prompt": "a red fox in a forest", "output_path": "/tmp/marouba-test.png"}'
```

Expected output:
```
[Marouba] Loading workflow: comfyui-generate-image-001
[Marouba] Route order: api, cli, uia, visual, ask
[Marouba] Trying route: api
[Marouba] POSTing to http://127.0.0.1:8188/prompt
[Marouba] Prompt queued: {prompt_id}
[Marouba] Polling for completion...
[Marouba] Complete. Output: /tmp/marouba-test.png
[Marouba] Run logged to vault/runs/2026-06-05-comfyui-generate-image-001.json
[Marouba] ✓ Phase 1a complete.
```

**If that runs clean, Phase 1a is done. Brief Dave and wait for Phase 1b instructions.**

---

## Rules

- Build directly to Z:\Marouba\
- No hardcoded API keys
- No UI, no frontend, no Flutter
- Python only today
- Run pytest before marking done
- Do not start Phase 1b without instruction

---

*Brief by Claude / NXeraTech*
*05 June 2026*
