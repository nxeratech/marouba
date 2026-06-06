# Show HN: Marouba – open source workflow memory engine that teaches your computer once and repairs itself

---

Every time your computer updates, moves a button, renames a menu — your automations break. You re-record the macro. You re-teach the AI. You re-do the thing you already did.

That's the problem. The frontier labs are building agents that can *use* computers, but none of them remember what they learned. Every session starts from zero. Every workflow is ephemeral. Every broken step is a human in the loop.

Marouba is an open-source workflow memory engine. It sits between you and your OS, watches what you do, stores it in a structured format called a **vault**, and replays it later. When something breaks — and it will — Marouba detects the failure, repairs the workflow using its own stored context, and keeps going. It doesn't ask you again.

## How it works

**The vault format.** Every workflow you teach Marouba is stored as a vault file — a structured, human-readable, version-controlled record of what you did. Not a screenshot. Not a video. A precise description of intent, actions, context, and outcomes. Vaults are git-friendly. You can diff them, branch them, share them.

**8-route hierarchy.** Workflows are organised into eight routes: **teach**, **replay**, **verify**, **repair**, **adapt**, **compose**, **share**, and **report**. Each route is a stage in the lifecycle of a workflow — from first demonstration through to shared community asset. The hierarchy isn't arbitrary. It maps to how humans actually think about repetitive tasks: "show me" → "do it again" → "check it worked" → "fix what broke" → "handle the new version" → "chain it with another task" → "give it to someone else" → "tell me how it's going."

**The repair loop.** This is the part that matters. When Marouba replays a workflow and something has changed — a button moved, a dialog appeared, a page loaded differently — it doesn't crash or ask for help. It uses the vault's stored context (what the screen looked like, what the intent was, what the fallback options are) to attempt a repair. If it succeeds, the repair is written back to the vault. If it can't, it pauses and asks. But it only asks once. The next time it hits that situation, it knows.

**The marketplace.** Vaults are portable. You can share them, sell them, or download someone else's. A Photoshop workflow you taught your machine can run on someone else's machine — adapted to their screen size, their version, their language. The marketplace is where workflow knowledge becomes a creator economy asset.

## Why we built this

The current state of computer use agents is impressive and fragile. Claude Computer Use, Operator, Mariner — they can do amazing things once. Ask them to do the same thing tomorrow and they start over. Ask them to do it a hundred times and they'll fail differently each time.

We think the missing piece isn't better models. It's memory. Structured, repairable, shareable memory. The model is the engine. The vault is the map.

## Tech details

- Written in Python, runs locally
- Vault files are YAML + JSON schemas, stored on disk, synced via git
- Screen understanding via local vision models (or cloud if you prefer)
- Plugin system for route extensions
- MIT licensed

## What's working

- Teach and replay on common desktop apps (browsers, IDEs, office tools)
- Basic repair loop for UI element relocation
- Vault format v0.1 with full schema
- CLI and experimental GUI

## What's not working yet

- Marketplace is design-stage only
- Compose route (chaining workflows) is experimental
- Repair loop handles ~70% of common breakages — the long tail still needs human intervention
- No mobile support yet

We're looking for people who are frustrated with teaching the same task to their computer over and over. If that's you, we'd love your feedback.

The repo will be public at launch. For now, the waitlist is at marouba.app.
