---
title: "Observability rollout across active repositories"
status: draft
version: "1.0"
spec: 019
---

# Solution Design Document

## Validation Checklist

### CRITICAL GATES (Must Pass)

- [x] Every PRD requirement maps to exactly one component
- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Every architecture decision has rationale and trade-offs
- [x] All interfaces are specified
- [x] No component owns another's responsibility

### QUALITY CHECKS (Should Pass)

- [x] Existing codebase patterns explored and cited
- [x] Directory map matches the repository's real layout
- [x] Error handling is designed, not assumed
- [x] Every acceptance criterion is machine-checkable
- [x] Cross-cutting concerns addressed
- [x] Technical debt named rather than hidden
- [x] Load-bearing assumptions verified rather than asserted

---

## Output Schema

### SDD Status Report

| Field | Value |
|---|---|
| specId | 019-observability-rollout-across-active-repos |
| status | COMPLETE |
| components | 4 |
| adrs | 8 |
| acceptanceCriteria | 26 |
| clarificationsRemaining | 0 |

### SectionStatus

| Section | Status |
|---|---|
| Constraints | COMPLETE |
| Implementation Context | COMPLETE |
| Solution Strategy | COMPLETE |
| Building Block View | COMPLETE |
| Runtime View | COMPLETE |
| Deployment View | COMPLETE |
| Cross-Cutting Concepts | COMPLETE |
| Architecture Decisions | COMPLETE — 8 ADRs, all confirmed by the maintainer |
| Quality Requirements | COMPLETE |
| Acceptance Criteria | COMPLETE |
| Risks and Technical Debt | COMPLETE |

### ADRStatus

| ADR | Decision | Confirmed |
|---|---|---|
| ADR-1 | Register in the target's untracked local settings layer | yes — maintainer |
| ADR-2 | Scripts live under `$HOME/.claude/`, referenced by `$HOME` in the command | yes — maintainer |
| ADR-3 | Adopt the bundle-versioning pattern rather than an absolute path into this repository | yes — implied by ADR-2 |
| ADR-4 | Merge like satori, write unlike it | yes — maintainer |
| ADR-5 | Ownership is proven by path namespace, not by exact command identity | yes — maintainer |
| ADR-6 | Locations config is TOML in this repository's auto-ignored config directory | yes — maintainer |
| ADR-7 | The report splits by the record's own `repo` field; only coverage is unioned | yes — maintainer |
| ADR-8 | The coverage denominator stays one repository's shipped inventory | yes — maintainer |

---

## Constraints

- **CON-1**: bash 3.2 (the macOS default) for all shell code. No associative arrays, no `${var^^}`,
  no PCRE classes in `[[ =~ ]]`.
- **CON-2**: A hook must never change the wrapped tool call's exit status, stdout or stderr. This is
  inherited unchanged from spec-018 and is why every failure path here is fail-open.
- **CON-3**: No new runtime dependency. TOML parsing uses `tomllib`, which is stdlib on the local
  Python (3.14) and already pinned as an acceptance test by spec-002.
- **CON-4**: Nothing this feature writes into a target repository may be reachable by version
  control. Verified per target rather than assumed — see ADR-1.
- **CON-5**: A registered hook costs roughly 3–5 ms per matching event on macOS whether or not it
  records. This is a platform floor, not an implementation defect (spec-018 README, Decisions Log,
  2026-09-07: script size and early-exit position both measured and refuted). The design cannot
  reduce it; it can only decide where to spend it.
- **CON-6**: The record's location and the instruction-inventory walk are both derived from `$HOME`.
  Any design that changes one must change the other consistently.

---

## Implementation Context

### Required Context Sources

```
# Internal documentation and patterns
docs/XDD/specs/018-observability-load-and-fire-log/solution.md   # the recorder this extends; ADR-1, ADR-5, SDD-AC-15
docs/XDD/specs/018-observability-load-and-fire-log/README.md     # the measured platform facts every number here traces to
docs/XDD/specs/012-tcs-git-helpers-hook-runtime-contract/solution.md  # the bundle-versioning pattern, 8 ADRs
docs/XDD/specs/019-observability-rollout-across-active-repos/requirements.md

# Source code that must be understood before implementing
scripts/observability/report.py                                   # the reader being extended
plugins/tcs-helper/scripts/observability/logwrite.sh              # the writer; `repo` is frozen at :660-695
plugins/tcs-helper/scripts/observability/log_instructions.sh      # adapter; self-locates via ${BASH_SOURCE[0]} at :38
modules/satori/scripts/install-hooks.sh                           # the settings-merge precedent, :62-106
plugins/tcs-git-helpers/skills/git-setup/SKILL.md                 # the install process pattern: lock, detect, confirm, write
plugins/tcs-git-helpers/skills/git-setup/lib/install_files.sh              # copy + substitute + atomic version marker
plugins/tcs-git-helpers/skills/git-setup/lib/detect_conflicts.sh           # severity exit codes; version-marker ownership
plugins/tcs-git-helpers/skills/git-setup/lib/lock.sh                       # bash 3.2 lock via set -C noclobber
plugins/tcs-git-helpers/scripts/lib/drift_check.sh                # OK / MISSING / DRIFT comparator
plugins/tcs-git-helpers/tests/bats/install-files.bats             # the canonical target-repo test shape
plugins/tcs-git-helpers/tests/fixtures/repos/build.sh             # named-scenario fixture builder
```

### Implementation Boundaries

**In scope:** a setup and removal command; a versioned script bundle installed per environment; a
locations config; the report's extension to several records.

**Out of scope:** any change to what the recorder records. This spec adds no event type, no field,
and no change to the writer. It changes only *where the recorder runs* and *how many records the
reader reads*.

### External Interfaces

```
# Inbound — what invokes this system
The maintainer, deliberately, via a setup/removal command and via the report.
Nothing invokes it automatically. There is no scheduled component and no daemon.

# Outbound — what this system calls
git         : to resolve a target's toplevel and to ask whether a path is ignored
the filesystem : to copy the bundle, to read records, to walk inventories

# Data interfaces
reads : events.jsonl records written by spec-018's writer (schema unchanged)
writes: a target repository's .claude/settings.local.json (merge only)
        $HOME/.claude/observability/ (the script bundle plus its version marker)
        .claude/observability-sources.toml in THIS repository (the locations config)
```

### Project Commands

```bash
pytest -q                                   # the report's tests
bats plugins/*/tests/bats                   # the shell tests, including the new setup suite
python3 scripts/observability/report.py     # the reader, now with no arguments needed
```

---

## Solution Strategy

Four ideas carry this design, and three of them are chosen because the repository already proved
them somewhere else.

1. **Let `$HOME` do the work.** spec-018 found that the record's two location shapes — container and
   host — "differ only in what `$HOME` is". This design applies the same trick to the scripts
   themselves. A bundle at `$HOME/.claude/observability/` resolves to the repository's gitignored
   container home inside a container, and to the real home on the host. One command string is
   therefore correct in every target, and no absolute path is ever baked into a target's config.
   **Verified rather than assumed (2026-09-08): `$HOME` does expand inside a hook command string** —
   a throwaway hook registered as `"$HOME/…/probe.sh"` fired, and `$0` inside it resolved to the
   fully expanded path.
2. **Adopt the bundle-versioning pattern (spec-012).** A version marker beside the installed bundle,
   a drift check that compares it against the plugin's current version, and a CI gate that fails a
   PR changing the bundle without bumping the marker. The alternative — pointing every target at
   this repository's checkout — has no upgrade path and fails silently when the checkout moves.
3. **Merge like satori, write unlike it.** Satori's `install-hooks.sh` is the only precedent here
   for editing a user-owned settings file, and its merge semantics are right: read the whole
   document, append only when absent, never touch a foreign entry. Its *write* is not: it truncates
   the real file before rewriting it, so an interruption destroys the user's configuration. Three
   other writers here replace atomically instead, by renaming over the target — `install.sh:729-731`
   and `the-custom-startup-configure-statusline.sh:176-180` via `mktemp`, `install_files.sh:130-132`
   via a fixed `.tmp` suffix. The rename is the safety property; how the temporary name is chosen is
   not.
4. **Split by the record's own `repo` field.** Every record already carries it, frozen and not
   caller-settable, and `report.py` reads it nowhere. It is the dimension the reader is missing, and
   adding it is what makes several records safe to read at once.

---

## Building Block View

### Components

| Component | Responsibility | Owns PRD |
|---|---|---|
| **Bundle installer** | Places a versioned copy of the recorder's scripts at `$HOME/.claude/observability/`, and reports drift against the plugin's current version | F1 bundle placement, F5 bundle currency |
| **Registration editor** | Merges and un-merges the three hook entries and the switch in a target's `.claude/settings.local.json`, without disturbing what it does not own — and reads them back, which is how anything answers whether a target is registered at all | F1, F2, F5 registration presence |
| **Locations config** | Records which targets exist and where each one's record lives, so the reader needs no arguments | F3 |
| **Report aggregation** | Reads several records as a set, splits every per-repository analysis by the record's `repo` field, and unions exactly one figure | F4, F5 record liveness |

Responsibility matrix — **every PRD *requirement* has exactly one owner. A *feature* may
decompose into requirements owned by different components**, which is not overlap and is worth
stating because an earlier draft of this section conflated the two granularities: F1 was already
split into requirement rows while F5 was left as a single feature row, so F5 appeared to have two
owners when it actually had two requirements. The check that matters is the one below it — no
component reads or writes another's storage — and that holds.

| PRD requirement | Owner |
|---|---|
| F1 setup writes registration | Registration editor — it owns the outcome and delegates bundle placement to the Bundle installer. A call edge is not co-ownership; treating one as such would fail MECE for every orchestrated design |
| F1 nothing foreign is modified | Registration editor |
| F1 writes only where git ignores | Registration editor |
| F2 removal | Registration editor |
| F3 the list of locations | Locations config |
| F4 per-repository reporting | Report aggregation |
| F4 union coverage | Report aggregation |
| F5 — is the installed bundle current? | Bundle installer (a property of the installed files) |
| F5 — is this target registered at all? | Registration editor (a property of the target's settings; the report sees records, not registrations, so nothing else can answer it) |
| F5 — is this source still producing records? | Report aggregation (a property of the record stream) |
| F6 assisted discovery | Locations config |

### Directory Map

```
plugins/tcs-helper/
  skills/observability-setup/
    SKILL.md                       # the invoked command: install, remove, status
    lib/
      bundle_install.sh            # copy the bundle to $HOME/.claude/observability/, write the version marker
      registration.py              # the settings.local.json merge/unmerge (see ADR-4)
      detect.sh                    # classify a target before writing: clean / ours-current / ours-old / foreign
  templates/observability/
    tcs-helper-observability-version      # source of truth for the bundle version (spec-012 pattern)
  scripts/observability/           # unchanged: the bundle's source files

scripts/observability/
  report.py                        # extended: reads N records, splits by `repo`
  sources.py                       # NEW: reads the locations config, resolves each to a record path

.claude/
  observability-sources.toml       # NEW, never committed: the locations config (see ADR-6)

tests/
  test_observability_sources.py    # NEW: the config reader
  test_observability_report.py     # extended: aggregation cases
plugins/tcs-helper/tests/bats/
  observability-setup.bats         # NEW: the install/remove suite
```

### Interface Specifications

**The locations config (ADR-6).** TOML, in this repository's `.claude/`, which ignores any new file
by default — a property verified mechanically rather than assumed, and one that fails safe: nobody
has to remember to add an ignore rule.

```toml
# .claude/observability-sources.toml — never committed; holds real names and paths
[[source]]
label     = "repo1"                     # what the report prints
repo_root = "/abs/path/to/repo1"        # also the inventory walk root
homes     = ["/abs/path/to/repo1/claude-docker-home"]   # optional; omit for a host-only target

[[source]]
label     = "repo2"
repo_root = "/abs/path/to/repo2"
# no `homes` — the real $HOME applies

[[source]]
label     = "repo3"
repo_root = "/abs/path/to/repo3"
# worked in BOTH environments: one source, two record locations, one identity
homes     = ["/abs/path/to/repo3/claude-docker-home", "~"]
```

**`homes` is a list, and that is a deliberate correction (2026-09-08).** It was a single optional
value until a completeness audit found that PRD F3 promises a repository worked on in *both*
environments can express both its record locations, and the single value could not. The obvious
workaround — two `[[source]]` entries sharing a `repo_root` — is worse than it looks: both would
emit records under the *same* frozen `repo` value while carrying two different labels, leaving the
renderer an undecided two-to-one mapping. Grouping by `repo` would silently discard a label;
grouping by `label` would print one repository as two sections, which is the class of dishonesty
ADR-7 exists to prevent. It would also walk the same inventory twice.

A list keeps **one repository = one label = one `repo` value = one section**, whose records are read
from several files and merged — which is precisely the rotated-chain merge `read_events` already
performs, applied one level up.

**Which home feeds the inventory walk (CON-6, decided 2026-09-08).** The walk reads the repository
*and* `$HOME`, and the `$HOME` half is the user-level instruction files — which genuinely differ
between a container home and the real one. The denominator is therefore the **union of both
homes' instruction trees**, walked from the single `repo_root`. That answers the question the
report actually asks — *across every way I work in this repository, which instruction file never
loads?* A designated primary home would have been simpler and silently wrong: the other home's
files would appear neither as loaded nor as never-loaded, vanishing from the analysis with nothing
to show they were missing.

`repo_root` and each entry in `homes` are exactly the values `report.py` already accepts as
`--repo-root` and `--home`, and `_resolve_events_path` already derives both location shapes from
them. The config therefore stores no derived path and cannot drift from the resolver.

**The registration written into a target.** Three hook entries and one switch, all inside the
untracked local settings layer:

```json
{
  "env": { "CLAUDE_OBSERVABILITY_ENABLED": "1" },
  "hooks": {
    "InstructionsLoaded": [{ "matcher": "", "hooks": [
      { "type": "command", "command": "\"$HOME/.claude/observability/log_instructions.sh\"" }]}],
    "PreToolUse": [{ "matcher": "Skill", "hooks": [
      { "type": "command", "command": "\"$HOME/.claude/observability/log_skill.sh\"" }]}],
    "SubagentStart": [{ "matcher": "", "hooks": [
      { "type": "command", "command": "\"$HOME/.claude/observability/log_agent.sh\"" }]}]
  }
}
```

**The report's aggregation interface.** `report.py` gains no required argument. With no arguments it
reads the locations config; `--events` continues to mean "this one record", so every existing
invocation keeps working.

---

## Runtime View

### Primary Flow — setup

1. Resolve the target's toplevel. Not a repository → report, write nothing.
2. Acquire a lock, before detection rather than before writing, so two concurrent runs serialize
   across the whole sequence (the ordering `git-setup` establishes and explains).
3. Detect, read-only, and classify: is the local settings file absent, valid, or unparseable; does
   it already carry entries in our namespace; are those current or older; are there foreign entries
   under the same event names.
4. Verify the write target is ignored by version control. If it is not, stop — this is the check
   that would have prevented the design's original mistake.
5. Report the plan and what it would change. Confirm.
6. Install the bundle to `$HOME/.claude/observability/` with its version marker.
7. Back up the settings file, then merge: read the whole document, append only what is absent, write
   to a temporary file, rename over the original.
8. Report what changed and how to reverse it.
9. Release the lock.

### Error Handling

| Failure | Behaviour |
|---|---|
| Target is not a repository | Report, write nothing, exit 0 |
| Settings file is unparseable | Write nothing, report it as unreadable, exit non-zero. Never repair a file we did not author |
| Foreign entries under the same event | Report precisely what and where, change nothing, exit 0 — a stop condition, not a failure (the `with_gha.sh` posture) |
| Write target is not ignored by version control | Refuse and explain. This is the one refusal that protects a third party |
| Interrupted mid-write | The original is intact: the rename is atomic, and a backup exists |
| Lock held by a live process | Wait or report; never force-remove a live foreign lock |
| A configured source has no record yet | The report says so for that source and still reports the others |
| A configured source's path no longer exists | Report the source as missing; never treat it as "recorded nothing" |

### Complex Logic — how the report splits without lying

The single hardest correctness question in this spec, because the naive merge looks right.

Every record carries `repo`. The reader currently ignores it and keys instruction statistics on the
redacted path alone, so `CLAUDE.md` from two repositories is one key. Merging records without
introducing the dimension therefore produces a plausible, wrong number.

- Instruction statistics key on `(repo, path)`, and render grouped by repository.
- The never-loaded list is a difference per repository — an inventory walked with that repository's
  own `repo_root` and its `homes`, minus what loaded there. It is never a difference against a
  pooled set, and a source with several homes is still one inventory walk from one `repo_root`.
- Recording status is computed per repository and rendered per repository. **It is never merged.**
  Merging takes the newest timestamp across everything, so one live repository would report the
  whole set as fresh and hide a source that stopped months ago — inverting spec-018's SDD-AC-15,
  which exists to prevent exactly this class of dishonesty.
- Hook timing's `installed` flag is likewise per repository, for the same reason.
- Firing coverage is the exception and the one union: numerators from every source, against a single
  denominator. It needs no repository identity, which is why it is the only analysis that merges
  cleanly. Its per-repository detail is reported *alongside* it, because "fired somewhere" and
  "fired in both places it should" are different questions and the PRD asks the second.

---

## Deployment View

Nothing is deployed. Installation is a person running a command against a named repository. The
bundle lands in one directory per environment; the registration lands in one untracked file per
target; the locations config lands in this repository and is never committed. Removal reverses the
second, leaves the first (harmless and shared), and leaves records untouched.

---

## Cross-Cutting Concepts

### Patterns used

- **Bundle versioning (spec-012)** — version marker beside the installed copy, drift check, CI gate.
- **Install sequencing (`git-setup`)** — lock → detect → confirm → write → summarize → release.
- **Severity-coded detection (`detect_conflicts.sh`)** — clean / warn / conflict / abort, never a
  boolean.
- **Foreign content is a stop condition (`with_gha.sh`)** — warn, change nothing, exit 0.
- **Atomic replace (`install.sh:729-731`, `the-custom-startup-configure-statusline.sh:176-180`,
  `install_files.sh:130-132`)** — write elsewhere, then rename over the target. The first two use
  `mktemp`; the third uses a fixed `.tmp` suffix. The rename is the safety property.
- **Fail-open recording (spec-018)** — unchanged, and untouched by this spec.

### New pattern

- **Namespace ownership.** JSON has no comment in which to write a version banner, so ownership
  cannot be proven the way `git-setup` proves it. It is proven instead by the command string living
  under our path namespace, `$HOME/.claude/observability/`. See ADR-5.

---

## Architecture Decisions

**ADR-1 — Register in the target's untracked local settings layer, not its shared one.**
*Choice:* write to `.claude/settings.local.json`.
*Rationale:* the shared file is version-controlled in three of the four intended targets and all
four have remotes. A registration written there would appear in diffs, could be committed, and once
pushed would silently start recording for anyone who cloned the repository. The local layer is
untracked in all four, and one of them already carries a `hooks` block there — evidence that the
harness honours hooks at that layer, not a claim from documentation.
*Trade-offs:* the local layer is invisible to version control, so `git checkout` is not a rollback;
a backup file is therefore mandatory rather than optional (ADR-4). Confirmed by the maintainer.

**ADR-2 — The bundle lives under `$HOME/.claude/observability/` and is referenced by `$HOME`.**
*Choice:* one versioned copy per environment; the command string is identical in every target.

*Where the copy comes from — added 2026-08 after a gap was noticed:* the source is the setup
skill's own plugin directory, `../../scripts/observability/` relative to the skill's base
directory, which the harness names when the skill loads. **Not `$CLAUDE_PLUGIN_ROOT`** — this
repository has already recorded that the variable does not reach a Bash-tool subprocess, which is
what a skill's helper scripts run as, and spec-018's ADR-1 exists because of exactly that. The
relative-to-base-directory form is what `git-setup` already uses for its own `lib/` scripts.

*This makes publishing a prerequisite rather than a side effect.* Until the observability scripts
ship in a released plugin version they exist only in this repository's working tree, so a setup
command invoked from a target repository would have nothing to copy. Merging them to `main`
bumps `tcs-helper` and puts them in the plugin cache, which is where every target's setup run
reads them from. The scripts travel; **no registration and no switch travels with them**, so a
consumer who never runs setup carries inert files and pays nothing.
*Rationale:* `$HOME` is the container's gitignored docker home inside a container and the real home
on the host, so a single expression covers both shapes — the same mechanism spec-018 found for the
record locations. No absolute path is baked into any target, so nothing breaks when this repository
moves. Verified: `$HOME` expands in a hook command string.
*Trade-offs:* one bundle per environment rather than one per machine, so a container target needs
its bundle installed inside its own home. Confirmed by the maintainer.

**ADR-3 — Adopt bundle versioning rather than pointing at this repository.**
*Choice:* the spec-012 pattern — version marker, drift check, CI gate.
*Rationale:* the alternative has no upgrade path. A bug fix would need hand-patching per target, and
a moved checkout would break every target silently, because hooks fail open. This is precisely the
failure spec-012 was written to prevent, and the maintainer has previously asked for this pattern by
name for cross-repo distributed files.
*Trade-offs:* more machinery than a path string, and a maintainer contract to keep (the CI gate
fails a PR that changes the bundle without bumping the marker).

**ADR-4 — Merge like satori; write unlike it.**
*Choice:* satori's merge semantics — read the whole document, `setdefault` the hooks block, append
only when absent, never modify a foreign entry. An audit of that precedent found **nine** gaps.
**Seven are closed here**: atomic replace via `mktemp` → `mv`; a backup before writing; a parse
check that refuses rather than tracebacks; `ensure_ascii=False` so foreign non-ASCII values are not
silently rewritten; a plan-then-confirm step; a lock; and an ownership concept (ADR-5).

**Two are deliberately not closed, and saying "nine gaps closed" would have been false** — an
earlier draft of this row did say exactly that, and a consistency audit caught the count against the
list. (8) *Formatting preservation*: `indent=2` reflows a differently formatted document. Nothing in
this repository solves it, so it is accepted as a cost below rather than pretended away.
(9) *Key ordering*: nothing pins it beyond the interpreter's insertion order, which puts appended
keys last. That is acceptable and is recorded so the next reader does not mistake silence for
oversight.
*Rationale:* the merge half is proven in this repository and does exactly what the PRD requires. The
write half truncates the real file before rewriting it, so an interruption destroys the user's
configuration outright — the worst failure this command can have, and the one the PRD names first.
*Trade-offs:* `indent=2` reflows a differently formatted document, so a target's settings file may
show as wholly changed. No precedent in this repository solves that; it is named here as an accepted
cost rather than discovered in a diff.

**ADR-5 — Ownership is proven by path namespace, not by exact command identity.**
*Choice:* an entry is ours when its command string points inside `$HOME/.claude/observability/`.
*Rationale:* JSON has no comment, so `git-setup`'s version-banner mechanism is unavailable. Satori's
alternative — exact command-string equality — has a specific failure: a changed command registers as
a second, duplicate group rather than an update, with no way to recognise or remove the old one. A
namespace prefix survives a version change, an added flag and a renamed script.
*Trade-offs:* anything else placing a command under that path would be claimed as ours. The
namespace is specific enough that this is acceptable, and detection reports what it will treat as
ours before writing.

**ADR-6 — The locations config is TOML in this repository's `.claude/`.**
*Choice:* `.claude/observability-sources.toml`, holding `label`, `repo_root` and an optional `homes` list.
*Rationale:* TOML is this repository's format for its own config, and `tomllib` is stdlib, so CON-3
holds. `.claude/` ignores any new file by default — verified mechanically — which makes the file
uncommittable without anyone remembering an ignore rule. Storing `repo_root` and `homes` rather than
a derived record path means the config cannot drift from the resolver that consumes it.
*Trade-offs:* there is no precedent in this repository for a user-maintained local config file; the
existing local files are harness-owned. This is a new category and is justified rather than
inherited. Discovery is not a substitute: three record directories on this machine today were
produced by tests, and a discovery pass would have ingested them as repositories.

**ADR-7 — Split by `repo`; union only coverage.**
*Choice:* per-repository rendering for instruction statistics, byte accounting, recording status and
hook timing; a single unioned figure for firing coverage, with per-repository detail beside it.
*Rationale:* merging is not uniformly safe. Recording status and the hook `installed` flag become
actively misleading when merged, because both collapse to a single winner across the set. Coverage
is the one analysis that gains from merging, and the only one needing no repository identity.
*Trade-offs:* more output. The report becomes a document rather than a screenful, which is the
correct shape for something read at the end of a collection period.

**ADR-8 — The coverage denominator stays one repository's shipped inventory.**
*Choice:* walk the shipping repository for the inventory; union numerators from every source.
*Rationale:* globbing every source's root for the denominator would inject a target's own local
agents into a fraction meant to measure the shipped inventory. Records naming something outside the
inventory are already reported separately rather than dropped, so unknown names degrade gracefully.
*Trade-offs:* the denominator is only as current as the shipping repository's checkout at report
time.

---

## Quality Requirements

| Quality | Requirement | Verified by |
|---|---|---|
| Safety | No file this feature writes in a target is reachable by version control | A test asserting `git check-ignore` succeeds for every written path |
| Non-destruction | A foreign entry present before setup is byte-identical after it | bats case over a foreign-entry fixture |
| Atomicity | An interrupted write leaves the original file intact | A test that writes via the real path and asserts the temporary file is distinct |
| Idempotency | Running setup twice equals running it once | bats case asserting no diff on the second run |
| Reversibility | Removal restores the pre-setup content of what it authored, and leaves foreign entries | bats case over a mixed fixture |
| Honesty | No merged figure is presented where the merge would be misleading | pytest cases over multi-source fixtures with divergent freshness |
| Overhead | Unchanged from spec-018 — this spec adds no work to the hook path | No new code runs inside a hook |

---

## Acceptance Criteria

| # | Criterion | Traces to |
|---|---|---|
| SDD-AC-1 | Given a target that is not a repository, when setup runs, then nothing is written and it reports why | PRD F1 |
| SDD-AC-2 | Given a target whose local settings file is absent, when setup runs, then it is created containing only authored entries | PRD F1 |
| SDD-AC-3 | Given a target whose local settings file holds unrelated top-level keys, when setup runs, then those keys are unchanged | PRD F1 |
| SDD-AC-4 | Given a target holding a foreign entry under one of the three event names, when setup runs, then that entry is unchanged and setup exits 0 without writing | PRD F1 |
| SDD-AC-5 | Given a target whose local settings file cannot be parsed, when setup runs, then nothing is written and it exits non-zero with a diagnosis rather than a traceback | PRD F1 |
| SDD-AC-6 | Given any target, when setup would write, then the written path is confirmed ignored by version control first, and setup refuses if it is not | PRD F1, CON-4 |
| SDD-AC-7 | Given setup has already run at the current version, when it runs again, then nothing changes and it reports "already configured" | PRD F1 |
| SDD-AC-8 | Given setup has run at an older bundle version, when it runs again, then it reports an update rather than an install, and the old entries are replaced not duplicated | PRD F1, ADR-5 |
| SDD-AC-9 | Given a write is interrupted, when the target is inspected, then the original file is intact and a backup exists | PRD F1, ADR-4 |
| SDD-AC-10 | Given a settings file containing non-ASCII values, when setup writes, then those values are byte-identical afterwards | ADR-4 |
| SDD-AC-11 | Given two concurrent setup runs against one target, when both proceed, then they serialize and neither observes a partial write | ADR-4 |
| SDD-AC-12 | Given a target where setup previously ran, when removal runs, then only authored entries are gone and foreign entries remain | PRD F2 |
| SDD-AC-13 | Given a target where setup never ran, when removal runs, then nothing changes and it exits 0 | PRD F2 |
| SDD-AC-14 | Given a target with existing records, when removal runs, then the records still exist | PRD F2 |
| SDD-AC-15 | Given a bundle installed at an older version than the plugin's marker, when the status command runs, then drift is reported | PRD F5, ADR-3 |
| SDD-AC-16 | Given a locations config with a container source and a host source, when the report runs with no arguments, then both records are read | PRD F3 |
| SDD-AC-17 | Given a configured source whose record does not exist, when the report runs, then that source is reported as not yet recording and the others are still reported | PRD F3 |
| SDD-AC-18 | Given a configured source whose path no longer exists, when the report runs, then it is reported as missing, never as "recorded nothing" | PRD F3 |
| SDD-AC-19 | Given records from two repositories both containing a file of the same name, when the report runs, then the two are counted separately | PRD F4, ADR-7 |
| SDD-AC-20 | Given one source recording now and one whose newest record is months old, when the report runs, then each source's recording state is reported separately and the stale one is named | PRD F4, ADR-7 |
| SDD-AC-21 | Given the timing wrapper installed in one source only, when the report runs, then timing is not presented as available for the others | PRD F4, ADR-7 |
| SDD-AC-22 | Given a shipped skill that fired in one source and not another, when the report runs, then both facts are visible | PRD F4 |
| SDD-AC-23 | Given records from several sources, when coverage is computed, then the denominator is the shipping repository's inventory alone | PRD F4, ADR-8 |
| SDD-AC-24 | Given the existing single-record invocation `--events <path>`, when it is used, then behaviour is unchanged from spec-018 | Backwards compatibility |
| SDD-AC-25 | Given one source configured with two homes, when the report runs, then its records from both locations are merged into a single section under one label, and the instruction inventory is the **union of both homes' trees** walked from the one `repo_root` | PRD F3, ADR-6, CON-6 |
| SDD-AC-26 | Given a source configured but absent from its target's settings, when the liveness check runs, then it is reported as *not configured*, distinct from *configured but silent* | PRD F5 |

---

## Risks and Technical Debt

### Known Technical Issues

- **Three record directories on this machine were produced by tests, not sessions.** They carry
  plausible-looking records under names that came from a pytest fixture. They are why discovery is
  rejected in ADR-6, and they should be removed before the collection period begins so they cannot
  be counted.
- **Ownership matching is a substring check, not an anchored one.** `NAMESPACE`,
  `OUR_NAMESPACE` and (since spec-019 ruling (y)) `LEGACY_NAMESPACE` are all tested with `in`
  rather than against the `$HOME/` or `$CLAUDE_PROJECT_DIR/` prefix the real commands carry. A
  third party's path that happened to contain one of those literal strings -- most plausibly a
  vendored copy of this plugin -- would read as ours. Found by T4.1's code-quality gate while
  reviewing ruling (y), which had just replaced a far wider basename match (`endswith("log_skill.sh")`,
  which any script of that name satisfied and which would have deleted a third party's hook).
  Deliberately not changed there: anchoring it means touching the ownership predicate ADR-5 defines
  and phase 2 established, at the end of a task that had already grown five times, with no measured
  case reaching it. Note the most plausible shape reaching the substring match is a **true**
  positive, not a false one: a repository vendoring this plugin and hand-registering
  `<vendor>/plugins/tcs-helper/scripts/observability/log_skill.sh` is registering this plugin's own
  adapter in the legacy in-repo pattern, and migrating it to the `$HOME` bundle is the correct
  outcome -- the same migration this repository is having done to it. Anchoring would break that
  case. The genuinely false case needs a third party to reproduce the five-segment path AND one of
  our three exact script basenames AND the matching event name, with none of it being our code --
  a coincidence of a different order from the basename collision ruling (y) fixed, where one common
  filename sufficed. **Reopen if a target is found carrying that path under one of our event names
  where the file is NOT this plugin's adapter.**

- **Two of the three adapters lack the early switch check the third has.** Adding one looks like an
  obvious optimisation and is **refuted**: spec-018 measured both mechanisms it would rely on —
  hoisting the check made things worse, and shrinking the script was inside noise. Recorded here so
  the next reader does not re-propose it.

### Technical Debt

- The bundle is copied per environment, so a container target and the host each hold one. The drift
  check reports staleness but does not update automatically.
- `indent=2` on write reflows a differently formatted settings file (ADR-4).
- `install-hooks.sh` ships a `--settings <path>` override that nothing tests; this spec's own
  registration editor should have the equivalent and should test it, since it is the lever that
  keeps the suite off real files.

### Implementation Gotchas

- The lock must be released by a different process than acquired it, because the skill runs acquire
  and release as separate calls — `git-setup`'s lock handles this explicitly and the reason is not
  obvious from reading it.
- Exclude the command's own artifacts from its own conflict detection, or the first run reports
  itself as a pre-existing foreign install.
- `report.py` takes the data directory as `--data-dir`, not from the environment; pointing an
  environment variable at it silently reports on the wrong record.
- `selfcheck.sh` reports "cannot record" when run through Claude's Bash tool, because the sandbox
  denies writes under `~/.claude/plugins`. Run it with the sandbox disabled before believing it.

---

## Glossary

| Term | Definition |
|---|---|
| **Source** | One configured target in the locations config: a label, a repository root, and optionally a list of homes. One source is always one repository identity, even when its records live in several places |
| **Bundle** | The copy of the recorder's scripts installed at `$HOME/.claude/observability/`, with its version marker |
| **Namespace ownership** | Treating an entry as ours because its command points inside our path namespace (ADR-5) |
| **Union figure** | The one aggregate this design computes across sources: firing coverage |
| **Host shape / container shape** | The two record locations, distinguished only by what `$HOME` is |
