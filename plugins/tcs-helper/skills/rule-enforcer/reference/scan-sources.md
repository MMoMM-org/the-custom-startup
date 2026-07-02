# Rule Enforcer — Batch Scan Sources

Defines the default source set the batch mode enumerates at workflow step B1
(`--scan` sweep). Batch mode reads these files, extracts candidate
directives, and routes each through the 4-question triage.

Default scope is **repo + project**. Global is **opt-in only** (`--scope global`)
because global files hold personal content — never sweep them without an explicit
request.

---

## Default: repo + project scope

Enumerated on every batch run:

| Source | Pattern | Scope |
|--------|---------|-------|
| Root repo instructions | `./CLAUDE.md` | repo |
| Nested instructions | `**/CLAUDE.md` (Glob) | repo |
| Memory bank | `docs/ai/memory/*.md` | repo |
| Project instructions | project `CLAUDE.md` reached via @-import chain | project |

---

## Opt-in: global scope (`--scope global`)

Added **only** when `--scope global` is passed:

| Source | Pattern | Scope |
|--------|---------|-------|
| Global instructions | `~/.claude/CLAUDE.md` | global |
| Global rules | `~/.claude/rules/*` | global |
| Global includes | `~/.claude/includes/*` | global |
| Auto-memory index | the auto-memory `MEMORY.md` index | global |

These files contain personal profile/preference content. Requiring an explicit
flag keeps that content out of the sweep by default (privacy).

---

## @-import follow policy

Eager @-imports are followed **transitively**: when a scanned file contains an
`@path` import, the imported file joins the scan set, and its imports are
followed in turn.

Do **not** reimplement the traversal. Reuse the discovery model already built in
`memory-claude-md-optimize` (see its `SKILL.md` Step 1 and
`reference/scope-rules.md`), which:

- resolves eager @-imports (expand `~`, resolve relative to the containing file,
  honor absolute paths)
- tracks the import chain that led to each discovered file
- guards against circular imports via a `visited` set of absolute paths
- classifies scope by resolved path: under `~/.claude/` → global; outside the
  repo but not `~/.claude/` → project; inside the repo → repo

That classification is what enforces the scope gate above: files resolving to
`global` are dropped from the scan set unless `--scope global` was passed.

---

## Protected / structural exclusions

These lines are structural, not enforceable rules. They must **never** be
extracted as candidate rules, even when they appear in a scanned file:

| Excluded content | Why |
|------------------|-----|
| Routing rules (e.g. "personal → global, repo conventions → general.md") | Describe where content lives, not a behavior to enforce |
| Category-definition comments (e.g. memory-bank section headers) | Structural scaffolding of the memory system |
| @-import lines themselves (`@path`) | Discovery directives — followed, not enforced |

Everything else surviving the scope gate and these exclusions becomes a
candidate directive for the 4-question triage.
