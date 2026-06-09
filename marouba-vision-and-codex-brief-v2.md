# Marouba — Vision, Users, Architecture & Codex Brief
**NXeraTech / Dave Reilly**
**Version: 2.0**
**Date: 09 June 2026**
**Status: Locked**

---

## PART 1 — WHAT MAKES MAROUBA VIABLE AND DIFFERENTIATED

### The Problem Nobody Has Solved

Every AI tool on the market today is stateless. It starts from zero every session. OpenAI, Anthropic, Microsoft, Google — they are all building smarter models. None of them are building memory with real human taste.

Computer use agents (OpenClaw, Claude Computer Use, Operator) watch the screen, guess what to click, click, look again. They have no memory of how YOU work. Every session is a blank slate.

Templates and presets exist. But they capture the output, not the process. They capture what was made, not the decisions that shaped it.

### The Marouba Answer

**The vault is the product. The engine is open source.**

Marouba sits between you and every app on your computer. You show it how to do something once — including every decision, every tool choice, every parameter adjustment, every route you take. It saves that as a human-readable Markdown file in your vault.

Next time — whether you trigger it, or your AI agent triggers it — it executes your process. Not a generic process. Yours.

### Why This Is Defensible

1. **The vault cannot be scraped.** It encodes real human creative process taught one workflow at a time. No frontier lab can replicate it from public data.

2. **The engine resolves cheapest first.** Direct API → App scripting → CLI → UI Automation → Keyboard shortcuts → Visual fingerprint → Vision scan → Ask user once. This cuts AI vision costs by ~90% versus naive computer use.

3. **Taste is not scalable.** Alex Karp (Palantir): "Taste plus money — AI scales the money side, taste cannot be scaled or scraped." Marouba is the architecture that preserves taste permanently.

4. **Long-form session capture.** Not just discrete tasks. A 3-hour Ableton session. A full day in Photoshop. Marouba captures the whole thing — every micro-decision, every pause, every revision — and the AI distils it into patterns you didn't know you had.

5. **Vault composition.** "Use the bassline approach from this session, the arrangement style from that one, the mixdown decisions from this other one." No tool does this. This is the moat.

### Locked Positioning Lines

- **"Your Taste. Your Value."** — marketplace hero line
- **"The model gets smarter every month. The vault is what makes it yours."** — Shapiro angle
- **"Anyone can prompt. Nobody else has your process."** — differentiation line
- **"A value system built into the architecture."** — technical credibility line
- **"The frontier labs are building smarter models. Nobody is building memory with real human taste."** — market positioning

### What Marouba Is NOT

- Not a macro recorder (no taste, no AI layer, no route hierarchy)
- Not a computer use agent (no persistent memory, starts from zero)
- Not a template system (captures process not output)
- Not token-maxing (productivity theatre with no real process underneath)

---

## PART 2 — WHO USES MAROUBA AND HOW

### Primary Users

#### 1. Creative Professionals (Core Market)
**Music producers, video editors, photographers, graphic designers, sound designers, animators.**

These people have spent years developing their taste. Their value is not in knowing how to use the software — it is in the specific decisions they make when using it. The order of operations. The settings they reach for. The things they always check. The things they never do.

They cannot explain their process. They just do it. Marouba observes the behaviour, not the narration. It reads:
- Dwell time — long pause before committing = high value decision point
- Revisit patterns — came back and changed it = wasn't right yet
- Undo frequency — struggled here, this matters
- Session exit point — what was the last thing touched before calling it done
- Repetition across sessions — same micro-sequence every time = instinct encoded

**How they use it:**
- Hit Record, work normally, stop when done
- Marouba saves the session as a vault file
- Next project: load the vault, hit Replay, watch their own process execute
- Over time: the vault builds into a graph of their creative identity
- Eventually: sell workflow packs on the marketplace — their taste, their value

#### 2. Tradespeople and Professionals (Secondary Market)
**Contractors, accountants, legal professionals, system administrators.**

Repetitive multi-step processes across desktop apps. Currently done manually every time. No institutional memory when staff change.

**How they use it:**
- Record a process once (e.g. generating a site report, running a compliance check)
- Replay it on demand or schedule it
- Share vaults across a team — institutional knowledge encoded and transferable

#### 3. AI Agents (Programmatic Market)
**Barry, Claude Desktop, OpenClaw, n8n, any HTTP-capable agent.**

Agents call Marouba workflows via MCP or REST API. The agent doesn't need to know how to use the app — it calls the vault. Marouba executes on the machine.

**How they use it:**
- Barry says: "Run the dark techno bassline workflow, F minor, 138bpm"
- Marouba opens Ableton, executes Dave's exact process, returns status
- Agent gets the result without needing computer vision or app knowledge

### User Constraints to Design For

- **Variable screen sizes** — laptop, desktop, multi-monitor, 4K, 1080p
- **Variable window positions** — users position windows where they want
- **Variable app versions** — Paint on Windows 10 vs Windows 11 looks different
- **Variable DPI/scaling** — 100%, 125%, 150%, 200% display scaling
- **No forced window positioning** — Marouba must work with the user's layout, not impose its own

---

## PART 3 — HOW WE ACHIEVE IT (CORRECT TECHNICAL ARCHITECTURE)

### The Core Principle: Position-Independent Replay

**Marouba must never force a window to a specific position or size.**

Users have different screens, different layouts, different preferences. The correct architecture is:

1. At **record time** — capture all coordinates normalised relative to the window rect at that moment. Store the record-time window rect in the vault.

2. At **replay time** — measure the LIVE window rect. Map all normalised coordinates against the live rect. The window can be anywhere. Marouba adapts.

3. **Never call SetWindowPos** to move or resize a user's window. This is wrong for a product. It breaks multi-monitor setups, violates user expectations, and is unnecessary if normalisation is correct.

### The 8-Route Hierarchy (Cheapest First)

```
1. Direct API call           ← fastest, free (ComfyUI, Ableton OSC)
2. App scripting             ← fast, reliable (Photoshop JSX, Python)
3. CLI command               ← batch ops, scriptable
4. Windows UI Automation     ← reads buttons/menus by name/role
5. Keyboard shortcuts        ← stable, predictable
6. Cached visual fingerprint ← "this looks like the export button"
7. Vision scan (region/full) ← last resort, expensive
8. Ask user once → repair    ← updates vault, never asks again
```

For gesture/drawing replay (Paint, Photoshop brush, etc.) the path is:
- Normalised coordinates against live window rect
- SendInput absolute for mousemove during stroke (proven working)
- SendInput absolute for mousedown/mouseup (confirmed working as of 09 June)

### AI Layer (Phase 8 — Future)

The mechanical replay must be bulletproof first. Once it is:

1. **AI toggle** — single button in companion. Off = pure mechanical replay. On = AI brain engaged.
2. **AI provider selector** — plug in OpenClaw, Hermes, or direct API key
3. **Long-form session distillation** — AI reads run logs, extracts decision patterns, writes annotations back to vault
4. **Behavioural signal reading** — dwell time, revisit patterns, undo frequency, exit points. No narration needed.
5. **Vault composition** — "combine the bassline from this vault with the arrangement from that one"
6. **Obsidian graph memory** — vault files cross-reference, backlinks, graph view. AI traverses the graph not just individual files.

### Universal Agent Integration

```
Barry (WSL/OpenClaw)       → HTTP → localhost:7842 → companion
Claude Desktop (Windows)   → MCP  → mcp/server.py  → companion
OpenClaw Windows           → MCP  → mcp/server.py  → companion
n8n / any agent            → HTTP → localhost:7842  → companion
```

---

## PART 4 — CURRENT BUILD STATE (09 June 2026)

### What Is Working

- ✅ Canvas gesture replay — freehand pencil strokes, curves, loops replaying faithfully
- ✅ Toolbar/flyout click replay — UIA with 500ms timeout, coordinate fallback
- ✅ Colour capture — palette horizontal region detection, colour_hex stored in vault
- ✅ Colour replay — Red confirmed pixel-verified (237, 28, 36) on canvas
- ✅ Normalised coordinate system — all coordinates relative to record-time window rect
- ✅ Position-independent replay — no SetWindowPos, no forced alignment, live rect only
- ✅ SendInput absolute throughout — mousemove, mousedown, mouseup all via SendInput
- ✅ Timestamp-based replay timing — honours original gaps, min 8ms, max 1000ms
- ✅ UIA targets recorded window_title — not Marouba's own window
- ✅ Canvas events excluded from UIA path — strokes replay as gestures only
- ✅ Paint auto-launch when not open
- ✅ 29 tests passing, CI green
- ✅ MCP server built — list_workflows, read_workflow, replay_workflow

### What Is Currently Broken / Open

- ❌ **Shape tool replay** — circle/ellipse/rectangle tools not replaying correctly. Shape tool records mousedown→drag→mouseup with large movement. Current replay path is optimised for pencil (many mousemoves). Needs dedicated handling.
- ❌ **Fill/paint bucket replay** — single click with no drag. Not replaying correctly. Needs dedicated single-click path separate from stroke behaviour.
- ❌ **Colour replay with shape+fill workflows** — partially verified. Needs clean manual pass after shape and fill are fixed.
- ❌ **Demo video** — not until full system works without thinking about it
- ❌ **Phase 8** — AI toggle, creator.md loader, behavioural distillation, vault composition, Ableton profile testing

### Architecture Rules (Non-Negotiable)

- **No SetWindowPos** — ever. Position-independent is a product principle, not a preference.
- **No forced window alignment** — live rect is always the reference.
- **No hardcoded app coordinates** — all tool selection from recorded vault events.
- **Diagnose before fixing** — always read the vault file and main.rs, report root cause before changing anything.
- **Canvas strokes never go through UIA** — gesture path only.
- **Always verify:** cargo check + npm run build:web + cargo build --release + pytest tests -v (29 tests must pass)

---

## PART 5 — NEXT STEPS IN ORDER

1. ⬜ **Shape tool replay** — fix mousedown→drag→mouseup for shape tools (circle, rectangle)
2. ⬜ **Fill tool replay** — fix single click path for paint bucket
3. ⬜ **Full workflow test** — record circle + fill + pencil stalk, replay end to end, all three correct
4. ⬜ **Push to GitHub**
5. ⬜ **Colour replay clean pass** — manual visual verification after shape/fill fixed
6. ⬜ **Second app test** — Notepad, record typing, replay
7. ⬜ **Phase 8 scoping** — AI toggle, session distillation, vault composition

---

*Maintained by Claude / NXeraTech*
*Updated: 09 June 2026*
