# Marouba Vault Workflow Format

Version: 0.1
Status: launch draft

The Marouba vault is a directory of human-readable Markdown files. Each workflow is one `.md` file with YAML frontmatter and optional Markdown body notes. The frontmatter is executable metadata; the body is documentation for humans.

## Workflow File

```markdown
---
id: browser-screenshot-page
name: Browser Screenshot Page
app: Browser
description: Capture a screenshot of a browser page.
params:
  - name: url
    type: string
    required: true
  - name: output_path
    type: string
    required: true
tags: [browser, screenshot]
author: nxeratech
created: 2026-06-06
routes: []
fallback_order: [api, cli, uia, shortcut, visual, ask]
verification:
  type: file_exists
  path: "{output_path}"
calls: []
depends_on: []
---

# Human notes
```

## Required Frontmatter Fields

Every workflow must begin with a YAML frontmatter block delimited by `---`.

| Field | Type | Description |
| --- | --- | --- |
| `id` | string | Stable workflow id. Use lowercase kebab-case. |
| `name` | string | Human-readable workflow name. |
| `app` | string | App or environment this workflow targets. |
| `description` | string | One-sentence summary shown to agents, users, and marketplace listings. |
| `params` | list[object] | Input parameters accepted by the workflow. Each item should include `name`, `type`, and `required`. Empty list allowed only for workflows with no inputs. |
| `tags` | list[string] | Search and marketplace tags. |
| `author` | string | Creator or organization. |
| `created` | date string | Creation date, ISO `YYYY-MM-DD`. |
| `routes` | list | Ordered route definitions available to execute the workflow. |
| `fallback_order` | list[string] | Route types to try, cheapest first. Must end with `ask`. |
| `verification` | object | Completion check. |
| `calls` | list | Workflows or external actions called by this workflow. Empty list allowed. |
| `depends_on` | list | Required profiles, assets, scripts, or tools. Empty list allowed. |

## Optional Frontmatter Fields

| Field | Type | Description |
| --- | --- | --- |
| `app_version` | string | Tested app version or `latest`. |
| `category` | string | Workflow category. |
| `last_verified` | date string | Last date this workflow was verified. |
| `notes` | string | Short machine-readable note. |
| `license` | string | Workflow/profile-specific license if different from project. |
| `inputs` | object | Optional schema for expected params. |
| `outputs` | object | Optional schema for produced artifacts. |
| `platform` | string | Optional route/workflow platform: `windows`, `mac`, or `all`. Default is `all`. |

## Route Types

Marouba recognizes eight route types. Engines should skip unavailable routes and try the next route in `fallback_order`.

### `api`

Use direct app or service APIs.

Required:
- `type: api`
- `endpoint`: URL, local endpoint, websocket URL, or named API entrypoint
- `method`: HTTP method, `CDP`, `PYTHON`, or other protocol label

Optional:
- `payload_template`: path to JSON, Python, or protocol payload template
- `headers`: object
- `timeout_seconds`: number

### `cli`

Use a command-line executable.

Required:
- `type: cli`
- `command`: command string with `{param}` placeholders

Optional:
- `cwd`: working directory
- `env`: environment variables

### `script`

Use app scripting, such as JSX, Python, AppleScript, Lua, or Max for Live.

Required:
- `type: script`
- `runtime`: scripting runtime or host app
- `script`: script path

Optional:
- `args`: list or object of arguments

### `uia`

Use Windows UI Automation through the Marouba Companion.

Required:
- `type: uia`
- `app_window` or `window_title`: target window title
- `element` or `name`: UI element name

Optional:
- `role` or `control_type`: UIA role
- `timeout_seconds`: number
- `platform`: normally `windows`

### `macos_uia`

Use macOS Accessibility through the Mac Marouba Companion. This keeps the same companion HTTP API shape as Windows while using Cocoa/UIElement underneath.

Required:
- `type: macos_uia`
- `app_window` or `window_title`: target frontmost app/window title
- `element` or `name`: accessibility element name

Optional:
- `role` or `control_type`: macOS accessibility role such as `AXButton`
- `timeout_seconds`: number
- `platform`: normally `mac`

### `shortcut`

Send a keyboard shortcut to the active window.

Required:
- `type: shortcut`
- `keys`: list of keys, for example `[ctrl, enter]`

Optional:
- `window_title`: expected active window

### `visual`

Use visual fallback data.

Required, one of:
- `snapshot`: path to image fingerprint
- `coordinates`: object with `x` and `y`

Optional:
- `region`: object with `x`, `y`, `width`, `height`
- `button`: mouse button

### `ask`

Ask the user once and repair the vault.

Required:
- `type: ask`

`ask` should only appear in `fallback_order`, normally as the final item. The repair loop may add a `manual_repair` route internally; this is a recorded repair artifact, not a primary spec route.

## Verification Types

### `file_exists`

Required:
- `type: file_exists`
- `path`: file path, may include `{param}` placeholders

Optional:
- `timeout_seconds`

### `http_poll`

Required:
- `type: http_poll`
- `endpoint`: URL to poll
- `success_path`: response field path to inspect
- `success_value`: expected value

Optional:
- `interval_seconds`
- `timeout_seconds`

### `process_running`

Required:
- `type: process_running`
- `name`: process name

Optional:
- `timeout_seconds`

## Run Log Format

Run logs are JSON files under `vault/runs/`.

```json
{
  "workflow_id": "comfyui-generate-image",
  "logged_at": "2026-06-06T00:00:00+00:00",
  "result": {
    "success": true,
    "route_type": "api",
    "output": "C:/path/output.png",
    "error": null,
    "duration_ms": 1234
  }
}
```

Required fields:
- `workflow_id`
- `logged_at`
- `result.success`
- `result.route_type`
- `result.duration_ms`

Optional fields:
- `result.output`
- `result.error`
- `result.repair`
- `result.failure_signature`

## Versioning

The current vault spec is `0.1`. Until `1.0`, fields may be added without breaking older workflows. Breaking changes require:

1. A new spec version.
2. A migration note in this file.
3. Backward-compatible loading where practical.
4. Tests for old and new examples.

Workflow files may add `vault_spec: "0.1"` later. Absence of `vault_spec` means `0.1` during the launch period.
