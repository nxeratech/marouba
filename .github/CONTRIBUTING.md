# Contributing to Marouba

Marouba is an open source memory and replay engine for desktop workflows. The most useful early contribution is a high-quality app profile: a profile document plus at least two real workflows that can teach, replay, and repair reliably.

## Add a New App Profile

1. Fork the repository.
2. Copy an existing profile folder from `profiles/`.
3. Rename it to `profiles/{app}/`.
4. Fill in `{app}-profile.md` frontmatter:
   - app name and version
   - APIs and endpoints
   - UIA window title and known element names
   - keyboard shortcuts
   - CLI commands
   - output folder paths
5. Add at least two workflows under `profiles/{app}/workflows/`.
6. Make each workflow valid vault Markdown. See `VAULT_SPEC.md`.
7. Run `python -m pytest tests/ -v`.
8. Submit a pull request using the PR template.

## Profile Quality Bar

- Tested on a real install of the app.
- Includes at least two useful workflows.
- Documents all known cheap routes before UI routes.
- Includes verification rules where possible.
- Uses `ask` only as the final fallback.
- Avoids secrets, local API keys, and private paths.

## Mac Profile Contributions

Mac support uses `macos_uia` routes through `companion-mac/`, backed by Cocoa accessibility APIs. When adding or Mac-testing a profile:

1. Keep existing `uia` routes for Windows.
2. Add parallel `macos_uia` routes for Mac-specific accessibility names or roles.
3. Set `platform: mac` on Mac-only routes when needed.
4. Test with the Mac companion running on `127.0.0.1:7842`.
5. Note the app version and macOS version in the profile body.
6. Update `PROFILES.md` from `Mac-untested` to `Mac-verified` only after a real replay passes.

## Development Setup

```powershell
pip install -r requirements.txt
python -m pytest tests/ -v
```

The Windows companion lives in `companion/` and requires the Tauri/Rust toolchain. The Mac companion lives in `companion-mac/` and additionally requires Python with PyObjC access to Cocoa accessibility APIs.
