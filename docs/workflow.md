# Workflow

The Agentic Startup follows **spec-driven development**: write a specification first, then implement it. This prevents scope creep, reduces rework, and keeps Claude focused on what you actually want to build.

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
│  /specify ────► PRD → SDD → PLAN (one command)           │
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

---

## Multi-AI Extension

Some phases work better outside Claude Code. Use Claude.ai for conversational spec writing, Perplexity for research, then bring the results back with the import script.

→ See [multi-ai-workflow.md](multi-ai-workflow.md) for the full guide, export/import scripts, and prompt templates.

---

## Step by Step

### Step 0 (optional): Set up project context

Two optional steps run once per project, before the BUILD loop begins.

**Governance rules** — run `/constitution` to create a `CONSTITUTION.md` at the project root. This defines enforceable coding, architecture, and process rules (L1 blocking with autofix, L2 blocking manual, L3 advisory). Once created, it is auto-checked during implementation.

**Multi-AI front-load** — if you want to use Claude.ai or Perplexity for brainstorming, research, or PRD writing before opening Claude Code, set that up now. See [multi-ai-workflow.md](multi-ai-workflow.md) for the template files and session flow.

Neither step is required. Skip both and go straight to `/specify`.

---

### 1. Specify

```bash
/specify Add real-time notification system with WebSocket support
```

Creates a spec directory with three documents:

```
the-custom-startup/specs/001-notification-system/
├── requirements.md    # What to build and why (PRD)
├── solution.md        # How to build it (SDD)
└── plan/
    ├── README.md      # Plan manifest
    └── phase-1.md     # Per-phase tasks
```

> The spec directory location is configured in `.claude/startup.toml`. Default: `the-custom-startup/specs/`.

The spec cycle takes 15–30 minutes. Claude researches your codebase, asks clarifying questions, and produces three comprehensive documents in sequence.

**Resume pattern** — context window full? Just run:
```bash
/specify 001
```
Pass the ID instead of a description. Claude reads the existing spec and continues from where it left off. Each document (PRD → SDD → PLAN) can be completed in separate sessions.

### 2. Validate

```bash
/validate 001
```

Checks three things before you invest implementation time:
- **Completeness** — all sections filled, no missing details
- **Consistency** — no contradictions between PRD, SDD, and PLAN
- **Correctness** — requirements are testable and achievable

Validation is advisory — it provides recommendations but doesn't block you.

### 3. Implement

```bash
/implement 001
```

Executes the plan phase by phase, runs tests after each task, uses parallel agents within phases. You approve between phases.

Large implementations may also need context resets. Run `/implement 001` again in a fresh conversation — Claude tracks progress in the spec files.

### 4. Test, Review, Document

```bash
/test        # Run tests, catch regressions
/review      # Four parallel specialists: security, performance, quality, tests
/document    # Generate or sync docs
```

---

## Spec Directory

Specs live in the directory configured via `.claude/startup.toml`:

```toml
[paths]
specs_dir = "the-custom-startup/specs"
ideas_dir = "the-custom-startup/ideas"
```

**Fallback chain** (if no config):
1. `.claude/startup.toml` → `specs_dir`
2. `the-custom-startup/specs/`
3. `.start/specs/` (migration compat)
4. `docs/specs/` (legacy)

---

## All Commands

→ See [skills.md](skills.md) for the full command reference and decision tree.
