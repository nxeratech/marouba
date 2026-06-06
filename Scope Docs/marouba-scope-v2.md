# Marouba — Project Scope v2
**NXeraTech / Dave Reilly**
**Date: 05 June 2026**
**Status: Pre-build — vision locked, architecture agreed**

---

## The One-Line Vision

> "Teach your computer how work gets done. Once."

---

## What This Actually Is

Not desktop automation.
Not computer use.
Not RPA.
Not macros.

**An open standard for capturing, replaying, and selling human taste and process.**

The engine is open source. The vault format is the standard. The marketplace is where creators earn from their expertise. The network effect is the moat.

---

## The Problem Nobody Has Solved

The frontier labs (Anthropic, Microsoft, Google) are all racing to build computer use. They're building stateless vision-click loops:

```
Look at screen → guess what to click → click → look again
```

Every session starts from zero. No memory. No taste. No learning.
Expensive. Slow. Brittle. Breaks on every UI update.

There's a deeper problem nobody is addressing:

**AI has extracted enormous value from human creative knowledge without consent or compensation.** Styles scraped. Workflows reverse-engineered. Taste replicated. The people whose years of practice made the training data valuable got nothing.

Marouba inverts both problems at once.

---

## The Core Insight

Every app action has multiple routes to the same outcome. The system tries cheapest first:

```
1. Direct API / backend call ────── fastest, free
        ↓ (fails)
2. App scripting (JSX, Python) ──── fast, reliable
        ↓ (fails)
2b. CLI command (ffmpeg, ImageMagick) ── batch ops, transforms
        ↓ (fails)
3. Windows UI Automation ─────────── reads buttons by name/role
        ↓ (fails)
4. Keyboard shortcuts ────────────── stable, predictable
        ↓ (fails)
5. Cached visual fingerprint ─────── "this looks like the export button"
        ↓ (fails)
6. Vision scan (region or full) ──── last resort, targeted not global
        ↓ (fails)
7. Ask user once → repair → done ─── never asks again
```

Vision is the fallback, not the foundation. This cuts AI vision costs by ~90% versus naive computer-use approaches — and more importantly, it means the system gets *faster and cheaper over time* as the vault fills in.

---

## The Three Modes

### Teach
```
User clicks Record → performs task once normally
        ↓
System captures: app, window, element names, shortcuts,
                 screenshots, mouse path, keyboard actions
        ↓
Saved as human-readable workflow in the vault
```

### Replay
```
User says "run the export workflow"
        ↓
System reads vault → resolves each step via cheapest route
        ↓
Executes → verifies result → done
```

### Repair
```
Step fails (UI updated, app changed, element renamed)
        ↓
Tries all routes in order
        ↓
All fail → asks user to correct it once
        ↓
Vault updates → never asks again
        ↓
Repair is shared back to the community profile (opt-in)
```

**The repair loop is what nobody else has built cleanly.**

---

## The Vault — An Open Standard

The vault is structured like an Obsidian knowledge graph. Human-readable. Inspectable. Portable. Shareable.

```
vault/
  workflows/
    photoshop-export-web.md       ← a complete recorded task
    comfyui-generate-image.md
    ableton-bounce-stems.md
  elements/
    export-button.md              ← UI element with all routes
    brush-tool.md
  snapshots/
    export-button.crop.png        ← visual fingerprint
  runs/
    2026-06-05-export.json        ← execution log
```

Each workflow file:

```yaml
---
app: Photoshop
app_version: 26.x
last_verified: 2026-06-05
author: davesynths84
category: export
tags: [web, batch, optimise]
routes:
  - type: jsx_script
    path: scripts/export-web.jsx
  - type: uia
    element: export-button
  - type: shortcut
    keys: Alt+F, E
  - type: visual
    snapshot: snapshots/export-menu.crop.png
calls: []
depends_on: []
---
```

**This format is the product.** Once it becomes the standard for sharing desktop workflows, the network effect kicks in. Every app profile contributed by the community makes every user's vault more capable.

---

## The Marketplace — Executable Human Knowledge

Sample packs changed music production. Preset packs changed photography. Workflow packs are the next category — but unlike samples or presets, they're not outputs or ingredients. They're **process**. The difference between buying someone's drum samples and buying the way they hear rhythm and build a groove.

```
Creator records their workflow ── their taste, their order of operations,
                                   their decision rules, their shortcuts
        ↓
Packages it with: prompts, presets, screenshots, example outputs,
                  decision rules, required plugins
        ↓
Lists on marketplace
        ↓
Buyer purchases → workflow installs to their vault
        ↓
Agent executes and adapts it on their own machine
        ↓
Creator earns 70% of every sale
```

**This is the ethical inversion.** Instead of AI extracting creative knowledge without consent, creators package their expertise as executable IP and earn from it directly.

---

## Why This Is Acquisition-Worthy

The frontier labs cannot build this. Not because of technical capability — because it requires human participation at scale. You can't scrape taste. A marketplace of human-verified, executable creative workflows is a dataset no lab can replicate.

```
Open source engine
        ↓
Community builds app profiles (Photoshop, Blender, Ableton, ComfyUI...)
        ↓
Vault format becomes the standard
        ↓
Marketplace grows — creators earn, buyers get executable process
        ↓
Network effect: more profiles → more users → more creators → more profiles
        ↓
Acquirer buys: the network + the vault standard + the marketplace
               + the only dataset of real human creative process
```

The open source engine actually strengthens the acquisition case. GitHub, Figma, Hugging Face — open ecosystems with network effects are worth more to acquirers than closed products. You're buying the community and the data flywheel, not just the code.

**The 12-18 month window is real.** Move before Microsoft ships this into Creative Cloud or Anthropic ships persistent computer use memory. The moat after that point is the community vault — which takes time to build.

---

## Architecture

```
┌─────────────────────────────────────┐
│   Windows Companion App             │  ← "the hands and eyes"
│   (Tauri — Rust + webview)          │
│                                     │
│   • Watches active app/window       │
│   • Reads UI element names (UIA)    │
│   • Takes targeted screenshots      │
│   • Executes mouse/keyboard         │
│   • Multi-monitor aware             │
│   • Never captures passwords/banking│
└──────────────┬──────────────────────┘
               │ localhost HTTP/WebSocket
┌──────────────▼──────────────────────┐
│   WSL / Local Backend               │  ← "the brain"
│   (Python + graph DB)               │
│                                     │
│   • Workflow planner                │
│   • Route resolver                  │
│   • Vault read/write (Markdown)     │
│   • LLM calls (repair + teach)      │
│   • Embeddings / semantic search    │
│   • Obsidian vault sync             │
└─────────────────────────────────────┘
```

Phase 1: Python prototype (no companion UI needed).
Phase 3+: Tauri companion for production.

---

## MVP — The 60-Second Demo

One task. Multiple routes. One repair. This is the entire pitch.

```
"Make me a finished image"
        ↓
Route 1: ComfyUI API → generates image ✓
        ↓
Route 1: Filesystem → finds output ✓
        ↓
Route 2: Photoshop JSX → opens, polishes, exports ✓
        ↓
[Deliberately break the JSX route]
        ↓
Route 3: UIA → finds Export menu by name ✓
        ↓
[Deliberately break UIA too]
        ↓
Route 7: Asks Dave once → Dave clicks → vault updates ✓
        ↓
[Run again] → works automatically, never asks again ✓
```

---

## Non-Goals (What Marouba Is NOT)

- Not a general AI agent or chatbot
- Not a screen recorder
- Not SaaS-only (local-first, always)
- Not limited to one app or ecosystem
- Not a replacement for human creativity — an amplifier of it
- Not trying to out-resource the frontier labs on vision

---

## Build Phases

```
Phase 1a (Week 1) ── Prove the vault format
  ComfyUI API route only. No companion app.
  Python script → ComfyUI API → image → saved to folder
  Workflow saved as .md in vault. Format locked.

Phase 1b (Week 2) ── Prove multi-route + repair
  Add UIA route. Add shortcut route.
  Repair loop working: ask once → vault updates → never asks again.
  60-second demo achievable.

Phase 2 (Weeks 3-4) ── Teach mode
  User clicks Record. System captures full workflow.
  Saves to vault automatically. Replay works.

Phase 3 (Weeks 5-6) ── Companion app MVP
  Tauri Windows companion: UIA scanning, screenshots, execution.
  Replace Python prototype for UIA routes.

Phase 4 (Weeks 7-8) ── First 5 community profiles
  Photoshop, ComfyUI, Ableton, Blender, Browser.
  NXeraTech builds these — they seed the marketplace.

Phase 5 ── Open source launch
  GitHub public. README + demo video.
  Workflow format spec published.
  First external contributors invited.

Phase 6 ── Marketplace beta
  Creators can list workflows.
  70/30 revenue split.
  Review + signing system.

Phase 7 ── Mac port
  Cocoa/UIElement replaces UIA on companion.
  Same vault format, same backend.
```

---

## Success Metrics Per Phase

| Phase | Done When |
|---|---|
| 1a | ComfyUI API route executes, workflow saved as valid .md |
| 1b | Repair loop: break a route, ask once, never asks again |
| 2 | Record a workflow, replay it cold 3 days later without prompting |
| 3 | Companion app replaces Python prototype for all UIA routes |
| 4 | 5 community profiles work on a machine Marouba has never seen |
| 5 | 10 external GitHub contributors in first month |
| 6 | First paid marketplace workflow sale |

---

## Competitive Landscape

| Competitor | What They Do | Marouba's Edge |
|---|---|---|
| Anthropic Computer Use | Stateless vision-click | No memory, no vault, no marketplace |
| Microsoft Copilot | Stateless, Windows-integrated | No community, no creator economy |
| Adobe (future) | Will build this for Creative Cloud only | Cross-app (can't touch ComfyUI/Ableton) |
| AutoHotkey | Windows scripting | No AI, no vision, no vault, power-user only |
| UiPath / Blue Prism | Enterprise RPA | €10K+/yr, no creative focus, no marketplace |
| Zapier / Make | Web automation | Desktop-blind |
| Apple Shortcuts | Mac automation | No AI, no repair, no learning |

**The real threat is Adobe shipping this natively in Creative Cloud.** Mitigation: cross-app moat — Adobe cannot touch ComfyUI, Blender, or Ableton. Community vault — 1000 community workflows beats anything Adobe builds internally.

---

## Security & Privacy

- **Local-first by default** — vault never leaves the machine unless user opts in
- **Screenshot redaction** — browser password fields, banking apps excluded by default
- **Allowlist model** — user controls which apps Marouba can watch
- **Vault encryption** option for sensitive workflows
- **Human-readable vault** — user can inspect and delete anything at any time
- **Signed marketplace workflows** — cryptographic signature on every distributed workflow

---

## Business Model

```
Engine ────── Open source (BSL licence — use free, sell derivative = pay)
Profiles ───── Open source (community contributed, MIT)
Marketplace ── NXeraTech operated, 70/30 creator/platform split
Cloud sync ─── Optional paid feature (vault backup + team sharing)
Enterprise ─── Shared vaults, SSO, audit log
```

**Marketplace seeding strategy:**
- NXeraTech ships 10 high-quality launch workflows before public launch
- Featured creator programme for first 6 months
- Workflow format designed so one developer can write a profile in an afternoon

---

## Domains (Registered 05 June 2026)
- **marouba.app** — primary
- **marouba.eu**
- **marouba.ie**
- Registrar: Blacknight, order 8501789379
- Trademark: clear to use (TMview search completed 05 June 2026)
- EUIPO filing recommended before public launch

---

## Build Team
| Role | Responsibility |
|---|---|
| Codex | All code — companion, backend, vault engine, teach/replay/repair |
| Opus | End-of-day architecture reviews only |
| Barry | ComfyUI/Ableton integration, Windows-side infra testing |
| Claude | Project manager, vision holder, scope, handovers |
| Dave | Direction, taste, final decisions, first power user |

---

## Decision Log

| Decision | Rationale | Date |
|---|---|---|
| Vault format: Markdown | Human-readable, Obsidian-native, portable, no DB needed for MVP | 05 Jun 2026 |
| Engine licence: BSL | Prevents commercial forks while keeping community open | 05 Jun 2026 |
| Companion: Tauri (Phase 3+) | Small binary, low resource, cross-platform path | 05 Jun 2026 |
| Phase 1: Python prototype | Prove vault format before investing in companion UI | 05 Jun 2026 |
| Start with ComfyUI + Photoshop | Dave uses both daily, ComfyUI has clean API | 05 Jun 2026 |
| Mac: Phase 7 | Windows-first, same vault format, Cocoa/UIElement later | 05 Jun 2026 |

---

*Scope v2 — Claude / NXeraTech*
*Incorporates Barry review v1*
*Last updated: 05 June 2026*
