# Marouba Scope — Barry Review & Improvements
**Reviewer:** Barry (NXeraTech)
**Date:** 05 June 2026
**Based on:** marouba-scope-v1

---

## Overall Verdict

The core thesis is strong. The 8-route fallback chain is the differentiator — nobody else is doing structured fallback with user-in-the-loop repair. "The vault is the product" is the right framing. Below are gaps, risks, and refinements worth considering before Day 1.

---

## 1. Naming Inconsistency ⚠️

The folder is "Mauroba" but the doc says "Marouba" everywhere. Pick one spelling and lock it before the GitHub repo goes public. This will cause confusion in domains, code, and branding if not resolved now.

---

## 2. The 8 Routes — Missing Ones

The route hierarchy is good but has gaps. Consider adding:

### CLI / Shell Command (between Route 2 and 3)
```
2b. CLI command ─────────────────── ImageMagick, ffmpeg, exiftool
```
For batch resize, ffmpeg transcode, EXIF strip — CLI is faster and more reliable than UIA. This is a huge route for creative workflows. ImageMagick handles batch resize (workflow #2) better than any Photoshop scripting route.

### File Watcher / Hot Folder (new Route 0 or parallel trigger)
```
0. Trigger: file appears in folder → auto-run workflow
```
Drop a .PSD into `/inbox` → Marouba runs export workflow automatically. This is how a lot of creative pros actually want to work. Not every workflow needs a voice or text prompt.

### App Plugin / Extension (parallel to Route 2)
Photoshop UXP plugins, VS Code extensions, Blender add-ons. These run *inside* the app with full API access — cheaper than JSX in some cases and more future-proof (Adobe is deprecating CEP/JSX in favour of UXP).

---

## 3. Route 5 and 6 — Merge or Clarify

Cached visual fingerprint (Route 5) and small region vision scan (Route 6) overlap significantly. The difference is just "use cached crop" vs "re-scan that region." Suggest merging into a single route with a cached/uncached sub-flag. 7 routes is cleaner to explain and implement than 8.

---

## 4. Architecture — Gaps to Address

### Windows Companion App Tech Stack
The scope doesn't specify what the companion is built in. This matters for Day 1:
- **Tauri (Rust + webview):** Small binary, low resource, native feel. Best fit.
- **Electron:** Heavier but faster to build. Established ecosystem.
- **C#/WPF:** Best Windows integration, hardest to maintain.
- **Python + PyQt:** Quick to prototype, poor distribution story.

**Recommendation:** Tauri for production, but for Phase 1 a Python prototype is fine. Don't over-invest in the companion UI before proving the vault concept.

### Security Model — Missing Entirely
The vault will contain screenshots, window titles, potentially visible passwords or client names. Needs:
- Local-only by default (no cloud unless user opts in)
- Screenshot redaction rules (exclude browser password fields, banking apps)
- Vault encryption option for sensitive workflows
- Which apps Marouba is allowed to watch (allowlist)

### Multi-Monitor
Creative pros run 2-3 monitors. The scope doesn't address how Marouba handles this. UIA element names alone may not disambiguate which monitor's "Export" button was clicked.

### Latency Targets
No performance requirements stated. For the MVP demo to feel good:
- Route 1 (API): < 100ms decision, execute at API speed
- Route 2 (script): < 500ms start
- Route 3 (UIA): < 2s per click
- Full repair cycle: < 30s

Without targets, "working" becomes subjective.

---

## 5. Business Model — Things Missing

### Marketplace Seeding Strategy
"Community builds app profiles" is the plan, but communities don't appear from nothing. You need:
- **10 launch workflows** built by NXeraTech before launch
- A **workflow format spec** that's clean enough for a single developer to write one in an afternoon
- A **review/verification system** (bad workflows = broken trust)
- **Creator incentives** for the first 6 months (revenue share, featured placement)

### Pricing Spec
Option A says "platform takes revenue cut" but no numbers. Even rough guidance helps:
- Free tier: 5 workflows, local only
- Pro: unlimited workflows, marketplace access
- Marketplace cut: 70/30 (creator/platform) is standard
- Enterprise: shared vaults, SSO

### Mac Support Timeline
Creative professionals disproportionately use Mac. The scope is Windows-only (WSL, UIA) with no Mac roadmap. This is fine for MVP but needs a "when do we port?" decision. Cocoa/UIElement on Mac serves the same role as UIA. Suggest: Phase 6 (post-launch), architect companion to be cross-platform from Day 1 even if you only ship Windows first.

---

## 6. Competitive Landscape — Incomplete

The scope mentions Copilot and Anthropic Computer Use but misses:

| Competitor | What They Do | Marouba's Edge |
|---|---|---|
| **Apple Shortcuts / Automator** | Built-in Mac automation | No AI, no repair, no learning |
| **Zapier / Make** | Web app automation | Desktop-blind. Can't touch Photoshop |
| **AutoHotkey** | Windows scripting | No AI, no vision, no vault, power-user only |
| **UiPath / Blue Prism** | Enterprise RPA | €10K+/yr, no creative focus, no marketplace |
| **Playwright / Puppeteer** | Browser automation | Browser only, no app support |
| **Rivet (open source)** | Visual scripting for AI | Different category (workflow builder, not memory) |

The real competitive risk isn't Microsoft Copilot — it's Adobe building this into Creative Cloud natively. They own Photoshop, they own the UI, they own the user. The moat has to be cross-app (Adobe can't automate ComfyUI or Ableton) and community vault (Adobe can't match 1000 community workflows).

---

## 7. Build Sequence — Refinements

### Phase 1 is Too Ambitious for 2 Weeks
"Read UI element names + take screenshots + WSL backend + ComfyUI API + vault" is a lot. Suggest splitting:

**Phase 1a (Week 1):** ComfyUI API route only. No companion app. Hardcoded workflow. Prove the vault format and the cheapest route works.
```
Python script → ComfyUI API → image generated → saved to folder
Workflow saved as .md in vault
```
This is doable in a week and proves the data model.

**Phase 1b (Week 2):** Companion app MVP. Read UIA elements from one app. Take screenshots. Send to WSL backend.

### No Testing Strategy
Every phase should include:
- What "done" looks like (acceptance criteria)
- How to test it (automated test, manual test, or demo)
- What counts as a regression (vault format changes break old workflows?)

### CI/CD
No mention of build pipeline. Even for MVP:
- GitHub Actions for lint + test on every push
- Companion app build artifact per commit
- Vault format migration tests

---

## 8. The Vault — Design Refinements

### Workflow Composition
Can workflow A call workflow B? e.g. "Batch export" calls "Export web-ready" in a loop. This needs to be in the spec from Day 1 or the vault format will need a breaking change later.

**Suggestion:** Add a `depends_on` or `calls` field to the workflow frontmatter.

### Versioning
Apps update. Photoshop 2025 → 2026 changes UI. The vault needs:
- App version tag on each workflow
- A `last_verified` timestamp
- Graceful degradation: if a workflow was verified on PS 2025 and you're running PS 2026, flag it and run with extra verification

### Vault Portability
If the vault is the product, it needs to be portable:
- Export/import a single workflow
- Share a workflow file (like sharing an Obsidian note)
- Marketplace distributes workflow .md files (simple)

### Privacy in Vault Files
Screenshots in `snapshots/` may contain client work, names, faces. Consider:
- Auto-blur text regions in cached fingerprints
- Configurable "don't capture" app list
- Per-workflow privacy flag

---

## 9. Risk Section — Additions

| Risk | Severity | Mitigation |
|---|---|---|
| Adobe ships this natively in Creative Cloud | 🔴 Critical | Cross-app focus (Adobe can't touch ComfyUI/Blender/Ableton). Community vault moat. |
| Windows UIA API changes or gets restricted | 🟡 High | Multiple fallback routes already handle this. Architect companion to be replaceable. |
| Open source fork without marketplace | 🟡 High | License carefully (BSL or source-available, not pure MIT). |
| Marketplace has low-quality/poisoned workflows | 🟡 High | Review process + reputation system + signed workflows. |
| User trust: "it watches my screen" | 🟡 High | Radical transparency — vault is human-readable, user owns all data, local-first. |
| Scope creep (too many apps too fast) | 🟠 Medium | Stick to Photoshop + ComfyUI for MVP. Reject community requests for new apps until Phase 5. |

---

## 10. Build Team — Suggestion

The current team table is fine for Phase 1 but missing one role:

| Role | Responsibility |
|---|---|
| **QA / Test User** | Dave is the primary user, but you need someone running workflows *wrong* to test repair mode. Consider recruiting one creative pro (photographer, designer) for weekly test sessions starting Phase 3. |

---

## 11. Quick Wins for the Scope Doc

These are easy additions that strengthen the document:

1. **Add a one-line positioning statement** at the top: "Marouba is to creative workflows what TextExpander is to text — learn once, replay forever."
2. **Add success metrics** for each phase (not just "demo works" but measurable: "replay succeeds in <5s", "repair completes in <30s")
3. **Add a "Non-Goals" section** — what Marouba explicitly is NOT (not a general AI agent, not a chatbot, not a screen recorder, not SaaS-only)
4. **Add a "Decision Log" section** — track key decisions and their rationale (like Obsidian vault vs graph DB) so you don't revisit them

---

## Summary of Recommendations

| # | What | Priority |
|---|---|---|
| 1 | Fix naming: Mauroba vs Marouba | 🔴 Now |
| 2 | Add CLI route (ImageMagick, ffmpeg) | 🟡 Phase 1 |
| 3 | Add file watcher / hot folder trigger | 🟡 Phase 2 |
| 4 | Specify companion app tech stack | 🟡 Phase 1 |
| 5 | Add security/privacy model section | 🟡 Phase 1 |
| 6 | Split Phase 1 into 1a + 1b | 🟡 Now |
| 7 | Add workflow composition to vault spec | 🟡 Phase 1 |
| 8 | Add vault versioning (app version tags) | 🟠 Phase 2 |
| 9 | Expand competitive landscape | 🟠 Now |
| 10 | Add Mac roadmap (Phase 6) | 🟢 Post-MVP |
| 11 | Add marketplace seeding strategy | 🟢 Phase 4 |
| 12 | Add "Non-Goals" section | 🟢 Now |
| 13 | Add success metrics per phase | 🟢 Now |

---

*Review by Barry — NXeraTech*
*05 June 2026*
