# Marouba — Vision, Users, Architecture & Codex Brief
**NXeraTech / Dave Reilly**
**Version: 1.0**
**Date: 08 June 2026**
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
- SetCursorPos + mouse_event for mousedown/mouseup

### Toolbar and UI Click Replay (The Current Problem)

**Root cause of current failures:**
- We have been trying to align Paint to a fixed position before replay
- This is the wrong approach — it breaks for users with different screen setups
- The correct approach: measure live window rect, map normalised toolbar coordinates against it

**Correct toolbar click replay:**
1. Focus target window (SetForegroundWindow)
2. Wait 500ms
3. Read LIVE window rect via GetWindowRect on the focused HWND
4. For each toolbar/UI click event: resolve coordinates against live rect using stored normalised values
5. Send click via SendInput
6. For flyout interactions: honour recorded timestamp gaps (already implemented)

**No SetWindowPos. No forced positioning. Live rect only.**

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

## PART 4 — CODEX BRIEF: CURRENT PROBLEM WITH CORRECT SCOPE

### What We Are Trying to Achieve

Marouba must record and replay any user action on any Windows app faithfully:
- Tool selections (clicking toolbar buttons, flyouts, dropdowns)
- Parameter changes (sliders, input fields, colour pickers)
- Drawing and gesture strokes (mouse movement with button held)
- Keyboard shortcuts
- Menu navigation

The replay must work regardless of where the window is on screen, what monitor it is on, or what size it is. No forced window positioning.

### What Is Currently Working

- ✅ Canvas gesture replay — curves, strokes, loops replaying faithfully
- ✅ Normalised coordinate system — coordinates stored relative to window rect
- ✅ SendInput absolute for mousemove during stroke
- ✅ Timestamp-based replay timing — honours original gaps between events
- ✅ Per-event window rect resolution for non-stroke events
- ✅ Paint auto-launch when not open

### What Is Currently Broken

- ❌ Toolbar/UI click replay — clicks not landing on correct elements
- ❌ SetWindowPos forced positioning — wrong approach, must be removed
- ❌ Pencil tool auto-select — not needed if toolbar clicks replay correctly from vault

### Root Cause

The current code calls `align_focused_window_to_record_rect()` which uses `SetWindowPos` to move and resize Paint to match the record-time window rect before replay. This is architecturally wrong because:

1. It forces the window to a fixed position — bad for users with different screen setups
2. It can fail silently on maximised windows or multi-monitor setups
3. It is unnecessary — normalised coordinates against the live rect achieve the same result without moving anything

### The Fix

**Remove `align_focused_window_to_record_rect()` entirely.**

Replace with:
1. Focus the target window (SetForegroundWindow) — already done
2. Wait 500ms — already done
3. Read live window rect via GetWindowRect on the focused HWND
4. Use that live rect for ALL coordinate resolution — both toolbar clicks and canvas strokes
5. Remove SetWindowPos call completely

This is position-independent. Works on any screen, any window position, any size.

### Verification

After the fix, test with Paint at three different positions and sizes:
1. Small window, top-left of screen
2. Large window, centre of screen
3. Maximised

Record a workflow including tool selection and drawing strokes at each position. Replay should work at all three without any window manipulation.

### Codex Prompt

```
Read companion/src-tauri/src/main.rs in full.

The current align_focused_window_to_record_rect() function uses 
SetWindowPos to force Paint to a fixed position before replay.
This is architecturally wrong — Marouba must be position-independent.
Users have different screens, different window positions, multiple 
monitors. We cannot and should not move their windows.

Make the following targeted changes:

1. Remove the align_focused_window_to_record_rect() call from the 
   replay flow entirely. Remove the function itself.

2. After SetForegroundWindow and the existing 500ms wait, read the 
   LIVE window rect of the focused HWND using GetWindowRect. Store 
   this as the replay_rect.

3. Use this live replay_rect for ALL coordinate resolution throughout 
   replay — both toolbar/UI clicks and canvas stroke mousemove events.

4. Remove all SetWindowPos calls from the replay path.

5. Remove the ShowWindow SW_RESTORE call that was added to support 
   the alignment — it is no longer needed.

6. Also remove the hardcoded pencil auto-select toolbar click that 
   was added before replay_mouse() — tool selection now happens 
   naturally from the recorded vault events replaying against the 
   live rect.

The result: replay works on any window position, any size, any 
monitor, without touching the user's window layout.

Verify: cargo check passes, npm run build:web passes,
cargo build --release passes, pytest tests -v passes (29 tests).
No push.
```

---

## PART 5 — NEXT STEPS AFTER TOOLBAR FIX

1. ✅ Position-independent toolbar click replay working
2. ⬜ Test with colour selection replay (record colour pick, replay it)
3. ⬜ Test with multiple tools in sequence (pencil → eraser → pencil)
4. ⬜ Test on a second app (Notepad — record typing, replay it)
5. ⬜ Push to GitHub
6. ⬜ Update handover doc to v7
7. ⬜ Phase 8 scoping — AI toggle, session distillation, vault composition

---

*Maintained by Claude / NXeraTech*
*Date: 08 June 2026*
