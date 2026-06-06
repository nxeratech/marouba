# Marouba Profiles

Profiles describe how Marouba controls real apps. A profile includes app metadata, known APIs, UIA element names, shortcuts, CLI commands, output folders, and at least two executable workflows.

## Supported Profiles

| App | Folder | Workflows | Platform status |
| --- | --- | --- | --- |
| ComfyUI | `profiles/comfyui` | `generate-image`, `img2img` | Windows-verified, Mac-untested |
| Photoshop | `profiles/photoshop` | `export-for-web`, `batch-resize` | Windows-verified, Mac-untested |
| Ableton Live | `profiles/ableton` | `bounce-stems`, `export-master` | Windows-verified, Mac-untested |
| Blender | `profiles/blender` | `render-still`, `export-fbx` | Windows-verified, Mac-untested |
| Browser | `profiles/browser` | `screenshot-page`, `fill-and-submit-form` | Windows-verified, Mac-untested |

## Add a New Profile

1. Copy an existing folder from `profiles/`.
2. Rename it to `profiles/{app}/`.
3. Create `{app}-profile.md`.
4. Add `workflows/`.
5. Add at least two workflow `.md` files.
6. Run `python -m pytest tests/ -v`.
7. Open a pull request.

## Profile File Checklist

- App name and tested version.
- Platform and install paths.
- All known APIs and endpoints.
- UIA window title and key element names.
- Common keyboard shortcuts.
- CLI commands where applicable.
- Output folder paths.
- Notes about plugins, bridges, or required settings.

## Workflow Quality Checklist

- At least two workflows per profile.
- Workflow follows `VAULT_SPEC.md`.
- Routes are ordered cheapest first.
- At least two real route types before `ask`.
- Verification is defined where possible.
- Tested on a real install.
- No secrets, API keys, or private local paths.
- Markdown body explains what the workflow does.

## Route Preference

Prefer cheap and deterministic routes first:

1. `api`
2. `cli`
3. `script`
4. `uia`
5. `macos_uia`
6. `shortcut`
7. `visual`
8. `ask`

On Windows, prefer `uia` routes before `macos_uia`. On macOS, prefer `macos_uia` before `uia`.
