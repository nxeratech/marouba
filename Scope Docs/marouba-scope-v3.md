# Marouba — Full Project Scope v3
**NXeraTech / Dave Reilly**
**Updated: 06 June 2026**
**Status: Architecture built, real-world testing next**

---

## What Is Marouba?

Marouba is a memory layer that sits between you and every app on your computer.

You show it how to do something once. It saves that workflow as a human-readable .md file in a vault. Next time — whether you ask, or your AI agent asks — it executes automatically, picking the fastest, cheapest route. If something breaks, it figures out a workaround. If it can't, it asks you once, learns the fix, updates the .md, and never asks again.

**The vault — not the agent — is the product.**

---

## The Core Vision

**Record once. Call from anywhere. Repairs itself.**

The vault stores creative decisions, not just button clicks. A well-crafted workflow captures taste — the way Dave handles colour grading, the way a producer layers sounds, the specific sequence of decisions that makes someone's work distinctly theirs.

That's what people will pay for in the marketplace. Not "load instruments" — but "sound like this producer" or "grade like this photographer."

```
Dave spends 3 hours getting something exactly right
— every creative decision, every adjustment
        ↓
Marouba remembers every single decision
        ↓
Next time: "do it like that"
        ↓
Done. Dave's taste. Instantly.
```

---

## The Universal Call Interface

No custom integration. Plug and play.

```
┌─────────────────────────────────────────┐
│  Anyone can call a workflow:            │
├─────────────────────────────────────────┤
│  MCP server  → Barry, Claude, OpenClaw  │
│  REST API    → n8n, Hermes, any HTTP    │
│  CLI         → scripts, cron jobs       │
│  Marouba app → humans recording/replay  │
└──────────────────┬──────────────────────┘
                   ↓
         Marouba engine
         (reads vault .md)
                   ↓
         Executes on your machine
         via cheapest route
```

If you've taught it once, every tool in your stack can replay it. Zero extra config.

---

## The 8 Routes (cheapest first)

```
1. Direct API call           ← fastest, free (ComfyUI, Ableton OSC)
2. App scripting             ← fast, reliable (Photoshop JSX, Python)
3. Windows UI Automation     ← reads buttons/menus by name
4. Keyboard shortcuts        ← stable, fast
5. Cached visual fingerprint ← "this looks like the export button"
6. Small region vision scan  ← only looks at part of screen
7. Full screen vision        ← last resort, expensive
8. Ask user once → repair    ← updates vault, never asks again
```

~90% cost reduction vs naive computer-use approaches.

---

## The Vault

```
vault/
  workflows/
    comfyui-generate-image.md     ← complete recorded task
    photoshop-grade-portrait.md   ← Dave's creative decisions
    ableton-mixdown.md
  elements/
    export-button.md              ← UI element, all routes
  snapshots/
    export-button.crop.png        ← visual fingerprint
  runs/
    2026-06-06-grade.json         ← execution log
```

Each .md file:
- Human readable and editable directly
- Shareable (send your vault, share your workflows)
- Sellable (marketplace)
- Git-friendly
- Obsidian-compatible (graph view, backlinks)

---

## Architecture

```
┌─────────────────────────────────┐
│   Windows Companion App         │  ← "the hands and eyes"
│   (Tauri, port 7842)            │
│                                 │
│   • Records workflows           │
│   • Reads UI element names      │
│   • Takes screenshots           │
│   • Moves mouse / types keys    │
│   • Token-gated security        │
└──────────────┬──────────────────┘
               │ localhost HTTP
┌──────────────▼──────────────────┐
│   WSL/Python Backend            │  ← "the brain"
│                                 │
│   • Workflow planner            │
│   • Vault reader/writer         │
│   • Route selector              │
│   • Repair loop                 │
│   • MCP server                  │
│   • REST API                    │
└──────────────┬──────────────────┘
               │
┌──────────────▼──────────────────┐
│   Vault (.md files)             │  ← "the memory"
│                                 │
│   Human readable, git-friendly, │
│   Obsidian-compatible           │
└─────────────────────────────────┘
```

---

## MCP Server — Critical Missing Piece

Exposes Marouba workflows as tools any AI agent can call natively.

```
marouba_list_workflows   → list all workflows in vault
marouba_run_workflow     → execute workflow by name
marouba_teach_workflow   → start recording a new workflow
marouba_get_status       → check last run result
marouba_repair_workflow  → force repair on a workflow
```

Barry, Claude, OpenClaw point at the MCP server URL → instantly access every workflow in the vault. No custom integration needed.

---

## The Real Demo

```
60 seconds. Teach → Replay → Break → Repair → Never asks again.
```

Not ComfyUI (too abstract, looks like Midjourney to outsiders).

**Photoshop — Dave makes something:**
- Opens a raw image
- Makes his specific creative decisions (colour, tone, style)
- Marouba records every decision
- New image: "do it like that one"
- Marouba replays Dave's exact creative process
- Break one step → repair loop fires → vault updates → fixed

**Why this demo works:**
- Everyone understands Photoshop
- The creativity is visible — not just button automation
- Dave not being a pro artist actually helps — it shows anyone can use it
- Nobody else is doing this

---

## Business Model

### Open Source + Marketplace
```
Engine → open source (BSL licence, GitHub)
        ↓
Community builds app profiles
        ↓
Creators sell workflow packs (their taste, their style)
        ↓
Platform takes 30% cut
        ↓
Moat = the vault + community, not the code
```

---

## What's Built (Phases 1-7)
- ✅ Vault format + ComfyUI API route
- ✅ Multi-route + repair loop (architecture)
- ✅ Teach mode (record workflow, save to vault)
- ✅ Tauri Windows companion (port 7842, token-gated)
- ✅ 5 community app profiles + 10 seed workflows
- ✅ Open source launch prep
- ✅ Marketplace (Ed25519 signing, .mwf bundles)
- ✅ Mac port
- ✅ Security hardened (Opus reviewed)
- ✅ CI green
- ✅ Website live (marouba.app)
- ✅ @marouba_app X account live

## What's NOT Done (Critical Path)
- ❌ MCP server
- ❌ Companion app actually running on Dave's machine
- ❌ Real end-to-end test on actual apps
- ❌ ComfyUI workflow taught and replayed for real
- ❌ Demo video

---

## The Right Order

```
1. Get it working on Dave's machine
   — Companion running, teach/replay/repair proven
   — ComfyUI first (API route, easiest)
   — Photoshop second (JSX route)
        ↓
2. MCP server live
   — Barry can call workflows natively
        ↓
3. Dave uses it every day for 2 weeks
   — Real creative work, not demos
   — Iron out everything annoying
        ↓
4. Dave makes something genuinely good with it
        ↓
5. Record that naturally
        ↓
6. HN, marketplace, everything else
```

Nothing goes out until Dave has used it and it's genuinely good.

---

## Session Rules (learned today)
- Never touch shared credentials without mapping what else uses them
- Graft is live — treat it as production, never share infra with Marouba
- Marouba is pre-alpha — don't build waitlists/marketing until the product works
- Only do things that make sense — weigh pros/cons before starting

---

## Domains
- **marouba.app** — primary (live, DNS propagated)
- **marouba.eu**
- **marouba.ie**

## Tagline
*"Teach your computer once. Every tool you run can replay it forever."*

---

## Build Team
| Role | Responsibility |
|---|---|
| Codex | All code |
| Opus | End-of-day architecture reviews only |
| Barry | Marketing only, zero infra |
| Claude | Project manager, scope, handovers |
| Dave | Direction, taste, final decisions |

---

*Last updated: 06 June 2026 evening*
*Maintained by Claude / NXeraTech*
