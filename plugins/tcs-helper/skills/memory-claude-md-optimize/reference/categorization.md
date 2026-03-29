# Content Categorization Reference

## How to Use This Document

During the Categorize phase, evaluate each extracted CLAUDE.md entry against the category
definitions below. Match signal keywords first. When multiple categories seem plausible,
apply the edge case rules. After assigning a category, apply the Scope Fit Assessment to
determine whether the entry is generic (goes to global memory) or repo-specific (stays in
repo memory).

---

## Categories

### general

**Definition:** Conventions that govern how the team writes, names, and structures things.
These are behavioral rules that apply uniformly — style, format, naming, branch patterns,
commit format, code style. They do not describe tools, domain logic, or architectural
rationale; they describe *how things are done consistently*.

**Signal keywords:** naming, convention, style, format, indent, case, structure, kebab-case,
camelCase, always, never, prefer, use X not Y, branch, commit message, file organization,
folder layout, no `any`, semicolons, linting rule

**Examples:**
- "Use kebab-case for all file names."
- "No `any` types in TypeScript — use `unknown` and narrow."
- "Commit messages must not end with a period."
- "Branch names follow `feat/`, `fix/`, `chore/` prefixes."
- "All exports from a module go through the index file."

**NOT general if:**
- The rule is about a specific tool's CLI or config (→ tools)
- The rule describes domain vocabulary or business logic (→ domain)
- The rule explains *why* a choice was made, not just *what* the rule is (→ decisions)

---

### tools

**Definition:** Knowledge about specific tools, APIs, CLI commands, build systems, CI
pipelines, or integrations. Covers non-obvious invocations, environment variables, known
quirks, and setup steps that only apply when using that tool.

**Signal keywords:** build, CI, deploy, script, command, API, client, SDK, tool, bun, npm,
pnpm, yarn, docker, GitHub Actions, env var, `run`, flag, cache key, pipeline, integration,
install, config file name, version pin

**Examples:**
- "Use `bun run` not `npm run` — the package.json scripts assume bun's module resolver."
- "GitHub Actions cache key is `bun.lock`."
- "Set `NODE_OPTIONS=--max-old-space-size=4096` for build commands on large workspaces."
- "The Stripe client must be initialized with `apiVersion: '2023-10-16'` or older versions
  break webhook signature verification."
- "`pnpm install --frozen-lockfile` is required in CI — direct `install` updates the lock file."

**NOT tools if:**
- The behavior is a general code style convention unrelated to a specific tool (→ general)
- The tool choice itself is an architectural decision with rationale (→ decisions)
- The tool has a bug with a proven fix (→ troubleshooting)

---

### domain

**Definition:** Business rules, data models, entity relationships, and domain-specific
vocabulary. Captures what things *mean* in this codebase and what rules govern them,
independent of any implementation detail.

**Signal keywords:** entity, model, rule, business, contract, domain, status, field,
enum, relationship, always lowercase, must be, returns null, identifier, schema, type,
invariant, constraint, means, refers to

**Examples:**
- "`Order.status` is always lowercase — uppercase values indicate a legacy import bug."
- "`UserRepository.findById` returns `null` for unknown IDs, never throws."
- "A `Draft` invoice cannot have line items with zero quantity — enforced at service layer."
- "The term `participant` in this codebase means a confirmed attendee, not a registrant."
- "`price` fields are stored as integer cents, never floats."

**NOT domain if:**
- The rule governs how code is written, not what it represents (→ general)
- The rule is about a specific database tool's quirk, not the data model (→ tools)
- The rule emerged from an architectural decision with a rationale (→ decisions)

---

### decisions

**Definition:** Architecture choices, technology selections, and significant trade-offs,
including the rationale. Captures *why we chose X over Y* so future contributors understand
the reasoning and do not reverse decisions unknowingly.

**Signal keywords:** decided, chose, choice, decision, trade-off, tradeoff, architecture,
why, rationale, ADR, instead of, over, because, considered, rejected, pros/cons, evaluated

**Examples:**
- "Chose hexagonal architecture over layered — enables testing without a live database."
- "Using SQLite because the expected concurrency is low and operational simplicity outweighs
  PostgreSQL's scaling features for this phase."
- "Rejected GraphQL in favour of REST — team has deeper REST expertise and queries are simple."
- "Monorepo over polyrepo — simpler cross-package changes during early development."
- "Using Zod for validation instead of class-validator — works at runtime and type level
  simultaneously."

**NOT decisions if:**
- The rule is a resulting convention with no rationale captured (→ general)
- The entry is about current sprint focus or active exploration (→ context)

---

### context

**Definition:** Time-bound, session-relevant information: current goals, active work items,
sprint focus, known blockers, and what is in progress right now. This category has a short
shelf life — entries older than two weeks are pruned by memory-cleanup.

**Signal keywords:** working on, current, this week, this sprint, right now, in progress,
active, next, focus, goal, milestone, blocker, paused, recently started, today, implementing,
planning to

**Examples:**
- "Implementing the auth module this sprint — JWT-based, targeting email + Google OAuth."
- "Currently blocked on the Stripe webhook integration until the test environment key is
  provided."
- "Active branch: `feat/payment-flow` — do not merge until billing team reviews."
- "This week's focus: stabilize the CI pipeline before adding new features."
- "Recently completed: database migration to schema v3."

**NOT context if:**
- The blocker has a known fix (→ troubleshooting)
- The current work led to an architectural decision (→ decisions)

---

### troubleshooting

**Definition:** Known bugs, proven workarounds, environment-specific failures, and "if X
fails, do Y" patterns. The entry must describe a specific failure mode and a resolution or
mitigation — not just a known limitation.

**Signal keywords:** bug, error, fails, crash, broken, issue, workaround, fix, resolved,
symptom, if X then Y, exception, timeout, retry, fallback, patch, root cause, known issue,
M1, arm64, platform-specific

**Examples:**
- "`bun test` crashes on M1 with native arm64 modules — use `--target=node` flag as
  workaround."
- "If the CI Postgres container refuses connections, the health-check interval needs
  `--health-interval=2s`; the default 30s causes a race."
- "`next build` fails with heap OOM on monorepos > 300 modules — set
  `NODE_OPTIONS=--max-old-space-size=4096`."
- "Stripe webhook signature verification fails when the request body has been pre-parsed by
  express.json — use `express.raw` on the webhook route only."
- "If `prisma generate` exits silently with no output, the issue is a missing `output` path
  in schema.prisma."

**NOT troubleshooting if:**
- The fix became a permanent convention with no failure mode attached (→ general or tools)
- The issue is a current open blocker with no known fix (→ context)

---

## Edge Cases

### Content that matches multiple categories

Apply the first matching rule below:

1. **Rule mentions a specific tool AND describes a convention** — if the rule can only be
   understood in the context of that tool's behavior, use **tools**. If the rule is a style
   decision that happens to mention a tool, use **general**.
   - "Don't use barrel re-exports in Next.js — causes RSC bundling issues" → **tools** (the
     reason is tool-specific)
   - "Don't use barrel re-exports" → **general**

2. **Rule is both a decision and a convention** — if rationale is present ("because", "why"),
   use **decisions**. If it is just the rule with no reasoning, use **general**.
   - "Use Zod because it validates at runtime and build time simultaneously" → **decisions**
   - "Use Zod for all schema validation" → **general**

3. **Rule describes a bug fix that became standard practice** — if the fix is now applied
   proactively as a convention, use **tools** or **general**. If it is still defensive
   "in case of failure", use **troubleshooting**.

4. **Rule is time-bound but mentions a tool** — if the entry describes current active work
   involving a tool, use **context**. The category reflects the *nature* of the entry, not
   its subject matter.

5. **Multiple valid categories with equal fit** — choose the category whose target audience
   is most narrow. A domain rule that only a domain expert needs beats a general convention
   that everyone applies.

---

## Scope Fit Assessment

Scope determines whether a categorized entry goes to global memory (`~/.claude/includes/`)
or stays in repo memory (`docs/ai/memory/`).

### Signals that indicate GENERIC scope (global memory)

Apply **global** scope when any of the following are true:

- Entry mentions a model name (e.g., `gpt-4`, `claude-3-5-sonnet`, `o3`) — model behavior
  is not repo-specific
- Entry references a universal CLI tool with no project-specific context (e.g.,
  "`git rebase -i` requires an interactive terminal" — true everywhere)
- Entry uses first-person workflow language ("I prefer", "always use worktrees", "never
  squash") — personal workflow belongs in global memory
- Entry is a general programming best practice with no repo-specific context
  ("always validate inputs at boundaries")
- Entry would apply identically in any other project the user works on

**Examples of generic content:**
- "Claude Sonnet 4.5 tends to over-explain in list form — prefer prose for design discussions."
- "Always use `git worktree` for parallel feature branches."
- "Never use `--break-system-packages` with pip on macOS."
- "`gh pr create` requires the branch to be pushed before it can create the PR."

### Signals that indicate SPECIFIC scope (repo memory)

Apply **repo** scope when any of the following are true:

- Entry mentions a specific file path (e.g., `src/lib/auth.ts`, `plugins/tcs-helper/`)
- Entry names a project-specific tool, script, or service (e.g., `tcs-helper`, `bun run dev`)
- Entry references repo-specific naming, schemas, or entities (`Order.status`, `UserRepository`)
- Entry describes a CI pipeline or deployment process that is repo-specific
- Entry would be incorrect or misleading if applied to a different project

**Examples of specific content:**
- "Use `bun run` not `npm run` in this repo — scripts assume bun's resolver."
- "`UserRepository.findById` returns `null` for unknown IDs."
- "The `feat/memory-claude-md-optimize` branch must not be merged without spec review."
- "GitHub Actions cache key for this repo is `bun.lock`."

### When scope is ambiguous

If you cannot determine scope from the entry text alone, default to **repo** scope. It is
safer to keep a potentially-generic entry in repo memory than to promote a repo-specific
fact to global memory where it could mislead other projects.
