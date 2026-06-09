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

- ❌ **Universal app launch** — replay fails for any app that isn't Paint. Codex working on this now (09 June).
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

1. ✅ Shape tool replay — fixed 09 June
2. ✅ Fill tool replay — fixed 09 June
3. ✅ Full Paint workflow — circle + fill + pencil stalk, pixel-verified
4. ✅ Pushed to GitHub — commit 15edd6d
5. ⬜ **Universal app launch** — Codex running now (09 June)
6. ⬜ **Notepad++ replay verified** — keystrokes land correctly
7. ⬜ **Ableton session test** — record rough 5-minute track, replay it (see Part 7)
8. ⬜ **Phase 8 scoping** — AI toggle, session distillation, vault composition

---

## PART 6 — HOW TASTE IS ACTUALLY CAPTURED: THE PREPARATION LAYER

*This section documents how taste really operates in creative workflows, using music production as the reference domain. The principles apply across all apps and all creative disciplines.*

### The Performed Process vs The Real Process

When a music producer shares a "made from scratch" session video online, what you see is a curated performance. The real process happened before the camera turned on — the sound design sessions, the sample hunting, the preset tweaking, the hours spent getting a drum bus to sit right. That prior work is where the taste actually lives. By the time recording starts, hundreds of decisions have already been made and compressed into defaults.

This has a direct implication for Marouba: a single session recording captures the output of accumulated taste, not the tinkering that produced it. The preparation layer — what a creator brings in already decided — is as important as what they do during the session.

### What the Preparation Layer Looks Like

When a creator opens a session they typically have:
- A template with their preferred signal chain already loaded
- A folder of sounds they have already processed and approved
- Instruments or plugins already configured to their defaults
- A rough mental structure for what they want to make

Each of these is a crystallised prior decision. The kick drum that sounds like them didn't happen in this session — it happened in a previous one. Marouba recording the current session captures that the kick was loaded. It doesn't capture why it sounds the way it does unless it was also recording the session where it was made.

### Vault Implications

The vault should distinguish between:
- **Loaded and left alone** — brought in already decided, high confidence in the sound
- **Loaded and heavily processed** — raw material that needed transformation, taste expressed through the chain of changes

The ratio of these across a session is a taste signal. High processing on one element, everything else left alone — that element mattered most to this creator in this session. Repeated across many sessions, a pattern emerges about where this creator's attention and taste consistently land.

When Marouba detects a file being loaded, it should log the path, filename, and what happened next. Over time the vault builds a map of what this creator reaches for repeatedly. That repetition map is their taste fingerprint — no narration needed, just pattern recognition across the graph.

---

## PART 7 — HOW TASTE IS ACTUALLY CAPTURED: THE TRANSFORMATION CHAIN

### Selection vs Transformation

There are two distinct creative personalities in how people work with raw material:

**Selection-first creators** — they audition carefully, choose deliberately, and the selection itself expresses taste. What they pick is the statement.

**Transformation-first creators** — they pick randomly or quickly and sculpt from there. The selection is almost irrelevant. What they do to it is everything. This is extremely common in electronic music production — grab whatever clap, see where it goes, use the design process to make your taste apparent.

Marouba must capture taste from both types. The behavioural signal approach handles both — it reads what happened, not why.

### The Transformation Chain Is the Signature

Two producers start with the same random clap sample. One ends up with something punchy and dry. The other ends up with something wide and textured. The sample was identical. The taste is completely different — visible only in the chain of decisions applied to it.

What Marouba captures from a transformation-first creator:
- Which processor they reached for first
- The order of operations — EQ before compression, or compression before EQ?
- The frequency they always cut, the frequency they always boost
- How much they automate vs leave static
- The point at which they decide something is done and move on
- What they never touch — absence is also a signal

This chain, repeated across sessions on different source material, is the creator's fingerprint. It cannot be inferred from the source material. It can only be observed from behaviour.

### Cross-Session Pattern Recognition Is the Real Product

A single session gives you a snapshot. Ten sessions give you a pattern. A hundred sessions give you a fingerprint detailed enough that Marouba can begin to anticipate decisions before they are made.

This is why long-form session recording is not a feature — it is the product. The vault that has ten Ableton sessions recorded is exponentially more valuable than the vault that has one. The graph that connects them — which elements appeared in multiple sessions, which transformation chains repeated, which decisions were always made in the same order — that is the moat no frontier lab can scrape.

### Vault Composition: The Real Demo

The ultimate expression of this is vault composition. When a creator has multiple sessions recorded, they can say:

*"I like the bass transformation chain from the dark techno session. I like the arrangement approach from the minimal house session. I like the mixdown decisions from the Berlin set recording. Make me something new that combines those three."*

The AI traverses the vault graph, extracts the relevant decision patterns from each session, and composes a new workflow that applies them to fresh source material. The output sounds like the creator — because it was built from the creator's actual decisions, not from a generic model of how music is made.

**This is the demo that matters.** Not Paint. Not Notepad. A real Ableton session — roughly five minutes of track-building, effects, and automation — recorded by Marouba, closed, and replayed faithfully. Then a second session with a different approach. Then the AI combining taste elements from both into something new.

That is the vision. Everything else is infrastructure to get there.

### Note on Scope

Ableton is used here as the reference domain because it is the domain where this thinking was developed. The principles apply universally — to video editing (Premiere, DaVinci), to graphic design (Photoshop, Figma), to 3D work (Blender), to any creative tool where process encodes taste. The vault format and engine are app-agnostic. The Ableton demo is the proof of concept for the full vision.

---

## PART 8 — APP PROFILES: HOW THE BASIC LAYER GETS SMARTER

### The Problem This Solves

Marouba works well on MS Paint because we spent significant time debugging its specific event patterns — double-click timing, toolbar flyout behaviour, coordinate precision. Ableton required the same effort. Every new app would need the same debugging cycle if there was no way to preserve and share what was learned.

Without a solution, the only apps that work reliably are the ones NXeraTech has personally tested. That is a hard ceiling on the product's usefulness.

The goal is for the basic mechanical replay layer — no AI required — to get progressively better across more apps over time, without burning user API tokens, without bloating the host machine, and without any legal exposure from data collection.

### What an App Profile Is

An app profile is a lightweight structured file that encodes what Marouba has learned about how a specific app behaves during replay. It is not AI. It is not vision. It is the distilled output of successful replays — the timing values that worked, the event patterns that landed correctly, the coordinate offsets that are reliable for that app's UI density.

App profiles live in the open source repo alongside the engine. They are maintained by NXeraTech. When we fix Ableton replay today, that fix becomes the Ableton profile that ships to every user in the next update. Same as Paint — that knowledge is in the codebase, not locked to one machine.

### No Data Collection — No Legal Exposure

Users do not contribute anything explicitly. There is no telemetry, no background reporting, no data leaving the user's machine without their knowledge. NXeraTech does the app testing. The fixes go into profiles. Profiles ship in updates. This is standard open source maintenance — no consent framework needed, no separate privacy policy, no new legal surface.

### How AI Accelerates Profile Creation Without Gating It

When a user has their AI agent connected, Marouba can use it to generate a profile for an unknown app during a session. The AI observes what worked and what did not, and writes a profile file to the user's local vault. That profile persists permanently on their machine. Next session on the same app, Marouba reads the local profile and replays without touching the AI at all. Tokens spent once. Benefit permanent.

If the user disconnects their AI agent, every profile it helped create remains fully functional. The AI wrote to the profile. The profile runs without the AI. This is the correct dependency direction — AI accelerates, mechanical layer executes.

### How Profiles Reach Other Users

Two paths, both voluntary and explicit:

**Path 1 — Open source contribution.** A user who has generated or refined a strong app profile can submit it to the Marouba repo as a pull request, exactly like any open source contributor. NXeraTech reviews, validates, and merges. It ships to all users in the next update. No hidden pipeline. No infrastructure beyond GitHub.

**Path 2 — Marketplace.** Verified, battle-tested app profiles for professional software are marketplace items. NXeraTech publishes a basic free profile for each supported app. A power user who has spent months refining their Ableton profile — tuned for their specific workflow, their hardware, their screen setup — can sell the premium version. Same marketplace model as workflow packs. Same 70/30 split. No new infrastructure.

### What This Means for the Product

The basic layer improves continuously from real usage and real fixes, not token spend. The AI layer accelerates profile creation for individual users without creating a dependency. The marketplace creates a new category of sellable asset — not just workflows (your taste in what you make) but profiles (your knowledge of how an app behaves).

The more apps that have profiles, the more useful Marouba is to every user on day one. The more users refine profiles through real use, the better the profiles get. This is the compounding value that makes the vault — and everything built on top of it — defensible over time.

### Profile Format (To Be Specced in Detail at Phase 8)

At minimum an app profile should encode:
- App name and version range it was validated against
- Double-click timing threshold for this app
- Drag behaviour — minimum movement before drag is recognised
- Click target padding — how much coordinate tolerance this app's UI requires
- Known UI regions — toolbar, canvas, browser, timeline etc. mapped as normalised zones
- Event sequences that are known to work — e.g. pencil tool selection in Paint
- Known failure modes — e.g. avoid clicking within Xpx of edge in Ableton mixer

This is a small structured Markdown file. Consistent with the vault format. Human readable. Version controlled. No binary dependencies.

### How Users Actually Contribute App Profiles

This is infrastructure contribution — not the marketplace. No taste involved, no money changes hands. The user is helping fix Marouba's mechanical replay for other users on the same app. It should require zero technical knowledge.

**The user journey:**

A video editor records several DaVinci Resolve sessions. Replay is rough at first. Over a few sessions, with their AI connected, Marouba quietly refines a local DaVinci profile in their vault — learning what timing values work, which drag patterns land, which click targets are reliable. After enough successful replays, Marouba surfaces a single prompt in the companion:

*"Your DaVinci Resolve profile is working well after 5 successful replays. Share it with the Marouba community so other users get a better experience on day one?"*

One tap. Yes or no. If yes, Marouba packages the profile and sends it to a lightweight NXeraTech endpoint. NXeraTech reviews it manually, validates it, and if it checks out it goes into the next repo update and ships to all users.

**What the user never does:**
- Touch GitHub
- Write a prompt or goal
- Understand what a profile file is
- Think about any of this

**The consent is clean and explicit:**
One opt-in at the point of contribution. The profile contains no personal data — no workflows, no recordings, no taste. Just timing values and event patterns for that app's UI. Privacy story is simple: Marouba collects nothing automatically. Sharing is always a conscious choice.

**Where this lives in the companion UI:**
A section in settings — "My App Profiles." Shows which apps have local profiles, last updated, number of successful replays. A Share button per profile. That is the entire contribution interface. No further complexity.

**Critical separation from the marketplace:**
App profile contribution and marketplace submissions are two entirely different things with different purposes, different flows, and different value. They must never be presented together or confused in the UI. Profile sharing fixes infrastructure. Marketplace sells taste. A user should never feel that contributing a profile is the same as giving away something they could sell.

---

## PART 9 — THE MAROUBA MARKETPLACE: TASTE-FIRST SUBMISSION

### What Is and Is Not Sold on the Marketplace

The marketplace sells taste. Specifically: recorded creative process that reflects a specific point of view, from which another creator can learn, start faster, or work more like the person who made it.

**What is sold:**
- Workflow packs — recorded sessions in any app where genuine creative decisions were made
- Instrument design workflows — how someone built a specific sound, all the way through
- Mixing and processing approaches — the order of operations, the settings reached for, the things always checked
- Arrangement and composition workflows — how someone structures from idea to finished piece
- Any recorded process where taste is visible in the decisions

**What is not sold:**
- App profiles — these are infrastructure fixes, not creative assets (see Part 8)
- Generic templates — output captured, not process
- Workflows with no discernible point of view — clicking through defaults adds no taste value

### The Bar for Entry Is Taste, Not Length

This is the most important principle of the marketplace. The criteria for a valid submission is not:
- Minimum recording length
- Minimum number of steps
- Minimum app complexity
- Minimum price point

The only question that matters: **does this workflow contain decisions that reflect a specific creative point of view, from which another creator would benefit?**

A three-minute synth patch design session where someone spent real time dialling in a specific tone — the filter envelope, the oscillator character, the exact compression after it — is a valid marketplace submission. It might be 40 steps. It is still taste captured.

A six-hour Photoshop retouching session with no discernible consistent approach is not a valid submission even though it is long. Length without taste is not the product.

### Spectrum of Valid Submissions

**Smallest valid submission — single instrument or sound design:**
One synth, one approach, one result that sounds specifically like that person. Could be 10 minutes recorded. The taste is in the sound decisions. Sellable.

**Small-mid — processing or mixing approach:**
How someone always treats a specific element — a vocal chain, a kick drum, a master bus. The order of operations. The things they always do and never do. One track worth of process. Sellable.

**Mid — genre or style workflow:**
A complete approach to a specific sound or style. How someone always builds a dark techno track, or grades a documentary, or retouches a portrait. Multiple decisions across a full piece. Sellable and commands more.

**Large — full long-form workflow:**
A complete creative session from blank canvas to finished piece. Every decision captured. The full taste fingerprint for this type of work. Sellable at a premium.

All four are equally valid. Price reflects depth of taste captured, not length.

### Submission Flow in the Companion

When a creator wants to list a workflow on the marketplace, Marouba asks three questions only:

1. **What app is this for?** — dropdown, any app
2. **What does this workflow do?** — one line, plain language
3. **What makes your approach specific?** — one line, the taste description

Examples of good taste descriptions:
- "I always compress before EQ on bass — this is why and how"
- "My low-end layering approach for club music — three elements, one pocket"
- "How I grade skin tones without touching the rest of the image"
- "The way I build tension in an arrangement before a drop"

NXeraTech reviews for genuine taste content. Not for length. Not for complexity. For point of view.

### Pricing

Creator sets their own price. No minimum. No maximum. NXeraTech takes 30%, creator keeps 70%. A one-euro synth patch and a fifty-euro full production workflow are both valid. The market decides the value of the taste.

### Why This Marketplace Is Defensible

Every other marketplace sells outputs — sample packs, presets, templates. They capture what was made. Marouba sells process — how it was made, and more specifically, how this specific person makes it. That cannot be scraped, copied, or replicated by a competitor without the actual recorded sessions. The vault is the asset. The marketplace is the distribution layer.

---

*Maintained by Claude / NXeraTech*
*Updated: 09 June 2026*
