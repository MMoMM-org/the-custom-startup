# Workflow

The Custom Startup follows **spec-driven development**: write a specification first, then implement it. This prevents scope creep, reduces rework, and keeps Claude focused on what you actually want to build.

---

## The Core Loop

```
┌──────────────────────────────────────────────────────────┐
│                    SETUP (optional)                      │
│                                                          │
│  /constitution  Create project governance rules          │
│                 Auto-enforced during BUILD               │
└──────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────┐
│                    BUILD (primary loop)                  │
│                                                          │
│  /xdd ────────► PRD → SDD → PLAN (XDD workflow)          │
│      ▼                                                   │
│  /validate ───► Quality check before you invest time     │
│      ▼                                                   │
│  /implement ──► Execute plan phase-by-phase              │
│      ▼                                                   │
│  /test ───────► Run tests, enforce code ownership        │
│      ▼                                                   │
│  /review ─────► Multi-agent code review                  │
│      ▼                                                   │
│  /document ───► Generate/sync documentation              │
└──────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────┐
│                    MAINTAIN (as needed)                  │
│                                                          │
│  /analyze ────► Discover patterns & business rules       │
│  /refactor ───► Improve code (preserve behavior)         │
│  /debug ──────► Fix bugs with root cause analysis        │
└──────────────────────────────────────────────────────────┘
```

The BUILD loop uses the **XDD workflow** (Experience-Driven Development): `/xdd` orchestrates three linked documents — PRD, SDD, and PLAN — before any code is written. See [../reference/xdd.md](../reference/xdd.md) for the full XDD deep dive.

---

## Multi-AI Extension

Some phases work better outside Claude Code. Use Claude.ai for conversational spec writing, Perplexity for research, then bring the results back with the import script.

See [../guides/multi-ai-workflow.md](../guides/multi-ai-workflow.md) for the full guide, export/import scripts, and prompt templates.

---

## Output Styles

Two built-in output styles adjust Claude's communication tone for your context:

```bash
/output-style tcs-workflow:The Startup    # high-signal, fast-paced — good for active builds
/output-style tcs-workflow:The ScaleUp    # structured, process-oriented — good for team reviews
```

---

## Step by Step

### Step 0 (optional): Set up project context

Two optional steps run once per project, before the BUILD loop begins.

**Governance rules** — run `/constitution` to create a `CONSTITUTION.md` at the project root. This defines enforceable coding, architecture, and process rules (L1 blocking with autofix, L2 blocking manual, L3 advisory). Once created, it is auto-checked during implementation.

**Multi-AI front-load** — if you want to use Claude.ai or Perplexity for brainstorming, research, or PRD writing before opening Claude Code, set that up now. See [../guides/multi-ai-workflow.md](../guides/multi-ai-workflow.md) for the template files and session flow.

Neither step is required. Skip both and go straight to Step 1.

---

### Step 1: Specify (XDD)

```bash
/xdd Add real-time notification system with WebSocket support
```

`/xdd` runs the XDD workflow — it calls `xdd-prd`, `xdd-sdd`, and `xdd-plan` in sequence, pausing for your confirmation between each phase. The result is three linked documents:

```
docs/XDD/specs/001-notification-system/
├── README.md          # spec manifest: phase status, decisions log
├── requirements.md    # PRD — what to build and why (xdd-prd)
├── solution.md        # SDD — how to build it (xdd-sdd)
└── plan/
    ├── README.md      # plan manifest with phase checklist
    └── phase-1.md     # per-phase tasks with TDD structure
```

> The spec base directory is configured via `.claude/startup.toml`. Default: `docs/XDD`.

The spec cycle takes 15–30 minutes. Claude researches your codebase, asks clarifying questions, and produces the three documents in sequence.

**Resume pattern** — context window full? Pass the spec ID instead of a description:

```bash
/xdd 001
```

Claude reads the existing spec and continues from where it left off. Each document (PRD → SDD → PLAN) can be completed in separate sessions.

For the full XDD reference — individual skills, TDD enforcement, directory layout, and configuration — see [../reference/xdd.md](../reference/xdd.md).

---

### Step 2: Validate

```bash
/validate 001
```

Checks three things before you invest implementation time:

- **Completeness** — all sections filled, no missing details
- **Consistency** — no contradictions between PRD, SDD, and PLAN
- **Correctness** — requirements are testable and achievable

Validation is advisory: it provides recommendations but does not block you.

---

### Step 3: Implement

```bash
/implement 001
```

Executes the plan phase by phase, runs tests after each task, uses parallel agents within phases. You approve between phases.

Large implementations may need context resets. Run `/implement 001` again in a fresh conversation — Claude tracks progress in the spec files.

---

### Step 4: Quality gates

```bash
/test        # Run tests, catch regressions
/review      # Four parallel specialists: security, performance, quality, tests
/document    # Generate or sync docs
```

---

## All Commands

See [../skills.md](../skills.md) for the full command reference and decision tree.
