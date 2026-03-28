# Docs Rewrite — Design

**Date:** 2026-03-28
**Goal:** Full v2 documentation rewrite for new users, restructured information architecture
**Trigger:** TCS v2 migration — plugin rename (tcs-start → tcs-workflow), 4-plugin architecture, XDD workflow, 20 skills

---

## Decision: Restructure IA (not in-place rewrite)

New docs/ hierarchy replaces the current flat structure. Old file names are not preserved — clean slate for v2.

**Why:** Current structure has legacy debt from tcs-start, missing tcs-patterns entirely, wrong skill counts, wrong plugin counts. A restructured IA matches the v2 mental model for new users discovering TCS.

---

## New Information Architecture

```
docs/
├── getting-started/
│   ├── index.md            ← what is TCS, 4-plugin overview, value prop for new users
│   ├── installation.md     ← install script + marketplace commands (tcs-workflow, tcs-team, tcs-helper, tcs-patterns)
│   ├── quick-start.md      ← first-project walkthrough: constitution → specify → implement
│   └── workflow.md         ← the core BUILD loop in detail (XDD-based v2 flow)
│
├── reference/
│   ├── plugins.md          ← all 4 plugins: overview, install command, skill list each
│   ├── skills.md           ← full skill reference (all 20 tcs-workflow skills + namespaces)
│   ├── agents.md           ← 15 agents across 8 roles (minor namespace fixes)
│   ├── output-styles.md    ← The Startup / The ScaleUp comparison (namespace: tcs-workflow)
│   └── xdd.md              ← XDD deep dive: prd/sdd/plan/tdd skills, phase files, spec structure
│
├── guides/
│   ├── tcs-patterns.md     ← tcs-patterns plugin: all 17 skills, when/why to install each
│   ├── multi-ai-workflow.md ← Claude.ai + Perplexity integration (moved from flat docs/)
│   └── statusline.md       ← 3 variants merged into 1 doc + config reference
│
└── about/
    ├── the-custom-philosophy.md  ← canonical philosophy (replaces PHILOSOPHY.md; incorporates concept/ insights)
    ├── sources.md                ← attribution: what came from where (rsmdt/the-startup, citypaul skills, TCS-native)
    └── principles.md             ← PRINCIPLES.md moved and lightly updated
```

---

## Work Scope Per File

### New files (5)
| File | What it contains |
|------|-----------------|
| `getting-started/index.md` | What is TCS, 4-plugin overview, value prop |
| `getting-started/quick-start.md` | First-project walkthrough |
| `reference/xdd.md` | XDD workflow deep dive |
| `guides/tcs-patterns.md` | All 17 pattern skills documented |
| `about/sources.md` | Attribution and origins doc |

### Major rewrites (5)
| File | Key changes |
|------|-------------|
| `README.md` | 4-plugin install, v2 feature list, links to new IA |
| `getting-started/installation.md` | `tcs-start` → `tcs-workflow`, tcs-patterns as optional |
| `getting-started/workflow.md` | Core loop for XDD-based v2 flow |
| `reference/plugins.md` | "3 plugins" → "4 plugins", full tcs-patterns section |
| `reference/skills.md` | "10 skills" → "20 skills", XDD skills, correct namespaces |

### Minor updates (5)
| File | Key changes |
|------|-------------|
| `reference/agents.md` | Namespace fixes only |
| `reference/output-styles.md` | `tcs-start:` → `tcs-workflow:` |
| `guides/multi-ai-workflow.md` | Move from flat docs/, minimal content changes |
| `guides/statusline.md` | Merge 3 statusline files into one |
| `about/principles.md` | Move, lightweight update |

---

## Files to Delete

| File | Reason |
|------|--------|
| `docs/index.md` | Superseded by getting-started/index.md |
| `docs/concepts.md` | Folded into getting-started/index.md |
| `docs/PHILOSOPHY.md` | Superseded by about/the-custom-philosophy.md |
| `docs/the-custom-philosophy.md` | Moved to about/ |
| `docs/statusline-starship.md` | Folded into guides/statusline.md |
| `docs/statusline-starship-reddit.md` | Folded into guides/statusline.md |

## Files to Promote then Delete

| Directory | Valuable content → destination |
|-----------|-------------------------------|
| `docs/concept/` | Philosophy insights → about/the-custom-philosophy.md; v2 rationale → reference/xdd.md |
| `docs/concept/v2/` | Same as above |

---

## Key v2 Changes Driving the Rewrite

- Plugin rename: `tcs-start` → `tcs-workflow`
- 4 plugins (was 3): added `tcs-patterns`
- Skill count: 20 in tcs-workflow (was 10 in tcs-start)
- New XDD skills: xdd, xdd-meta, xdd-prd, xdd-sdd, xdd-plan, xdd-tdd
- All install commands updated: `tcs-workflow@the-custom-startup`
- Output style namespace: `tcs-workflow:The Startup`
- Spec location: `docs/XDD/specs/` (configured via `.claude/startup.toml`)

---

## Attribution Notes (for sources.md)

- Base fork: [the-startup](https://github.com/rsmdt/the-startup) by [@rsmdt](https://github.com/rsmdt)
- citypaul-derived skills in tcs-patterns: 10 skills ported to PICS format
- TCS-native skills in tcs-patterns: event-driven, api-design, go-idiomatic, node-service, python-project (5)
- Integration skills: mcp-server, obsidian-plugin (2) — full SKILL.md rewrites in M3 Phase 3

---

## Next Step

Run `/specify` with this design as context to create PRD → SDD → PLAN for the docs rewrite.
