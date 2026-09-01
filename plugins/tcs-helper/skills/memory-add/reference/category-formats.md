# Memory Entry Format

## The form

A memory entry is **one falsifiable rule, its tell, and one pointer**. Everything else is L2 —
it belongs in the spec, the ADR, or git blame.

```
<!-- YYYY-MM-DD -->
- **<rule>** — <tell>. → <consequence>. [<pointer>]
```

**Budget: ≤ 250 characters per entry.** This is measurable, unlike "keep it short":

```bash
awk '/^- \*\*/ && length($0) > 250 {print FILENAME":"FNR"  "length($0)" chars"}' docs/ai/memory/*.md
```

## Anatomy

| Part | Required | Rule |
|---|---|---|
| Rule | yes | Bold. Imperative or a factual claim. Must be falsifiable — a reader can tell whether it holds. |
| Tell | usually | How you recognize you have hit it. Drop it when the rule is self-evident. |
| Consequence | usually | What to do instead. Drop it when it follows from the rule. |
| Pointer | yes, if one exists | Exactly one: `spec-NNN`, `path:line`, or `#N`. A lookup key, not a citation. |

## Before and after

**Before** — 1100 characters:

> **`CLAUDE_PLUGIN_ROOT` / `CLAUDE_PLUGIN_DATA` are harness-spawned only** — the Claude Code
> harness sets these env vars when *it* directly spawns plugin code (settings.json
> `${CLAUDE_PLUGIN_ROOT}/scripts/...` hooks, plugin `hooks.json` registrations, skill-invoked
> Bash). They are NOT propagated to git-spawned subprocesses (git hooks like
> `.githooks/post-merge` fired by `git merge`) NOR to processes spawned by the Bash tool.
> `CLAUDE_CODE_SESSION_ID` and `CLAUDECODE=1` DO propagate through git. Verified empirically
> 2026-05-13 via 3-context env probe in this repo. Implication: plugin code that runs in
> git-hook context (any `templates/githooks/*` installed via `core.hooksPath`) cannot rely on
> these env vars — it must self-derive paths, inline its dependencies, or accept install-time
> substitution. This is the root architectural cause behind spec/012
> (`docs/XDD/specs/012-tcs-git-helpers-hook-runtime-contract/`).

**After** — 280 characters:

> **`CLAUDE_PLUGIN_ROOT`/`CLAUDE_PLUGIN_DATA` reach only harness-spawned plugin code.** Not
> git-spawned hooks (`core.hooksPath`), not Bash-tool subprocesses. `CLAUDECODE=1` and
> `CLAUDE_CODE_SESSION_ID` do propagate. → Git-hook code must self-derive its paths.
> [spec-012]

Dropped: the verification date and method (git blame has the date, the spec has the method),
the enumeration of every harness context, and the "root architectural cause" narrative. The
bare `[spec-012]` pointer carries all of it for anyone who needs it.

## What does NOT go in an entry

- **Verification date and method** — "Verified empirically 2026-05-13 via 3-context env probe".
- **Incident history** — "T2.3, T2.2, T2.1 all shipped this trap initially".
- **Restating a neighbouring entry** — merge the two instead.
- **More than one pointer.** If a second one is load-bearing, the entry is really two entries.
- **Code blocks over 3 lines** — link a file at `path:line`.
- **Hedging and framing** — "This is correct behavior, not a bug", "worth remembering that".

## What is not an entry at all

Three things routinely land in memory that are not memory. Route them out:

| Looks like | Actually is | Goes to |
|---|---|---|
| A correction to another entry | A qualifier on that entry | Merge into it |
| A reusable recipe or pattern | Skill or test-suite material | A skill, or the tests' README |
| Absorbed prior art from another project | Provenance | `docs/about/sources.md` |

## Category shapes

Most files take the standard form above. Two differ:

### decisions.md

Decisions carry their date inline and a rationale rather than a tell:

```
- 2026-03-25 — Chose SQLite over Postgres. → Expected low concurrency; simpler ops. [spec-004]
```

### troubleshooting.md

Problem records carry a status, and are removed once resolved and the fix has shipped:

```
## bun test crash on M1 — Status: open
NODE_OPTIONS=--max-old-space-size=4096 fixes OOM on large test suites. [#41]
```

A resolved record earns its place only if the fix is non-obvious from the code. Otherwise
delete it — the repository already remembers.
