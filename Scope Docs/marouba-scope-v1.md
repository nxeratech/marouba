# Marouba — Full Project Scope
**NXeraTech / Dave Reilly**
**Date: 05 June 2026**
**Status: Pre-build — Saol shipping first**

---

## What Is Marouba? (One Page)

Marouba is a memory layer that sits between you and every app on your computer.

You show it how to do something once. It remembers every possible way to do it. Next time you ask, it does it automatically — picking the fastest, cheapest route. If something breaks, it figures out a workaround. If it can't, it asks you once, learns the fix, and never asks again.

**The vault — not the agent — is the product.**

```
You show it once
        ↓
It records everything (clicks, shortcuts, API calls, scripts)
        ↓
You ask it to do it again
        ↓
It picks the cheapest route automatically
        ↓
Something breaks?
        ↓
Tries all fallbacks → asks you once → updates → never asks again
```

---

## The Problem It Solves

Every creative professional repeats the same annoying workflows every day:

- Export this Photoshop file 5 different ways
- Load this ComfyUI workflow, change the prompt, queue it
- Batch resize a folder of images
- Open Ableton, drop to a new track, bounce stems

Current AI tools (Microsoft Copilot, Anthropic Computer Use) do this:

```
Look at screen → guess what to click → click → look again → repeat
```

**Slow. Expensive. Breaks constantly.**

Marouba does this:

```
Check memory → find cheapest route → execute → verify → done
```

---

## How It Works — The 8 Routes

For any task, Marouba tries these in order, cheapest first:

```
1. Direct API call ──────────────── fastest, free
        ↓ (fails)
2. App scripting (JSX, Python) ──── fast, reliable
        ↓ (fails)
3. Windows UI Automation ─────────── reads buttons/menus by name
        ↓ (fails)
4. Keyboard shortcuts ────────────── stable, fast
        ↓ (fails)
5. Cached visual fingerprint ─────── "this looks like the export button"
        ↓ (fails)
6. Small region vision scan ──────── only looks at part of screen
        ↓ (fails)
7. Full screen vision ────────────── last resort, expensive
        ↓ (fails)
8. Ask user once → repair → done ─── never asks again
```

This cuts AI vision costs by ~90% vs naive computer-use approaches.

---

## The Three Modes

### Teach
```
User clicks Record
        ↓
Performs task once normally
        ↓
Marouba captures: app, window, button names, shortcuts, 
                  screenshots, mouse path, keyboard actions
        ↓
Saves as workflow in the vault
```

### Replay
```
User says "run the export workflow"
        ↓
Marouba reads vault → finds workflow
        ↓
Resolves each step via cheapest route
        ↓
Executes → verifies result → done
```

### Repair
```
Step fails (UI updated, app changed)
        ↓
Tries all 8 fallback routes
        ↓
All fail? → asks user to click correct thing once
        ↓
Updates vault → future runs work automatically
```

---

## The Vault — What Gets Saved

The vault is structured like an Obsidian knowledge graph. Human-readable, inspectable, editable.

```
vault/
  workflows/
    photoshop-export-web.md       ← a complete recorded task
    comfyui-generate-image.md
    ableton-bounce-stems.md
  elements/
    export-button.md              ← a UI element with all routes
    brush-tool.md
  snapshots/
    export-button.crop.png        ← visual fingerprint
  runs/
    2026-06-05-export.json        ← log of what actually happened
```

Each workflow file contains:
- What the task is
- Every step in order
- For each step: API path, script path, UIA path, shortcut, visual fingerprint
- Fallback chain
- Verification rule (how to confirm it worked)
- User corrections history

---

## Architecture — Two Parts

```
┌─────────────────────────────────┐
│   Windows Companion App         │  ← "the hands and eyes"
│   (native Windows)              │
│                                 │
│   • Watches screen              │
│   • Reads UI element names      │
│   • Takes screenshots           │
│   • Moves mouse / types keys    │
│   • Detects which app is open   │
└──────────────┬──────────────────┘
               │ localhost HTTP/WebSocket
┌──────────────▼──────────────────┐
│   WSL Backend                   │  ← "the brain"
│   (WSL2 Ubuntu on your machine) │
│                                 │
│   • Workflow planner            │
│   • Graph database              │
│   • LLM calls                   │
│   • Vault sync (Obsidian)       │
│   • Python tools                │
└─────────────────────────────────┘
```

---

## MVP — What Needs To Be Proven

One task. Multiple routes. One repair. 60 seconds.

```
"Make me a finished image"
        ↓
ComfyUI API → generates image
        ↓
Filesystem → finds output file
        ↓
Photoshop JSX → opens, polishes, exports
        ↓
Saves to output folder
```

Then deliberately break one step:

```
Break Photoshop JSX step
        ↓
Marouba tries: UIA → shortcut → visual scan
        ↓
All fail → asks Dave once
        ↓
Dave clicks correct button
        ↓
Vault updates → never asks again
```

**That demo is the entire pitch.**

---

## First 5 Workflows (Start Here)

Don't try to support every app. Start with these:

| # | App | Workflow |
|---|-----|----------|
| 1 | Photoshop | Export web-ready image |
| 2 | Photoshop | Batch resize a folder |
| 3 | Photoshop | Add watermark |
| 4 | ComfyUI | Load workflow, set prompt, queue render |
| 5 | Browser | Upload file + fill repeated form fields |

---

## Options — Business Model

### Option A: Open Source + Marketplace ⭐ Recommended
```
Engine → open source (GitHub)
        ↓
Community builds app profiles (Photoshop, Blender, Ableton)
        ↓
Creators sell workflow packs on marketplace
        ↓
Platform takes revenue cut
        ↓
Moat = the vault, not the code
```
**Pros:** Community builds what you can't. Trust (creators see it's not scraping). Scales without headcount.
**Cons:** Slower initial revenue. Requires community nurturing.

### Option B: Closed SaaS
```
Subscription product → €X/mo per user
App profiles built internally
No marketplace
```
**Pros:** Faster revenue. Full control.
**Cons:** Can't out-resource Microsoft/Adobe. No community moat.

### Option C: Hybrid — Open engine, paid cloud sync
```
Engine open source
Vault sync to cloud = paid feature
Teams share vaults = enterprise tier
```
**Pros:** Revenue + community. Middle ground.
**Cons:** More complex to build.

**Recommendation: Start with Option A. Build the engine open, prove the demo, launch marketplace post-MVP.**

---

## Options — First Platform

### Option A: Photoshop + ComfyUI first ⭐ Recommended
- Dave already uses both daily
- ComfyUI has a clean API (cheapest route = API call)
- Photoshop has JSX scripting (second cheapest route)
- Real workflows Dave can test himself immediately

### Option B: Browser automation first
- Broader market (everyone uses a browser)
- Easier to demo
- Less differentiated — lots of competition

### Option C: Ableton first
- Unique angle, less competition
- Harder to automate (less UIA support)
- Smaller initial market

**Recommendation: Photoshop + ComfyUI. Dave can be the first power user.**

---

## Options — Tech Stack for Vault

### Option A: Obsidian-native Markdown ⭐ Recommended
- Human readable, inspectable, editable by Dave directly
- Already in Dave's workflow (Obsidian vault exists)
- No database setup needed for MVP

### Option B: Graph database (Neo4j / SQLite)
- Better for complex queries at scale
- Overkill for MVP
- Less inspectable

### Option C: JSON files
- Simple, fast to build
- Less structured than Markdown with frontmatter
- Harder to extend

**Recommendation: Markdown vault for MVP. Migrate to graph DB post-traction.**

---

## Build Sequence

```
Phase 1 — Prove the concept (weeks 1-2)
        ↓
Windows companion: read UI element names + take screenshots
WSL backend: receive instructions, call ComfyUI API
Vault: save first workflow as Markdown
Demo: "Generate image via ComfyUI API" — one route, working

        ↓

Phase 2 — Multiple routes + repair (weeks 3-4)
        ↓
Add UIA route (click by element name)
Add shortcut route
Add repair loop (ask once, update vault)
Demo: ComfyUI API fails → UIA takes over → repair loop works

        ↓

Phase 3 — Teach mode (weeks 5-6)
        ↓
User clicks Record
System captures full workflow
Saves to vault automatically
Replay works from recorded workflow

        ↓

Phase 4 — Photoshop integration (weeks 7-8)
        ↓
JSX scripting route working
5 Photoshop workflows in vault
Full demo: ComfyUI → Photoshop → export → done

        ↓

Phase 5 — Polish + open source prep
        ↓
GitHub repo public
README + demo video
Marketplace spec written
```

---

## Window + Risk

- **12-18 month window** before Microsoft/Adobe ship something overlapping
- Move fast on the demo — the 60-second proof is the entire pitch
- **Risk:** Microsoft has UIA access too. Moat must be the vault + community, not the tech.
- **Risk:** ComfyUI API changes. Mitigate: vault repair loop handles this automatically.
- **EUIPO trademark filing** recommended before any public launch

---

## Domains (Registered 05 June 2026)
- **marouba.app** — primary
- **marouba.eu**
- **marouba.ie**
- Registrar: Blacknight, order 8501789379

---

## Build Team
| Role | Responsibility |
|---|---|
| Codex | All code — Windows companion, WSL backend, vault, teach/replay/repair |
| Opus | End-of-day architecture reviews only |
| Barry | ComfyUI/Ableton integration, Windows-side infra |
| Claude | Project manager, vision holder, handovers |
| Dave | Direction, taste, final decisions |

---

## Next Action
1. ✅ Saol confirmed working on device
2. Write Day 1 Codex brief (Phase 1 only — prove the concept)
3. GitHub repo: `nxeratech/marouba`
4. Confirm project name: Marouba ✅

---

*Scope maintained by Claude / NXeraTech*
*Last updated: 05 June 2026*
