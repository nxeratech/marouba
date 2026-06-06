# Marouba

[![CI](https://github.com/nxeratech/marouba/actions/workflows/ci.yml/badge.svg)](https://github.com/nxeratech/marouba/actions/workflows/ci.yml)

Teach your computer how work gets done. Once.

Marouba is an open source memory and replay engine for desktop workflows. It records how a task is completed, stores the knowledge in a human-readable vault, and replays the cheapest reliable route automatically.

## What It Does

Teach records a workflow while the user performs it normally. Marouba captures app context, UI actions, shortcuts, and route metadata, then saves the workflow as Markdown in the vault. The result is inspectable and editable instead of trapped inside an opaque agent trace.

Replay loads a workflow from the vault and tries routes cheapest first. Direct APIs and CLI commands run before UI automation, shortcuts, visual fallbacks, and ask routes. A successful replay logs its run for later verification and marketplace quality checks.

Repair handles breakage without turning every failure into a new support ticket. When all known routes fail, Marouba asks once, records the correction, updates the vault, and tries that repair first next time. The goal is ask once, repair once, never ask again for the same failure.

## Quick Start

```powershell
pip install -r requirements.txt
python -m pytest tests/ -v
python scripts/replay.py --workflow comfyui-generate-image-001 --params '{"prompt": "a red fox in a forest", "output_path": "/tmp/marouba-test.png"}'
```

Run the ComfyUI replay command on a machine where ComfyUI is available at `http://127.0.0.1:8188`.

Teach a new workflow:

```powershell
python scripts/teach.py --name "Queue Prompt" --app "ComfyUI"
```

Type `done` and press Enter, or press Ctrl+C, to save the taught workflow.

## The Vault

The vault is the product. It is a portable folder of Markdown workflows, profile metadata, run logs, snapshots, and repair history. Workflows use YAML frontmatter for executable metadata and Markdown bodies for human notes, so creators can inspect, edit, version, and sell workflow packs without depending on a black-box agent runtime.

Read the formal standard in [VAULT_SPEC.md](VAULT_SPEC.md).

## Marketplace Beta

Creators can package signed workflow bundles for the marketplace beta. Bundles use the `.mwf` extension and contain `workflow.md`, `workflow.sig`, and `manifest.json`.

```powershell
python scripts/publish.py --workflow vault/workflows/comfyui-generate-image-001.md --author nxeratech --price 0.00
python scripts/install.py --bundle vault/workflows/comfyui-generate-image-001.mwf
```

Marketplace signing uses Ed25519. Unsigned or tampered bundles are rejected before install.

## Community Profiles

Marouba launches with profiles for ComfyUI, Photoshop, Ableton Live, Blender, and Browser automation. Each profile includes metadata plus at least two real workflows.

See [PROFILES.md](PROFILES.md) for the supported profile list and quality checklist.

## Companion App

The Windows companion is Marouba's hands and eyes. It runs locally, exposes `http://127.0.0.1:7842`, handles UIA lookups/clicks, reports the active window, and takes targeted screenshots. The Python backend remains the brain.

```powershell
cd companion
npm install
npm run build
```

The Mac companion lives in `companion-mac/` and exposes the same HTTP API. It uses a PyObjC/Cocoa accessibility sidecar bridge and the `macos_uia` route type while preserving the same vault format.

## Contributing

Contributions are welcome, especially high-quality app profiles. Start with [.github/CONTRIBUTING.md](.github/CONTRIBUTING.md), copy an existing profile, add at least two tested workflows, and open a pull request.

## Roadmap

- Phase 1: Vault format, replay, multi-route repair loop - complete
- Phase 2: Teach mode - complete
- Phase 3: Tauri Windows companion MVP - complete
- Phase 4: First 5 community app profiles - complete
- Phase 5: Open source launch prep - complete
- Phase 6: Marketplace packaging and signing - complete
- Phase 7: Mac companion port - current

## Licence

Marouba is licensed under the Business Source Licence 1.1. The change date is 2030-06-06, after which the code changes to Apache License 2.0. Personal and open source use is granted for free. See [LICENSE](LICENSE).
