# Reddit Posts — Marouba

---

## r/MachineLearning

**Title:** [D] We built an open-source workflow memory engine that lets computer-use agents remember and self-repair. Here's what we learned about structured memory vs context windows

**Body:**

The current wave of computer-use agents (Claude Computer Use, Operator, etc.) share a fundamental limitation: they have no persistent memory of workflows. Every session is stateless. Every task is re-learned from scratch. This isn't just inefficient — it means agents can't accumulate reliability over time.

We've been working on Marouba, an open-source workflow memory engine that sits between the agent and the OS. The core idea: **structured memory is more useful than larger context windows for repetitive tasks.**

**The approach:**

We store every workflow as a **vault** — a structured, version-controlled file that captures intent, actions, screen states, and outcomes. Vaults are organised through an 8-route hierarchy:

1. **Teach** — record a workflow demonstration
2. **Replay** — execute from stored vault
3. **Verify** — confirm outcome matches intent
4. **Repair** — detect breakage, attempt fix using vault context
5. **Adapt** — handle version/UI differences across machines
6. **Compose** — chain multiple vaults into pipelines
7. **Share** — export/import vaults (portable across users)
8. **Report** — analytics on workflow reliability

**What we've found so far:**

- **Repair accuracy sits around 70%** for common UI breakages (button moved, dialog appeared, page restructured). The vault stores enough context about intent that the model can usually find the right path. The remaining 30% is the long tail — unusual dialogs, permission changes, auth flows.

- **Structured memory outperforms in-context learning for repetition.** A vault file describing "export PDF from Chrome, save to Desktop, name with today's date" is more reliable than asking a model to figure it out fresh each time. Obvious in hindsight, but the performance gap is bigger than we expected.

- **The vault format is the hard problem, not the model.** Getting the schema right for what to store (intent vs. pixel coordinates vs. semantic description of UI elements) determines whether repair works at all. We're on v0.1 and it's already been rewritten twice.

- **Shareability creates a network effect.** If someone teaches a complex Photoshop workflow and shares the vault, others don't need to re-teach it. The vault adapts to their machine. This is where the marketplace comes in — workflow knowledge as a tradeable asset.

The system is Python-based, runs locally, MIT licensed. We're pre-launch but the architecture is stable enough to discuss.

Questions we're actively thinking about:
1. What's the right abstraction level for vault entries — DOM-level, accessibility-tree-level, or semantic description?
2. How do you handle workflows that involve human judgment (not purely mechanical tasks)?
3. What's the failure mode for the repair loop when the entire application has been updated?

Happy to go deeper on any of this. We think structured workflow memory is an under-explored area in agent research and we'd love to hear what others are working on.

---

## r/artificial

**Title:** The AI industry is building agents that forget everything. Here's why workflow memory might matter more than smarter models.

**Body:**

There's a pattern I keep seeing in AI agent development: the models get smarter, the demos get more impressive, and yet the actual day-to-day reliability of computer-use agents barely improves.

I think the reason is memory. Not RAM — *memory*. The kind where you teach your computer to do something and it remembers how to do it tomorrow.

Right now every AI agent session starts from zero. You can teach Claude or ChatGPT to navigate your accounting software, export a report, email it to your accountant. Tomorrow you ask it to do the same thing and it has to re-learn the entire flow. If a button moved in an update, it's completely lost.

We're building Marouba to fix this. It's an open-source workflow memory engine. The idea is simple:

1. **Teach once.** Show the agent what you want. It records the workflow in a structured format we call a vault.
2. **Replay forever.** The vault stores not just the clicks, but the intent behind them. "I want to export this report as PDF" not "click at coordinates (340, 290)."
3. **Repair itself.** When something breaks (and it will — software updates, layout changes, different screen sizes), Marouba uses the vault's context to figure out what changed and fix the workflow. It writes the repair back to the vault so it never breaks the same way twice.
4. **Share workflows.** Vaults are portable. Teach your computer a complex workflow, share it, and someone else's computer can run it adapted to their setup. Workflow knowledge becomes a creator economy asset.

The frontier labs are investing billions in making models smarter. We think there's equal value in making agents remember what they already know. A model that's 90% as smart but has perfect memory of your workflows is more useful than a model that's 100% smart but forgets everything between sessions.

We're pre-launch, open source (MIT), building the waitlist at marouba.app. Would love to hear from anyone else thinking about this problem.

---

## r/ComfyUI

**Title:** What if ComfyUI workflows could remember, repair, and share themselves? We're building that.

**Body:**

ComfyUI users know the pain: you build a perfect workflow, everything works, you save it. Then ComfyUI updates. Or you get a new custom node. Or you try to share your workflow with someone who has a different node setup. It breaks. You debug. You rebuild.

We're working on Marouba — an open-source workflow memory engine. The concept translates directly to what ComfyUI users already do:

**The problem:** Workflows are fragile. They depend on specific node versions, specific model paths, specific parameter values. Share a workflow JSON and there's a 50/50 chance it works on someone else's machine.

**What we're building:**
- **Vault format** — structured storage of not just the workflow graph, but the *intent* behind each node. Not "KSampler with these exact parameters" but "generate an image with this style at this quality level"
- **Repair loop** — when a workflow breaks (missing node, updated parameter, different model), Marouba detects the failure and attempts to fix it using the vault's stored context. Writes the fix back so it never breaks the same way twice.
- **Adapt route** — takes a workflow built on one machine and adapts it for another. Different model paths, different custom node versions, different VRAM constraints.
- **Marketplace** — share your workflows as vaults. Others download them and they auto-adapt. Creator economy for workflow knowledge.

**Where we are:** Early stage. The vault format is stable (v0.1). The repair loop works for common failure modes (about 70% success rate). ComfyUI-specific integration is on the roadmap but not yet built.

If you've ever spent an hour debugging someone else's workflow JSON, you understand the problem. We'd love input from ComfyUI power users on what the vault format should capture for image generation workflows specifically.

Waitlist and details at marouba.app. Open source, MIT license.

---

## r/ableton

**Title:** What if you could teach Ableton your production workflow once and it remembered forever? Building an open workflow memory engine.

**Body:**

Every Ableton producer has workflows they repeat constantly: specific routing setups, mastering chains, drum bus processing, session export sequences. You do them so often your hands know where to go.

But when Ableton updates, or you move to a different machine, or you try to explain your workflow to a collaborator — you're starting from scratch. Screenshots, screen recordings, "click here then here then here." It's 2026 and we're still teaching computers the same task hundreds of times.

We're building Marouba — an open-source workflow memory engine. For music production, here's what that means:

**Teach once.** Perform your workflow in Ableton — set up your drum bus, route your sends, configure your mastering chain. Marouba watches and records the workflow in a structured format called a vault. Not a macro. Not a script. A complete description of intent and actions.

**Replay forever.** Next time you need that same setup, Marouba replays it. Different project, different template — the intent carries over even if the specific clicks change.

**Repair itself.** Live 12 moved a menu? A plugin updated its UI? Marouba detects the breakage, uses the vault's stored context to figure out what changed, repairs the workflow, and saves the fix. Never breaks the same way twice.

**Share with other producers.** Vaults are portable. You could share your exact vocal chain setup with another producer and it would adapt to their machine, their plugin versions, their routing. Producer A's workflow runs on Producer B's machine.

**The marketplace angle:** This is the big one. Imagine a marketplace where producers sell workflow vaults — not presets, not templates, but actual demonstrated workflows. "How I process vocals for techno." "My mastering chain for vinyl release." Each one a teachable, replayable, repairable vault.

We're early stage, open source (MIT). The core engine works on desktop apps; Ableton-specific integration is on the roadmap. If you're a producer who's frustrated by repetitive setup work, we'd love your input on what workflows matter most.

Waitlist at marouba.app.
