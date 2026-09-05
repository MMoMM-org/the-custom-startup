# Agent Authoring Conventions

The definitive reference for Claude Code subagent structure. Apply when creating, modernizing, or auditing agents.

**Sources:**
- [Anthropic — Create custom subagents](https://code.claude.com/docs/en/sub-agents)
- [Anthropic — Subagents in the SDK](https://code.claude.com/docs/en/agent-sdk/subagents)
- [rsmdt/the-startup PRINCIPLES.md](https://github.com/rsmdt/the-startup/blob/main/docs/PRINCIPLES.md) (April 2026, primary-source-grounded)

This document supersedes any older conventions derived from pre-2026 community guides.

---

## Agent Anatomy

Agents are **flat `.md` files** with YAML frontmatter. There is no `agents/foo/AGENT.md` form — `agents/foo.md` is the only valid layout. **This differs from skills**, which must be directories with `SKILL.md`.

### Locations by scope (highest precedence first)

| Scope | Path | Notes |
|---|---|---|
| Managed (org) | per `permissions` config | Org-wide policy |
| `--agents` CLI flag | session-only JSON | Ad-hoc |
| Project | `<repo>/.claude/agents/<name>.md` | Team-shared via git |
| User | `~/.claude/agents/<name>.md` | Personal, all projects |
| Plugin | `plugins/<plugin>/agents/<role>/<activity>.md` | Read-only, requires plugin enabled |

For activity-scoped agents (most common case), nest under role: `agents/the-architect/design-system.md`. For role-less single-purpose agents, top-level: `agents/the-chief.md`.

**Agent types are indexed at session start.** A newly written agent file is not dispatchable in
the session that created it — `Agent type '<name>' not found` — the same way a skill is not.
Authoring and running therefore need a session boundary between them. A nested `claude -p` run
indexes at its own startup, which is the usable workaround when a fresh interactive session is not
convenient. Verified in Claude Code 2.1.252.

---

## Frontmatter Reference

Per Anthropic's official subagent schema:

| Field | Required | Notes |
|---|---|---|
| `name` | Yes | Matches filename stem, lowercase-kebab |
| `description` | Yes | Routing contract — see § Description below |
| `tools` | No | Whitelist; enforced at dispatch — see § Tool Scoping |
| `disallowedTools` | No | Denylist applied to inherited set |
| `model` | No | `haiku` \| `sonnet` \| `opus` \| specific ID — see § Model Selection |
| `color` | No | Visual identifier — see § Color Mapping |
| `permissionMode` | No | `default` \| `acceptEdits` \| `auto` \| `plan` (parent stricter mode wins) |
| `maxTurns` | No | Hard cap on agentic turns |
| `skills` | No | Preloads listed skills into the subagent at startup (full body, not just availability) |
| `mcpServers` | No | Name reference (share parent connection) or inline definition |
| `hooks` | No | Fires only while subagent is active |
| `memory` | No | `user` \| `project` \| `local` for persistent cross-session memory. **Also grants general-purpose `Write` and `Edit`** — see § Tool Scoping before using it |
| `background` | No | `true` for concurrent execution |
| `isolation` | No | `worktree` runs agent in fresh git worktree, auto-cleaned on no-op |
| `initialPrompt` | No | Auto-submitted first turn when running as main session via `--agent` |
| `user-invocable` | No | `false` to hide from `/` menu while keeping programmatic dispatch |
| `effort` | No | `low` \| `medium` \| `high` \| `xhigh` \| `max`, or an integer — reasoning effort for this agent |
| `observer` | No | Agent type auto-spawned as a background observer whenever this agent runs. Inert unless `CLAUDE_CODE_EXPERIMENTAL_OBSERVER_AGENTS` is set — see § Observers |
| `observerMessage` | No | Supplemental postamble appended after the harness-owned default to each activity digest sent to the observer. Blank values are ignored |
| `observeSubagents` | No | `false` stops subagents this agent spawns from inheriting its observer. Defaults to `true` |
| `experimental` | No | Per-agent experimental options; unknown keys are ignored. Currently `cacheTtl`: `"5m"` \| `"1h"` prompt-cache TTL for this agent's requests, used when no `subagentPromptCacheTtl` setting or env var is set (`"1h"` is ignored while a subscription is in overage) |

The last five were missing from this table until 2026-09-05, and are absent from the
documentation's own field list too. They were read out of the shipped schema in Claude Code
2.1.252; the wording above is the schema's, not a paraphrase of the docs.

### Observers

`observer` attaches a background watcher to an agent. It is not a reviewer dispatched after the
fact: it runs concurrently, receives activity digests rather than the task itself, and reports
through its own `ObserverReport` tool. That makes it a different mechanism from the review agents
in `tcs-workflow`, which only ever see a finished diff.

**The mechanism is off by default, and fails silently when off.** It sits behind the environment
flag `CLAUDE_CODE_EXPERIMENTAL_OBSERVER_AGENTS`, and additionally requires background tasks to be
enabled (`CLAUDE_CODE_DISABLE_BACKGROUND_TASKS` or the `backgroundTasksDisabled` setting turns it
back off). With the flag unset, an `observer:` declaration is a **no-op that reports nothing**: no
observer is spawned, no error is raised, `permission_denials` stays empty, and no `[agentObserver]`
line is logged — because the gate sits upstream of the arming code that would log. Anyone
debugging "my observer never ran" will find no evidence at all until they check the flag.

The findings below were measured in Claude Code **2.1.252** with the flag set, by pairing a probe
worker performing a known tool sequence with an observer that dumped every digest to disk.

- **"Read-only" describes the digest, not the observer.** An observer declared with no `tools:`
  line received `Bash, Edit, Read, Write, Skill, ToolSearch, ObserverReport` — it does *not*
  inherit the observed agent's tool scoping, and it is not confined to `ObserverReport`. In the
  probe it used `Bash` to append a line to a file in the observed agent's own workspace. Give every
  observer an explicit `tools:` line; an unscoped one can write to anything the session can.
- **A report informs, it does not steer.** Reports arrive as ordinary mid-run messages to the
  observed agent, which stays free to ignore them — the probe worker was sent an instruction inside
  a report and refused it, on the grounds that an observer message is not user consent. Design an
  observer to tell the agent something true, never to control it.
- **Delivery races the observed agent.** Reports are queued against the target's turn boundaries.
  A report queued after the observed agent's final turn is simply never delivered: the tool still
  answers `Report queued for <agent>`, which is an acceptance receipt and not proof of delivery. On
  a short, fast task the observer can therefore cost a full agent's budget and change nothing —
  observers pay off on long runs with turns left to correct.
- **Digests carry tool-level detail.** Each of the observed agent's turns arrives wrapped in
  `<{agentName}-activity>` tags containing its assistant text, `<tool-call name="…">` with the full
  JSON arguments, and the matching `<tool-result>`. File paths, file contents and command lines are
  all visible, so tool-level ordering can be supervised in principle. Turns are batched while the
  observer is busy. The harness-owned postamble is appended to every digest, and `observerMessage`
  after it.
- **The observer is spawned on every run of the observed agent**, so it costs a second agent's
  budget each time — another reason it earns its keep on long autonomous runs, not short dispatches.
- **`observeSubagents` defaults to `true`**, so an observed agent's own subagents are observed as
  well. On a fan-out that multiplies quietly — set it to `false` unless the nested work is the
  thing being watched.

Treat all of this as experimental: these fields are absent from the documented frontmatter list,
and a mechanism behind an experimental env flag can change shape without notice.

No TCS agent uses an observer yet; whether one should is evaluated in issue #99.

---

## Description — The Activation Contract

Claude's auto-delegation router reads the `description` field via **text reasoning**, not embedding retrieval or keyword matching. Description quality directly determines whether the agent ever gets invoked.

### Hard Rules (PRINCIPLES § 2.1)

- **Front-load the trigger scenario in the first ~50 characters** — the `/skills` UI truncates at 250 chars, the field hard-caps at 1,024.
- **Third-person, scenario-anchored.** *"Reviews changes for security and compliance issues. Use when the task mentions auth, permissions, or injection."* — not *"Helps with security."*
- **Expect under-triggering.** Anthropic explicitly notes Claude tends to skip skills/agents when it should invoke them. Use *"slightly pushy"* phrasing: `Use PROACTIVELY when…` and `MUST BE USED when…`.
- **Include 2–3 `<example>` blocks** showing concrete invocation scenarios — improves parent-side delegation accuracy.

See `description-patterns.md` for templates and good/bad examples.

---

## Tool Scoping (PRINCIPLES § 2.5)

For subagents, `tools` in frontmatter is a **whitelist applied before the first turn** — tools not listed are stripped from the catalog at dispatch time. Defaults differ by archetype:

| Archetype | Tools | Notes |
|---|---|---|
| Reviewer / Explorer / Architect | `Read, Grep, Glob` | Read-only, never `Write` |
| Debugger / Implementer | `Read, Edit, Write, Bash` | Needs to fix and verify |
| Test Runner | `Read, Bash` | Runs tests, reads output |
| Security Reviewer | `Read, Grep, Glob` | NEVER `Write` — risk of leaking findings into repo |
| Docs Writer | `Read, Write` | No `Bash` needed |

**Rules:**
- Never `tools: *`.
- Never `tools: inherit` without explicit justification — inheriting loses the parent's approval history, so dangerous tools re-prompt every call.
- When `Bash` is necessary, pair with a `PreToolUse` hook that validates commands (e.g., SELECT-only for a DB-query agent).
- For sub-subagent spawning, restrict explicitly: `tools: Agent(name1, name2)`.

### ⚠️ `memory:` widens the whitelist — silently

The whitelist above is not the whole story. Setting `memory: user|project|local` auto-enables
`Read`, `Write` and `Edit`, and **the write access is general-purpose — it is not confined to the
agent's memory directory.**

Measured on Claude Code 2.1.252, two agents differing in exactly one frontmatter line:

| Frontmatter | Tools the agent actually had | Write inside the memory dir | Write to an absolute path outside it |
|---|---|---|---|
| `tools: Read` + `memory: local` | `Read, Write, Edit` | succeeded | **succeeded** |
| `tools: Read` | none | refused | refused |

So this agent is **not** read-only, and nothing in its frontmatter says so:

```yaml
tools: Read, Grep, Glob     # reads as read-only
memory: project             # but this grants Write and Edit anywhere
```

Consequences when authoring:

- **Never put `memory:` on a reviewer, explorer, security or audit agent.** Those archetypes are
  read-only by design, and the field reverses that without touching the line that declares it.
- If an agent genuinely needs both, the write access has to be constrained by a `PreToolUse` hook
  limiting writes to the memory path — which then has to ship wherever the agent does.
- The field is part of **auto memory**. With auto memory disabled (`autoMemoryEnabled`, or
  `CLAUDE_CODE_DISABLE_AUTO_MEMORY`), `memory:` is a silent no-op: no instructions, no tool access.
  An agent that depends on its memory must therefore still work without it — do not ship one whose
  behaviour changes quietly based on a consumer's setting.

The bundle does contain path-containment guards with symlink resolution, but they sit on the memory
key/storage API rather than on the generic `Write`/`Edit` tools this field enables. If that changes,
this section should be re-measured rather than assumed — the spike and its confounds are recorded
in issue #85.

---

## Model Selection (PRINCIPLES § 2.6)

April 2026 pricing and capability:

| Model | Input $/M | Output $/M | SWE-bench |
|---|---|---|---|
| Haiku | 0.80 | 4.00 | ~73% |
| Sonnet | 3.00 | 15.00 | ~80% |
| Opus | 15.00 | 75.00 | ~89% |

| Model | When to use | Examples |
|---|---|---|
| `haiku` | High-volume **read-heavy** work | Codebase search, file discovery, pattern matching. Anthropic's built-in `Explore` uses Haiku |
| `sonnet` | Default for general coding and implementation | Reviewers, debuggers, implementers, doc writers, most architects |
| `opus` | Complex reasoning only | Architectural review of large systems, security analysis with novel threats, hard refactors |
| omit `model` | Inherit parent's session model | When no tactical reason to override |

**TCS convention** (deviates from upstream PRINCIPLES.md slightly):

For team-style activity agents that get dispatched many times, **explicitly set `model: sonnet`** rather than omitting. Reason: omitting inherits the session model — when the user runs Opus, every dispatch costs Opus tokens for tasks that don't need Opus reasoning. Explicit `sonnet` produces predictable cost.

Use `inherit` only when:
- The agent's reasoning genuinely scales with model (some architecture/security work)
- And the user explicitly requested model flexibility
- And you've documented why in a frontmatter comment

---

## Color Mapping (TCS Convention)

Optional `color:` field for visual identification. TCS team agents follow this palette:

| Color | Semantic | Examples |
|---|---|---|
| `blue` | Architect / analysis | `design-system`, `record-decision`, `review-compatibility` |
| `cyan` | Research / exploration | `research-product`, `the-meta-agent` |
| `magenta` | Designer / transformation | `design-interaction`, `design-visual`, `research-user` |
| `green` | Developer / building | `build-feature`, `optimize-performance` |
| `red` | DevOps / production / security-critical | `build-platform`, `monitor-production` |
| `yellow` | Tester / validator / chief | `test-strategy`, `the-chief`, `tdd-guardian` |

Match color to the agent's archetype, not its frontend nicety.

---

## Body Structure — ICMDA Layout

Body sections, in order. Each is a `## ` heading.

### 1. `## Identity`

One or two sentences. Role + purpose + frame.

> *"You are a senior code reviewer ensuring high standards of code quality and security."*

Keep enforcement rules out — those go in Constraints.

### 2. `## Constraints`

Use the `Constraints { require {} never {} }` block syntax (TCS convention). Markdown `**Always:**` / `**Never:**` lists are also acceptable.

```
Constraints {
  require {
    Capture decision context honestly — include pressures and constraints
    Document rejected alternatives with genuine reasoning
  }
  never {
    Create duplicates — check existing artifacts first
    Omit the Alternatives Considered section
  }
}
```

### 3. `## Vision` (optional)

What the agent reads and internalizes before doing the work. Lists for orientation:

> Before writing, read and internalize:
> 1. `.claude/startup.toml` — resolve `docs_base`
> 2. Existing ADRs in `{adr_dir}/`
> 3. The decision input from the user

### 4. `## Mission`

Single-sentence purpose statement. The "why" of the agent.

### 5. `## Decision: <Topic>` (one or more)

Routing tables for decision points. First match wins.

| IF condition | THEN action | Rationale |
|---|---|---|
| Multiple unrelated activities | Split into separate agents | Single-activity agents outperform generalists |
| One activity across many domains | Keep as one agent | Activity focus trumps domain |

Use multiple `## Decision: <X>` sections if the agent makes several distinct decisions during its workflow.

### 6. `## Activities`

Numbered list of concrete actions. Be specific — vague activities produce vague results.

> 1. Identify the relevant modules, interfaces, and architectural seams.
> 2. Check whether responsibilities are cleanly separated.
> 3. Look for coupling, unclear ownership, and likely long-term maintenance risks.

### 7. `## Output`

Typed table defining the agent's return contract:

| Field | Type | Required | Description |
|---|---|---|---|
| findings | Finding[] | Yes | Audit findings list |
| filesReviewed | string[] | Yes | Paths examined |
| recommendedNextStep | string | Yes | Single-sentence next action |

**Free-form prose output is reject-on-sight.** Every agent must define an explicit return contract.

### Optional sections

- `## YOLO Mode` — for agents that behave differently when `YOLO=true`
- `## Evaluation Logic` — for gate-style agents (e.g., `tdd-guardian`)
- `## Validation Checklist` — for agents that audit other artifacts

---

## Active-Agent Announcement

The first non-blank line after the frontmatter (and before any `## ` heading) **must be**:

```
**Active agent: <plugin>:<role>:<activity>**
```

For top-level agents:

```
**Active agent: <plugin>:<name>**
```

This appears in the terminal status line when the agent activates, letting users track which agent is running.

---

## Anti-Patterns (PRINCIPLES § 4.5)

- **`tools: *`** — grants everything; loses parent approvals; every call re-prompts
- **Mega-role god-agents** — single agent with 50+ KB prompt and ten responsibilities
- **Assuming parent context is visible** — it isn't; pass everything through the task prompt
- **Parallel agents with implicit inter-dependencies** — siblings don't see each other
- **Headless write-capable agents with no review gate** — run plan mode first, or require human review between read and write phases
- **Context bloat from verbose subagent returns** — ask for key findings, not exhaustive details
- **Permission-mode confusion** — parent mode overrides; stricter-than-parent honored, looser is not

See `anti-patterns.md` for the complete list with fix guidance.

---

## Size Targets

| Component | Target |
|---|---|
| Frontmatter | 5–15 lines |
| Body | ≤ 25 KB total (PRINCIPLES § 4.3) |
| Identity | 1–2 sentences |
| Mission | 1 sentence |

If the body exceeds 25 KB, externalize verbose checklists or examples to a sibling reference file (`agents/the-architect/reference/<topic>.md`), or preload via `skills:` frontmatter.

---

## Canonical Example

See `examples/canonical-agent.md` for a fully annotated agent demonstrating ICMDA layout with all conventions.
