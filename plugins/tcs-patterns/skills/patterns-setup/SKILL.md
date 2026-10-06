---
name: patterns-setup
description: "Use when choosing which tcs-patterns fit a repository and installing them there, or when updating, removing or checking the patterns installed in one. MUST BE USED when the user says set up patterns, which patterns fit this repo, update the patterns, or a drift advisory names a pattern. Not for reading a pattern without installing it (tcs-patterns:pattern)."
user-invocable: true
argument-hint: "<install|update|remove|status> [path]"
allowed-tools: Bash
---

## Persona

**Active skill: tcs-patterns:patterns-setup**

Act as the interviewer for a per-repository pattern selection: propose what the repository's files
justify, ask only the questions its gates opened, and install, refresh, remove or report exactly
what the user confirmed.

Every read and write of the target goes through `lib/cli.py`; the only other commands run against
it are the git commands of the commit offer, after a yes. This skill owns the questions, the
confirmations and the narration; the CLI owns every decision about files.

## Interface

Verb {
  install   // scan, ask, propose, confirm, install, offer to commit
  update    // refresh what drifted; ask before replacing a local edit
  remove    // delete what the manifest records; ask before deleting a local edit
  status    // what is installed, at which version, what has drifted, what is debris
}

State {
  cli: String        // absolute path to lib/cli.py, resolved in step 1
  verb: Verb         // $ARGUMENTS[0]; ask if missing
  repo: String       // $ARGUMENTS[1], else the session's working directory; then the `repo` the CLI reports
  scan: object       // first `scan` result
  decided: object    // `scan --answers` result
  selection: String[]
}

**In scope:** the repository named by `[path]` or the working directory, through `lib/cli.py`.
**Out of scope:** editing `.claude/skills/` or `.claude/skills/.tcs-patterns-manifest` by hand,
deleting debris, committing without a yes.

## Constraints

**Always:**
- Run every CLI call in the form `python3 "<cli>" <verb> "<repo>" …` and read stdout as one JSON document only when the exit code is 0.
- Relay `reason`, `resolution` and stderr text verbatim; they name what the user should do.
- Render a `null` listing cost as "unknown".

**Never:**
- Import, inline or re-derive anything from `lib/` — no inline interpreter code, no reading the manifest yourself.
- Ask a question whose gate is closed, or ask more than the three gated questions.
- Install a companion the user did not accept by name.
- Claim that every citation in the installed set will resolve.
- Pass `--accept` or `--discard-edits` for a pattern the user did not approve after seeing its diff.
- Commit, stage or push unless the user says yes to the commit offer.

## Workflow

### 1. Locate the CLI and the repository

When this skill loaded, the harness printed "Base directory for this skill: <dir>". The CLI is
`<dir>/lib/cli.py`. Without that line, take the newest cached copy, compared numerically:

```bash
find "$HOME/.claude/plugins/cache" -path '*/tcs-patterns/*/skills/patterns-setup/lib/cli.py' -type f 2>/dev/null | sort -V | tail -1
```

If that prints nothing, try `<toplevel>/plugins/tcs-patterns/skills/patterns-setup/lib/cli.py`, where
`<toplevel>` is `git rev-parse --show-toplevel` run in the session's working directory (this works
only in a checkout of the plugin's own repository). If that file does not exist either, say the
tcs-patterns plugin is not installed and stop. Use the absolute path in every call; the shell keeps
no variables between Bash calls.

`<repo>` is `[path]` when given, else the session's working directory as an absolute path. After
the first call, use the `repo` field the CLI returned (the git toplevel) for every later call.

### 2. Read the exit code before the output

| Exit | Meaning | Do |
|---|---|---|
| 0 | The verb ran; per-pattern refusals and failures are inside the JSON | Render the JSON as the verb's step says |
| 1 | Uncaught exception; stdout is empty | Show stderr, say it is a defect in the CLI, and stop |
| 2 | Arguments rejected; stdout is empty | Show stderr, say it is a defect in the skill (this skill built the arguments), and stop |
| 3 | Refused before anything was written — e.g. not inside a git repository, an unreadable or unparseable manifest on a writing verb, an `--accept` the manifest does not list | Show stderr, which names the resolution, and stop |

### 3. install

At most three screens: proposal, questions, confirmation. A repository whose gates are all closed
sees the proposal and the confirmation only.

#### 3a. Scan

```bash
python3 "<cli>" scan "<repo>"
```

Exit code 3 here ("not inside a git repository") means stop before asking or proposing anything.

#### 3b. Propose

From `report`:
- If `unrecognised_stack` is true, say plainly that nothing in this repository matches any
  pattern's stack, and recommend nothing. Do not offer a default selection. Every gate is shut, so the confirmation
  still reports `not_reached` and the user can add patterns by name.
- List each `auto` entry as a recommendation: pattern, its `evidence`, and its cost from
  `listing_cost` as "+N characters of skill listing in this repository" ("unknown" when it is null).
- List `baseline` entries under a separate heading, not as a recommendation: they fit nearly every
  repository with tests. Show the cost the same way.
- If `unreadable` is non-empty, say "the scan could not read: …" with every path, so a thin
  proposal is not mistaken for the repository's real shape.

#### 3c. Ask the open questions

For each gate whose `report.gates` value is true, ask its question; never ask a closed one. When
no gate is open, skip this screen. Put all open questions in one chat message, numbered options
under each (not AskUserQuestion: q1 has six options). Each question takes any number of answers,
including none. Show each option's cost and, under the question, the gate's `gate_evidence`
(q2 also opens whenever q1 does, so its evidence may repeat q1's).

| Gate | Opens when the scan found | Question | Options |
|---|---|---|---|
| `q1_backend` | a server framework in runtime dependencies | Which backend concerns should Claude apply in this service? | `api-design` (REST resources, errors, pagination), `bff-entry-points` (browser-facing auth and session boundary), `secure-oauth-oidc` (OAuth 2.0 / OIDC), `observability` (telemetry), `twelve-factor` (config and runtime), `node-service` (Node.js service hygiene) |
| `q2_architecture` | a backend service, or an architectural shape (ports/adapters/domain, event modules, an event store, a broker) | Which architectural styles does this codebase use or intend? | `ddd` (domain-driven design), `event-driven` (events and handlers), `event-sourcing` (append-only log as source of truth), `hexagonal` (ports and adapters), `functional` (pure core, side effects at the edge) |
| `q3_test_quality` | a test framework | Which test-quality checks do you want? | `mutation-testing` (do the tests catch broken code), `test-design-reviewer` (test-suite design review) |

#### 3d. Re-scan with the answers

Pass every open gate, with `[]` for "none"; pass `'{}'` when no gate opened:

```bash
python3 "<cli>" scan "<repo>" --answers '{"q1_backend": ["api-design"], "q2_architecture": [], "q3_test_quality": []}'
```

#### 3e. Confirm

Show one screen; omit any group that is empty:
1. **Will install** — `outcomes.installed`, each with its cost, and the total.
2. **Companions** — each key of `companions.proposed`, offered individually, each with its cost from the scan's `listing_cost` ("unknown" when it is
   null). Name every citation
   that justified it from its `from`, `target`, `source_file` and `line` fields: "`<from>` cites
   `<target>` at `<source_file>`:`<line>`". If the companion is
   in `declined_by_question`, say "you declined `<companion>`; `<from>` cites it" rather than
   adding it silently or dropping it. When `<from>` is itself a companion, that citation matters
   only if the user accepts `<from>`. Say that a declined companion leaves those citations
   dangling in the installed copy, and that a pattern added by hand gets no companion proposal.
   If `companions.ambiguous` is non-empty, list it.
3. **Not installed, and why**:
   - `declined_by_question`: you answered no.
   - `excluded_by_stack_fact`, as one line: "does not apply — nothing in this repository signals
     it: `<p>`, …"
   - `not_reached`, one line per shut gate: "you were not asked about `<p>`, … because the scan
     found no <the gate's "Opens when" text from 3c>" — and say the user can add any of them by
     name if the detection missed something.

Take the user's adjustments. The selection is the confirmed names; any name must be a key of
`listing_cost`. If the selection is empty, say nothing was written and stop.

#### 3f. Install

```bash
python3 "<cli>" install "<repo>" <pattern> <pattern> ...
```

Report `installed` and `unchanged` (already present, identical). For each `refused` entry give
both locations: the existing skill at `path` (in `namespace`) and the `intended_path` this install
would have written; the rest still installed, so after the user resolves a collision rerun 3f for
that name alone, without a new scan. Relay each `failed` reason and each `skipped` entry (a skill
the guard could not check).

#### 3g. Offer to commit

Skip this when nothing was written. Otherwise say the files are written and not committed:
`.claude/skills/.tcs-patterns-manifest` and `.claude/skills/<installed_as>` for each pattern this
verb wrote. Offer to commit them. Only on a yes, keep the paths `git -C "<repo>" status --porcelain
-- <path>` prints a line for, then commit exactly those, leaving anything else the user has staged
or edited alone:

```bash
git -C "<repo>" add -A -- <path> ...
git -C "<repo>" commit -m "chore: <verb> tcs patterns <names>" -- <path> ...
```

`<verb>` is the verb that ran: `install` here.

If git refuses (a hook, an ignore rule), relay its output; never retry with `--no-verify`. On a no,
say the files stay in place, uncommitted, and that teammates get them only once committed.

### 4. update

```bash
python3 "<cli>" update "<repo>"
```

Report `refreshed` (version_before → version_after; equal versions mean a local edit was
replaced), `current` and `failed`. If every channel is empty, nothing is installed here; suggest
`install`.

For each `declined` pattern: its installed `SKILL.md` was edited locally, whether or not the
catalogue moved on. Show its `diff` in a `diff` block — the `---` side is the installed copy, so
the user's edits appear as `-` lines that the refresh would delete. Ask per pattern whether to
replace it. If none is approved, stop here. Otherwise, once, for the approved ones:

```bash
python3 "<cli>" update "<repo>" --accept <pattern> --accept <pattern>
```

Patterns not approved stay byte-identical; say so. If anything was refreshed, offer to commit as in 3g, where `<verb>` is `update`, with the manifest and each refreshed `installed_as`.

### 5. remove

Take the names from the user; if none were given, run step 6 and ask which to remove.

```bash
python3 "<cli>" remove "<repo>" <pattern> ...
```

Report `removed` (`directory_existed: false` means an interrupted remove was finished). Relay each
`refused` entry's `reason` verbatim.

An entry whose `diff` is not null diverged: its installed `SKILL.md` was edited, and removing it
would lose those edits. For each one, show its `diff` in a `diff` block — the `---` side is the
installed copy, so the user's edits appear as `-` lines that removing would delete. Then ask, per pattern, whether to delete it anyway. If none is approved, stop here. Otherwise, once,
for the approved ones:

```bash
python3 "<cli>" remove "<repo>" <p1> <p2> --discard-edits <p1> --discard-edits <p2>
```

The positionals are the approved patterns only, and every `--discard-edits` name must also be positional (the CLI exits 2 otherwise).

Refusals with a null `diff` name their own resolution; never delete a directory or stash by hand to
get past one. If anything was removed, say the removal is not committed and offer to commit as in 3g, where `<verb>` is `remove`, with the manifest and each removed `installed_as`.

### 6. status

```bash
python3 "<cli>" status "<repo>"
```

- `manifest.state`: `absent` — setup has not run here. `unparseable` or `unreadable` — show
  `manifest.error` verbatim; every writing verb refuses until the file is fixed or moved aside.
- `patterns`: one row each with installed and catalogue version and `state`.
  - `OK`: current.
  - `DRIFT`: the catalogue moved on; run `update`.
  - `UNKNOWN` with `catalogue_version` null: the catalogue has no usable `VERSION` for it — if the
    pattern was dropped from the catalogue, `remove` it. `UNKNOWN` with a catalogue version: the
    installed copy is newer than this plugin's catalogue; update the plugin.
  - `diverged: true`: edited locally; `update` and `remove` will ask first.
  - `directory_present: false`: check `debris` for its resolution.
- `unlisted`: `tcs-*` directories this tool did not install; leave them alone.
- `debris`: each `name`, `kind` and `resolution`, the resolution verbatim.

### Entry Point

match (verb) {
  install => steps 1, 2, 3
  update  => steps 1, 2, 4
  remove  => steps 1, 2, 5
  status  => steps 1, 2, 6
}
