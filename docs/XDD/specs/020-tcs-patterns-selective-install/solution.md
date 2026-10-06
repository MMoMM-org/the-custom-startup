---
title: "tcs-patterns selective install"
status: draft
version: "1.0"
---

# Solution Design Document

## Validation Checklist

### CRITICAL GATES (Must Pass)

- [x] All required sections are complete
- [x] No clarification markers remain
- [x] Architecture pattern is clearly stated with rationale
- [x] All architecture decisions confirmed by user
- [x] Every interface has specification

### QUALITY CHECKS (Should Pass)

- [x] All context sources are listed with relevance ratings
- [x] Project commands are discovered from actual project files
- [x] Constraints → Strategy → Design → Implementation path is logical
- [x] Every component in the diagram has a directory mapping
- [x] Error handling covers all error types
- [x] Quality requirements are specific and measurable
- [x] Component names consistent across diagrams
- [x] A developer could implement from this design
- [x] Implementation examples use real field names, verified against the files they describe
- [x] Complex logic includes a traced walkthrough with example data

---

## Output Schema

### SDD Status Report

| Field | Value |
|-------|-------|
| specId | 020-tcs-patterns-selective-install |
| architecture.pattern | Catalogue-and-installer: the plugin ships templates plus a scanner, the repository holds the selection |
| architecture.keyComponents | Catalogue, Detector, Interview, Collision guard, Installer, Manifest store, Drift reporter, Catalogue reader, CI gate entry |
| architecture.externalIntegrations | none — no network, no services |
| validationPassed | 14 |
| validationPending | 0 |

### ADR Status

| ID | Decision | Status |
|----|----------|--------|
| ADR-1 | Installed patterns always carry a `tcs-` name prefix | CONFIRMED |
| ADR-2 | Detector and installer in Python; only the advisory segment in bash | CONFIRMED |
| ADR-3 | One `VERSION` file per pattern in the catalogue | CONFIRMED |
| ADR-4 | Content hash at install, unified diff on conflict | CONFIRMED |
| ADR-5 | An unrecognised stack gets no proposal and no default | CONFIRMED |
| ADR-6 | Manifest at `.claude/skills/.tcs-patterns-manifest` | CONFIRMED |
| ADR-7 | Obsidian rule stays duplicated, with a consistency test | CONFIRMED |
| ADR-8 | Install offers to commit and never commits | CONFIRMED |
| ADR-9 | The existing multi-bundle CI gate gains a per-pattern rule | CONFIRMED |
| ADR-10 | Cross-pattern references become co-recommendations from a derived map | CONFIRMED |

---

## Constraints

- **CON-1 Listing budget is external.** `skillListingBudgetFraction` defaults to 0.01 of the
  context window measured in characters — observed 8000 on a 200k-class model and 30000 in a
  1M-context session — and `skillListingMaxDescChars` caps each description at 1536. The design
  reduces pressure on that budget; it cannot raise it. No design element may assume a description
  arrives in full.
- **CON-2 Per-skill control exists only outside plugins.** `skillOverrides` is ignored when a
  skill's source is a plugin (the resolver returns `"on"` before consulting it). Any design that
  keeps patterns inside the plugin forfeits per-skill control. This is the load-bearing reason the
  patterns are copied into the repository rather than flagged in place.
- **CON-3 No name shadowing.** A repository skill and a plugin skill with the same name are both
  listed; measured as a 3-token difference against a free name, which is noise. The harness will
  not resolve a duplicate, so the design must prevent one.
- **CON-4 A skill registers under its frontmatter `name:`, not its directory.** Renaming a
  directory does not rename a skill. Any rename must edit the frontmatter.
- **CON-5 bash 3.2 for anything written in shell** — no associative arrays — and shellcheck-clean.
  macOS and Linux both: `stat -f` is a format string on BSD and means *filesystem* on GNU,
  `[[:<:]]` is BSD-only, `timeout` is absent on macOS. ADR-2 exists largely to keep new code out
  of this constraint's way.
- **CON-6 Version numbers in `plugin.json` are set by CI** (`scripts/ci/bump-and-push.sh`) and
  never by hand. The per-pattern versions of ADR-3 are a separate, maintainer-set namespace.
- **CON-7 Distribution must follow the established bundle-versioning pattern** (spec 012), which
  already has three instances in this repository. This is the fourth; it does not get a fourth
  mechanism.
- **CON-8 Real repository names and paths must never appear** in a specification document, commit
  message or test fixture. They belong only in the gitignored sources file.
- **CON-9 The patterns are 21 directories, 80 files, 848K.** Copying a selection is cheap; copying
  all of it into every repository would not be, which is a second reason selection matters.

## Implementation Context

**IMPORTANT**: Every source below was read during design. The three marked HIGH are the ones this
design copies rather than invents.

### Required Context Sources

#### Documentation Context

```yaml
- doc: docs/XDD/specs/020-tcs-patterns-selective-install/requirements.md
  relevance: HIGH
  why: "The 36 acceptance criteria this design must satisfy, and the business rules for the scan"

- doc: docs/XDD/specs/012-tcs-git-helpers-hook-runtime-contract/solution.md
  relevance: HIGH
  why: "Defines the bundle-versioning pattern (source of truth, mirrored marker, drift check, CI
        gate) that CON-7 requires this work to follow"

- doc: docs/about/principles.md
  relevance: MEDIUM
  why: "Line 167 states plugin skills do not support disable-model-invocation. Measured false this
        session. The correction belongs to this work even though the flag is not the chosen
        mechanism"

- doc: docs/about/skill-and-agent-design.md
  relevance: MEDIUM
  why: "Granularity rules for skills; the catalogue reader is one skill serving 21 bodies and has
        to be justified against them"
```

#### Code Context

```yaml
- file: plugins/tcs-git-helpers/skills/git-setup/lib/install_files.sh
  relevance: HIGH
  why: "The structural template for an installer: reads the plugin version from plugin.json,
        substitutes placeholders, writes the marker atomically via .tmp then mv, performs every
        write inside a subshell that exports a setup sentinel, and prints that it did not
        auto-commit"

- file: plugins/tcs-git-helpers/scripts/lib/drift_check.sh
  relevance: HIGH
  why: "Before T4.1, drift_check_hook_bundle <repo> <expected> [marker-filename] took an arbitrary
        marker name and returned OK / MISSING / DRIFT:<installed>, with the directory hardcoded to
        .githooks/ -- the only thing that needed generalizing. Corrected 2026-10-06: T4.1 did it;
        the function is now drift_check_bundle <repo> <ver> [<version_filename>] [<marker_dir>],
        and drift_check_hook_bundle is a wrapper pinning marker_dir to .githooks"

- file: plugins/tcs-git-helpers/scripts/ci/check-hook-bundle-version.sh
  relevance: HIGH
  why: "Already a table-driven multi-bundle gate (sources_dir|marker_file|glob), extended in
        spec-019 for exactly this kind of addition. ADR-9 adds a rule shape rather than a script"

- file: plugins/tcs-git-helpers/scripts/session-start-brief.sh
  relevance: HIGH
  why: "Section 8b (the hooks drift segment), 8c (the patterns segment) and 9 (composition) build
        the advisory. The patterns advisory is a sibling segment in the same composition, not a
        second mechanism. Sections are named, not numbered by line: line ranges went stale as 8c
        grew"

- file: plugins/tcs-helper/skills/observability-setup/SKILL.md
  relevance: MEDIUM
  why: "The closest precedent for a skill that installs a bundle into a target repository:
        <install|remove|status> verbs, abort-before-write discipline, and an explicit refusal when
        the target would be committable. Its stance is the opposite of ours and the contrast is
        instructive — it writes machine-local state, we write shared content"

- file: scripts/observability/report.py
  relevance: MEDIUM
  why: "Walks the real skill and agent tree and reports unreachable skill files. It is the
        instrument that verifies the relocation, and the only one that reads the working tree
        rather than the installed cache"

- file: plugins/tcs-patterns/skills/*/SKILL.md
  relevance: MEDIUM
  why: "The 21 bodies being relocated; three of them reference material outside their own
        directory and break on the move"
```

#### External APIs

None. The design performs no network access and integrates no service.

### Implementation Boundaries

**In scope**

- Relocating the 21 pattern directories inside the plugin, and the four outward references that
  relocation breaks.
- Two new skills in `tcs-patterns` (setup, catalogue reader) and the Python modules behind them.
- One new segment in the existing session-start advisory.
- One new rule shape in the existing CI gate.
- A fixture-based detection test suite.
- Correcting `docs/about/principles.md:167`.

**Out of scope** (from the PRD, restated so the boundary is testable)

- Raising or working around the listing budget for the other three large plugins.
- Any judgement on the 21 patterns' content: no merging, no pruning, no rewriting of bodies beyond
  the `name:` line and the three broken references.
- Changing any pattern's `user-invocable` setting.
- A graphical or non-interactive selection UI beyond the `--update` path.

### External Interfaces

The system's only boundaries are the filesystem and the Claude Code harness.

| Partner | Direction | Contract |
|---|---|---|
| Target repository filesystem | read | manifests, configuration files, directory shapes, file contents for the content greps |
| Target repository filesystem | write | `<repo>/.claude/skills/tcs-<name>/**` and `<repo>/.claude/skills/.tcs-patterns-manifest`, and nothing else |
| Claude Code skill discovery | indirect | installed patterns are discovered as repository skills at `<repo>/.claude/skills/<name>/SKILL.md`, exactly one level deep |
| Claude Code SessionStart hook | write (stdout) | one advisory segment appended to the existing composition |
| git | read | repository root resolution, and the diff range in CI |
| The user | interactive | at most three multiSelect questions, one confirmation of the selection, one offer to commit |

### Cross-Component Boundaries

Not applicable — single plugin, single repository, no team boundary.

### Project Commands

Discovered from the repository's own configuration rather than assumed:

```bash
# Tests — pytest.ini at the repo root, bats suites under plugins/*/tests/bats
python3 -m pytest -q                              # full suite (perf tests deselected by default)
python3 -m pytest -m perf                          # the perf-marked tests
bats plugins/tcs-helper/tests/bats                 # bats suite for tcs-helper
bats plugins/tcs-git-helpers/tests/bats            # bats suite for tcs-git-helpers

# Plugin validation and inspection
claude plugin validate plugins/tcs-patterns        # smoke test only; does not validate skill frontmatter
python3 scripts/observability/report.py            # walks the real skill/agent tree

# CI gates runnable locally
plugins/tcs-git-helpers/scripts/ci/check-hook-bundle-version.sh "origin/main..HEAD"
scripts/ci/check-docs-sync.sh
scripts/ci/check-changelog-version-sync.sh
```

## Solution Strategy

The plugin stops being a library of skills and becomes a **catalogue plus an installer**. Three
properties of the harness, all measured, force this shape:

1. A plugin skill is in every session's listing whether or not it applies (CON-1), and the
   consumer cannot turn one off individually (CON-2).
2. A repository skill is in the listing too — so it still auto-routes — but only in that
   repository, and it *does* honour per-skill control.
3. Nothing resolves a duplicate name for us (CON-3).

So: the 21 bodies move out of `skills/` into `templates/patterns/`, where the harness does not see
them; a setup skill decides which belong in a given repository and copies them into
`.claude/skills/`; and the copy is renamed on the way in so a duplicate cannot arise.

The decision procedure is deliberately asymmetric. Eight patterns follow from a *stack fact* and
are proposed with the file that proves them. Thirteen follow from an *architectural intent* that no
file states; for those, file signals decide only **whether the question is worth asking**, and three
gated questions settle them. A repository with no server framework and no tests is asked nothing.
This asymmetry is the design's core claim and the fixture suite exists to keep it honest.

Distribution follows spec 012's bundle-versioning pattern (CON-7) at a finer grain: per pattern
rather than per bundle, because a change to one pattern must not raise an advisory in repositories
that installed a different one.

## Building Block View

### Components

```
                         ┌───────────────────────────────────────┐
                         │  C1 Catalogue                         │
                         │  templates/patterns/<name>/           │
                         │    SKILL.md, reference/, VERSION      │
                         └───────┬───────────────────────┬───────┘
                                 │ reads                 │ reads
                                 ▼                       ▼
   target repo ──reads──▶ ┌──────────────┐        ┌──────────────────┐
                          │ C2 Detector  │        │ C8 Catalogue     │
                          │ detect.py    │        │    reader        │
                          └──────┬───────┘        │ skills/pattern/  │
                                 │ DetectionReport└──────────────────┘
                                 ▼
                          ┌──────────────┐
                          │ C3 Interview │  ≤3 gated multiSelect questions
                          │ SKILL.md     │
                          └──────┬───────┘
                                 │ Selection
                                 ▼
                          ┌──────────────┐  refuses on collision
                          │ C4 Collision │◀──reads── repo skills, user skills,
                          │    guard     │           ALL plugin skills (enabled or not)
                          └──────┬───────┘
                                 │ approved Selection
                                 ▼
                          ┌──────────────┐  writes ──▶ <repo>/.claude/skills/tcs-<name>/
                          │ C5 Installer │  writes ──▶ ┌──────────────────┐
                          │ install.py   │             │ C6 Manifest store│
                          └──────────────┘             │ .tcs-patterns-   │
                                                       │    manifest      │
                                                       └────────┬─────────┘
                                                                │ reads
                                                                ▼
                     ┌──────────────────┐   advisory   ┌──────────────────┐
                     │ C9 CI gate entry │              │ C7 Drift reporter│
                     │ (maintainer side)│              │ drift + brief    │
                     └──────────────────┘              └──────────────────┘
```

**Responsibility matrix** — every PRD Must feature traces to exactly one owning component:

| PRD feature | Owner | Note |
|---|---|---|
| F1 plugin stops shipping pattern skills | C1 | the relocation *is* C1 coming into existence |
| F2 scan and propose | C2 | evidence collection and the auto set |
| F3 ask only what the repo cannot answer | C3 | C2 supplies the gates, C3 owns the asking |
| F4 install the selection | C5 | |
| F5 refuse a duplicate name | C4 | separate from C5 so the refusal is testable without writing |
| F6 record what was installed | C6 | |
| F7 tell the user when a pattern moved on | C7 | |
| F8 update installed patterns | C5 | divergence data from C6; no new owner |
| F9 no shipping without a version change | C9 | |
| F10 consult without installing | C8 | |

No feature has two owners; no component is without a feature.

### Directory Map

```
plugins/tcs-patterns/
├── .claude-plugin/plugin.json          MODIFIED  2.0.0 (by CI, not by hand)
├── templates/patterns/                 NEW       C1 — the catalogue
│   ├── <name>/                         MOVED     21 dirs, git mv from skills/<name>/
│   │   ├── SKILL.md                    MOVED     `name: <name>` kept; installer rewrites it
│   │   ├── reference/ examples/ ...    MOVED     unchanged
│   │   └── VERSION                     NEW       single line, maintainer-set (ADR-3)
├── skills/
│   ├── patterns-setup/                 NEW       C3 — the interview and orchestration
│   │   ├── SKILL.md                    NEW       argument-hint: <install|update|remove|status> [path]
│   │   └── lib/
│   │       ├── cli.py                  NEW       C3's seam — the one entry point SKILL.md runs; JSON out (T5.1a)
│   │       ├── companions.py           NEW       companion map; + companion_citations() (T5.1a)
│   │       ├── detect.py               NEW       C2 — pure, fixture-callable; + `unreadable` (T5.1a)
│   │       ├── guard.py                NEW       C4 — namespace collision check
│   │       ├── install.py              NEW       C5 — copy, rename, hash, manifest; + remove() (T5.1a)
│   │       ├── manifest.py             NEW       C6 — read/write/compare; + drop(), without_pattern() (T5.1a)
│   │       ├── outcomes.py             NEW       the four-way outcome partition
│   │       ├── paths.py                NEW       leaf: plugin root, catalogue default, debris suffixes, SKILL.md hash (T5.1a)
│   │       └── status.py               NEW       read-only status(); drift_verdict(), catalogue_version() the reporter imports (T5.1a)
│   └── pattern/                        NEW       C8 — the catalogue reader
│       └── SKILL.md                    NEW       argument-hint: <pattern-name>
├── scripts/
│   ├── block-eslint-disable.sh         UNCHANGED stays in the plugin (ADR-7)
│   └── patterns_drift.py               NEW       C7 — manifest vs catalogue, OK/MISSING/DRIFT/UNKNOWN;
│                                                 imports drift_verdict, catalogue_version from lib/status.py (T5.1a)
└── README.md, CHANGELOG.md             MODIFIED  layout, the 2.0.0 entry, the kept promise

plugins/tcs-git-helpers/
├── scripts/lib/drift_check.sh          MODIFIED  directory becomes a parameter
├── scripts/lib/drift_check.py          MODIFIED  same change, same contract
├── scripts/session-start-brief.sh      MODIFIED  one new advisory segment (C7)
├── scripts/ci/check-hook-bundle-version.sh  MODIFIED  per-pattern rule (C9, ADR-9)
├── tests/bats/session-start-brief.bats MODIFIED  the advisory: drift, unknown, silence, layouts
├── tests/bats/drift-check-sh.bats      MODIFIED  marker_dir parameter and the wrapper's pin
└── tests/python/test_drift_check.py    MODIFIED  same parameter, parity with the bash twin

tests/
├── test_patterns_detect.py             NEW       parametrized over every fixture; MODIFIED by T5.1a for `unreadable`
├── test_patterns_detection_corpus.py   NEW       corpus integrity; green without a detector
├── patterns_detection_corpus_lib.py    NEW       shared fixture loading for the two above
├── test_patterns_install.py            NEW       rename, hash, manifest, idempotency
├── test_patterns_guard.py              NEW       three namespaces, the refusal partition, skips
├── test_patterns_drift.py              NEW       per-pattern drift, silence when current; unchanged by T5.1a
├── test_patterns_remove_status.py      NEW       remove()'s six rules and its order; status() vs the reporter (T5.1a)
├── test_patterns_cli.py                NEW       every verb as a subprocess: keys, exit codes, refusal order (T5.1a)
├── test_obsidian_rule_agreement.py     NEW       ADR-7's consistency test
├── test_tcs_patterns_companion_map.py  NEW       AC-18's seven edges; MODIFIED by T5.1a for companion_citations()
└── fixtures/patterns-detection/        NEW       synthetic repos, one per rule and trap
    └── <case>/
        ├── repo/                       NEW       the synthetic tree
        └── expected.json               NEW       expected auto set, gates, and evidence

conftest.py                             MODIFIED  collect_ignore_glob for fixture repo/ trees
docs/about/principles.md                MODIFIED  line 167 correction
docs/guides/tcs-patterns.md             MODIFIED  the guide the obsidian pattern cites
```

### Interface Specifications

No database and no HTTP surface. The interfaces are **six data models** and four process
contracts. Two of the six are not file formats and never reach disk: the **companion map**
is derived in memory from the catalogue on every `companion_map()` call, and the **outcome
partition** is a return value. Counted and corrected 2026-10-05 -- the sentence read "four
file formats" while five data models followed it, and the sixth was missing entirely. The fourth
process contract, *the CLI the skill drives*, was added 2026-10-06; the sentence said three until
then.

#### Data model: catalogue entry (C1)

One directory per pattern under `templates/patterns/`. Unchanged from today apart from two
additions:

| File | Required | Content |
|---|---|---|
| `SKILL.md` | yes | the body, frontmatter `name: <name>` (unprefixed — the installer rewrites it) |
| `VERSION` | yes | one line, a bare integer, maintainer-set. Not semver: a pattern body has no API, only "newer than what you have" |
| `reference/`, `examples/`, `templates/`, `checklists/` | no | copied verbatim with the pattern |

`VERSION` is an integer rather than semver on purpose. Semver invites a judgement about whether a
change is breaking, which for prose has no stable meaning, and the only question the drift reporter
asks is whether the numbers differ.

#### Data model: the manifest (C6)

`<repo>/.claude/skills/.tcs-patterns-manifest`, TOML — the format `observability-sources.toml` and
`startup.toml` already use in this repository, so it is reviewable in a pull request and parseable
with `tomllib`.

```toml
# Written by /tcs-patterns:patterns-setup. Reviewed and committed like any other file.
bundle = "2.0.0"            # the plugin version that produced this selection

[patterns.ddd]
version = "3"               # the catalogue VERSION at install time
installed_as = "tcs-ddd"    # the skill name actually written (ADR-1)
sha256 = "9f2b…"            # hash of the installed SKILL.md, for divergence detection (ADR-4)

[patterns.hexagonal]
version = "2"
installed_as = "tcs-hexagonal"
sha256 = "41ac…"
```

**The inline `#` comments in that example are annotation for the reader of this document, not
content the written file carries.** The header comment on the first line *is* content and is
written byte-for-byte; the per-field comments are not, and neither is the `"9f2b…"` ellipsis.
Stated 2026-10-05 after T3.1's spec-compliance review had to decide which it was and reasoned its
way to the right answer with nothing to cite — a second implementer could as easily have emitted
them and been equally defensible.

The hash covers the installed `SKILL.md` only, not the whole subtree. A reference file edited
locally is a weaker signal of intent than an edited body, and hashing 80 files to catch it is not
worth the cost. Stated here so the limit is deliberate rather than discovered.

**What C6 returns, and what an unparseable manifest does — settled 2026-10-05, before T3.1 was
dispatched.** The Error Handling table says an unparseable manifest is "treated as `MISSING` for
the advisory and reported verbatim by `status`", and T3.1's own test step says it "raises". Those
read as a contradiction and are not one, but the layering that reconciles them was unwritten, and
an implementer reading either sentence alone would have built the other half wrong:

```
read(repo_dir)   -> Manifest | raises ManifestUnparseableError
                    absent file -> an EMPTY manifest, not an error
write(manifest)  -> atomic: temp file in `.claude/skills/`, then os.replace
upsert(name, …)  -> returns a new Manifest; prior entries byte-identical
```

- **A missing manifest and a corrupt one must stay distinguishable at the reader**, because
  "never silently overwritten" is only enforceable if `write()` can never be handed a value
  derived from a file nobody could parse. If corrupt also returned empty, the two states would be
  indistinguishable and the first `install` into a repository with a damaged manifest would
  replace it with a record of that one install — erasing exactly what the row exists to protect.
- **`MISSING` is therefore C7's rendering, not C6's return.** The reporter (`patterns_drift.py`) and `status` catch
  `ManifestUnparseableError` and present it; the store itself refuses. Corrected 2026-10-06: this
  said "the advisory" catches it, but the bash advisory never sees the exception. The reporter
  catches it and prints `MISSING`, which the advisory then suppresses. Reading the row as the
  reader's contract is the mistake this paragraph exists to prevent.
- **The temp file goes in `.claude/skills/`, never `$TMPDIR`.** Different filesystems here —
  measured `dev=16777245` for the repository and `dev=16777234` for `$TMPDIR` — so `os.rename`
  across them raises `OSError: [Errno 18] Cross-device link` and `shutil.move` degrades to
  copy-then-delete, which is not atomic
  `[ref: SDD/Risks and Technical Debt/Implementation Gotchas]`.

  **And a second reason to insist on `os.replace`, measured 2026-10-05 and sharper than
  atomicity:** given an existing **directory** at the destination, `os.replace` raises
  `IsADirectoryError` while `shutil.move` does not raise at all — it moves the temp file
  *inside* the directory and deletes the source. So a `shutil.move`-based writer would
  silently relocate the manifest into a directory rather than failing, which is a worse
  outcome than a non-atomic write. Found as a side effect of T3.1's cleanup test, where the
  trigger for a mid-write failure is a pre-existing directory at the manifest path.
- **Currency is determinable from the manifest alone** — `version` per pattern against the
  catalogue `VERSION`, with no pattern file read `[ref: SDD/Acceptance Criteria/AC-17; PRD/F6
  3rd]`. That is what makes the `sha256` field's job divergence detection only, and not currency.

**Writing the TOML is hand-serialised, and that is forced rather than chosen — settled
2026-10-05.** `tomllib` is a *reader*: it has no `dumps` and no `dump` (measured), and neither
`tomli_w` nor `toml` is importable here. Nothing in this repository writes TOML today —
`scripts/observability/sources.py` only reads it — so C6 is the first writer and the question had
no precedent to inherit.

A third-party serialiser is not available to it. A plugin ships as files into whatever Python the
user's machine provides, with no install step, so a runtime import that is not stdlib is a
runtime failure on someone else's computer. Measured across every `.py` under `plugins/`: every
top-level runtime import is stdlib or a local sibling module, with no third-party package
anywhere (the two `pydantic` hits are inside `doc-product` **test fixtures** and are never
executed as plugin code). Vendoring a serialiser would work and is rejected as disproportionate
to a file with one scalar and three keys per table.

**The hazard this creates, and the guard for it.** Hand-serialising TOML means getting string
quoting right, and the honest way to bound that is to keep the value space narrow and **refuse**
what cannot be represented rather than escaping cleverly: pattern names come from the catalogue,
`installed_as` is a `tcs-`-prefixed pattern name, `version` is a catalogue `VERSION`, `sha256` is
a hex digest. A value outside those shapes is a bug upstream, not a quoting problem, so the writer
raises on it. The round-trip assertion T3.1 already requires is the standing guard: write, then
`tomllib.loads` the bytes back, then compare — which fails on a mis-quoted value without anyone
having to enumerate the escapes.

#### Data model: detection report (C2 → C3)

`detect.py` returns this and writes nothing. It is the whole contract between scanning and asking,
which is what makes the scanner testable in isolation.

```json
{
  "schema": 1,
  "repo": "<absolute path as given>",
  "auto": [
    {"pattern": "typescript-strict", "evidence": "tsconfig.json"},
    {"pattern": "mcp-server", "evidence": "packages/server/package.json: dependencies.@modelcontextprotocol/sdk"}
  ],
  "baseline": [
    {"pattern": "testing", "evidence": "pytest.ini", "surface": false}
  ],
  "gates": {"q1_backend": false, "q2_architecture": true, "q3_test_quality": true},
  "gate_evidence": {
    "q2_architecture": ["src/orders/events.py", "src/event_store/"],
    "q3_test_quality": ["pytest.ini"]
  },
  "manifests_walked": ["package.json", "packages/server/package.json"],
  "unrecognised_stack": false,
  "unreadable": []
}
```

Three fields carry design decisions rather than data:

- `baseline` with `surface: false` is trap 1 made structural. `testing` is detected and installed
  when chosen, but C3 must not present it as a recommendation, because it fires in nearly every
  repository with a test suite and therefore tells the user nothing.
- `gates` is a decision about *whether to ask*, never about what to install. No pattern is ever
  installed because a gate opened.
- `unrecognised_stack` is distinct from all gates being false (ADR-5). A repository can have an
  unrecognised language and still reach Q2 through a content signal. It is computed from `auto`
  **alone** — a `baseline` entry does not make a stack recognised, because `testing` is a stack
  fact with near-zero discriminating power and must not flip the headline state (ADR-5, *Which
  set the flag reads*).

**A ninth key, `unreadable`, specified 2026-10-06; T5.1a builds it.** The example above shows
the target state: until T5.1a lands, `detect.py` returns eight keys. The Error Handling row "Target
repository unreadable in part" required this report to name what the scan could not read, and the
report had no field for it, so `detect.py` silently skips what it cannot list or open. The key
will be a sorted array of root-relative paths, always present. Its definition, and why `schema`
stays `1`, are under *Process contract: the CLI the skill drives*, `scan`.

#### Detection rules: the eight stack facts and the three gates (C2)

Everything `detect.py` decides, stated as rules rather than as prose about rules. **This section was
added on 2026-10-03, after Phase 1**, because the signals were missing: `fastify`, `nestjs`, `hono`,
`gin`, `chi`, `celery`, `kafkajs`, `amqplib`, `enzyme` and `mark3labs` appeared nowhere in this spec
directory, and the only concrete signals present were the four in the trap table. The rules
themselves are not new -- they are the set validated against six repositories during this SDD's
research, which this document described in effect and never transcribed. T2.1 requires each fixture
to be built from the written rule; without this section there was no written rule to build from, and
T2.2's rules would have been written to satisfy whatever the fixture author guessed. That is the
circularity `[ref: PRD/Risks and Mitigations]` names as the top risk.

The partition was checked against the catalogue before being recorded: 8 + 6 + 5 + 2 = 21, no
pattern in two groups, no pattern in none, and every name a real directory under
`templates/patterns/`. That check is AC-6's "decided exactly once" invariant, and it is a test in
T2.5 rather than a claim here.

**The eight stack facts.** Decided from files alone, proposed with evidence, never asked about.

| Pattern | Fires when | Notes |
|---|---|---|
| `obsidian-plugin` | a `manifest.json` carrying `minAppVersion`, **or** an `obsidian` dependency | the manifest key matters; a bare `manifest.json` is not evidence |
| `mcp-server` | dependency `@modelcontextprotocol/sdk`, or `mcp`, or `github.com/mark3labs/mcp-go` | the three ecosystems' SDK names |
| `typescript-strict` | any `tsconfig.json` | presence only; the `strict` flag is not required to fire |
| `go-idiomatic` | a `go.mod` | |
| `python-project` | any `.py` file **and** one of `pyproject.toml`, `requirements.txt`, `setup.py` | trap 7: both `venv` and `.venv` are recognised wherever a virtual environment is tested for |
| `react-testing` | a `react` dependency **and** one of `@testing-library/react`, `react-test-renderer`, `enzyme` | `react` alone is not evidence |
| `frontend-testing` | DOM-render evidence in test files: `render(`, `screen.`, `fireEvent`, `userEvent`. **Test file** means `_is_test_filename`, i.e. `test_*.py`, `*_test.py`, `*_test.go`, `*.bats`, `*.test.{js,jsx,ts,tsx}`, `*.spec.{js,jsx,ts,tsx}` -- the same set the tests shape uses, so the search is **not** limited to JS/TS | trap 2: never a directory name, never jsdom alone. Consequence, measured 2026-10-05: `render(` inside a `test_*.py`, an `*_test.go` or a `*.bats` file fires this rule. Accepted -- the marker set is specific enough that a Go or shell test containing `screen.` or `fireEvent` is far likelier to be exercising a DOM than coincidence, and narrowing the set per ecosystem would make the rule and the tests shape diverge for no measured gain |
| `testing` | any non-UI test framework together with a tests shape — both defined under *What counts as a test framework* below | trap 1: `baseline` with `surface: false`, never surfaced as a recommendation |

**The three gates.** A gate decides only **whether to ask**. Nothing is installed because a gate
opened `[ref: SDD/Interface Specifications/Data model: detection report]`.

| Gate | Opens when | Settles |
|---|---|---|
| `q1_backend` | a server framework in **`dependencies`**, never `devDependencies` (trap 4): Node `express`, `fastify`, `koa`, `@nestjs/core`, `hono`; Python `fastapi`, `flask`, `django`, `aiohttp`; Go `gin`, `echo`, `chi` | `api-design`, `bff-entry-points`, `secure-oauth-oidc`, `observability`, `twelve-factor`, `node-service` (6) |
| `q2_architecture` | `q1_backend` opened, **or** any one weak content signal: all three of `ports/` + `adapters/` + `domain/` as directories; **two or more** `events.py` / `events.ts` in distinct module directories; one directory named `event_store` or `eventstore`; one broker dependency `kafkajs`, `amqplib`, `@aws-sdk/client-sqs`, `celery` | `ddd`, `event-driven`, `event-sourcing`, `hexagonal`, `functional` (5) |
| `q3_test_quality` | any test framework present — framework evidence only, no tests shape required, defined under *What counts as a test framework* below | `mutation-testing`, `test-design-reviewer` (2) |

**Which dependency sections a rule may read — settled 2026-10-03.** A **stack fact** reads both
`dependencies` and `devDependencies`: a repository with `react` or `@modelcontextprotocol/sdk`
declared as a development dependency is still a React repository, still an MCP server, and the
pattern still applies to it. A **gate** reads `dependencies` only — trap 4 — because `q1_backend`
asks whether this repository *runs a service*, and a server framework present solely to drive a
test harness does not make it one. The split is therefore about the question being asked, not
about the section being tidier. Stated because the table above gave the restriction only for
`q1_backend` and the permission only for `testing`'s Node row, leaving `mcp-server`,
`obsidian-plugin` and `react-testing` genuinely ambiguous; T2.2 read both for all three, which
is now the rule rather than an unreviewed choice.

**Which declaration counts as `dependencies` outside `package.json` — settled 2026-10-04.** The
paragraph above states the split in `package.json` vocabulary, and nothing anywhere in this
document mapped it onto the other three ecosystems. Found at T2.3's task-validation gate, before
dispatch, by asking which clause `trap-03` traces to: that fixture opens `q1_backend` on `fastapi`
in a `requirements.txt`, and no written rule permitted a gate to read that file at all. Searching
the spec directory for `optional-dependencies` and `install_requires` returned nothing, and
`indirect` appeared once, in an unrelated row about skill discovery. So three of the four
ecosystems' `q1_backend` path were unwritten, and an implementer would have had to read a fixture
to resolve them — the circularity `[ref: PRD/Risks and Mitigations]` names as the top risk.

**The rule: a gate reads every runtime-dependency declaration the detector already parses, and
excludes every declaration that is development-only or transitive.**

| Manifest | A gate reads | A gate does not read |
|---|---|---|
| `package.json` | `dependencies` | `devDependencies` |
| `pyproject.toml` | `[project] dependencies` and `[tool.poetry] dependencies`, **merged into one list** -- see the note below | `[project.optional-dependencies]`, `[tool.poetry.group.*.dependencies]` |
| `requirements.txt` | every requirement line | — (the format has no development section) |
| `setup.py` | `install_requires` | `extras_require` |
| `go.mod` | a direct `require` | a `require` marked `// indirect` |

**The two `pyproject.toml` sources are merged, and the evidence string does not distinguish
them.** `_pyproject_deps_and_pytest` returns one flat list of names, and every caller formats
its evidence with the literal key `dependencies`. Measured 2026-10-05: a `fastapi` declared
only under `[tool.poetry.dependencies]` opens `q1_backend` citing
`pyproject.toml: dependencies.fastapi`, byte-identical to what a `[project] dependencies`
declaration produces. So a reader following that evidence opens the file, looks for a
`[project] dependencies` array, and finds no such table. The merge is correct -- both are
runtime declarations and the rule below turns on nothing else -- so this is a reporting
limit, not a detection defect, and it is recorded rather than fixed because the evidence
string's job is to name the **file** that justified a signal, which it does. Added by the
Phase 2 drift check, which read the table above as promising two distinguishable sources.

The principle is the one already written above and is simply applied consistently: `q1_backend`
asks whether this repository *runs a service*. A development-only declaration does not make it
one, and neither does a transitive one — a CLI tool whose dependency happens to pull in `gin` does
not run an HTTP service, and `// indirect` is exactly how Go records that distinction. Two
consequences worth naming because they are easy to get wrong:

- **`requirements.txt` has no development section, so every line counts.** The absence of a
  `devDependencies` analogue is not a reason to exclude the file; it means the exclusion has
  nothing to bite on. A repository that pins its test-only tooling in a separate
  `requirements-dev.txt` is served correctly by this rule, because that file is a different file.
- **`_go_mod_requires` strips `//` comments and therefore reads an indirect require as direct**
  (measured 2026-10-04 in `detect.py`). That is harmless for the stack facts as they stand —
  `go-idiomatic` fires on the file's presence — but it would make `mcp-server` fire on a
  transitively pulled `mark3labs/mcp-go`, and under this rule it would open `q1_backend` on a
  transitive `gin`. The indirect marker must survive parsing for gate purposes.

**And which declaration counts as the development section outside `package.json` — settled
2026-10-05.** The table above maps the *gate* rule onto all four manifests. The stack-fact rule
one paragraph earlier — "a stack fact reads both `dependencies` and `devDependencies`" — was
never mapped onto anything but `package.json`, and that silence was not harmless: measured on
2026-10-05, `mcp` declared in `[tool.poetry.group.dev.dependencies]` did **not** fire
`mcp-server`, so the document promised a behaviour the code did not deliver. Found by the Phase 2
alignment check. Decided by Marcus the same day: widen the code, because recording a measured
false negative as intent is worse than leaving it or fixing it — the same reasoning that pulled
the hook fix into T2.6.

| Manifest | A stack fact additionally reads | Still excluded from both halves |
|---|---|---|
| `package.json` | `devDependencies` | — |
| `pyproject.toml` | `[tool.poetry.group.*.dependencies]`, any group name | `[project.optional-dependencies]` |
| `setup.py` | `extras_require` | — |
| `requirements.txt` | — (no development section to read) | — |
| `go.mod` | — (no development concept; `// indirect` is transitivity, not intent) | a `require` marked `// indirect` |

**Why `[project.optional-dependencies]` stays out while `extras_require` goes in**, given that
both are "extras" in packaging vocabulary. The question a stack fact asks is *what is this
repository*, and the two sections answer differently in practice. `[tool.poetry.group.*]` is
Poetry's actual `devDependencies` analogue — it is where a Poetry project puts the tooling its
authors develop with, and that is precisely the case the stack-fact rule was written for. PEP 621
`[project.optional-dependencies]` is the published extras of a *distribution*: `mcp` behind an
extra named `server` says this package can optionally speak MCP, not that this repository is an
MCP server. `setup.py`'s `extras_require` is the same field in older vocabulary and the same
argument would exclude it — it is included only because setuptools projects have no group
mechanism, so excluding it would leave `setup.py` with no development section at all while every
other Python manifest has one. That asymmetry is a judgement call, recorded as one.

**The implementation constraint this created, because it is the part most likely to be undone by
a later tidy-up.** `_pyproject_deps_and_pytest` and `_setup_py_deps` are called by the *gate* path
as well as the stack facts. Widening them in place would have opened `q1_backend` on a
development-only framework — trap 4, reintroduced, and invisible to the corpus as it stood,
because no fixture declared a server framework in a development section. Both readers therefore
return runtime and development declarations **separately**, mirroring `_node_deps`'s existing
`(deps, dev_deps)` pair, and the gate reads only the runtime half. `auto-mcp-server-poetry-dev-group`
carries both halves in one tree — `mcp` and `fastapi` in the *same* development group, so
`mcp-server` must fire while `q1_backend` must stay shut — and the gate-widening mutation was
confirmed to fail that fixture.

The development mapping also carries **the declaring section into the evidence string**:
`pyproject.toml: tool.poetry.group.dev.dependencies.mcp`, not `dependencies.mcp`. That is a direct
response to the merged runtime label recorded above as a reporting limit; reproducing the same
shape in new code written the same day would have been a known fault committed on purpose.

Three consequences the fixtures must assert rather than assume:

- **The triad's three directories need no common parent, and none of the four signals is
  depth-restricted — settled 2026-10-04.** The row says "all three of `ports/` + `adapters/` +
  `domain/` as directories" and says nothing about where. `trap-06` happens to place them as
  siblings under `src/`, so it passes under either reading and cannot settle the question — which
  means this is a genuine silence rather than something a fixture lookup would resolve. Ruled the
  loose way, by the asymmetry already argued below: a gate only decides whether to *ask*, so a
  false open costs one question while a false close denies patterns to exactly the repositories
  whose architecture is deliberate. A Go service with `internal/ports`, `internal/adapters` and
  `pkg/domain` has the shape the signal is looking for and must reach Q2. The same applies to the
  other three signals, consistent with the traced walkthrough, which finds `events.py` at
  `src/<feature>/` and the store at `src/event_store/` rather than at the root
  `[ref: SDD/Runtime View/Complex Logic]`. The exclusion list still applies at every depth:
  nothing inside `node_modules`, `.venv`, `venv`, `vendor`, `.git` or `.claude` is a signal.
- **Each weak signal's quantity is fixed, not left to taste.** `ports/` + `adapters/` +
  `domain/` needs all three; `event_store` and a broker dependency need one; the per-module
  events file needs **two or more in distinct module directories**. One `events.py` is a
  utility file, not a convention. The threshold is deliberately low rather than matched to
  the validated repository's ~15 feature directories, because a gate only decides whether to
  *ask*: a false open costs the user one extra question, while a false close denies patterns
  to exactly the repositories whose architecture is deliberate — the asymmetry ADR-5's
  rationale already argues. The `~15` in the traced walkthrough
  `[ref: SDD/Runtime View/Complex Logic]` describes what one real repository happened to
  have; it is not a minimum, and reading it as one would close the gate on most deliberate
  architectures.
- **`q2_architecture` can open while `q1_backend` is shut.** That is the whole point of the `or`
  (trap 6): event-driven and event-sourcing are routinely hand-rolled with no distinctive
  dependency, so a repository in an uncovered language with a ports/adapters shape must still reach
  Q2. `unrecognised_stack` is therefore not the same state as all gates closed `[ref: SDD/Architecture Decisions/ADR-5]`.
- **`secure-oauth-oidc` is settled by Q1 but defended by trap 3.** Opening Q1 does not propose it;
  and nothing may propose it on `jwt`, `bcrypt` or `pyjwt`, which are session and hashing tools, not
  a federated-identity protocol. Protocol evidence means an AS/client/RP library, or `.well-known`,
  or `redirect_uri` together with `client_id`.
- **`.git` and `.claude` were added on 2026-10-05, and the list was wrong without them.**
  Found at T2.6, by measuring `detect('.')` against this repository rather than against a
  fixture: it proposed `obsidian-plugin`, citing a `manifest.json` inside a vendored plugin
  cache at `claude-docker-home/.claude/plugins/cache/.../with-manifest-only/manifest.json`.
  That is trap 5's own family -- an embedded foreign tree read as this repository's signal --
  with two directories the rule never enumerated. At the time, the same omission also made the write-time
  Obsidian guard and this rule disagree, because that guard then walked the tree downward
  and pruned `.git` while this walk did not. **That half is now historical**: since the
  guard became file-scoped later the same day it walks only upward and carries no exclusion
  list at all, so there is no bash-side list to keep in sync with `SKIP_DIRS`. Corrected
  2026-10-05 — as first written the sentence implied one, and a reader adding a seventh
  segment would have gone looking for it `[ref: SDD/ADR-7, as amended]`.
- **Residual, accepted rather than closed: tracked test fixtures fire most of the detector.**
  This clause first read "still proposes `obsidian-plugin`", citing one foreign fixture. That
  understated it by most of the report, and was corrected on 2026-10-05 after the Phase 2 drift
  check ran `detect('.')` instead of reading the note. Measured on this repository:

  | | |
  |---|---|
  | `auto` | **7 of the 8 stack facts** -- `typescript-strict`, `go-idiomatic`, `python-project`, `mcp-server`, `obsidian-plugin`, `react-testing`, `frontend-testing` |
  | `baseline` | `testing` -- so all eight are accounted for |
  | `gates` | **all three open** |
  | `q1_backend` evidence | 3 of 3 entries from `tests/fixtures/patterns-detection/` |
  | `q2_architecture` evidence | 13 of 13 entries from `tests/fixtures/patterns-detection/` |
  | `manifests_walked` | 23, of which **19** are the corpus's own |

  So the dominant source is not another plugin's fixture; it is **the detection corpus this
  spec created**. A repository that contains a detector's own test data is the hardest possible
  input for that detector, and this one is it.

  **One consequence is worth naming on its own: the q2 triad assembles across unrelated
  subtrees.** `gate-q2-partial-triad` contributes `src/ports/` and `src/domain/` and
  `trap-06-hand-rolled-architecture` contributes `src/adapters/`, so q2 opens from three
  directories that belong to two different fixtures. That follows directly from the
  2026-10-04 ruling that the triad needs no common parent and no depth restriction, and it
  means a **threshold negative stops being negative at repository scope** --
  `gate-q2-partial-triad` exists precisely to assert that two of three must keep q2 shut, and
  at repo scope a sibling supplies the third. The same shape reaches a real monorepo: three
  unrelated services each owning one of the three directories opens q2.

  That is tolerable rather than wrong, and the reason is structural: **a gate decides only
  whether to ask.** Nothing is installed because a gate opened, so a triad assembled across
  siblings costs exactly one question the user answers "none" to. Were the triad ever promoted
  from a gate to a proposal, the no-common-parent ruling would have to be revisited with this
  measurement in front of it.

  Why the residual is not chased: no directory-name exclusion separates a committed fixture
  from a real manifest, and excluding test-shaped paths generally would break two rules to fix
  one -- `testing` and `frontend-testing` read test files deliberately. The design already
  answers it: every proposal carries the path that justified it and every proposal is
  declinable, so the user sees `.../tests/fixtures/...` and says no
  `[ref: SDD/Interface Specifications/Data model: detection report; PRD/F2 1st]`.
- **The walk excludes `node_modules`, `.venv`, `venv`, `vendor`, `.git` and `.claude`** (trap 5),
  and walks nested
  manifests so a workspace root declaring nothing still yields its children's signals. Every
  manifest the walk *discovers* is listed in `manifests_walked`, so a missing signal is
  explicable.
  The manifests walked are **`package.json`, `pyproject.toml` and `go.mod`**, at every depth
  outside the excluded directories -- not only at the root. Naming the set matters because the
  only walk shown in this document is `walk_manifests(root, "package.json")`
  `[ref: SDD/Implementation Examples]`, and a fixture author reading that alone would place a
  nested Python or Go signal at the root and never exercise trap 5 for those ecosystems.
  `manifest.json` is read for `obsidian-plugin` but is not a dependency manifest and does not
  contribute to `manifests_walked`.
- **`manifests_walked` lists every discovered instance of the five dependency-manifest
  filenames, not only the three the walk discovers by -- and `_manifests_walked` opens none
  of them.** Corrected 2026-10-05 by the Phase 2 drift check: this clause read "every
  dependency manifest whose contents **were read**", which the function has never done. It
  lists names by discovery and explains why in its own docstring -- a rule may
  short-circuit before reaching a later manifest (`_rule_mcp_server` returns on its first
  hit), so "was read" is not a property the field could report without a second,
  discarded read whose result nobody checks, which would add the one crash surface the
  module does not otherwise have. The field's purpose is unaffected: naming every
  discovered instance is what makes a missing signal explicable. **Worth noting how this
  defect arose** -- the sentence was itself the 2026-10-03 correction recorded below, and
  the correction is what went wrong, not the thing it corrected. A claim written beside a
  correction is the likeliest one in the paragraph to be false. `requirements.txt` and `setup.py` are read where present --
  `python-project` needs one of them, and `mcp-server` looks for `mcp` in them -- so both
  belong in the list. Settled on 2026-10-03 after T2.2 read the earlier wording the other way,
  which was a fair reading of "the manifests walked are" plus the `manifest.json` exception.
  The field's only purpose is making a missing signal explicable, and a `requirements.txt`
  that was read and held no `mcp` is indistinguishable from one that was never found unless it
  appears. `manifest.json` remains the exception because it carries no dependencies to
  explain -- it is Obsidian metadata the `obsidian-plugin` rule reads for one key.


**What counts as a test framework — decided 2026-10-03.** Two rules depend on this and neither
defined it: `testing` fires on "any non-UI test framework together with a tests shape", and
`q3_test_quality` opens on "any test framework present". The only concrete instance anywhere in this
spec was `pytest.ini`, in a single walkthrough. Evidence is **config or manifest**, enumerated per
ecosystem, never a directory name — trap 2's lesson generalises, and a `tests/` folder holding only
fixtures is not a test suite.

| Ecosystem | Framework evidence |
|---|---|
| Python | `pytest.ini`, `tox.ini`, a `[tool.pytest.ini_options]` table in `pyproject.toml`, or any `test_*.py` / `*_test.py` |
| Node | `jest`, `vitest`, `mocha`, `jasmine` or `ava` in `devDependencies` **or** `dependencies`, or a `jest.config.*` / `vitest.config.*` |
| Go | any `*_test.go` — Go tests declare no dependency, which is why dependency-only detection was rejected |
| Shell | any `*.bats` |

**Why Node is the only row that demands a declared runner.** Python, Go and Shell accept a
bare test file as framework evidence; Node does not, and that asymmetry is deliberate rather
than an oversight. A bare test file is evidence exactly where the language ships the runner
that executes it: `go test` is part of the Go toolchain, `unittest` is in the Python standard
library and `test_*.py` is the convention both it and pytest discover by. Node has no single
such convention — `*.test.js` is shared between jest, vitest, mocha and others and names none
of them — so a `*.test.js` file alone does not establish that any runner is present. Written
down because the asymmetry reads as an inconsistency at a glance, and "fixing" it by
accepting bare `*.test.js` would make `q3_test_quality` open on a repository that cannot run
its own tests.

**`frontend-testing` reading only test *files* also prevents a feedback loop, which nobody
designed against — do not relax it.** Measured 2026-10-05: five catalogue files quote the DOM-render
markers in prose — `frontend-testing/SKILL.md`, `frontend-testing/reference/testing-patterns.md`,
`react-testing/SKILL.md`, `react-testing/reference/react-patterns.md` and
`obsidian-plugin/reference/architectural-patterns.md`. C5 installs a pattern by copying its whole
directory into `<repo>/.claude/skills/<name>/`, so after an install those files are inside the
target repository. They are invisible to the rule only because it searches `files_matching(
_is_test_filename)` and a `.md` never matches that. If the rule were ever relaxed to "markers
anywhere", installing `frontend-testing` or `react-testing` would make the detector propose them on
the **next** run, from its own output — a pattern recommending itself. A repository built only from
installed patterns was measured both with and without `.claude` in `SKIP_DIRS` and proposes nothing
either way, so this is a constraint on future change rather than a live defect, and it is **not** an
additional justification for the `.claude` exclusion, which rests on the vendored plugin cache
alone. The catalogue also carries no manifest-named file, no `.py` and no test-named file, so no
other stack fact has the same exposure today.

Three distinctions the fixtures must preserve, because the two rules are deliberately asymmetric:

- **`q3_test_quality` needs framework evidence only.** Any row above opens it.
- **`testing` needs framework evidence AND a tests shape, and the framework must be non-UI.** The
  tests shape is a `tests/`, `test/`, `spec/` or `__tests__/` directory, or test files beside the
  code they cover. "Non-UI" excludes the react/frontend evidence of the two rows above it: a
  repository whose only testing is `@testing-library/react` with `render(` calls yields
  `react-testing` and `frontend-testing`, and does **not** additionally yield `testing`. Otherwise
  trap 1's near-universal signal would also be double-counted against trap 2's cases.
- A `go.mod` repository with `*_test.go` and no `tests/` directory **does** fire
  `testing`, and opens `q3`. Go convention places tests beside the code, which is exactly
  what the "test files beside the code they cover" clause is for; requiring a `tests/`
  directory would make `testing` unreachable for every idiomatic Go repository. Stated
  explicitly because the directory-only reading is the tempting one, and a fixture will
  fix whichever reading its author happens to hold.


#### Data model: the outcome partition (C2 → C3)

Added 2026-10-05. The partition was specified only as prose arithmetic in
`[ref: SDD/Runtime View/Complex Logic]` — `installed + declined-by-question +
excluded-by-stack-fact + not-reached = 21` — which names no module, no function and no
signature, so the one interface C3 consumes to build its outcome report had no contract while
every other interface here had one. Found by the Phase 2 alignment check.

```
decide(report, answers=None) -> Outcomes          # lib/outcomes.py, pure

Outcomes:  frozen, four frozensets, pairwise disjoint, union == the 21 catalogue names
  installed                # a stack fact fired, OR an open gate's question selected it
  declined_by_question     # an open gate's question did not select it
  excluded_by_stack_fact   # a stack fact that did not fire
  not_reached              # its gate stayed shut, so nobody was asked
```

- `report` is a detection report `[ref: SDD/Interface Specifications/Data model: detection
  report]`. `answers` maps an **open** gate's name to the patterns selected for it; each gate is
  multiSelect, so any subset including the empty one is valid.
- **A closed gate is never consulted**, even if `answers` carries a key for it: a shut gate
  produced no question, so there is nothing to have answered.
- **The function touches no filesystem and re-scans nothing.** It needs the 21 names and the
  gate-to-pattern mapping, neither of which the report carries, so the module holds that table
  as a hand-copy of the *Settles* column of the gate table above. A test pins it to a separate
  hand-typed literal and a second test ties its keys to the ones `detect()` actually emits —
  the second was added after a reviewer renamed one key and watched six patterns of an **open**
  gate land silently in `not_reached` while disjointness and the sum both held.
- **Raises `ValueError`** on a report it cannot partition honestly: when `auto` or `baseline`
  names a pattern outside the stack-fact set, and when an `auto`/`baseline` entry carries no
  `pattern` key. The first exists because silently dropping such a name yields four sets that
  still sum to 21 and look exactly like a clean partition — measured.

**What this interface cannot check, stated because two defects hid there.** Disjointness and
sum-to-21 see whether every name was assigned once; they see neither **provenance** nor whether
the assignment was **correct**. A name decided by both a file signal and a question, and a name
assigned to the wrong set, both leave the arithmetic intact. The two guards above exist for
exactly those blind spots `[ref: SDD/Acceptance Criteria/AC-6]`.

#### Data model: companion map (C1 → C2 → C3)

Nine pattern pairs cite each other's files, measured over the catalogue on 2026-10-03: 14
references in total, reduced to nine distinct (pattern, cited path) pairs.

**Three different counts, and the table below is the third — disambiguated 2026-10-04.** All
three numbers above and below are correct, and re-measured against the catalogue on 2026-10-04 to
confirm it: **14** raw cross-pattern references, **9** distinct (source pattern, cited *path*)
pairs, **7** distinct (source pattern, target *pattern*) edges, which is what the table rows sum
to. Nine collapses to seven because two sources each cite two different files inside one target.
Stated because T2.4 said "the derived map equals the nine measured pairs" three times while
listing the seven-edge table beneath it, so an implementer could assert either count and claim
compliance, and AC-18 inherited the same ambiguity. **The map is the 7 pattern-to-pattern edges**
— that is what C3 consumes, since a companion is a *pattern* to add to the proposal, not a path.
The 9 and the 14 are provenance for how the 7 was found, not assertions the test makes.

| Pattern | Cites a file living in |
|---|---|
| `ddd` | `hexagonal` |
| `event-driven` | `hexagonal`, `event-sourcing` |
| `event-sourcing` | `event-driven`, `hexagonal` |
| `hexagonal` | `ddd` |
| `observability` | `hexagonal` |

`ddd`/`hexagonal` and `event-driven`/`event-sourcing` are mutual, so the relation is a cycle and
must not be treated as a dependency tree.

This matters because C5 copies **one** pattern directory `[ref: SDD/Runtime View]`. Install `ddd`
alone and `ddd/reference/testing-by-layer.md`'s citation of `reference/testing-hex-arch.md` — which
lives in `hexagonal/` — resolves to nothing in the consumer repository. Q2 is multiSelect, so that
selection is reachable, not hypothetical. Before this spec the defect was invisible: shipping all
21 made every citation resolve.

**Derived, not hardcoded.** The map is computed from the catalogue by a resolution rule of its own,
sharing the link test's extraction plumbing but not its rule: **a code-span path that does *not*
resolve under its own pattern root, yet does resolve under exactly one other pattern's root, is a
companion edge.** A test asserts the derived map equals the seven edges above, so adding a
cross-pattern reference to a new target either updates the map or fails the suite. A hardcoded
table would silently go stale the first time a pattern's references changed.

Two things were wrong with that sentence and both are corrected above.

**The rule itself was garbled** — it read "resolves under no pattern root but its own, yet does
resolve under another pattern's root", whose two halves contradict each other: the first says its
own root is the only match, the second says another root matches too. Read literally it declares
an own-plus-other match a companion edge, which is the **opposite** of what the own-root
precedence requires and of what the implementation does. Found 2026-10-04 by T2.4's
spec-compliance review, in the one sentence a future reader would go to in order to learn the
rule. It survived two same-day rewrites of this paragraph because both were aimed at the
attribution clause in front of it.

**And the attribution was wrong**, reading "by the same resolution rule the link test uses" until
2026-10-04. It is contradicted two paragraphs below, under *How the citations are actually
written*: the link test's rule keys on `../` climbs, companion citations never climb, and a
derivation built on that rule finds **zero** edges. This paragraph previously called itself the
"fourth and last" place that attribution survived, which was also false — a sixth was found
afterwards in ADR-10's own *Decision* paragraph, by a reviewer rather than by my sweep, because
the sentence wrapped across a line break and a line-wise `grep` cannot match it.

**How the citations are actually written, and why the path rule is the right one — measured
2026-10-04.** The real shape is not a `../` climb, which is what the link test's own rule keys on,
and a derivation written for that shape finds **nothing**:

```
ddd/reference/testing-by-layer.md:3
  … see `tcs-patterns:hexagonal` `reference/testing-hex-arch.md`.
```

The path is relative to the **target** pattern's root, not to the citing file, and a
`tcs-patterns:<name>` marker names the target beside it. So two derivations are available, and
they describe different relations:

| Derivation | Edges | What it means |
|---|---|---|
| the path rule, above | **7** | the citation would **dangle** if this pattern were installed alone |
| the `tcs-patterns:<name>` marker | **43** | this pattern **mentions** that pattern |

The path rule is correct for this map's purpose, and the measurement is what makes that an
argument rather than an assumption: the map exists because C5 copies one directory, so the thing
worth repairing is a path that resolves to nothing in the consumer repository. A marker with no
accompanying path is prose — "see also `tcs-patterns:testing`" — and nothing breaks when it is
absent. 43 is "mentions"; 7 is "breaks". An implementation keyed on the marker would add up to six
companions to a single-pattern selection and justify none of them.

Two consequences for T2.4: resolve each candidate path against **every** pattern root rather than
against the citing file's directory, and treat a path that resolves under **more than one** other
pattern as ambiguous rather than picking one. Zero are ambiguous today — measured — which is worth
asserting so the day one appears is the day the suite says so.

**The citing pattern's own root wins, always — recorded 2026-10-04 after T2.4's implementer hit
it.** A path that resolves under the citing pattern's own root is never a companion edge
**regardless of what else it also matches**, and that precedence is load-bearing rather than
pedantic: `reference/node-patterns.md` exists under **both** `node-service` and `observability`,
different content at the same relative path. Without own-root-first, `node-service`'s reference to
its own file reads as an edge to `observability`. Measured: a naive "exclude own, single other is
an edge" reading yields **12** edges instead of 7. The rule follows from reading "resolves under
no pattern root but its own" strictly, and it is written down here because the *collision* that
makes it matter is a fact about this catalogue that no amount of careful reading would predict.

**Cross-checked against the authors' intent, which is the one thing that could have falsified the
precedence.** If a citation the own-root rule excludes actually meant another pattern's copy, the
rule would be hiding a real edge. The catalogue records intent beside the path, in the
`tcs-patterns:<name>` marker, so the two can be compared — and they agree completely: all **14**
resolving citations carry a marker, every marker names the pattern the path resolved to, nothing
is hidden by the precedence, and nothing is mistargeted. This also confirms from the other
direction why the path rule is the right derivation and the marker is not: the gap between 7 edges
and 43 markers is entirely markers with **no resolving path** — prose cross-references, where
nothing breaks when the pattern is installed alone.

**Expansion is the transitive closure, not one level — settled 2026-10-04 (Marcus).** The document
said "adds its companions" and never fixed the depth, and the difference is observable on three of
the five sources, all of them gaining `ddd`:

| Selected | Direct companions | Transitive closure |
|---|---|---|
| `ddd` | `hexagonal` | `hexagonal` |
| `hexagonal` | `ddd` | `ddd` |
| `observability` | `hexagonal` | `hexagonal`, **`ddd`** |
| `event-driven` | `event-sourcing`, `hexagonal` | + **`ddd`** |
| `event-sourcing` | `event-driven`, `hexagonal` | + **`ddd`** |

One level does not achieve what this map is for. Install `observability` and accept `hexagonal`,
and `hexagonal`'s own citation of a file under `ddd/` then dangles — the same defect one step
further out. The closure is what makes "no citation resolves to nothing" reachable at all.
Measured blast radius: at most **three** companions for any one selection, so four patterns from
one choice, which is why the cheaper rule was not worth its residual defect.

Two consequences. The traversal **must** carry a visited set: `ddd`↔`hexagonal` and
`event-driven`↔`event-sourcing` are mutual, so an unguarded depth-first walk from any of the four
never terminates — this is the hazard T2.4's cycle criterion names, and it is only a real hazard
once a traversal exists, which is to say once the closure is the rule. And the closure **informs
rather than guarantees**: a user who accepts `hexagonal` and declines `ddd` still ships a dangling
citation. The map's job is to make that visible and declinable, not to prevent it — ADR-8 already
settles that nothing is installed without acceptance.

**Three things are exposed for C3, not two** — the seven-edge map, the closure function, and the
list of ambiguous citations. The third was called out as possible over-building by T2.4's review
and judged in scope by it, correctly: an ambiguous candidate is simply *absent* from the map,
indistinguishable from "no citation existed", so the requirement that a future ambiguity be
**audible** cannot be met by the map alone. Zero are ambiguous today, which is exactly why the
reporting path needs to exist before one appears.

**Consumed as a proposal, never as a rule.** When the interview settles on a pattern, C3 adds its
companions to the proposal with the reason stated — "`ddd`'s testing reference lives in
`hexagonal`" — and the user may still decline. Companions join the proposal **before** the outcome
partition is computed, so the four sets stay disjoint and still sum to 21; a companion is
installed because the user accepted it, not because the map said so.

#### Data model: fixture expectation (test suite)

`tests/fixtures/patterns-detection/<case>/expected.json` sits beside a synthetic `repo/` tree and
declares the full expected verdict. The test asserts equality of the normalised report, so an
unexpected extra proposal fails just as loudly as a missing one.

```json
{
  "why": "trap 3 — session auth must not be read as federated identity",
  "auto": ["python-project"],
  "baseline": ["testing"],
  "gates": {"q1_backend": true, "q2_architecture": true, "q3_test_quality": true},
  "must_not_propose": ["secure-oauth-oidc"],
  "unrecognised_stack": false
}
```

`must_not_propose` is redundant against `auto` and deliberately so: it names the trap in the
fixture, so a future reader sees what the case is defending and a careless widening of `auto` fails
with a message that explains itself.

**`surface` is an invariant, not fixture data — and must be asserted as one.** `baseline` here is a
list of bare pattern names, while the report's `baseline` carries objects with a `surface` field.
That field exists only to mark a baseline entry as never-surfaced, is `false` for every baseline
entry by definition, and has no counterpart on `auto` entries — so it is not per-case data and
adding a `surface` key here would be wrong (it would also break the exact-key guard this contract
is checked by). It must instead be asserted **universally** in the detection test: every entry in
the report's `baseline` has `surface is False`.

Without that assertion trap 1 cannot fail if it is reintroduced. A detector emitting
`{"pattern": "testing", "surface": true}` satisfies every one of the 18 fixtures, because the
comparison reads `entry["pattern"]` and nothing else — while `testing` would then be surfaced to
the user as a recommendation, which is exactly the trap. That would violate
`[ref: SDD/Quality Requirements]`'s own row, "all seven traps have a fixture that fails if the
trap is reintroduced". Found by the T2.1 spec-compliance review on 2026-10-03: the trap-1 fixture
says "must report as baseline with surface:false" in its `why` and had no means to check it.

**`evidence` is the same shape of problem, and the same shape of answer.** Every `auto` and
`baseline` entry in the report carries `evidence` naming the file or dependency that justified
it `[ref: PRD/F2 1st]`, and it is T2.2's first success criterion — but `expected.json` has no
`evidence` key either, and the detection test does not compare one, so a detector emitting
`evidence: ""` satisfies **every fixture in the corpus** while failing the criterion outright.
Declaring exact paths per fixture would be the wrong fix: it adds a key the exact-key guard
rejects, and it pins every fixture to incidental path strings. (This paragraph carried two
different fixture counts two sentences apart — "all 18" and "all 26" — against a corpus that is
now 27. The count is incidental to the argument, which is why it went stale twice; it is stated
generically now rather than given a third number that will also expire.)

Assert it as three universal invariants instead, in the detection test:

1. every `auto` and `baseline` entry has a non-empty `evidence` string;
2. its path part — everything before the first `": "`, since dependency evidence is formatted
   `"packages/server/package.json: dependencies.foo"` — resolves to a file that **exists**
   inside that fixture's `repo/`;
3. that path is **not** under `node_modules`, `.venv`, `venv`, `vendor`, `.git` or `.claude`.

The third invariant is the one with teeth: it fails any detector that reads a vendored tree and
cites it, which is trap 5 reintroduced, and it does so for every fixture rather than only the
two that plant decoys there. None of the three needs per-case data, so the fixture contract is
unchanged.

**`gate_evidence` is the fourth field of this kind, and takes the same treatment.** The report
carries `gate_evidence` naming what opened each gate; `expected.json` has no such key and the
detection test compares none, so T2.3 could emit `{}` for every fixture and satisfy all 18
while leaving every gate unjustified. Caught at T2.3's task-validation gate on 2026-10-04,
before the task was dispatched, by asking what the corpus can prove rather than what the task
claims. Assert it as two invariants:

1. **every gate reported open has a non-empty `gate_evidence` entry**, and each path it cites
   resolves inside that fixture's `repo/` and has no segment in `node_modules`, `.venv`,
   `venv`, `vendor`, `.git` or `.claude` -- the list is duplicated in
   `tests/test_patterns_detect.py` as `EXCLUDED_SEGMENTS` rather than derived from
   `SKIP_DIRS`, deliberately: a derived copy would agree by construction, so a future
   **narrowing** of `SKIP_DIRS` would narrow this invariant along with it and never be
   caught. A separate test asserts the two are equal, which catches the opposite
   direction -- `SKIP_DIRS` widened and the invariant left behind, which is what happened
   on 2026-10-05 when `.git` and `.claude` were added;
2. **every gate reported closed has no entry**, so a gate cannot carry evidence it did not act
   on.

Together these make "no gate opens without a signal from its own rule" a mechanical check
rather than a reading. They need no per-case data: which gates are open is already declared in
each `expected.json`, and the invariants key off that.

**What a `gate_evidence` entry looks like when the signal is a dependency — settled 2026-10-04.**
The example report above shows only path-shaped entries (`"pytest.ini"`, `"src/event_store/"`),
because the one gate it opens on a dependency is not shown. `q1_backend` opens on a dependency in
every case, so its entries take the **same form the `evidence` field already uses** for a
dependency-sourced stack fact: `"<manifest path>: <section>.<name>"`, as in
`"go.mod: require.github.com/gin-gonic/gin"` or
`"packages/api/package.json: dependencies.express"`. Two reasons it has to be this form rather
than the bare manifest path:

- It reuses the resolution rule already in the suite rather than adding a second one. The
  existing `evidence` invariants take the part before the first `": "` and resolve that as a
  path, so the dependency form costs T2.3's two `gate_evidence` invariants nothing: a bare
  `"go.mod"` would satisfy them as well, and say nothing about which require opened the gate.
- It is the only way the corpus can discriminate the `// indirect` rule. `gate-q1-go-direct-require`
  declares both a direct `gin` and an indirect `chi`; both are server frameworks in the same file,
  so the `gates` dict cannot tell a detector that credited the right one from a detector that
  credited either. The named dependency can: q1's evidence must name `gin` and must not name
  `chi`. Without this form, the ruling above would be unenforceable by any fixture.

**What `q2_architecture`'s evidence is when it opens purely through the `q1_backend` disjunct —
settled 2026-10-04.** The row makes q2 open on "`q1_backend` opened, **or** any one weak content
signal", and the invariant demands non-empty evidence for every open gate, but nothing said what
that evidence is when no content signal exists at all. `trap-03` and both q1 fixtures are in
exactly that state. **q2 carries q1's evidence list.** It is the only reading that keeps the
invariant satisfiable without fabricating a content signal the repository does not have, and it
is honest: what opened q2 there really was q1, and the report should say so rather than cite a
`ports/` directory nobody found. Raised by T2.3's implementer as a genuine silence rather than
quietly resolved, which is the behaviour the task asked for.

**And when both are present, q2 lists both.** This clause covered only the pure-disjunct case when
it was written, and a review then found the implementation already doing the broader thing: q1's
evidence is folded in whenever it is non-empty, union'd with whatever content signals fired. That
is correct and follows from the completeness rule below rather than needing one of its own — both
really did contribute, so both are cited. Worth stating because the combined case is
**unreachable through the corpus by construction**: `gates` carries booleans, so no fixture can
distinguish "q2 opened" from "q2 opened for two reasons", and the exact-key guard forbids any
`expected.json` from declaring `gate_evidence`. Every corpus case that opens q2 does so for
exactly one reason. It is pinned instead by a direct test against a constructed tree carrying both
an `express` dependency and an `event_store/` directory; mutating away either half of the union
fails exactly that test and nothing else.

**Where completeness binds, and where one signal is a complete explanation — settled
2026-10-04.** The clause below was written generally, and a code-quality review then found
`q3_test_quality` not honouring it: all four ecosystems are consulted, but each per-ecosystem
helper returns on its first match, so a repository with `pytest.ini` beside a `tox.ini` cites only
`pytest.ini`. Measured across all four ecosystems rather than inferred from one.

The narrower behaviour is right, and the general wording was too broad. **Completeness binds where
an entry's contents are the only observable that can discriminate a rule.** There are exactly
three such places, and in each one a first-match entry would let a wrong implementation pass:

| Where | Mechanism | What the contents have to discriminate |
|---|---|---|
| `q1_backend`, every ecosystem | **exclusion** | a runtime declaration from one excluded as development-only or transitive. Whenever an excluded framework sits beside a runtime one, the gate opens either way and only the contents say which was credited. Go's `// indirect` split is one instance of this, not a separate case |
| `q2_architecture`, the triad | **count truncation** | two `ports/` directories are two contributing signals; citing one under-reports a count rather than admitting something excluded |
| `q2_architecture`, the union | **disjunction collapse** | q1 and a content signal both contributing, where reporting either alone loses the fact that both did |

**Three mechanisms, not three instances of one** — named that way on a reviewer's observation,
and the distinction is what makes the rule checkable. The unifying test is the middle column's
consequence: a wrong implementation produces the *same* `gates` boolean as a correct one, so the
boolean cannot grip it and the contents are the only hold a test has. Listing mechanisms rather
than instances is what the first version of this table got wrong: it named only Go's `// indirect`
split, and the q1 row above was found an hour later by someone looking for more instances of
*exclusion* — when the thing to look for is a fourth mechanism.

The first row was **not** in this table when it was written an hour earlier — it named only
Go's `// indirect` split. Found by probing the scoped rule for a place it had missed, which is
the check a scoping needs if it is not to be a convenience: the mixed case (`express` in
`devDependencies` beside `fastapi` in `dependencies`) opens q1 under both a correct and an
incorrect detector, so `gate-q1-node-runtime-dependency` and the paired dependency-source test,
which assert only the boolean, are both satisfied by a detector that credits the development
dependency. Measured: the implementation is correct in every case probed, and q1's evidence is
genuinely complete — two runtime frameworks in one `package.json` cite both — but nothing asserted
either property until `test_q1_evidence_omits_an_excluded_declaration_while_the_gate_still_opens`
and `test_q1_evidence_lists_every_runtime_framework_not_only_the_first`.

`q3_test_quality` has no such rule. Nothing is excluded from its evidence, so there is no wrong
match for the contents to rule out, and a second Python config does not change the answer to "is
there a test framework here". Its evidence exists to tell the user why they are being asked, and
one config file says that completely. Recorded as a scoped rule with its reason rather than left
as a general claim the code quietly fails, because narrowing a rule to fit the code is precisely
the move this phase has caught nine times.

**Within those three places, a `gate_evidence` entry lists EVERY signal that contributed to that
gate, not the first one found.** This is not a new shape — the example report above already gives `q2_architecture`
two entries — but it has to be stated, because the `// indirect` discrimination collapses
without it. Written and then checked on 2026-10-04: a detector that strips `//` comments (which
`_go_mod_requires` does today), credits both requires, and reports whichever it matched first
would name `gin`, because `gin` precedes `chi` both in the file and in sort order. It would
therefore satisfy "names the direct module, not the indirect one" while implementing the rule
wrongly, and reordering the fixture only moves the luck around — a detector that sorts what it
finds is unaffected by file order. Requiring the complete set removes the luck: crediting `chi`
puts it in the list, and the assertion fails on its presence rather than on which entry happened
to come first. The completeness requirement is what carries the check; the dependency form only
makes the contents legible.

**`repo` and `schema` complete the sweep.** Having found four of these one at a time, the
remaining report fields were checked mechanically on 2026-10-04 — every key `detect.py` emits,
against every `report[...]` the detection test reads — and two more were unasserted:

- **`schema`** must equal `1`. This is the field a consumer would read to refuse an
  incompatible report, so letting it drift silently makes the only versioning handle in the
  contract worthless. Asserting it also means a future `schema: 2` cannot ship without the
  change being deliberate.
- **`repo`** must equal the path `detect()` was given. Low stakes on its own, free to check,
  and it is the field every error message and every piece of evidence is relative to.

Neither is interesting in itself. They are listed because the sweep is the point: four fields
were found one at a time, in review or at a task gate, and the fifth and sixth took one
command. **When a contract gains a field, it gains an assertion in the same change, or the
field is decoration.**

The trap numbers used in `why` are defined in **The seven traps, numbered** under Quality
Requirements. Use those numbers; do not renumber them.

#### Process contract: drift reporter (C7)

`patterns_drift.py <repo> [--catalogue <dir>]` prints zero or more lines and exits 0 regardless —
the caller decides what to do, exactly as `drift_check_hook_bundle` does today.

```
OK                              # manifest present, every installed pattern current
MISSING                         # no manifest — the repository never ran the setup
DRIFT:ddd:3:4                   # installed pattern BEHIND: installed version, catalogue version
DRIFT:hexagonal:2:5             # one line per drifted pattern
UNKNOWN:obsidian-plugin:2       # installed pattern, installed version; the catalogue cannot account for it
```

`UNKNOWN` covers three cases, which share one property: the catalogue cannot account for what is
installed. The catalogue `VERSION` is absent or non-numeric; the pattern's catalogue directory is
gone, because it was deleted upstream; or the installed version is **ahead** of the catalogue's, as
after a plugin rollback. Versions are compared as integers, so `01` against `1` is current.

`MISSING` is reported, not acted on: F7's fourth criterion requires that a repository without
patterns is *not* nagged, so the advisory suppresses `MISSING` entirely and only the `status` verb
surfaces it. An unparseable manifest also prints `MISSING` here (Error Handling, "Manifest present
but unparseable"); telling the two apart is `status`'s job, not this contract's.

`UNKNOWN` added 2026-10-06 by Marcus, during T4.2. The Error Handling table already required C7
to report a pattern with no usable catalogue `VERSION` "as unknown rather than drifted", but this
contract had no line for it. `OK` means every installed pattern is current, so any `UNKNOWN` or
`DRIFT` line suppresses it. Drift is computed from each pattern's own manifest `version`, never from
the manifest's top-level `bundle` (decision 9 of the update path).

**Behaviour the code has that this contract did not say, added 2026-10-06 at the Phase 4 drift
check.**

- **`--catalogue <dir>` is a test seam.** It substitutes the catalogue directory; the default
  resolves from the script's own location (`<plugin>/templates/patterns`), so any cwd works.
- **Lines are sorted by pattern name.** `OK` is printed only when no `DRIFT` or `UNKNOWN` line was.
- **A repository path that does not exist prints `MISSING`**, because `MISSING` keys on the
  manifest file's absence.
- **A manifest that exists but cannot be read (`OSError`, for example permissions) is not
  `MISSING`.** `manifest.read` lets the `OSError` through, the reporter catches only
  `ManifestUnparseableError`, and `main()`'s catch-all prints `patterns_drift: <error>` to stderr,
  writes nothing to stdout and exits 0. Measured 2026-10-06 with a mode-000 manifest. The advisory
  therefore shows nothing, which is the fail-open outcome, though `status` is the verb that names
  the problem.
- **The advisory composes the reporter's lines in a fixed order.** The drift segment comes first,
  `patterns <p> v<i> → v<c>, …; run /tcs-patterns:patterns-setup update`, then the unknown
  segment, `patterns <p> v<i>, … not in the catalogue; run /tcs-patterns:patterns-setup status`.
  `MISSING` and `OK` are silent. A line that does not match its shape exactly is dropped, and
  lines are parsed under `LC_ALL=C` in a subshell.

**Revised 2026-10-06 by Marcus, at the Phase 4 drift check.** Two corrections, both found by the
validation that closes the phase.

- **"Drifted" now means behind, not different.** The reporter compared versions for string
  equality, so an installed version newer than the catalogue printed `DRIFT:ddd:3:2`, and the
  advisory turned that into "ddd v3 → v2; run … update", which is advice to downgrade. F7 and
  AC-11 both say *behind*. Ahead is now `UNKNOWN`. The comparison lives in the reporter;
  `manifest.is_current` stays string equality, because `update()` also calls it, and how
  `update()` treats a rollback belongs to F8, not this contract. **To be moved by T5.1a**
  (specified 2026-10-06; not built yet) into `lib/status.py` as `drift_verdict` and
  `catalogue_version`, which the reporter will import, so that `status` reuses the rule rather
  than restating it. Today the reporter still holds `_catalogue_version` and an inline comparison
  in `drift_lines`. Its stdout must not change, and `is_current` stays untouched.
- **The advisory surfaces `UNKNOWN`.** It used to stay silent, on the grounds that C9 fails a
  pattern without a `VERSION`. C9 catches a missing `VERSION`, but not a deleted pattern ("a
  deleted one raises nothing"), so a user who kept a pattern removed upstream was never told.
  Because C9 stops `VERSION` defects from shipping, an `UNKNOWN` seen in a consumer repository
  almost always means deleted upstream or ahead, which are both things the user should hear about.
  The advisory names the pattern and the read-only verb:
  `patterns ddd v3 not in the catalogue; run /tcs-patterns:patterns-setup status`.

#### Process contract: the generalized drift check

`drift_check.sh` and `drift_check.py` gain a directory parameter, keeping the existing contract.
The Python twins are `check_bundle` (generalized) and `check_hook_bundle` (the wrapper).

```
drift_check_bundle <repo_path> <expected_version> [<version_filename>] [<marker_dir>]
  version_filename default: tcs-git-helpers-version
  marker_dir       default: .githooks        <-- new, was hardcoded
  stdout           OK | MISSING | DRIFT:<installed>
  exit             always 0
```

The existing name `drift_check_hook_bundle` stays as a thin wrapper so no current caller changes.

Corrected 2026-10-06: this contract named the third parameter `marker_filename`; the code calls it
`version_filename`, kept deliberately because it is `check_hook_bundle`'s pre-existing keyword and
renaming it would change a current caller's call site.

#### Process contract: the skills

```
/tcs-patterns:patterns-setup <install|update|remove|status> [path]
  install   scan, ask at most three questions, propose, guard, write, offer to commit
  update    refresh drifted patterns only — no scan, no questions (F8)
  remove    delete a pattern and its manifest entry
  status    report what is installed, at which version, and what has drifted

/tcs-patterns:pattern <pattern-name>
  prints the named pattern's body from the catalogue; writes nothing.
  An unknown name lists the available 21 rather than returning empty (F10 2nd).
```

#### Process contract: the CLI the skill drives (C3's seam)

Added 2026-10-06 by Marcus, before T5.1 — the plan had no task for remove, status, or how a
Markdown skill reaches the library. The skill contract above names four verbs; the library had
code for two of them (`install()`, `update()`), nothing for `remove` or `status`, and no entry
point at all: a `SKILL.md` can run a command, but it cannot import a Python module. So C3 is two
things — the interview, which is Markdown and owns every question, and this CLI, which owns every
library call. The skill never reads or writes the target repository by any other route.

```
python3 <abs path>/skills/patterns-setup/lib/cli.py [--catalogue <dir>] <verb> <repo> [args]

  scan    <repo> [--answers <json>]                 reads    detect -> outcomes -> companions, + listing cost
  install <repo> <pattern>...                       WRITES   guard -> install
  update  <repo> [--accept <pattern>]...            WRITES   update, declining every diverged pattern not named
  remove  <repo> <pattern>... [--force <pattern>]...WRITES   remove
  status  <repo>                                    reads    status
```

**Runtime.** Python 3.11+, standard library only (ADR-2). `cli.py` puts its own directory
(`Path(__file__).resolve().parent`) on `sys.path` and imports its siblings from there, so any cwd
works; it never reads `CLAUDE_PLUGIN_ROOT`, which is absent in the Bash-tool subprocess this runs in
(decision 5 of the install plan). The catalogue defaults to `paths.DEFAULT_CATALOGUE_DIR` (below,
under `status`), one derivation rather than another copy of the `parents[3]` arithmetic. `--catalogue <dir>` is a test
seam, as it is on the drift reporter: one global option, placed before the verb, which `remove`
ignores because it never reads the catalogue. `home_dir` for the guard is `Path.home()`, the
CLI-entry-point half of the convention under *the three namespaces (C4)*; `Path.home()` honours `$HOME`, so a test sets `HOME` and the CLI
needs no `--home` flag (decided here: one seam is enough when the platform already provides it).
`bundle` is never passed, so `install()`/`update()`/`remove()` read it from `plugin.json` lazily.

**Output.** One JSON document per call, on stdout, only on exit 0: `json.dumps(doc,
ensure_ascii=False, sort_keys=True)` plus a newline, encoded as UTF-8 and written to
`sys.stdout.buffer` — decided here, because `ensure_ascii=False` through a text stream raises
`UnicodeEncodeError` under a non-UTF-8 locale, and a crash there would arrive after the writes it
was meant to report. The library's named channels become JSON **objects with named fields**, never
arrays: a positional tuple in JSON is the unpacked-wrong hazard the dataclasses were named to avoid
(`GuardReport`, "Named channels rather than a 3-tuple"). Sets become sorted arrays. Human-readable
messages, warnings and usage go to stderr only.

**Paths are not one kind, and each field says which it is** (corrected 2026-10-06; this said
"absolute POSIX strings" for all of them, which `report` and the citations contradict):

| Field | Form |
|---|---|
| every verb's `repo`; `install`'s `refused.*.path` and `refused.*.intended_path`; `install`'s `skipped[].path` | absolute (the toplevel, `Path.home()` and every root the guard walks are absolute) |
| `scan`'s `report` | verbatim from `detect()`: `report.repo` is the absolute toplevel the CLI passed in; `evidence`, `gate_evidence`, `manifests_walked` and `unreadable` are relative to it, as `detect.py` writes them (`tree.rel`) |
| `scan`'s `companions.*[].source_file` and `companions.ambiguous[].source_file` | relative to the catalogue root, as `companions._derive` writes them |
| `status`'s `unlisted[]` and `debris[].name` | a bare entry name inside `<repo>/.claude/skills/` |
| reason strings | free text; any path inside one is whatever the library interpolated |

**Exit codes — four, and each one tells the skill what to do next.** Decided here.

| Exit | Meaning | stdout | The skill |
|---|---|---|---|
| 0 | The verb ran. Per-pattern refusals and failures are **in the JSON channels**, not in the exit code | one JSON document | renders it |
| 1 | An unexpected exception — a bug. Python's own exit code for an uncaught exception, deliberately left as is, so a crash can never be mistaken for a refusal | empty | shows stderr, says it is a defect in the CLI, and stops |
| 2 | Usage: the arguments are invalid. `argparse`'s own code, so no custom handling is needed for the shape errors it already catches; the CLI also uses it for names and answers it rejects after parsing (below) | empty | shows stderr, says it is a defect in the skill (the skill built the arguments), and stops |
| 3 | Refused: a precondition for the whole call failed — interpreter older than 3.11, `<repo>` not inside a git work tree, a manifest that cannot be read or parsed on a verb that writes, an `--accept` naming a pattern the manifest does not list. Nothing written | empty | shows stderr, which names the resolution, and stops |

This table is the one authority for how the skill treats an exit code; T5.1 cites it rather than
restating it.

A per-pattern problem is exit 0 because the library already decided that one pattern's fault never
stops the others (install plan, "Who raises, and who catches") — an exit code cannot carry "three
installed, one refused", and the JSON can. The drift reporter's always-0 is a different contract on
purpose: its caller is a session-start hook that must fail open, while this one's caller is a skill
that must not carry on after a refusal.

**Order of checks, identical for every verb.** (1) `argparse` (exit 2). (2) `sys.version_info >=
(3, 11)`, before any lib import (exit 3). (3) Resolve `<repo>` with `git -C <repo> rev-parse
--show-toplevel`; a non-zero exit, a missing `git`, or a path that does not exist is exit 3 with
"not inside a git repository: <repo>" — Primary Flow step 1 and the Error Handling row "Not inside a
git repository". **Every verb then works on the toplevel, not on the path given**, and reports it
as `repo`. Nothing under the target is opened before this step returns; git's own read of `.git` is
the check, not a read of the target. (4) The verb.

##### `scan` — reads only

Calls, in order: `detect.detect(toplevel)`; if `--answers` was given, validates it against the
report and calls `outcomes.decide(report, answers)`; `companions.expand_companions(selection,
catalogue_root)`, `companions.companion_citations(catalogue_root)` and
`companions.ambiguous_citations(catalogue_root)`; then the listing cost of every catalogue pattern.
Writes nothing.

**How the answers get back: `scan` is called twice, the second time with `--answers`.** Decided
here, as the smallest thing that serves F3 and the four-outcome report. The first call returns the
report and `outcomes: null`; the skill asks the open gates' questions; the second call passes
`--answers '{"q1_backend": ["api-design"], "q2_architecture": []}'` and gets the partition. Not
`decide(report, None)` on the first call: with no answers, every open gate's patterns would land in
`declined_by_question`, a statement about the user that is false before anyone was asked. Not a
sixth verb taking the report back as input: the re-scan costs one walk ("without a visible pause",
Quality Requirements), and a report round-tripped through the skill is a second copy that can drift
from the tree. `--answers` must be a JSON object whose keys are gate names **open in this scan's
report** and whose values are arrays of patterns that gate settles (`outcomes.GATE_SETTLED_PATTERNS`);
anything else is exit 2 (decided here). `decide()` silently ignores such entries, which is right for a library and
wrong at this boundary: a misspelt pattern would become a silent "declined". An open gate absent
from `--answers` means "asked, none chosen" — the same as an empty array.

| Key | Type | Content |
|---|---|---|
| `repo` | string | the git toplevel |
| `report` | object | `detect()`'s report verbatim, including `unreadable` (below) |
| `outcomes` | object or `null` | `null` without `--answers`; else `{installed, declined_by_question, excluded_by_stack_fact, not_reached}`, each a sorted array, the four summing to 21 |
| `companions` | object | `{proposed, ambiguous}`. `proposed`: companion → array of `{from, source_file, line, target}`, one per citation on an edge into that companion from the selection or from another proposed companion. Its keys are exactly `expand_companions(selection)`. `ambiguous`: array of `{source_file, line, target, candidate_patterns}` from `ambiguous_citations()` |
| `listing_cost` | object | catalogue pattern → integer or `null`, one key per pattern directory in the catalogue in use (21 in the real one), defined below |

The **selection** companions are computed for is `outcomes.installed` when answers were given, and
otherwise the `auto` plus `baseline` pattern names — what the proposal starts from. A pattern the
user adds by hand at Confirm gets no companion proposal; the closure informs rather than guarantees
(companion map, "Expansion is the transitive closure"), and the skill says so rather than implying
otherwise.

**`companion_citations()` is new in `companions.py`, decided here, because T5.1 cannot meet its
own criterion without it.** T5.1 requires each proposed companion to arrive "with the citation that justified it
named", but `companion_map()` returns `pattern → frozenset[pattern]`, and the citation is discarded
inside `_derive`. `companion_citations(catalogue_root) -> dict[str, dict[str,
tuple[Citation, ...]]]` returns source → companion → the citations that produced that edge, where
`Citation(source_file, line, target)` is a frozen dataclass shaped like `AmbiguousCitation` without
`candidate_patterns`. It is filled in the same `_derive` pass, so its two outer key levels equal
`companion_map()`'s edges by construction — a test asserts that equality rather than trusting it.

**Listing cost, defined.** Nothing in this document said how to compute it. Primary Flow step 3
says C3 renders "the character cost each description adds to the listing"; *User Interface & UX*
says "in characters of listing"; CON-1 caps a description at `skillListingMaxDescChars` 1536; and
ADR-1 says the prefix adds to "each entry's listing cost", so the name counts. **Decided here:**

```
listing_cost(p) = len("tcs-" + p) + min(len(description(p)), 1536)
```

where `description(p)` is the value of the single `description:` line inside the catalogue
`SKILL.md`'s frontmatter block, parsed with `guard._parse_name_scalar` — the plain/single/double
quoted scalar parser C4 already has, which despite its name parses any single-line scalar — so
`\"` counts as one character, not two; and `len` counts code points, which equals the harness's
UTF-16 count for all 21 today (their only non-ASCII character is `—`, in the BMP). It is `null` when
the frontmatter has no single `description:` line or the parser returns `ok=False` or an empty value,
and the skill renders a `null` as "unknown", never as zero. Measured 2026-10-06: all 21 parse, and
the 21 costs sum to **5990**. The spec's own "5918 characters" reproduces exactly as unprefixed name
plus the *raw* text between the quotes; parsing removes 12 characters (twelve `\"` in
`obsidian-plugin`'s description) and the prefix adds 84 (21 × 4). The figure counts the separator
characters the harness puts between name and description as zero, because they are not ours to
know; a cost is a comparison between entries, and a constant per entry does not change one.

**A partially unreadable target, and the gap this exposed.** The Error Handling row "Target
repository unreadable in part" assigns C2 a report that "names what it could not read". `detect.py`
does not implement it: `_Tree` calls `os.walk` with no `onerror`, so an unlistable directory is
skipped silently, and `_read_text` returns `None` for an `OSError` exactly as for undecodable
content. Decided here, T5.1a adds one key to the detection report: **`unreadable`**, a sorted array of paths
relative to the scanned root — directories that `os.walk` could not list, with a trailing `/` as
`gate_evidence` writes directories, and files a rule opened whose read raised `OSError`. A
`UnicodeDecodeError` is content, not access, and is not listed. The key is always present, `[]`
when everything was readable; `schema` stays `1`, because the key is additive and nothing outside
this plugin consumes the report. `scan` carries it inside `report`, and the skill must say "the
scan could not read: …" whenever it is non-empty.

##### `install <repo> <pattern>...` — writes

Each `<pattern>` must name a catalogue pattern directory (exit 2 otherwise, before the guard
runs; decided here): a typo is a usage error, not a pattern that "failed". Calls, in order:

1. `manifest.read(toplevel)` for `own_installed = {e.installed_as for e in patterns.values()}`.
   `ManifestUnparseableError` or `OSError` is exit 3 with nothing written — `install()` would
   raise on the same read anyway, and failing before the guard keeps the refusal ahead of every
   other message.
2. `guard.check(toplevel, {"tcs-" + p ...}, home_dir=Path.home(), own_installed=...)`.
3. `install.install(toplevel, sorted(<patterns whose tcs- name is in approved>),
   catalogue_dir=...)`. Only the names the guard cleared — AC-10 is C4 and C5 together, and this
   call is where they meet.

**Companions are never added here.** The skill proposes them and the user accepts each by name
(the install plan's decision 4, "C5 reports; C3 offers", and T5.1's "Nothing is installed by the companion map alone");
`install` installs exactly the names it is given.

| Key | Type | Content |
|---|---|---|
| `repo` | string | the git toplevel |
| `installed` | object | pattern → `{installed_as, version, sha256}`, from `InstallReport.installed` |
| `unchanged` | object | pattern → `{installed_as, version, sha256}` |
| `failed` | object | pattern → reason string |
| `refused` | object | pattern → `{installed_as, namespace, path, intended_path}`: the guard's `(namespace, path)` and the directory this install would have written, so the collision is reported **with both locations** (F5) |
| `skipped` | array | `{path, reason}` per `GuardReport.skipped` entry |
| `committed` | boolean | always `false` (ADR-8) |

##### `update <repo> [--accept <pattern>]...` — writes

`decide` cannot prompt through a CLI, so **`update` is non-interactive by construction**: it calls
`install.update(toplevel, catalogue_dir=..., decide=lambda name, diff: name in accepted)`. A
diverged pattern not named by `--accept` is declined — reported with its unified diff and left
byte-identical — which keeps ADR-4's default-decline in the library's hands, not the skill's. A
pattern that is merely behind refreshes without asking, exactly as decision 2's middle row says;
`--accept` has no effect on it. The skill shows each declined diff, asks, and runs `update` again
with `--accept` for each pattern the user approved. Each `--accept` must name a pattern the
manifest lists (exit 3 otherwise, decided here, checked after the manifest read and before `update()` is called):
a misspelt name would otherwise silently decline the pattern the user just approved. Accepted
risk: a file edited again between the two calls is refreshed against a diff the user did not see.
The window is one skill turn, and binding consent to a hash would add an argument format for a
case nobody has hit.

A manifest that cannot be read or parsed is exit 3, decided by the CLI's own `manifest.read` before
`update()` is called. Inside `update()` the manifest read is not the first thing that can fail:
with `bundle=None`, `_bundle_version()` reads `plugin.json` first (`install.py`, the `if bundle is
None` lines of both `install()` and `update()`). Both reads precede every write, so either failure
leaves the repository untouched.

| Key | Type | Content |
|---|---|---|
| `repo` | string | the git toplevel |
| `refreshed` | object | pattern → `{installed_as, version_before, version_after, sha256}` |
| `declined` | object | pattern → `{version, diff}` — diverged and not accepted |
| `current` | object | pattern → `{installed_as, version, sha256}` |
| `failed` | object | pattern → reason string |
| `committed` | boolean | always `false` |

##### `remove <repo> <pattern>... [--force <pattern>]...` — writes

Calls `install.remove(toplevel, patterns, force=frozenset(forced))`; each `--force` must also be
one of the positional patterns (exit 2 otherwise). The library function, new in `install.py`:

```
remove(repo_dir, names, *, bundle=None, force=frozenset()) -> RemoveReport

RemoveReport (frozen, named channels)
    removed:   name -> (installed_as, version, directory_existed)
    refused:   name -> reason          a rule said no; nothing touched
    failed:    name -> reason          an OSError; rolled back where possible
    committed: always False
```

**`install.py` and not a new module, decided here:** `remove()` is C5's third write verb, and it
needs `_bundle_version` and `_stash_path`, which are private to that module. Splitting would export
private helpers to save one file from growing. The `SKILL.md` hash it compares comes from
`paths.sha256_or_none`, the same function `install.py` itself moves to (see `status` below).

Reads the manifest once up front; `ManifestUnparseableError` and `OSError` propagate before
anything is touched (exit 3 in the CLI), the same as `install()` and `update()`. Then, per pattern,
in sorted order, **the first rule that applies decides**:

| # | Condition | Outcome |
|---|---|---|
| 1 | the manifest does not list the pattern | `refused`: "not recorded in the manifest; remove deletes only what the manifest records". **`remove` never deletes a directory the manifest does not own** — a hand-made `tcs-foo/` is someone's skill, not ours |
| 2 | the entry's `installed_as` is not `"tcs-" + name` | `refused`. ADR-1 makes this always true for what `install()` writes; a hand-edited manifest pointing `ddd` at `tcs-hexagonal` would otherwise delete the wrong pattern |
| 3 | `.<installed_as>.replaced` exists **and `<installed_as>/` does not** | `refused`, naming it, with the resolution: "an interrupted refresh left your copy at `<stash>`; move it back to `<installed_as>/` and run remove again, or delete it yourself if you do not want it". With the directory absent the stash is the user's only copy (update path, decision 8), and dropping the manifest entry would orphan the only reference to it. **A stash beside a present directory is not this rule's case**: decision 8 calls that state debris that costs nothing, because the next refresh deletes it — and once the pattern is removed no refresh will come, so `remove` deletes it with the directory (step 4). Corrected 2026-10-06; this rule refused whenever a stash existed, which made a current pattern with old debris unremovable by any verb |
| 4 | `<installed_as>` exists but is a symlink, or is not a directory | `refused`: `install()` never creates either, so it is not ours as written |
| 5 | the directory exists and the hash of its `SKILL.md` differs from the manifest `sha256` — an unreadable or absent `SKILL.md` counts as differing — and the name is not in `force` | `refused`: "diverged from what was installed; local edits would be lost — re-run with --force <name>". Decided here: refuse, mirroring ADR-4's stance that nothing destroys local work without consent. As with `update`, only `SKILL.md` is hashed, so an edit confined to `reference/` is deleted without asking — ADR-4's accepted limit, not a new one |
| 6 | otherwise | removed, in the four steps below |

**Order: move aside, then the manifest, then delete.** Decided here, because each interrupted state
is one `status` can name and one re-running `remove` completes:

1. If `.<installed_as>.removing` exists, `shutil.rmtree` it — this verb's own debris from an
   earlier interrupted run, exactly as `install()` removes its own `.tmp`.
2. If `<installed_as>/` exists, `os.rename` it to `.<installed_as>.removing` (same directory, so
   atomic). The pattern leaves the skill listing in one step, never half-deleted.
3. Write the manifest without the entry: new `manifest.drop(repo_dir, name, *, bundle) -> Manifest`,
   the mirror of `upsert` (read, `Manifest.without_pattern(name, bundle=...)`, atomic `write()`;
   prior entries byte-identical, since `_serialize_pattern` depends only on its own entry). If it
   raises, report `failed` — and **only if step 2 renamed a directory**, rename `.removing` back to
   `<installed_as>/` first. On the resume path (`directory_existed: false`) there is nothing to
   rename back, and a `.removing` found there was already deleted in step 1.
4. `shutil.rmtree(.<installed_as>.removing, ignore_errors=True)`, and the same for a
   `.<installed_as>.replaced` stash if one sat beside the directory (rule 3's second half). A
   leftover is reported by `status` as debris.

Interrupted after step 2: the manifest lists the pattern, its directory is absent, and
`.<installed_as>.removing` is present — `status` shows all three, and re-running `remove` reaches
rule 6 with `directory_existed: false` and finishes. Interrupted after step 3: debris only, no
record — a re-run is refused by rule 1, because the manifest no longer lists the pattern, and
`status` reports the `.removing` entry as debris that is safe to delete. That is the one state a
re-run does not finish, and it needs nothing finished: the pattern is already out of the listing
and out of the record. The alternative orders are worse. Manifest first leaves an unrecorded `tcs-<name>/`, which
rule 1 then forbids `remove` from deleting, so the user must delete it by hand. Delete first leaves
a half-deleted directory the harness still lists.

The manifest's `bundle` is set to the plugin version doing the removing, because `bundle` records
the plugin version that last wrote the file (decision 9 of the update path). **Removing the last
pattern leaves a manifest with zero patterns, not no manifest.** Decided here: `write()` already
serialises a manifest with a `bundle` and no tables, `patterns_drift.py` prints `OK` for it
(`test_present_manifest_naming_no_patterns_prints_ok`), and the advisory stays silent for it. A
deleted manifest would print `MISSING`, which is also silent, but it would need a second kind of
write with its own interruption states, and it would erase the record that setup ever ran here.

| Key | Type | Content |
|---|---|---|
| `repo` | string | the git toplevel |
| `removed` | object | pattern → `{installed_as, version, directory_existed}` |
| `refused` | object | pattern → reason string |
| `failed` | object | pattern → reason string |
| `committed` | boolean | always `false` |

##### `status <repo>` — reads only

The verb the advisory's `UNKNOWN` segment points users to. Calls `status.status(toplevel,
catalogue_dir=...)`, in a new read-only module `lib/status.py` — decided here, so that "status
writes nothing" is checkable from the module's source rather than argued.

**A leaf module, `lib/paths.py`, decided here** — corrected 2026-10-06. This section first said
`status.py` "never imports `install`", while it needs `install.DEFAULT_CATALOGUE_DIR` and the
`SKILL.md` hash, which is `install._hash_if_present`, a private function. `paths.py` holds what
both the writer and the reader need, and nothing that writes:

```
PLUGIN_ROOT, PLUGIN_JSON, DEFAULT_CATALOGUE_DIR     path expressions, no I/O at import
TMP_SUFFIX = ".tmp"; REPLACED_SUFFIX = ".replaced"; REMOVING_SUFFIX = ".removing"
sha256_or_none(path) -> str | None                  install._hash_if_present, moved
```

`install.py` and `companions.py` import the root and the catalogue default from it, which
collapses two of the three `parents[...]` derivations (`install.py`'s `_PLUGIN_ROOT`,
`companions.py`'s `_DEFAULT_CATALOGUE_DIR`); `install.DEFAULT_CATALOGUE_DIR` stays as a re-export,
because it is a public name. `install.py` uses the three suffixes for `.tmp` and `.replaced`, and
`remove()` uses `.removing`. **`patterns_drift.py` keeps its own derivation**, because it must find
`lib/` before it can import anything from it, and its "missing lib → exit 0, silent stdout"
contract forbids any lib import at module level, which a `paths`-derived default argument would
need. `paths.py` stays importable from a copy, as the others are: no I/O at import.

The property, stated so a test can check it: among this plugin's modules, `status.py` imports only
`manifest` and `paths`, and calls only `manifest.read` and `manifest._manifest_path` — never
`write`, `upsert` or `drop`. A test parses `status.py` with `ast` and asserts both.

```
status(repo_dir, *, catalogue_dir=paths.DEFAULT_CATALOGUE_DIR) -> StatusReport

StatusReport (frozen)
    manifest_state: "present" | "absent" | "unparseable" | "unreadable"
    manifest_error: str | None        str(exception), verbatim, when unparseable or unreadable
    bundle:         str | None
    patterns:       name -> PatternStatus
    unlisted:       tuple[str, ...]   tcs-* directories no manifest entry names, sorted
    debris:         tuple[Debris, ...] sorted by name

Debris (frozen)
    name:       str                   entry name inside .claude/skills/
    kind:       "install-tmp" | "replaced" | "removing" | "manifest-tmp" | "unknown"
    resolution: str                   what the user should do, from the table below

PatternStatus (frozen)
    installed_as, installed_version: str
    catalogue_version: str | None     None when absent, unreadable or non-numeric
    state:     "OK" | "DRIFT" | "UNKNOWN"
    directory_present: bool
    diverged:  bool | None            None when the directory or its SKILL.md is absent or unreadable
```

**`state` reuses the reporter's rule; it does not restate it (decided here).** T5.1a moves the comparison out of
`patterns_drift.py` into `lib/status.py`, as `catalogue_version(catalogue_dir, name) -> str | None`
(the reporter's `_catalogue_version`, unchanged) and `drift_verdict(installed: str, catalogue: str
| None) -> "OK" | "DRIFT" | "UNKNOWN"` (`UNKNOWN` when `catalogue` is `None` or the installed
integer is greater; `DRIFT` when it is smaller; integer comparison throughout). The reporter
imports both, lazily inside `drift_lines` as it already imports `manifest`, so a missing lib still
exits 0 silently. The 2026-10-06 reason for keeping the comparison in the reporter was to keep
`manifest.is_current` as string equality for `update()`; that still holds, since neither function
touches `is_current`. A duplicate in `status.py` was rejected because two copies of a rule that has
already been corrected once (string equality to integers) is how the second copy stays wrong.
**The test is still independent.** Its expected verdicts are a hand-typed table, and each row is
asserted against **both** `status()` and the reporter's stdout line. The shared function cannot
supply the expected value, so a wrong rule fails both rows instead of agreeing with itself.

`status` reports a manifest that cannot be parsed
**verbatim, with exit 0**: that is the Error Handling row "Manifest present but unparseable",
"reported verbatim by `status`", and it is the one verb that must still work when the manifest is
broken. An `OSError` on the manifest is `unreadable`; there the reporter writes empty stdout, exits
0, and puts one line on stderr, `patterns_drift: <error>`, which the advisory never shows. When the
manifest is not `present`, `patterns` is empty and every `tcs-*` directory is `unlisted`.

**`debris` is classified, with the resolution text the skill renders** — corrected 2026-10-06. It
first listed `.tcs-*` names unclassified, on the grounds that restating the writer's suffixes would
be a second copy. `paths.py` now holds the suffixes, so classifying them reads the writer's own
constants, and two states needed telling apart: one is the user's only copy, and one is safe to
delete. That first version also missed the manifest's own temp file, which `manifest.write` names
`.` + `.tcs-patterns-manifest` + `.<random>.tmp` (two leading dots, so a `.tcs-*` glob misses it).
An entry is debris when its name starts with `.tcs-` and is not the manifest itself, or starts
with `.` + `manifest.MANIFEST_FILENAME` + `.`:

| `kind` | Name | `resolution` |
|---|---|---|
| `install-tmp` | `.tcs-<p>` + `TMP_SUFFIX` | safe to delete; the next `install` of `<p>` deletes it itself |
| `replaced` | `.tcs-<p>` + `REPLACED_SUFFIX` | with `tcs-<p>/` present: safe to delete, and the next refresh or `remove` deletes it. With `tcs-<p>/` absent: **this is your copy of `<p>`**; move it back to `tcs-<p>/` |
| `removing` | `.tcs-<p>` + `REMOVING_SUFFIX` | with the manifest still listing `<p>`: run `remove <p>` to finish. Otherwise: safe to delete; the removal had finished except for this |
| `manifest-tmp` | `.` + `MANIFEST_FILENAME` + `.*` + `.tmp` | safe to delete; a manifest write was interrupted before its rename, and the manifest itself is intact |
| `unknown` | any other match | not a name this tool writes; left alone |

| Key | Type | Content |
|---|---|---|
| `repo` | string | the git toplevel |
| `manifest` | object | `{state, error, bundle}` |
| `patterns` | object | pattern → `{installed_as, installed_version, catalogue_version, state, directory_present, diverged}` |
| `unlisted` | array | directory names |
| `debris` | array | `{name, kind, resolution}` |

### Implementation Examples

Three places where the obvious implementation is wrong. Everything else follows the components.

**Nested manifests, runtime dependencies only (traps 4 and 5).** The validated monorepo has an
empty root `dependencies`; the signal is three levels down. Reading only the root finds nothing, and
reading `devDependencies` finds a framework that is only there to drive tests.

```python
# The normative exclusion list is exactly these four -- see the walked-manifest bullet
# under "Detection rules". This sample once added ".git", "dist" and "build", which
# widened it beyond the rule and would have been copied as if authoritative.
SKIP_DIRS = {"node_modules", ".venv", "venv", "vendor", ".git", ".claude"}

def walk_manifests(root, filename):
    """Every manifest named `filename`, root first, vendored trees excluded."""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        if filename in filenames:
            yield os.path.join(dirpath, filename)

def runtime_deps(root):
    """Runtime dependencies only. devDependencies is a different question (trap 4)."""
    found = {}
    for path in walk_manifests(root, "package.json"):
        try:
            data = json.load(io.open(path, encoding="utf-8"))
        except (ValueError, OSError):
            continue                      # an unparseable manifest is not a signal, not a crash
        for name in (data.get("dependencies") or {}):
            found.setdefault(name, path)  # first occurrence wins; the path is the evidence
    return found
```

**The name rewrite (ADR-1 against CON-4).** A skill registers under its frontmatter `name:`, so
copying the directory to `tcs-ddd/` is not enough — the frontmatter must change, and nothing else
may. The rewrite touches the first `name:` line inside the frontmatter block and refuses if it is
not there, because a silent no-op would install a pattern under the unprefixed name and defeat
ADR-1.

```python
def rename_in_frontmatter(text, new_name):
    # Three corrections, 2026-10-05, each measured against the previous version
    # of this sample before T3.3 was dispatched.
    #
    # (a) `text.index` raised a bare ValueError("substring not found") when the
    #     frontmatter never closed. The Error Handling table promises
    #     InstallError for a bad frontmatter block, so the sample contradicted
    #     it. An unterminated block is its own input class -- C4 carries five
    #     skip cases for exactly this reason.
    # (b) `startswith("---\n")` refused a CRLF file with the message
    #     "does not open with a frontmatter block", which is false: it does.
    #     The catalogue is LF today and nothing enforces that.
    # (c) worst: `^name:[ \t]*\S.*$` MATCHES `name: >-` and replaced that line
    #     while leaving the block scalar's continuation line behind, producing
    #     broken YAML in an installed skill -- silently, reported as success.
    #     All 21 catalogue files are plain scalars today and no test pins it.
    if not re.match(r"^---\r?\n", text):
        raise InstallError("SKILL.md does not open with a frontmatter block")
    m = re.search(r"(?m)^---[ \t]*\r?$", text[4:])
    if m is None:
        raise InstallError("SKILL.md frontmatter block never closes")
    end = 4 + m.start()
    head, body = text[:end], text[end:]
    # Reject a `name:` this rewriter cannot safely replace, rather than
    # replacing its first line and orphaning the rest.
    value = re.search(r"(?m)^name:(.*)$", head)
    if value is None or not value.group(1).strip():
        raise InstallError("no `name:` line in frontmatter; refusing to install unprefixed")
    if value.group(1).strip()[0] in ">|!&*%":
        raise InstallError("`name:` is not a plain scalar; refusing to rewrite it")
    # `.` does not match \n but DOES match \r, so `^name:.*$` spans the
    # carriage return on a CRLF file and the replacement silently drops it --
    # measured, a 5-line CRLF input came out with 4 CRLF lines and 1 bare LF
    # line. Mixed line endings in a file this tool generates is a defect, not a
    # contract guarantee. Fourth correction to this sample, 2026-10-05, found by
    # T3.3's implementer; the 15-input verification missed it because
    # `yaml.safe_load` tolerates mixed endings and the body-unchanged assertion
    # does not look at the rewritten line's own ending.
    patched, count = re.subn(r"(?m)^name:[^\r\n]*", "name: " + new_name, head, count=1)
    if count != 1:                      # unreachable given the checks above; kept as a tripwire
        raise InstallError("no `name:` line in frontmatter; refusing to install unprefixed")
    return patched + body
```

**The rewrite preserves every line ending, including the one it rewrites.** A CRLF file installs
as CRLF throughout; an LF file installs as LF throughout. That is the assertion to write — not the
weaker "the body after the closing delimiter is byte-identical", which holds even when the rewritten
line's own ending has been changed.

**A test must pin that all 21 catalogue `name:` values are plain scalars**, because (c) above is
only harmless while that holds and nothing currently enforces it.
`test_all_21_frontmatter_blocks_still_parse_as_yaml` proves they *parse*, which a block scalar also
does `[ref: tests/test_tcs_patterns_catalogue_relocation.py:141]`. The precondition the installer
depends on is narrower than parseability and needs its own assertion.

**The per-pattern CI rule (ADR-9).** The existing gate asks "did this bundle's marker change". For
patterns that is too coarse: changing `ddd` while bumping `hexagonal`'s VERSION would pass the gate
and leave `ddd` silently stale — the exact failure the gate exists to prevent. The rule is
per-directory instead, and needs no parsing:

```bash
# For every changed file under templates/patterns/<name>/, that pattern's own
# VERSION must be in the same changeset. One rule, 21 patterns, no table rows.
#
# Derive the names from the DIFF, not from the working tree: a pattern added in
# the same changeset is gated without anyone registering it, and a deleted one
# raises nothing.
changed_patterns="$(printf '%s\n' "$changed_paths" \
  | sed -n 's|^plugins/tcs-patterns/templates/patterns/\([^/]*\)/.*|\1|p' \
  | sort -u)"

# Then reuse the CI gate's check_bundle (not drift_check.py's, which is unrelated) rather than reimplementing the failure path. It takes
# ONE marker per call, so per-pattern invocation is exactly the semantics the
# rule needs -- bumping a different pattern's VERSION cannot satisfy this call.
# It already owns the FAIL banner, the offending-file list and the "Fix: bump
# <marker>" line; a second loop with its own printf would drift from those.
for p in $changed_patterns; do
  check_bundle "plugins/tcs-patterns/templates/patterns/$p" \
               "plugins/tcs-patterns/templates/patterns/$p/VERSION" \
               '*'
done
```

Three properties of the CI gate's `check_bundle` make this work, each verified by reading it rather than assumed:

- **It takes one marker per call.** The bundle table's single-marker-per-row shape is what ADR-9
  rejects; the *function* is fine, and per-pattern invocation gives each pattern its own marker, so
  bumping the wrong one cannot satisfy another pattern's call.
- **Its path match spans subdirectories.** `case "$path" in "${sources_dir}"/*)` is a shell case
  glob, where `*` crosses `/`, so `<name>/reference/x.md` matches. A filesystem glob would not have.
- **`'*'` is already an accepted glob value.** Its dispatch is a literal `case` over `'*'` and
  `'*.sh'` that hard-errors on anything else, so the rule needs no new glob and must not introduce
  one.

The marker file itself is skipped by the function's own `[ "$path" = "$marker_file" ]` branch, so a
changeset containing only a `VERSION` bump is not treated as a changed source.

## Runtime View

### Primary Flow

**How to read this section.** Steps 1 to 6 run contiguously below. Steps **7, 8 and 9 are
interleaved** with the `#### Data model:` sections for the components they invoke, so the nine steps
span roughly 600 lines rather than a dozen: step 6 is followed by *the three namespaces (C4)*, step 7
by *the update path (C5's second verb)*, step 8 by *the install plan and report (C5)*, and step 9
closes the sequence. Each section was placed beside the step that calls it, which is useful when
reading one component and misleading when reading the flow. **Consequence worth knowing before you
cite a number:** a numbered item in this region may belong either to the flow or to a data-model
section's own decision list, and raw line order does not tell you which. Both this document's author
and a reviewer independently misread `8. **Offer.**` as a data-model decision on 2026-10-05, and the
proposed renumbering would have collided with step 9. Check which list a number belongs to before
citing or changing it.

`install` in a repository that has never run the setup:

1. **Resolve.** C3 resolves the repository root via git and refuses outside a repository.
2. **Scan.** C3 calls C2 with that path. C2 reads manifests (nested, vendored trees skipped),
   configuration files, directory shapes, and runs the content greps. It returns a DetectionReport
   and writes nothing.
3. **Propose.** C3 renders `auto` with per-entry evidence and the character cost each description
   adds to the listing. `baseline` entries are listed separately and not as recommendations.
4. **Ask.** C3 asks only the questions whose gate is open — zero to three, each multiSelect. A
   closed gate produces no question at all, rather than a question whose answer is "none".
5. **Confirm.** C3 presents the final selection — auto plus baseline plus question answers — and
   the user adjusts or accepts. Nothing has been written at this point.
6. **Guard.** C4 checks every intended name `tcs-<pattern>` against the repository's skills, the
   user's global skills, and **every plugin skill it can find, enabled or not**. A collision stops
   that pattern only. What those three namespaces *are*, concretely, is specified under
   `[ref: SDD/Interface Specifications/Data model: the three namespaces (C4)]`. This step used to
   read "the reachable plugin skills" — a phrase used three times in this document and defined
   nowhere until 2026-10-05, and wrong in substance once it was defined: the contract drops
   reachability deliberately, because a disabled plugin is a future collision one settings edit
   away.

#### Data model: the three namespaces (C4)

Added 2026-10-05, before T3.2 was dispatched. Four facts measured on a live installation decide
how this is implemented, and an implementer working from the phrase alone would get at least two
of them wrong without any fixture revealing it.

**1. A skill's name is its frontmatter `name:`, never its directory (CON-4), so enumeration must
read files rather than list directories.** Re-measured 2026-10-05 over **259 `SKILL.md` files**
across all four namespace roots — the user's global skills, this repository, the plugin cache and
the marketplace tree — carrying **127 distinct registered names**: exactly **one** diverges, the
`hookify` plugin's `skills/writing-rules/` directory registering as `writing-hookify-rules`.
(This figure has been corrected twice and the reason differs each time. An earlier revision said
"131 files", which was simply wrong. It was then 253, measured correctly but with the narrower
marketplace glob this section later rejects — widening that glob adds 3 roots and 6 files, hence
259. Treat it as a snapshot of one machine, not a constant: what it is *for* is the denominator of
the divergence claim below, which has now survived three independent re-measurements on 131, 253
and 259 files.) One in 259 is
enough: a guard that collects directory names would look for a collision against a name that is
not registered, and miss the name that is. The rule is therefore: a directory is a skill **iff**
it contains a `SKILL.md`, and its name is that file's frontmatter `name:`.

Also measured, and relevant to the "skipped, not fatal" rule at the end of this section:
**zero** of the 259 files failed to parse. Every one has frontmatter and a non-empty `name:`. So
the skip-and-report branch has no naturally occurring instance anywhere on this machine, and its
test must construct one — an unreadable file, a file with no frontmatter, and a frontmatter block
with no `name:` key are three distinct inputs and none of them can be found by sampling reality.

**2. A skills directory can contain things that are not skills, and real skills sit at more than
one depth.** `~/.claude/skills/` here holds seven entries. Six are ordinary skills at
`<name>/SKILL.md`. The seventh — `synced/` — has no `SKILL.md` of its own and holds **13 real
skills** two levels further down, at `synced/<uuid>/<name>/SKILL.md`. So the user namespace
contains **19** skills whose depth below the root is either 1 or 3 directories, and:

| enumeration | finds |
|---|---|
| `iterdir()`, one level | 7 entries, 6 of them skills, `synced` wrongly reported as an occupied name |
| `glob("*/SKILL.md")` | 6 of 19 |
| `glob("*/*/*/SKILL.md")` | 13 of 19 |

A one-level `iterdir()` is therefore wrong in both directions at once — it reports `synced` as an
occupied name *and* hides thirteen names that really are taken. The `SKILL.md` test from fact 1
settles both, but only if the walk is **unbounded in depth**: no fixed number of `*/` segments
covers this namespace, so the enumeration has to recurse.

**3. The plugin cache holds several versions of the same plugin.** Re-measured 2026-10-05: **four**
cached plugins carry more than one version — `tcs-git-helpers` (`2.2.21`, `2.2.22`), `tcs-helper`
(`4.3.9`, `4.3.10`), `tcs-team` (`3.4.2`, `3.4.4`) and `plugin-dev`, whose two version directories
are **opaque hashes** (`517b2fcd1b60`, `ab024cdcfa7c`) rather than semantic versions. That last one
matters: any attempt to pick "the newest" cached version by sorting or comparing version strings
has no defined answer here. The guard does not need one — it takes the **union** of names across
every version, so which version is current never arises. Walking the cache does therefore
double-count skills and does include versions that are not reachable; both are harmless to a union
of names and neither justifies version arithmetic. The marketplace tree
(`~/.claude/plugins/marketplaces/<marketplace>/<segment>/<plugin>/skills/`) has one directory per
plugin and needs no version comparison. The `<segment>` is deliberately a wildcard and not the
literal `plugins`: see the interface block below, where the live installation's `external_plugins/`
roots are the reason. An earlier revision of this paragraph wrote the literal form, which the same
section goes on to declare wrong — corrected after T3.2's fourth gate pass, which found it in the
one paragraph two earlier sweeps of this document did not reach, because both swept for the old
glob and the old signature and neither swept for the *counts* those changed.

Measured counts for scale, re-walked 2026-10-05 with the corrected glob: 127 `SKILL.md` under the
11 cache roots, **113 under the 25 marketplace roots** (was 107 under 22 with the literal-`plugins`
form), 19 under the user root, and **0** under this repository's `.claude/skills/`, which does not
exist. The absent-namespace rule below is therefore the live case on this machine, not an edge
case.

**4. Reachability is recorded in `enabledPlugins`, merged across two files — and the guard
deliberately does not consult it.** The key format is `<plugin>@<marketplace>` with a boolean;
`~/.claude/settings.json` carries the enables and `<repo>/.claude/settings.json` can carry an
explicit `false` (measured: `plugin-dev@claude-plugins-official: false` in this repository).

**The decision: enumerate broadly and ignore reachability.** Take the union of every plugin skill
name found in the cache *and* the marketplace tree, across all versions, enabled or not. The
asymmetry is what settles it: **over-inclusion is safe and under-inclusion is not.** Refusing a
pattern because a disabled plugin owns the name costs the user one declined proposal, and the
report names the colliding location so the refusal is explicable `[ref: PRD/F5 1st-3rd]`. Letting
a name through because the owning plugin happens to be disabled today writes a manifest entry that
becomes a live duplicate the moment someone enables that plugin — and the harness will not resolve
a duplicate `[ref: SDD/Constraints/CON-3]`, so the damage is a wrong skill body silently preloaded,
discovered later and far from its cause. A disabled plugin is a *future* collision, one settings
edit away.

That decision also removes `enabledPlugins` from the guard entirely: no two-file merge, no
`<plugin>@<marketplace>` key parsing, no precedence rule between user and repository settings. The
facts above are recorded anyway, because the next person to consider filtering by reachability
needs to find the reason it was rejected rather than rediscover the merge rule.

```
check(repo_dir, intended_names, *, home_dir, own_installed) -> GuardReport

GuardReport (frozen, named channels -- not a positional tuple)
    approved: the names no namespace already owns
    refused:  name -> (namespace, path of the colliding SKILL.md)
    skipped:  (path, reason) for every SKILL.md that could not be read

namespace roots, in the order a refusal reports them:
    repo    <repo_dir>/.claude/skills/
    user    <home_dir>/.claude/skills/
    plugin  <home_dir>/.claude/plugins/cache/*/*/*/skills/
            <home_dir>/.claude/plugins/marketplaces/*/*/*/skills/

within every root: recurse to any depth, following symlinks, deduplicating
visited directories by (st_dev, st_ino); a directory is a skill iff it holds
a SKILL.md; the name is that file's frontmatter `name:`
```

**`skipped` is a third channel, not an afterthought — and it is why this returns a structure
rather than a tuple.** The rule below says an unreadable `SKILL.md` is skipped **and reported**,
because a file the guard could not parse is a name it could not check. A two-value return has
nowhere to put that, which leaves the "reported" half of the rule unfalsifiable: a test could only
assert that the call does not raise, and a guard that silently discarded every malformed file would
pass. Found by T3.2's TDD gate on 2026-10-05, against the signature as first written here.

Named channels rather than a 3-tuple for two reasons. `detect.py`'s report is the house precedent
for a multi-channel return in this design and it is keyed, not positional
`[ref: SDD/Interface Specifications/Data model: detection report (C2 → C3)]`; and three positional
values of three different shapes — a set of names, a map keyed by name, a sequence of file
problems — is a return that gets unpacked wrong once and then stays wrong, since two of the three
are falsy-when-empty containers. `manifest.py`, the sibling module delivered in this same component
set, already uses frozen dataclasses for exactly this
`[ref: plugins/tcs-patterns/skills/patterns-setup/lib/manifest.py]`.

**The marketplace glob is `*/*/*/skills/`, not `*/plugins/*/skills/`.** An earlier revision of this
section wrote a literal `plugins` segment, and the live installation already violates that layout.
Measured 2026-10-05: three marketplace roots sit at
`marketplaces/claude-plugins-official/external_plugins/<plugin>/skills/`, holding the registered
names `access` and `configure` — two names that the literal-`plugins` glob can see in **neither**
plugin root, so the guard would approve them while a plugin owns them. Neither collides with any of
the 21 catalogue names today, bare or `tcs-` prefixed, so nothing is broken right now; the defect is
the same direction as the symlink one above, and `access` and `configure` are generic enough to be
a plausible future catalogue name. Widening to three wildcards is a strict superset — it finds 25
roots where the literal form finds 22 — and over-inclusion is the safe direction by this section's
own decision.

The asymmetry is worth stating once more as a rule for anyone editing these globs: applying the
**cache** pattern to the marketplace root over-collects (25 against 22, harmless to a union of
names), while applying the **marketplace** pattern to the cache root collects **nothing at all** —
measured, zero roots, because the cache has no literal `plugins` segment. A guard that silently
enumerated no plugin skills would still pass every test that only checks the repo and user
namespaces, which is why T3.2 requires the two plugin roots to be exercised separately and at their
documented depths.

**`own_installed` is required, and it exists because this guard otherwise refuses our own
earlier work.** Found 2026-10-05, after T3.2 shipped, while settling C5's contract. Step 6 of the
Primary Flow says C4 checks every intended name **`tcs-<pattern>`** — and an installed pattern
registers in the repository namespace under exactly that name. Measured against the built C4, with
one pattern already installed as `tcs-ddd`:

```
check(repo, {"tcs-ddd", "tcs-hexagonal"}, ...)
  -> approved = ['tcs-hexagonal']
     refused  = {'tcs-ddd': 'repo'}
```

The guard refuses the pattern *this tool installed on the previous run*. The consequences compound:
`install()` never receives an already-installed name, so C5's `unchanged` channel is unreachable
through C3's flow, and **"a second identical install is a no-op" — a T3.3 success criterion and a
Quality Requirement both — cannot happen.** The obvious escape is worse: pass bare catalogue names
instead and nothing ever collides, which means ADR-1's prefix is never checked against anything and
the guard stops doing the one job it exists for.

The root cause is that this section specified the wrong question. "Is this name taken?" is not what
C4 needs to answer; **"would installing here create a duplicate nobody can resolve?"** is
`[ref: SDD/Constraints/CON-3]`. Re-installing a name we already own creates no duplicate — it
replaces or updates one entry — so it is not a collision, and the manifest is precisely the record
that tells the two apart.

**The rule.** `own_installed` carries the `installed_as` values the manifest records for this
repository `[ref: SDD/Interface Specifications/Data model: the manifest (C6)]`. A hit in the
**repository** namespace whose registered name is in `own_installed` is **not** a refusal: it is
reported neither in `refused` nor as an obstacle, and passes through to `approved`, where C5 decides
between `unchanged` and `failed` on version and hash. Three boundaries on that:

- **Only the repository namespace.** A `tcs-<name>` found in the user's global skills or in any
  plugin is genuinely somebody else's and is always a collision, `own_installed` or not. We only
  ever install into the repository, so a match anywhere else cannot be ours.
- **Required, with no default.** A default of `frozenset()` would silently restore exactly the bug
  above the first time a caller forgot to pass it. Required means forgetting is a `TypeError` at
  the call site, which is the loudest possible failure and the cheapest to fix. Same reasoning as
  `home_dir` being a parameter rather than an ambient read.
- **An unreadable manifest means nothing is ours.** The caller that cannot parse the manifest passes
  an empty set, so every installed pattern is refused. That is the over-inclusive direction and
  therefore the safe one by this section's own decision — a declined proposal costs one message, a
  duplicate costs a silently wrong skill body.

Note the benign case this also handles: if the manifest claims we installed `tcs-ddd` but the skill
now sitting there is somebody's replacement, C4 lets it through and C5 finds the hash does not match
and reports `failed`. The user is told, and nothing is overwritten
`[ref: SDD/Interface Specifications/.../"install() is purely additive"]`.

**`home_dir` is a parameter, not `Path.home()`.** Two of the three namespaces live outside the
repository, so a guard that reads the real `$HOME` internally cannot be driven by a fixture at
all — and the two namespaces that would go untested are the two the repository cannot influence.
This repository already settled the convention twice, in the module that walks this very tree:
"A CLI entry point passes `Path.home()`; every test passes an explicit `tmp_path` fixture instead"
`[ref: scripts/observability/report.py:686]`, and "Passed explicitly rather than read from
`Path.home()` internally, matching `report.py`'s own convention of taking every path as an
argument so the module stays pure and testable without a real session"
`[ref: scripts/observability/sources.py:349]`. C4 follows it. `detect.py` and `manifest.py` take
`repo_dir` for the same reason; `home_dir` is the same decision for the half of the problem that
lives in the user's home.

**The enumeration is `os.walk(followlinks=True)`, and the obvious alternatives are all wrong
here.** Measured 2026-10-05 against the live user namespace, which contains one symlinked skill
directory (`~/.claude/skills/obsidian-eval`, a link into a shared global-config checkout — this
machine keeps shared Claude configuration as a symlink farm, so a symlinked skill is the house
convention rather than an oddity):

| enumeration | finds | verdict |
|---|---|---|
| `Path.rglob("SKILL.md")` | 18 of 19 | **misses the symlinked skill** |
| `Path.glob("**/SKILL.md")` | 18 of 19 | same defect, same reason |
| `Path.glob("**/SKILL.md", recurse_symlinks=True)` | 19 of 19 | correct, but **3.13+** — below ADR-2's 3.11 floor |
| `os.walk(root, followlinks=True)` | 19 of 19 | correct on 3.11 |

The third row is the trap worth naming, because it is the one that passes on the machine this was
built on: the interpreter here is 3.14.3, where `recurse_symlinks=` exists and works. ADR-2 sets
the floor at **3.11** `[ref: SDD/Architecture Decisions/ADR-2]`, and that keyword was only added in
3.13, so a guard written with it is a `TypeError` on a supported interpreter — and the first two
rows are a *silent* undercount on every interpreter. An undercount is the unsafe direction: a name
the guard cannot see is a name it approves, and then a duplicate goes live
`[ref: SDD/Constraints/CON-3]`.

**Deduplicate directories by `(st_dev, st_ino)` while walking.** `followlinks=True` re-enters a
directory reachable by more than one path, and the Kouzou-style symlink farm makes that likely
rather than hypothetical. On a *self-referential* symlink it does not hang — measured, macOS stops
it with `ELOOP` after 66 redundant directory visits — but 66 walks of one tree is still wrong, and
the `(st_dev, st_ino)` set reduces the same fixture to **3** visits. Cheap, and it also stops two
links to one real directory from reporting the same skill twice under two paths.

- **The guard writes nothing, under any input**, and runs to completion across the whole selection
  before C5 writes anything `[ref: SDD/Cross-Cutting Concepts/System-Wide Patterns]`. Prove that
  with a digest over the tree before and after rather than only a read-only directory: a read-only
  directory catches a write *into that directory* and says nothing about a write anywhere else.
- **A missing namespace directory is empty, not an error.** `~/.claude/skills/` need not exist, and
  a repository need not have `.claude/skills/` before its first install.
- **An unreadable or frontmatter-less `SKILL.md` is skipped, not fatal** — the same stance
  `detect.py` takes for an unparseable manifest, and for the same reason: a third party's broken
  file must not stop this repository's install. It is reported **through `GuardReport.skipped`**,
  as a `(path, reason)` pair, because a skipped file is a name the guard could not check and a
  caller that cannot see the omission cannot warn about it. Five distinct inputs land here and each
  needs its own case: a file that cannot be read, a file with no frontmatter block at all, a
  frontmatter block that opens and never closes, a frontmatter block with no `name:` key, and a
  `name:` whose value is empty. None of the five occurs naturally — all 259 real files parse — so
  every one has to be constructed in a fixture. A test that asserts only "the call did not raise"
  does not cover this rule; it has to assert the entry lands in `skipped` with the right reason.
  The **reasons** must be distinguishable, but note that five inputs need not yield five strings:
  an unterminated block and a missing block are both "no usable frontmatter block" and may share
  one reason, so a test asserting `len(skipped) == 5` alongside `len(reasons) == 4` is correct and
  a test asserting five distinct reasons is wrong.

- **A directory the guard cannot list is skipped and reported too, not silently treated as empty.**
  Added 2026-10-05 after T3.2's review round, because the rule above covers only *files* and the
  gap was the unsafe direction. Measured: `os.walk`'s default `onerror=None` **swallows**
  directory-listing failures, so an unreadable directory holding a `SKILL.md` makes the guard
  **approve** that name with nothing in `skipped`, and an unreadable namespace root makes an entire
  namespace vanish the same way. `root.is_dir()` returns `True` on a `chmod 000` directory, so the
  existing missing-root guard clause does not help. Pass `onerror=` and route the failure into
  `skipped` — verified to catch both the unreadable intermediate directory and the unreadable root.
  The principle is the same one that justifies `skipped` existing at all: a name the guard could not
  check is a name it cannot vouch for, and the caller must be able to see the omission. An
  *unreadable* namespace is not a *missing* one, and conflating them is how a taken name gets
  approved `[ref: SDD/Constraints/CON-3]`.

- **"Its frontmatter `name:`" means what a YAML parser makes of it, because that is what the
  harness registers.** Settled 2026-10-05; the rule previously said only "that file's frontmatter
  `name:`", which reads as settled and is not. `guard.py` must be stdlib-only on a 3.11 floor
  `[ref: SDD/Architecture Decisions/ADR-2]`, so it cannot import a YAML parser — but Claude Code
  does, and a skill registers under whatever YAML yields. Measured across 14 constructed `name:`
  lines, a regex that captures to end-of-line disagrees with YAML on **9**, and **4 of those 9
  make the guard approve a name that is genuinely taken**:

  | `name:` line | regex captures | YAML yields | consequence |
  |---|---|---|---|
  | `name: ddd # comment` | `ddd # comment` | `ddd` | `ddd` approved though taken |
  | `name: >-` / `name: \|` (block scalar) | `>-` / `\|` | `ddd` | same |
  | `name: !!str ddd` | `!!str ddd` | `ddd` | same |
  | `name: &anchor ddd` | `&anchor ddd` | `ddd` | same |
  | two `name:` keys | the first | **the last** | wrong one checked |
  | `  name: ddd` (indented) | skipped, reported | `ddd` | safe — `skipped` did its job |

  **The rule: the parser recognises a plain scalar, optionally single- or double-quoted, and skips
  and reports anything else.** It must never return a value it is not confident of — a garbage name
  is worse than a skip, because a skip is reported and a garbage name silently frees the real one.
  An unquoted `#` begins a comment and is not part of the value; a leading `>`, `|`, `!`, `&`, `*`
  or `%` means a construct this parser does not implement and therefore a skip; a duplicate `name:`
  key is a skip rather than a guess at precedence. Zero of the 259 real files on this machine use
  any of these, so every case is fixture-only — which is exactly why the parser must be pinned
  against something other than itself.

  **The test suite may use PyYAML even though `guard.py` may not**, and should: assert the
  hand-rolled parser and a real YAML parser agree on a corpus of `name:` lines, or that the
  hand-rolled one skips. This repository already set that precedent for the same class of bug — a
  frontmatter value ending in `': '` made YAML read it as a key, ten descriptions in this repository
  stopped parsing, and `claude plugin validate` passed over all ten, which is why the catalogue's
  frontmatter is parsed with a YAML parser *in the test suite*
  `[ref: SDD/Risks and Technical Debt/Implementation Gotchas]`. A differential test is also the
  strongest shape available here, because the expected value enters the test from a source with no
  shared ancestry with the code under test.

- **No defensive `OSError` guard around the dedup's own `stat()`.** Removed 2026-10-05. Three
  mutations of those guards — dropping a stat-failing child, removing the child guard, removing the
  root guard — **survived all 25 tests**, and neither candidate fixture can reach them: `os.walk`
  classifies a dangling symlink as a *file*, so it lands in `filenames` and the dedup never stats
  it, and a symlink behind a `chmod 000` intermediate is never discovered because the walk cannot
  list the intermediate. What remains reachable is a genuine race — a directory removed between the
  walk's `scandir` and the dedup's `stat` — and letting that surface is the better behaviour, not
  worse: this section's whole stance is that a name the guard could not check must be reported
  rather than swallowed, and an exception is the loudest possible report. The silent `continue` was
  the only branch in this component that failed that stance.
7. **Write.** C5 copies each approved pattern's directory to `<repo>/.claude/skills/tcs-<name>/`,
   rewrites the frontmatter `name:`, computes the hash of the installed `SKILL.md`, and writes the
   manifest atomically (`.tmp` then `mv`, following `install_files.sh`).
#### Data model: the update path (C5's second verb)

Added 2026-10-05, before T3.4 was gated. `update()` previously had **no signature and no section
anywhere in this document** — the same gap `report_only` had, found by T3.3's gate and recorded in
the Error Handling table so this pass could not miss it.

```
update(repo_dir, *, catalogue_dir, bundle, decide=_decline) -> UpdateReport

UpdateReport (frozen, named channels)
    refreshed:  name -> (installed_as, version_before, version_after, sha256)
    declined:   name -> (version, unified_diff)    diverged, and decide() said no
    current:    name -> (installed_as, version, sha256)    nothing to do
    failed:     name -> reason
    committed:  always False

decide(name, unified_diff) -> bool        defaults to returning False
```

**1. No `names` parameter — `update()` reads the manifest to learn the selection.** F8's first
criterion is "only those patterns are refreshed and the selection is otherwise unchanged — **no
scan, no questions**" `[ref: PRD/F8 1st]`. That is the sharpest difference from `install()`, which
is handed a list someone else chose: `update()` is not allowed to re-derive a selection, so the
manifest is its only input about what to act on `[ref: SDD/Interface Specifications/Data model: the
manifest (C6)]`.

**2. Three states per installed pattern, and only one of them asks.** Settled by ADR-4's own
rationale — "with the hash, overwriting is safe precisely when it is uninteresting":

| manifest `version` vs catalogue `VERSION` | installed `SKILL.md` hash vs manifest `sha256` | `update()` does |
|---|---|---|
| equal | equal | nothing; reports `current` |
| **behind** | equal | **refreshes without asking** — nothing local can be lost |
| any | **differs** | computes a unified diff, calls `decide(name, diff)`; `True` refreshes, `False` reports `declined` |

The middle row is the one worth stating explicitly, because "ask before replacing" read naively
would ask there too, and an advisory that interrupts for a change the user cannot have made is how
a prompt becomes noise that gets clicked through. The hash is what buys the distinction, and it is
the whole reason ADR-4 chose to record one.

**3. `decide` is a callback that defaults to declining, so ADR-4's guarantee is structural.**
`update()` lives in `install.py`, which has no interactive surface — `AskUserQuestion` can only be
raised by a skill, exactly as settled for `install()`
`[ref: SDD/Interface Specifications/Data model: the install plan and report (C5), decision 4]`. So
C3 supplies a `decide` that prompts, and a test supplies a stub. **The default declines**, which
means "an unanswered prompt cannot destroy local work" `[ref: SDD/Architecture Decisions/ADR-4]` is
held by this module and can be mutation-tested, rather than living in C3's prose where nothing can
check it. A two-phase report-then-apply API was considered and rejected: it is the shape of the
`report_only` parameter deleted from `install()` for being speculative, and it would move the
safety guarantee back into the caller.

**4. The diff compares what the user has against what they would get.** `difflib.unified_diff`
between the **installed** `SKILL.md` and the catalogue's version **as it would be installed** —
that is, after the frontmatter rename, so the `name:` line is not reported as a spurious
difference. Three lines of `difflib` given ADR-2's 3.11 floor
`[ref: SDD/Architecture Decisions/ADR-4]`.

**Two properties of this diff are normative, because the user's accept-or-decline decision
depends on them, and a third is deliberately left open.** Added 2026-10-05 after a gate pass found
that a test pinning the diff by exact string implicitly depended on formatting this section never
settled.

- **Direction is fixed: the installed file is the `from` side, the catalogue is the `to` side.** So
  the user's own edit appears as a **deletion** (`-`) and the incoming upstream text as an
  **addition** (`+`). The operand order above already said this; it is restated as a requirement
  because reversing it produces a diff that is *well-formed, contains the same two lines, and is
  backwards* — it shows the user their own work as the change being introduced and the upstream
  text as what they would lose, in the one prompt where that reading decides whether their file
  survives. Measured: a check that the diff "contains the user's edit" without checking the sign
  passes both directions.
- **Both file labels are populated: `fromfile="installed"`, `tofile="catalogue"`.** `difflib`
  defaults both to the empty string, which renders the header as `---` and `+++` with nothing
  after them — measured — leaving the user to infer which side is their file from the content
  alone. These two literals are the contract so a test can assert them without guessing.
- **The context width `n` is NOT pinned and must not be asserted.** It changes the output length
  without changing what the diff means (measured: `n=5` takes this example from 8 lines to 10),
  so it is the implementer's choice. This is the line between the two: direction and labels are
  what the user reads to decide; context width is presentation.

**5. `update()` is the only component that may replace a user's file, and only with consent.** This
is the deliberate asymmetry against `install()`, which is purely additive and never removes or
overwrites anything `[ref: SDD/Interface Specifications/.../"install() is purely additive"]`. Every
other write-safety rule carries over unchanged: the refreshed directory appears atomically via a
temp directory inside `<repo>/.claude/skills/`, the manifest is upserted **per pattern after** that
pattern's directory lands, and a fault in one pattern is caught and recorded in `failed` without
escaping `update()`.

**6. ADR-4's stated limit applies here and is not a defect to fix in T3.4.** The hash covers
`SKILL.md` only, so a locally edited file under `reference/` is replaced **without** a prompt. That
is recorded as an accepted trade-off, not an oversight `[ref: SDD/Architecture Decisions/ADR-4,
"Trade-offs accepted"]`; hashing 80 files per pattern to catch a rarer case costs more than it
returns.

**7. A pattern the catalogue no longer carries is `failed`, and nothing is touched.** Added
2026-10-05 by T3.4's gate, which was asked to hunt for exactly this and found it: decisions 1-7
define the three states entirely in terms of **manifest `version` vs catalogue `VERSION`** and
**installed hash vs manifest `sha256`**, and *both comparisons presuppose the catalogue still has
the pattern*. An upstream removal leaves a manifest entry with nothing to compare against, and the
table has no row for it.

The resolution follows this module's existing convention rather than inventing one:
`_read_catalogue_version` already raises `InstallError` when a pattern's `VERSION` cannot be read,
and `install()` already catches that per pattern into `failed`
`[ref: plugins/tcs-patterns/skills/patterns-setup/lib/install.py]`. `update()` does the same — the
name lands in `failed` with a reason naming the absent catalogue entry, and **nothing under
`tcs-<name>/` is touched**, which is the only safe answer: a pattern the catalogue has dropped is
not stale, and refreshing it from a source that no longer exists is impossible while deleting it
would destroy a working skill the user still has. Removing an installed pattern is a separate verb
nobody has asked for `[ref: PRD/Out of scope]`.

Note this is **not** the mirror of decision 8 below, and is not covered by it. Decision 8 is the
*installed* side being absent; this is the *catalogue* side. Both report `failed`, for different
reasons, and each needs its own fixture.

**When both sides are absent, THIS reason wins.** Added 2026-10-05 after a mutation round found
that reordering the two guards survives every test in T3.4's suite, because the two fixtures above
are exact inverses and neither constructs the overlap. The state is reachable without anything
exotic: a user deletes `tcs-<name>/` by hand and a plugin update drops the pattern from the
catalogue, while the manifest still records it. Measured under both orderings, the messages differ
in what they tell the user to do:

| guard order | message | is the advice actionable? |
|---|---|---|
| catalogue first | the catalogue no longer carries `<name>` | **yes** — the pattern is gone upstream, so drop the manifest entry |
| installed first | that directory is missing; **run install to write it** | **no** — `install()` would fail, because the catalogue has nothing to copy |

So the catalogue check runs **first**, and that ordering is a requirement rather than an accident.
Decision 8's message is only correct when the catalogue still has the pattern, which is precisely
what makes it the second test and not the first.

**And when a `.<installed_as>.replaced` stash is ALSO present, this reason names it and must not
claim the directory was left alone.** Added 2026-10-06 (Marcus) after a spec-compliance review
surfaced the intersection and measuring it showed it was worse than reported. Three independent
failures co-occur: upstream dropped the pattern, a prior refresh was hard-killed, and the manifest
still records it. Measured, the reason read:

> the catalogue no longer carries pattern `'ddd'`; `'tcs-ddd'` was left exactly as it is

Both halves are wrong in this state. `tcs-ddd` was **not** left as it is — it does not exist — and
the stash is never named. That stash is the **only copy of the content anywhere**: the user's edits
*and* the pattern itself, which the catalogue no longer has, so unlike decision 8's case `install`
cannot recreate it from any source. A message asserting the directory is untouched while the only
copy sits unmentioned in a dotted directory is the worst of the three stash states, and it was
reachable without anything exotic.

**The precedence does not change.** The catalogue cause stays the headline because it remains the
actionable fact — the pattern is gone upstream, so the manifest entry should be dropped — and no
guard is reordered. What changes is that the reason names the stash path when one exists, and the
"left exactly as it is" clause is suppressed in that case because it is untrue. Where no stash
exists, the message is exactly as before.

**8. A manifest entry whose directory is missing is `failed`, not refreshed.** The record claims a
pattern is installed and it is not, which is a different problem from being out of date — and
`install()` already handles an absent directory by writing it. Reporting it tells the user which
verb to reach for instead of silently papering over a manifest that lies.

**Unless a `.<installed_as>.replaced` stash is sitting beside it, in which case the reason names
the stash and does not recommend running `install`.** Added 2026-10-06, measured. The
requirement is that the *recommendation* is absent, not the substring: both branches share the
prefix "the manifest records `<name>` as **installed** at `<installed_as>`", which describes the
manifest's claim rather than suggesting a verb, so "zero occurrences of the string `install`" is
neither achievable nor intended — flagged by the spec-compliance review so the looser wording could
not later be read that way. `update()` replaces a
subtree by moving the current directory aside to that stash and only deleting it once the new one
has landed; an exception puts it back, so the stash survives a crash only on a **hard kill** between
the two. In that state the user's own copy — including whatever they had edited — is the *only*
copy, and it sits in a dotted directory nothing names. Measured: `update()` reported "that directory
is missing; run install to write it", said nothing about the stash, and left it in place; following
that advice writes a fresh copy and orphans the user's work for good.

So when `dest` is absent and the stash exists, the reason says where their copy is. `update()` still
**does not move it back** — restoring a file the user has not asked about is precisely what ADR-4
forbids this verb from doing without consent, and the whole point of the stash mechanism is that
nothing overwrites local work silently. Naming it converts a silent trap into a decision the user
can make. Nothing else changes: the channel is still `failed`, and nothing under `tcs-<name>/` is
touched.

**Only the directory-ABSENT state needs this, because the other stash state heals itself.** Measured
2026-10-06, and recorded because the asymmetry looks like an oversight and is not. A hard kill
*after* the new directory lands but *before* the stash is removed leaves `dest` present **and** a
stash beside it. `update()` then reports that pattern `current` or `refreshed` normally, says nothing
about the stash, and leaves it — but `_replace_subtree` deletes a pre-existing stash before
refreshing, so the debris expires at the next refresh of that pattern. Nothing is lost either,
because `dest` holds a working pattern. The directory-absent case is the one that cannot heal,
precisely because the cleanup site is unreachable once the missing-directory guard fires first. One
state is debris with an expiry; the other is the user's only copy with no expiry, and only the
second earns a clause.

**That expiry is conditional, and an earlier revision of this paragraph claimed it
unconditionally.** Corrected 2026-10-06 after the implementer read the argument back against the
catalogue-removal row — the second time it caught this document overstating a guarantee. The expiry
depends on the refresh path being reachable, and if the catalogue has **dropped** the pattern it
never is: `update()` raises on the catalogue guard before `_replace_subtree`, and `install()` fails
on the absent `VERSION`. Measured over repeated calls to both verbs, the stash was never cleared;
restoring the pattern to the catalogue cleared it on the next refresh. So in the
catalogue-dropped + `dest`-present state the stash is **permanent** debris.

It still gets no message, and the reason is the half of the argument that does survive: `dest` holds
a working pattern, so nothing is at risk and an alarm would be noise about a directory the user can
delete at leisure. What does not survive is calling it temporary. The distinction matters because
the three states now differ along **two** axes rather than one — whether anything is at risk, and
whether the debris expires — and only "at risk" earns a message:

| catalogue | `dest` | at risk? | expires? | message |
|---|---|---|---|---|
| present | present | no | yes | none |
| present | absent | **yes** — only copy, recreatable | no | names the stash (decision 8) |
| dropped | absent | **yes** — only copy, NOT recreatable | no | names the stash (decision 7) |
| dropped | present | no | **no** — permanent | none |

**A directory that exists but has no readable `SKILL.md` is `failed` too, and that message may name
`install`.** This extends decision 8 rather than adding a state: the record claims an installed
pattern and what is there cannot be read, so neither comparison can run. `install()` is the right
verb — it rewrites the directory from the catalogue — and unlike the case above nothing is at risk,
because a stash in this state is covered by the self-healing paragraph and `dest` is present either
way. Noted 2026-10-06 after the implementer flagged the message as its own extension with no home
in this document.

**An exception raised by `decide` propagates out of `update()`; it is not caught into `failed`.**
Only `InstallError` is caught per pattern, which is the rule `install()` already follows. Deliberate:
`decide` is C3's prompt, so an exception from it is a defect in the caller rather than a condition of
one pattern, and burying it in a per-pattern `failed` row would report "this pattern could not be
updated" for what is actually a broken interview. The patterns processed before it keep their
already-written state, which is the same guarantee every other partial failure gives
`[ref: SDD/Interface Specifications/Data model: the install plan and report (C5), decision 3]`.

**9. `bundle` records the plugin version that last WROTE to this manifest, not the version every
pattern came from.** Added 2026-10-06 after the implementer flagged it as unspecified and it was
measured: installing `aaa` and `bbb` at bundle `1.0.0` and then refreshing **only** `aaa` at
`2.0.0` leaves `bundle = "2.0.0"` with `bbb` still at its version `1` content. A *declined* update
does not touch the field at all, because it writes nothing.

That is the honest meaning of a single field at the top of a per-pattern manifest, and the
alternative — advancing it only once every pattern is current — was rejected: it would stall
indefinitely on one permanently declined diverged pattern, which is a state ADR-4 deliberately
makes comfortable to stay in.

**The consequence is a constraint on C7, and it is where the real risk sits.** The drift advisory
must compute drift from the **per-pattern** `version` lines against the catalogue's per-pattern
`VERSION` files, and must never read `bundle` as evidence that the installed set is current — here
it would have said so while `bbb` was a version behind. That is also what F7 asks for directly: one
line per drifted pattern, so a change to one pattern only flags the repositories that installed it
`[ref: PRD/F7 1st and 2nd; plan/phase-4.md, T4.2]`.

8. **Offer.** C5 prints what it wrote, states that it did not commit, and offers to commit
   (ADR-8). Declining leaves the files in place. The *offer* is C3's, not C5's — see the boundary
   note under `[ref: SDD/Interface Specifications/Data model: the install plan and report (C5)]`.

#### Data model: the install plan and report (C5)

Added 2026-10-05, before T3.3 was dispatched, for the same reason the C4 namespace contract was:
four things an implementer needs were undefined, and each has more than one defensible answer.

```
install(repo_dir, names, *, catalogue_dir, bundle) -> InstallReport

InstallReport (frozen, named channels)
    installed:  name -> (installed_as, version, sha256)   newly written
    unchanged:  name -> (installed_as, version, sha256)   already current, not rewritten
    failed:     name -> reason                            raised internally, caught, skipped
    committed:  always False
```

**No `report_only` parameter.** An earlier revision of this signature carried `report_only=False`
and defined it nowhere — found by T3.3's TDD gate, which grepped the spec, located the parameter
exactly once, in this signature, and refused to pass a plan containing a test against undefined
behaviour. It is removed rather than given semantics: nothing in `[ref: PRD/F4]` asks for a dry run,
and the proposal a user sees *before* an install is C3's, assembled from `detect()` and `check()`
rather than rehearsing `install()`. Recorded rather than quietly deleted because the next person to
want a dry run should find the reason it is absent.

**Who raises, and who catches — a per-pattern fault never escapes `install()`.** `InstallError` is
raised by the frontmatter rewrite `[ref: SDD/Implementation Examples]` and by the catalogue reads
around it, and `install()` **catches it per pattern**, records `failed[name] = reason`, and carries
on to the next name. `install()` itself does not raise for a fault in one pattern — that is what
makes "a write failing mid-selection leaves earlier patterns in place" observable at all
`[ref: SDD/Runtime View/Error Handling]`, and what T3.3's success criterion means by "raises rather
than installing unprefixed": the *rewrite* raises, so nothing is written unprefixed, and the report
names the casualty. A test wrapping the whole call in `pytest.raises(InstallError)` would therefore
be testing the opposite of the contract, and could not observe the other patterns installing.

**1. C5 takes names, never a `GuardReport`.** C4 and C5 are deliberately separate so a refusal is
testable without a write `[ref: SDD/Building Block View, F5 row]`, and that separation is defeated
if C5 imports the guard. The caller (C3) runs `check()`, takes `GuardReport.approved`, and passes
those names here. So `install()` **assumes every name it is given has already been cleared** and
does not re-check the namespaces — no rescan, which is the second half of AC-10
`[ref: SDD/Acceptance Criteria/AC-10]`. The consequence worth stating: AC-10 is satisfied by C4 and
C5 *together* and by neither alone — C4 produces the partition, C5 installs exactly the approved
half — so T3.2 owned the partition and T3.3 owns "the others still install".

**2. Idempotency is defined on content, and implemented by a hash comparison.** "A second identical
install is a no-op" `[ref: SDD/Quality Requirements]` must not be read as "no bytes are written" —
re-copying an identical file writes bytes and changes an mtime while leaving content identical, and
a test that asserts on mtimes would fail a correct implementation while a content test passes a
wrong one. The requirement is therefore: **after a second install, every installed file and the
manifest are byte-identical to after the first**, proven by a digest over the installed tree *and*
the manifest, never by mtime. T3.1 already learned this distinction the other way round — an mtime
check cannot see a rewrite with identical content, which is why its write-nothing proof is a content
digest `[ref: plan/phase-2.md, T2.7]`.

The implementation that satisfies it, and the one the Error Handling table means by "idempotent by
name and hash": for each requested name, if the manifest already carries an entry whose `version`
equals the catalogue's `VERSION` **and** whose `sha256` equals the hash of the `SKILL.md` currently
installed at `tcs-<name>/`, that pattern is **skipped entirely** — no copy, no rename, no manifest
rewrite — and reported under `unchanged`. **A mismatch on either half means the pattern is not
current, and what happens to it then is decided under "6. `install()` is purely additive" below —
not here.** This sentence previously read "Anything else is a write", which was true when it was
written and became false four paragraphs later on the same day, when (6) established that a
present-but-not-current pattern is reported and left alone rather than replaced. Corrected
2026-10-05 after T3.3's third gate pass found the two paragraphs contradicting each other; this
section is the one the task directs implementers to read first, so a reader hitting (2) was being
told the opposite of (6).

Comparing the **installed** file's hash rather than the catalogue's remains the point, and it is
unaffected by that correction: it is what distinguishes "never touched" from "deliberately adapted",
which is what makes T3.4's divergence path possible at all
`[ref: SDD/Architecture Decisions/ADR-4]`.

**3. Each pattern appears atomically, and the manifest is upserted after the directory, per
pattern.** Two sub-decisions, both forced by "a write failing mid-selection leaves earlier patterns
in place with the manifest recording exactly what succeeded"
`[ref: SDD/Runtime View/Error Handling]`:

- **Per pattern, not per run.** A single manifest write at the end of the run would record *nothing*
  when the run fails midway, which is the opposite of the requirement. So C6's `upsert` is called
  once per successfully written pattern, each call being its own atomic whole-file rewrite
  `[ref: SDD/Interface Specifications/Data model: the manifest (C6)]`. N patterns means N manifest
  rewrites; that is the cost of the requirement, not an inefficiency to optimise away.
- **Directory first, then manifest.** A crash between the two leaves one of two states, and they are
  not equally bad. Files present with no manifest entry: C7 stays silent about them and a re-install
  simply writes them again — recoverable and harmless. A manifest entry with no files: C7 reports a
  pattern as installed that is not there, and the record lies about the tree. So the directory lands
  first and the manifest records it second.

**The directory itself must appear atomically**, because a half-copied `tcs-<name>/` is a third
state the requirement does not allow for. Copy the pattern into a temp directory **inside the
destination** — `<repo>/.claude/skills/.tcs-<name>.tmp/` — rewrite the frontmatter there, then
`os.rename` it into place. Inside the destination is not a style preference: the catalogue and a
consumer repository need not share a filesystem (measured: the catalogue is `dev=16777245` here and
`$TMPDIR` is `dev=16777234`), and a rename across filesystems raises `Cross-device link`
`[ref: SDD/Risks and Technical Debt/Implementation Gotchas]`. A temp directory beside the final
target is always on the target's filesystem, so the rename is always atomic. The copy into it may
cross filesystems freely, because a copy is not a rename.

**4. C5 reports; C3 offers.** `install.py` is a library with no interactive surface, and ADR-8's
offer needs `AskUserQuestion`, which only a skill can raise. So C5 returns `InstallReport` with
`committed=False` always, and stating "nothing was committed" plus making the offer is C3's
rendering of that report `[ref: SDD/Architecture Decisions/ADR-8]`. T3.3's success criterion
"Report lists writes and states no commit was made" is therefore satisfied by the report *carrying*
every write and `committed=False`; no test in T3.3 should look for an interactive prompt, and no
`AskUserQuestion` belongs in `install.py`.

**5. The catalogue root is derived from `__file__`, never from `CLAUDE_PLUGIN_ROOT`.** Measured
2026-10-05: `CLAUDE_PLUGIN_ROOT` is `None` in a Bash-tool subprocess, and the skill runs this code
by invoking `python3`, so the variable that exists for harness-spawned plugin code is absent exactly
where this module runs `[ref: SDD/Constraints]`. From
`plugins/tcs-patterns/skills/patterns-setup/lib/install.py`, `Path(__file__).resolve().parents[3]`
is the plugin root and `parents[3] / "templates" / "patterns"` is the catalogue — verified to resolve
correctly. `catalogue_dir` is nevertheless a **parameter** with that derivation as its default, for
the same reason `home_dir` is a parameter on C4: a test must be able to point it at a fixture, and
the two namespaces a test cannot reach are the ones that go unverified
`[ref: scripts/observability/report.py:686]`.

**6. `install()` is purely additive. It never removes or overwrites anything under
`tcs-<name>/`.** Settled 2026-10-05, replacing an earlier sentence here which said a stale or
locally edited directory "is removed before the rename". That would have put a silent `rm -rf` of a
user's directory inside the one component whose other tests all prove it only adds, and it is not
what the design says. ADR-4 places divergence detection, the diff **and** the asking all "on
`update`" `[ref: SDD/Architecture Decisions/ADR-4]`, and every acceptance criterion for F8 is
phrased "When the update runs" or "When the update would overwrite it"
`[ref: PRD/F8]`. Nothing in either document puts an overwrite in `install`.

So the three cases are closed, and none of them deletes:

| state of `<repo>/.claude/skills/tcs-<name>/` | `install()` does |
|---|---|
| absent | writes it, and reports it under `installed` |
| present, and current — manifest `version` matches the catalogue `VERSION` **and** manifest `sha256` matches the installed `SKILL.md` | nothing at all; reports it under `unchanged` |
| present, and anything else — stale, locally edited, or both | **nothing at all**; reports it under `failed` with a reason naming `update` as the path |

Three things follow, and all three are improvements:

- **"`install()` never removes a file" is a testable invariant**, provable by a digest over the
  installed tree before and after, in the same shape as C4's write-nothing proof but one step
  weaker. Every test in T3.3 can carry it, which is far stronger than reasoning about a delete
  being correct.
- **The `os.rename`-onto-a-non-empty-directory problem dissolves.** The rename's target is absent in
  the only case that reaches it, so the atomic-appearance mechanism needs no special case and no
  removal step.
- **T3.4's scope becomes crisp**: `update()` owns *every* present-but-not-current case, which is
  exactly where the interactive prompt and the diff belong, and where the default-to-skip rule
  protects local work `[ref: SDD/Runtime View/Error Handling]`.

The one delete `install()` may perform is of **its own** leftover `.tcs-<name>.tmp/` from a crashed
earlier run. That directory is this installer's, never the user's, and removing it is required for
the next run to proceed. Worth distinguishing in the tests: a leftover temp directory is cleaned, a
user's installed pattern never is.

The user-visible consequence, which C3 renders: running `install` after the catalogue has moved on
reports some patterns as needing `update` rather than silently refreshing them. That is the correct
separation — F8 exists precisely because refreshing is a different operation with a different
safety question — and C7's advisory already tells the user that `update` is the move
`[ref: SDD/Runtime View/Primary Flow, step 9]`.

**7. `bundle` is a parameter, with the same derived default as `catalogue_dir`.** Added
2026-10-05 by T3.3's implementer, which found the gap and said so rather than burying it: the
signature here omitted `bundle` entirely while `manifest.upsert()` requires it with no default
`[ref: SDD/Interface Specifications/Data model: the manifest (C6)]`, so there was no legal way to
call C6 from C5 as specified. Its own resolution — deriving the value internally from this plugin's
`.claude-plugin/plugin.json` — was reasonable and is kept **as the default**, but not as the only
route, for two reasons:

- **It would be the one input to `install()` a test cannot drive.** `catalogue_dir` and C4's
  `home_dir` and `own_installed` are parameters for precisely that reason, and the argument that a
  production caller would never want to override `bundle` is equally true of `catalogue_dir` — the
  parameter exists for the test, not for production.
- **CI bumps `plugin.json` on merge** `[ref: scripts/ci/bump-and-push.sh]`. A test that asserts the
  manifest's `bundle` line while the value is read from the real file breaks on every version bump,
  and the failure would arrive looking like a manifest defect rather than a stale literal. No test
  asserts it today, which is why this was invisible; the manifest records it, so one eventually
  will.

`update()` needs the same value, so settling it here rather than in T3.4 means that task inherits a
decided answer instead of repeating the derivation
`[ref: plan/phase-3.md, T3.4's three pre-dispatch gaps]`.
9. **Next session.** The installed patterns appear in the listing and route automatically; C7 finds
   the manifest current and says nothing.

### Error Handling

| Error | Detected by | Behaviour |
|---|---|---|
| Not inside a git repository | C3, step 1 | Abort before any read of the target. Message names the resolution. |
| An unparseable `package.json` / `pyproject.toml` | C2 | **Never fatal; the dependency *read* is skipped, not the manifest.** Corrected 2026-10-05 -- this row read "A broken manifest is not a signal", which measurement contradicts: a rule keying on a manifest's **existence** keeps firing, so a `pyproject.toml` holding `[project` still yields `python-project`, a garbage `go.mod` still yields `go-idiomatic`, and a `tsconfig.json` holding `{` still yields `typescript-strict`. Only content-derived signals vanish. One further deliberate case: `_pyproject_deps_and_pytest` matches `[tool.pytest.ini_options]` by regex **before** parsing, so a file `tomllib` rejected still opens `q3_test_quality` -- a typo in `pyproject.toml` has not stopped the repository running pytest. A broken manifest never poisons its siblings. The file is listed in `manifests_walked` so its absence from dependency evidence is explicable. All six legs are pinned by tests as of 2026-10-05 and each was mutation-checked against the guard clause it covers `[ref: tests/test_patterns_detect.py, "An unparseable manifest"]`. |
| Target repository unreadable in part | C2 | Scan continues over what is readable; the report names what it could not read, so a thin proposal is never silently a permissions artefact. Unimplemented: `detect.py` skips unreadable paths silently. T5.1a's `unreadable` key is specified to carry them (2026-10-06). |
| Name collision | C4, step 6 | That pattern is not written; the collision is reported with both locations; the remaining patterns still install (F5's fourth criterion). No rescan. |
| `SKILL.md` without a frontmatter `name:` line, **in the catalogue being installed** | C5 | `InstallError`, nothing written for that pattern. Prevents installing under the unprefixed name. |
| A `SKILL.md` **in a scanned namespace** that cannot be read or carries no usable `name:` | C4, step 6 | Skipped, never fatal, and reported through `GuardReport.skipped` as `(path, reason)`. Four inputs reach this and each needs a distinguishable reason: unreadable, no frontmatter block, no `name:` key, empty `name:`. Added 2026-10-05; the row above it is the same condition with the opposite behaviour, and the difference is deliberate rather than an inconsistency. **The file C5 refuses to install is ours; the file C4 skips belongs to a third party.** A broken file in our own catalogue is a defect in this repository and must stop that pattern loudly, because installing it would register the pattern under the unprefixed name and silently defeat ADR-1. A broken file in somebody else's plugin is not ours to fix and must not stop this repository's install — the same stance `detect.py` takes for an unparseable manifest two rows above. It is reported rather than swallowed because a name the guard could not check is a name it cannot vouch for, and a caller that cannot see the omission cannot warn about it. Measured: zero of the 259 real `SKILL.md` files on this machine fail to parse, so every one of the four cases is fixture-only `[ref: SDD/Interface Specifications/Data model: the three namespaces (C4)]`. |
| Write fails mid-selection | C5 | Patterns already written stay; the manifest records exactly what succeeded. Re-running `install` is idempotent by name and hash. |
| Manifest present but unparseable | C6 | Treated as `MISSING` for the advisory and reported verbatim by `status`. Never silently overwritten — overwriting it would erase the record of what is installed. |
| Manifest present but unreadable (`OSError`, for example permissions) | C7 | Not `MISSING`: `manifest.read` lets the `OSError` through, the reporter catches only `ManifestUnparseableError`, and `main()`'s catch-all prints `patterns_drift: <error>` to stderr, nothing to stdout, exit 0. The advisory shows nothing (fail-open). Measured 2026-10-06 with a mode-000 manifest. |
| Installed pattern diverges from its hash | C5 on `update`, **not `install`** | The user is asked per pattern with a unified diff (ADR-4). Default is to skip, so an unanswered prompt cannot destroy local work. **This row is T3.4's, not T3.3's** — noted 2026-10-05 after T3.3's gate flagged that it reads as a third `install()` obligation and would contradict "no `AskUserQuestion` in `install.py`" if anyone tried to satisfy it there. `install()` detects divergence only to the extent of declining to call a locally-edited pattern `unchanged`; prompting about it is `update()`'s. **That gap is now closed** — `update()`'s signature, its three-state table and its eight decisions are at `[ref: SDD/Interface Specifications/Data model: the update path (C5's second verb)]`, settled before dispatch the same way C5's four were settled before T3.3. The diff this row refers to has two normative properties as of decision 4: the installed file is the `from` side, so the user's own edit appears as a deletion, and both file labels are populated. |
| Catalogue `VERSION` missing or non-numeric | C7, C9 | C7 reports the pattern as unknown rather than drifted; C9 fails the gate. A pattern without a version cannot be distributed. |
| Pattern name given to the catalogue reader is unknown | C8 | Lists the 21 available names. |
| Invalid CLI arguments: an `install` pattern name not in the catalogue (`remove` takes any name, since a pattern deleted upstream is exactly what `status` sends a user to remove), `--answers` naming a closed gate or a pattern its gate does not settle, `--force` naming a pattern not being removed | C3's CLI | Exit 2, stdout empty, nothing written. Added 2026-10-06 `[ref: SDD/Interface Specifications/Process contract: the CLI the skill drives]`. |
| Manifest unparseable or unreadable when `install`, `update` or `remove` runs through the CLI | C3's CLI | Exit 3 before the guard or any write, stderr naming the file and pointing to `status`. `status` itself still exits 0 and reports the manifest's state and error verbatim. Added 2026-10-06. |
| `update --accept` names a pattern the manifest does not list | C3's CLI | Exit 3 before `update()` is called. A misspelt name would otherwise silently decline the pattern the user had just approved. Added 2026-10-06. |
| `remove` names a pattern the manifest does not list | C5 `remove()` | `refused`, and nothing is deleted. `remove` deletes only what the manifest records. Added 2026-10-06. |
| `remove` names a pattern whose installed `SKILL.md` no longer matches the manifest hash | C5 `remove()` | `refused` unless named by `--force`, the same consent ADR-4 requires before `update` replaces an edit. Added 2026-10-06. |
| `remove` finds a `.<installed_as>.replaced` stash with the pattern directory absent, or a symlink or file where the pattern directory should be | C5 `remove()` | `refused`, naming the path and the resolution. That stash is the user's only copy, and a link or file is not something `install()` wrote. A stash beside a **present** directory is debris and is deleted with it. Added 2026-10-06. |
| `remove` interrupted between its steps | C5 `remove()` | Either the directory is absent while the manifest still lists it and `.<installed_as>.removing` is present, or only the `.removing` debris is left. `status` shows both states. Re-running `remove` completes the first; in the second the manifest no longer lists the pattern, so a re-run is refused by rule 1, and `status` reports the `.removing` entry as debris that is safe to delete. Added 2026-10-06. |
| A catalogue `SKILL.md` whose `description:` cannot be parsed | C3's CLI, `scan` | That pattern's `listing_cost` is `null`, and the skill shows "unknown", never 0. Added 2026-10-06. |

### Complex Logic

The gating is the only conditional structure in the design worth tracing, because the asymmetry
between "decidable" and "intent" is where it can go quietly wrong. Traced against the validated
Python web service — generically: a server-rendered web service with cookie sessions, a large test
suite, and a hand-rolled append-only event store.

```
INPUT SIGNALS FOUND
  pyproject.toml: dependencies -> fastapi, jinja2, pyjwt, bcrypt
  pytest.ini present, tests/ with 150+ files
  src/<feature>/events.py in ~15 feature directories
  src/event_store/ directory, schema columns seq / occurred_at
  no tsconfig.json, no go.mod, no manifest.json, no obsidian dep
  no @testing-library/*, no render( / screen. in any test

STEP 1 — auto set, from stack facts only
  python-project        <- .py files + pyproject.toml                      PROPOSE (evidence: pyproject.toml)
  typescript-strict     <- no tsconfig.json                               no
  go-idiomatic          <- no go.mod                                      no
  obsidian-plugin       <- no manifest.json with minAppVersion            no
  mcp-server            <- no mcp SDK dependency                         no
  react-testing         <- no react                                       no
  frontend-testing      <- no render evidence  (TRAP 2 holds)             no
  testing               <- pytest.ini + tests/                            BASELINE, surface:false (TRAP 1)

STEP 2 — gates, deciding only whether to ask
  q1_backend       fastapi in [dependencies]  (TRAP 4: not devDependencies) -> OPEN
  q2_architecture  q1 open, and content signals: events.py per module,
                   event_store/ dir  (TRAP 6: no broker dependency exists)   -> OPEN
  q3_test_quality  pytest detected                                           -> OPEN
  unrecognised_stack = false

STEP 3 — questions actually asked: three. Answers given by the user:
  Q1 -> REST API conventions, Browser-facing auth/session boundary, 12-factor
        (user did NOT pick OAuth/OIDC, and nothing proposed it — TRAP 3 holds:
         pyjwt + bcrypt are present and are not federated-identity evidence)
  Q2 -> Event-driven, Event sourcing            (not DDD, not hexagonal, not functional)
  Q3 -> neither

STEP 4 — selection, and every one of the 21 decided exactly once
  install: python-project (auto), testing (baseline),
           api-design, bff-entry-points, twelve-factor (Q1),
           event-driven, event-sourcing (Q2)                            = 7
  declined by question: secure-oauth-oidc, observability, node-service,
           ddd, hexagonal, functional, mutation-testing,
           test-design-reviewer                                          = 8
  excluded by stack fact: typescript-strict, go-idiomatic, obsidian-plugin,
           mcp-server, react-testing, frontend-testing                   = 6
  not reached (gate stayed shut):  none here -- all three gates opened   = 0
  7 + 8 + 6 + 0 = 21  ✓  no pattern decided twice, none left undecided

STEP 5 — names written: tcs-python-project, tcs-testing, tcs-api-design,
         tcs-bff-entry-points, tcs-twelve-factor, tcs-event-driven,
         tcs-event-sourcing.  Listing cost: 7 descriptions in this repository,
         0 in every other.
```

The arithmetic in step 4 is not decoration. "Each of the 21 is decided exactly once" is F3's fourth
acceptance criterion, and summing the disjoint outcomes to 21 is how a fixture asserts it.

**There are four outcomes, not three — settled 2026-10-04 (Marcus), and this walkthrough is why
the fourth was missed.** Every gate opens in the stack traced above, so every one of the thirteen
gate-settled patterns is either installed or declined and the fourth set is empty. That is not the
normal case. Computed across all 26 detection fixtures: a three-set partition covers the 21 in
**zero** of them, because a pattern settled by a gate that stayed **shut** falls outside all
three — nobody was asked, so it is neither installed nor declined by a question, and no stack fact
excluded it either. **Every one of the 26 leaves patterns unaccounted for**: fifteen leave 13,
four leave 11, four leave 8, and three leave 2 -- the best case in the corpus -- since no
fixture opens all three gates. Re-measured 2026-10-04 across the full corpus with the
gate-to-pattern mapping taken from the gate table above rather than from `detect.py`. The
figure this paragraph carried until then, "twenty of the 26 leave 8 or 13", was wrong twice
over: it undercounted, and "8 or 13" omits the eleven-pattern bucket that the four
test-framework-only fixtures produce. It was computed while the corpus was smaller, and
survived the corpus growing 18 -> 26 in the same session.

So the fourth outcome is **not reached: the gate that settles it stayed shut**, and the invariant
is `installed + declined-by-question + excluded-by-stack-fact + not-reached = 21`.

The distinction is worth a category rather than being folded into the third, because the two
explain differently to the user. "`typescript-strict` does not apply — no `tsconfig.json` anywhere"
is a statement about the repository. "You were not asked about DDD, because nothing indicated a
backend service" is a statement about the **detection**, and a user who disagrees with it should
be able to see it and say so. Collapsing them would put both under one heading and hide the second.

This does not strain F3's own wording, which reads "decided exactly once — by a file signal or by
one question, never both": a gate that stayed shut *is* a file signal deciding the matter. The
four-way split reports which file signal decided, rather than adding a mechanism F3 does not have.

## Deployment View

### Single Application Deployment

Nothing is deployed. Three distribution paths, all existing:

1. **The plugin** reaches users through the marketplace. `2.0.0` is published by the normal CI
   bump on merge (CON-6). A user on `1.x` keeps 21 plugin skills until they update; after updating
   they have none until they run the setup, which is what makes this a major version.
2. **The patterns** reach a repository only by the setup writing them, and reach other developers
   only if the files are committed (ADR-8). An uncommitted install is per-developer by
   construction.
3. **The advisory** reaches a session through the existing SessionStart hook in `tcs-git-helpers`,
   which already composes segments; this adds one.

Rollback: the patterns are files in the repository, so `git revert` removes them, and `remove`
takes them out with their manifest entries. Rolling the plugin back to `1.x` restores the 21 plugin
skills, at which point an installed `tcs-<name>` and a plugin `<name>` coexist — different names,
no collision, duplicated content. Named in Technical Debt rather than solved.

### Multi-Component Coordination

One coordination point: `tcs-patterns` writes the manifest, and `tcs-git-helpers` reads it to build
the advisory. The dependency is one-way and through a documented file format, not through code.
`tcs-git-helpers` must tolerate `tcs-patterns` being absent or at `1.x` — the advisory segment
stays silent when `patterns_drift.py` cannot be found.

**How the segment finds `patterns_drift.py` — decided 2026-10-06 by Marcus, before T4.3 was
dispatched.** This section said what happens when the script cannot be found, but not how it is
looked for. The segment resolves it from its own location and nothing else: no
`installed_plugins.json`, which is an undocumented Claude Code file, and no `CLAUDE_PLUGIN_ROOT`,
which does not reach every context. It tries two layouts:

```
$_SCRIPT_DIR/../../tcs-patterns/scripts/patterns_drift.py         # repository and marketplace layout
$_SCRIPT_DIR/../../../tcs-patterns/<version>/scripts/patterns_drift.py  # plugin cache layout
```

When several cached versions carry the script, the highest numeric version wins, compared
field by field because BSD `sort` has no `-V`. A `1.x` copy has no script, so it is not a
candidate. The accepted risk is that a stale newer copy left in the cache wins over the active
install. The segment also runs nothing at all unless `<repo>/.claude/skills/.tcs-patterns-manifest`
exists. That is the cheap test that keeps a repository without patterns off the Python path. It matters
because of two constraints in the hook's own header: "CON-4: fail-open" (not this SDD's CON-4, which
is the frontmatter-name constraint) and a p99 budget of 300 ms, against a first-exec cost on macOS
of 151-286 ms.

## Cross-Cutting Concepts

### Pattern Documentation

The bundle-versioning pattern (spec 012) is reused at a finer grain. Its four parts map as:

| spec-012 part | Here |
|---|---|
| Source of truth in the plugin | `templates/patterns/<name>/VERSION` — per pattern, not per bundle |
| Mirrored in the consumer repo | one entry per pattern in `.tcs-patterns-manifest` |
| Drift-check skill | `patterns_drift.py` plus the advisory segment, reporting per pattern |
| CI gate on the maintainer contract | the per-directory rule in the existing multi-bundle gate |

The grain change is the only deviation and it is forced: a per-bundle marker would raise an
advisory in every repository for a change to one pattern, which F7's second criterion forbids.

### User Interface & UX

The interaction is three screens at most: a proposal with evidence, up to three multiSelect
questions, a confirmation. The bar set by the PRD is `claude init`, not an interview, and the gates
are what enforce it — a repository with no server framework and no tests sees one screen.

Costs are shown per entry at the moment of choosing, in characters of listing, because that is the
scarce resource (CON-1) and the user cannot otherwise see it.

### System-Wide Patterns

- **Nothing is written before every check has passed.** C4 runs to completion across the whole
  selection before C5 writes anything, mirroring `observability-setup`'s abort-before-write
  discipline.
- **Atomic single-file writes.** `.tmp` then `mv`, as `install_files.sh` does for its marker. Note
  the known hazard: `$TMPDIR` and the repository may be on different filesystems, so the temporary
  file is created in the destination directory, never in `$TMPDIR`.
- **Reading is free, writing is announced.** Every write is listed in the final report, and the
  report states that nothing was committed.
- **No network, no services, no environment variables.** The plugin root is resolved the way
  `install_files.sh` does it — `CLAUDE_PLUGIN_ROOT` when present, otherwise relative to the
  module's own location — because that variable does not reach every context.

## Architecture Decisions

### ADR-1: Installed patterns always carry a `tcs-` name prefix — CONFIRMED

**Decision.** A pattern installed into a repository is named `tcs-<pattern>`: the directory is
`.claude/skills/tcs-ddd/` and the frontmatter reads `name: tcs-ddd`. The catalogue keeps the plain
name; the installer rewrites the one frontmatter line (CON-4).

**Rationale.** Collisions become structurally impossible within our namespace rather than merely
detected. There are zero exact collisions today — the 21 names clash with no other plugin skill and
with none of the user's seven global skills — so the alternative (plain names plus a guard) would
have worked today and been fragile tomorrow: a repository is free to create a skill called
`testing` or `observability` at any time, and with plain names that repository could then never
install that pattern at all. The prefix also makes provenance visible at the point of use: `/tcs-ddd`
is identifiably ours, `/ddd` is not.

**Trade-offs accepted.** The user types a name they did not choose: `/tcs-ddd` in the slash menu,
and `skillOverrides: { "tcs-ddd": "name-only" }` when reaching for the per-skill dial that CON-2
makes available — so the key never reads quite like the thing it refers to. Seven characters are
added to each entry's listing cost, which is a real if small charge against the budget this spec
exists to relieve. And the prefix does nothing about the four near-misses (`api-design` versus
`api-contract-design`, `frontend-testing` versus `frontend-patterns`, `observability` versus
`observability-setup`, `test-design-reviewer` versus `test-practices`); in fact `tcs-api-design`
sits no further from `api-contract-design` than `api-design` did. Near-misses are a description
problem and remain one.

**Consequence for F5.** The collision guard is still built and still tested, but it now rarely
fires. Its criteria are unchanged — a repository could hold a `tcs-ddd` of its own — and it remains
the mechanism that keeps a partial install coherent.

### ADR-2: Detector and installer in Python; only the advisory segment in bash — CONFIRMED

**Decision.** `detect.py`, `guard.py`, `install.py`, `manifest.py` and `patterns_drift.py` are
Python **3.11 or newer**, standard library only. The only shell this work adds is the advisory
segment inside the existing `session-start-brief.sh` and the per-pattern rule inside the
existing CI gate script.

**The 3.11 floor, decided 2026-10-03 by Marcus.** `tomllib` entered the standard library in
3.11, and `pyproject.toml` must be parsed. No floor was stated anywhere in this document
before now, which is the root cause of a real defect: T2.2's implementer, facing a question
the specification had not answered, wrote a regex fallback for older runtimes. Measured, that
fallback matched `dependencies\s*=\s*\[(.*?)\]` across the **whole file** rather than the
`[project]` table, so a `pyproject.toml` carrying an unrelated `[tool.x] dependencies = ["mcp"]`
array produced a false `mcp-server` proposal — citing `pyproject.toml: dependencies.mcp`, a
confidently wrong evidence string that the evidence invariants cannot catch because the path
genuinely exists. A silently wrong answer, which is worse than no answer.

So: **detect it and refuse, loudly.** On a pre-3.11 interpreter the setup must fail with a
message naming the required version, never degrade to a weaker parser. A consumer on a stock
macOS `python3` gets an actionable error instead of a wrong proposal. The alternatives were
rejected: scoping the regex to `[project]` keeps every other regex-TOML trap (multi-line
arrays, comments, inline tables), each needing its own fixture; and skipping dependency
extraction on pre-3.11 would silently disable the `q1_backend` gate for `pyproject`-only
repositories, which is the more damaging loss.

**Rationale.** Two of the seven traps are structural-parsing problems. Trap 4 requires
distinguishing `dependencies` from `devDependencies` inside JSON, and trap 5 requires walking
nested manifests while excluding vendored trees. In bash that means either a hand-rolled JSON
reader built from `grep` and `sed` — which is how a detector comes to believe a package named
`"express"` in a comment is a dependency — or a `jq` dependency this repository cannot assume.
Python also steps around CON-5 entirely for all new code: no `stat -f` divergence, no BSD-only
`[[:<:]]`, no absent `timeout`. And it puts the detector in the repository's own test home, where
`pytest` can parametrize over fixture directories and call the detection function directly, which
is what the PRD's top risk demands.

**Trade-offs accepted.** The design diverges from `install_files.sh`, the installer it otherwise
copies, so the structural template is followed in spirit rather than line by line — the subshell
sentinel in particular has no Python equivalent and its purpose (bounding a sentinel environment
variable) does not apply. Two languages now implement installers in this repository. That is
already true of `drift_check`, which ships as both `.sh` and `.py`, so the precedent exists.

### ADR-3: One `VERSION` file per pattern in the catalogue — CONFIRMED

**Decision.** `templates/patterns/<name>/VERSION`, a single line holding a bare integer, set by the
maintainer. No central catalogue file.

**Rationale.** F7's second criterion — a change to a pattern this repository did not install says
nothing — requires per-pattern versions. Given that, the version can live in a central file keyed
by pattern or in each pattern's own directory. Per-directory wins on the CI gate: "every changed
pattern directory must contain a changed `VERSION`" needs no parsing, no table and no per-pattern
registration, and a pattern added later is covered by the rule that already exists. A central file
would need the gate to diff individual lines to answer the same question, and bumping the wrong
line would pass.

An integer rather than semver because a prose body has no API surface for "breaking" to describe,
and the only question asked of it is whether two numbers differ.

**Trade-offs accepted.** 21 extra files. No single place to read the whole catalogue's state —
`status` has to walk the directories, which is cheap but is a walk rather than a read.

### ADR-4: Content hash at install, unified diff on conflict — CONFIRMED

**Decision.** The manifest records a SHA-256 of the installed `SKILL.md`. On `update`, a pattern
whose file no longer matches its hash is reported as diverged, and the user is asked per pattern
with a unified diff available. The default is skip.

**Rationale.** Without a hash the installer cannot distinguish "never touched" from "deliberately
adapted", and its only safe behaviour would be to never overwrite — which leaves a diverged pattern
permanently stale and the advisory repeating every session. With the hash, overwriting is safe
precisely when it is uninteresting. The diff costs three lines of `difflib` given ADR-2, so the
machinery being bought here is the hash; the diff is nearly free once it exists.

**Trade-offs accepted.** The hash covers only `SKILL.md`. A locally edited `reference/` file is not
detected, and `update` will replace it. This is a deliberate limit, recorded in the Interface
Specifications so it is not discovered later. Hashing 80 files per pattern to catch a rarer case
costs more than it returns.

### ADR-5: An unrecognised stack gets no proposal and no default — CONFIRMED

**Decision.** When no stack fact matches, `unrecognised_stack` is true, nothing is proposed, and the
setup says so plainly. It does not fall back to a stack-independent selection. Crucially,
`unrecognised_stack` does not suppress the gates: a repository in a language none of the 21 cover
that nonetheless shows a ports-and-adapters shape still reaches Q2.

**Rationale.** The validated set deliberately included a desktop application in a language no
pattern addresses, and the right answer there was nothing — a default selection would be the
product guessing, which is what the whole spec is replacing. But "nothing detected" and "nothing
applicable" are different states: architectural intent is language-independent, and gating Q2 on a
recognised language would deny patterns to exactly the repositories whose architecture is
deliberate. Separating the two states is the point of the flag existing at all.

**Which set the flag reads — decided 2026-10-03.** `unrecognised_stack` is computed from `auto`
alone. `baseline` is ignored. This matters because `testing` is one of the eight stack facts and
would otherwise make almost any repository "recognised": trap 1 exists precisely because
`testing` fires in nearly every repository with a test suite and therefore tells the user
nothing. A signal declared non-discriminating must not flip the headline state either, or adding
one test file to a desktop application in an uncovered language changes the message from "nothing
here fits your stack" to "recognised" while the proposal stays empty. It also keeps AC-4
satisfiable: `auto: []` with `unrecognised_stack: true` is reachable for any uncovered stack,
with or without tests, so the true-negative fixture does not have to be artificially testless.
The validated set's uncovered stack was a desktop application whose test situation the study
never recorded, which is how the ambiguity survived into the plan.

**Trade-offs accepted.** A user in an unsupported stack may see a question and then a short
proposal, which can read as the tool straining to be useful. The alternative — silence — denies a
real case. With the clause above, such a user may also see `baseline: [testing]` reported
alongside `unrecognised_stack: true`; those two are consistent, not contradictory, and C3 words
the message from the flag.

### ADR-6: Manifest at `.claude/skills/.tcs-patterns-manifest` — CONFIRMED

**Decision.** The manifest lives beside the installed skills, as decided before this SDD began.
Format TOML (see Interface Specifications).

**Rationale and evidence.** It was verified this session that a non-skill dotfile placed in
`.claude/skills/` produces no warning and is not mentioned by the skill discovery walk at all — the
walk reports only directory entries it skips for reserved names, and the manifest is not one.
Beside the skills is also where a reviewer looks: the file and the thing it describes appear in the
same diff. The PRD listed this as an open question in error; it was already settled, and the
evidence is recorded here rather than the question being re-asked.

**Trade-offs accepted.** A non-skill file inside a skills directory is a small structural
impurity, and it depends on discovery continuing to ignore plain files there. The behaviour is
measured, not assumed, but it is the harness's behaviour and not our contract.

### ADR-7: The Obsidian rule stays duplicated, with a consistency test — CONFIRMED (amended 2026-10-05)

> **Amendment.** The decision stands: two independent implementations plus a test, no shared
> source. What was wrong is the framing below — this ADR described the two as answering one
> question. Since 2026-10-05 they answer two distinct ones, the hook file-scoped and
> `detect()` repo-scoped, and the test asserts a deliberate divergence as well as agreement.
> Corrected in *Rationale* and in AC-14. The amendment is a consequence of the file-scoped
> ruling, not a reopening of this ADR's choice.

**Decision.** `scripts/block-eslint-disable.sh` keeps its own Obsidian gate in bash, `detect.py`
has its own, and `tests/test_obsidian_rule_agreement.py` asserts that both answer identically over
the detection fixtures.

**Rationale.** The hook is a write-time guard: it must work standalone, and making it depend on a
file outside itself is the failure mode issue #163 already records twice in this repository — a
plugin file referencing something by a path that resolves to nothing at runtime. Two independent
implementations with a test that fails when they disagree gets the safety of a shared source
without the coupling. The test is also the cheaper artefact: it needs no new abstraction, only the
fixtures the detection suite builds anyway.

**The two answer different questions — corrected 2026-10-05.** This ADR originally read as two
implementations of one question, "is this an Obsidian plugin?". They are not. The hook answers
a **file-scoped** question — is the file about to be written inside a plugin — because that is
what a write-time guard must decide. `detect()` answers a **repo-scoped** one — does this
repository contain a plugin anywhere — because that is what an install decision needs. The two
coincide for every detection fixture, and for any write inside a nested plugin. They diverge,
and are asserted to diverge by name, for a write **outside** a nested plugin in a repository
that contains one elsewhere.

The distinction was forced by measurement rather than chosen: while both rules asked the
repo-scoped question, both classified **this** repository as an Obsidian plugin, because six
`manifest.json` files carrying `minAppVersion` live here as test fixtures. The hook therefore
denied every write of a non-Markdown file containing `eslint-disable` anywhere in the tree.
Both rules agreed, so AC-14 was satisfied while both were wrong — **agreement is not
correctness, and an agreement test cannot tell the two apart.** That is the limit of what this
ADR's mechanism buys, and it is worth stating plainly next to the mechanism itself.

**Trade-offs accepted.** The rule is written twice, so a change must be made twice. The test turns
that from a silent divergence into a failing build, which is the trade being bought. It does not
prevent someone changing both in the same wrong way.

### ADR-8: Install offers to commit and never commits — CONFIRMED

**Decision.** After writing, the setup reports what it wrote, states that it did not commit, and
offers to. Declining leaves the files uncommitted.

**Rationale.** Decided before this SDD; recorded for completeness. It matches
`install_files.sh`, which deliberately does not auto-commit (spec-012 PRD M10 AC5), and the
selection is a project-level decision worth sharing and reviewing. Writing to someone's history
unasked is a different class of action from writing files.

**Trade-offs accepted.** An uncommitted install is per-developer, so the inheriting teammate
persona gets nothing until someone commits — and the drift advisory will then differ between
developers in the same repository. The `status` verb is what makes that visible.

### ADR-9: The existing multi-bundle CI gate gains a per-pattern rule — CONFIRMED

**Decision.** `check-hook-bundle-version.sh` keeps its bundle table for the existing three bundles
and gains one additional rule: for every changed file under
`templates/patterns/<name>/`, that pattern's own `VERSION` must be in the same changeset. No new
script, no new workflow.

**Rationale.** The gate was already generalized in spec-019 from one bundle to a table of them, and
its workflow already runs on every pull request. The patterns bundle does not fit the table's shape
— the table asks "did this bundle's single marker change", which for 21 independently versioned
patterns would pass when the wrong one was bumped, leaving a pattern silently stale. That is the
precise failure the gate exists to prevent, so the rule is per-directory instead. It is a sed
extraction and a membership test; see Implementation Examples.

**Trade-offs accepted.** The script now has two rule shapes rather than one, so its own structure
is slightly less uniform. The alternative — a second script and a second workflow — splits a
single contract across two places, which is worse.

## Quality Requirements

| Quality | Requirement | How it is measured |
|---|---|---|
| Listing footprint | `tcs-patterns` contributes at most 2 skill descriptions to a session | `python3 scripts/observability/report.py` reports the plugin's skills; a session's listing confirms |
| Relocation fidelity | every pattern file is a rename with unchanged content | `git log --follow` survives, and `git diff -M --name-status` reports `R100` for all 80 files. Not `--summary`, which renders a rename as ` rename a/b (100%)` and never emits the token `R100` -- measured 0 matches against 80. Verified at the T1.1 commit, where the claim is still meaningful; against `HEAD` it reads 0 forever |
| Interaction cost | zero questions for a repository with no server framework and no test framework; never more than three | the fixture suite asserts `gates` for those cases |
| Detection correctness | every fixture classified exactly as declared, extra proposals failing as loudly as missing ones | `pytest tests/test_patterns_detect.py`, normalised-report equality |
| Trap coverage | all seven traps have a fixture that fails if the trap is reintroduced | one fixture per trap, each naming it in `why` and `must_not_propose` |
| True negative | a stack none of the 21 cover yields nothing | a fixture with `auto: []` and `unrecognised_stack: true` |
| Scan cost | the scan reads no vendored tree and completes without a visible pause on a repository of this one's size — 1114 Python files, 457 shell files | measured on this repository; the excluded-directory list is asserted by a fixture containing a populated `node_modules` |
| Write safety | nothing is written until every name has been checked | a guard test with one colliding and two free names asserts the two are written and the third is not |
| Idempotency | a second `install` with the same selection writes no change | hash comparison before write; asserted by test |
| Advisory precision | a changed pattern raises an advisory only where installed, and in every such repository | drift test over a manifest holding a subset |
| Portability | all new Python runs on macOS and Linux; the two shell edits stay bash 3.2 and shellcheck-clean | CI runs both platforms per leg, read per leg and not from the run verdict |

#### The seven traps, numbered

This document refers to a trap by number **13 times across 12 lines**, citing traps 1 through 6
and never 7, and T2.1 requires one fixture per trap naming it in `why`. Until now the numbering
existed only as the order of a prose sentence in `[ref: PRD/Supporting Research]` -- narrative,
not contract -- so trap 7 was recoverable only by elimination. The order below is
the one already in use -- it was checked against every existing numeric reference in this document
before being written down, not chosen.

| # | Trap | What must not happen | The rule that defends it |
|---|---|---|---|
| 1 | A near-universal signal with no discriminating power | `testing` presented as a recommendation | detected, but `baseline` with `surface: false` |
| 2 | UI testing inferred from a directory name | `frontend-testing` or `react-testing` firing on a `ui/` directory, or on jsdom alone | require render evidence: `render(`, `screen.`, `fireEvent`, `userEvent` |
| 3 | Federated identity inferred from session tooling | `secure-oauth-oidc` firing on jwt / bcrypt / pyjwt | require an AS/client/RP library, or `.well-known`, or `redirect_uri` + `client_id` |
| 4 | A development dependency read as a runtime one | a server framework present only to drive a test harness opening Q1 | server frameworks count only from `dependencies` |
| 5 | A workspace root whose manifest declares nothing | the real signal three levels down being missed, or a vendored tree being read as source | walk nested manifests, excluding `node_modules`, `.venv`, `venv`, `vendor`, `.git`, `.claude` |
| 6 | Architecture that is routinely hand-rolled | `event-driven` or `event-sourcing` auto-proposed, or false-negatived by manifest-only detection | content signals gate Q2 only; never auto-propose |
| 7 | A virtual-environment check that knows one spelling | `venv` recognised and `.venv` missed, or the reverse | both directory names tested |

Trap 1 is the only one that changes a report *field* rather than suppressing a proposal, which is
why it appears in the detection-report contract above and not only here.

**Traps 3, 4 and 6 are designed out, not defended by code — recorded 2026-10-03.** All three
concern patterns settled by a gated question, and **no gate-settled pattern is ever emitted by
the detector**: `detect.py` cannot name `secure-oauth-oidc`, `node-service`, `ddd`,
`event-driven`, `event-sourcing`, `hexagonal`, `functional` or any of the other gate-settled
patterns, verified by grep. The trap cannot occur, so there is nothing for a rule to defend.

This matters for how their fixtures are read. `trap-03`'s `must_not_propose:
["secure-oauth-oidc"]` passes because the pattern is unreachable, not because any code
distinguishes protocol evidence from session tooling. That is **not** a vacuous guard: it is a
forward regression guard, and it fails the moment anyone makes a gate-settled pattern
auto-proposable — which is the only way the trap could return. Same for traps 4 and 6.

One consequence to state plainly rather than leave as a loose end: trap 3's protocol-evidence
definition — an AS/client/RP library, or `.well-known`, or `redirect_uri` with `client_id` —
**has no implementer and is not assigned to any task**. It is research residue from when
auto-detecting OIDC was still on the table; the design answered the trap by never auto-proposing
the pattern at all. It is retained because it documents what *would* be required if that ever
changed, and a future reader should not go hunting for the code that implements it. Found by the
T2.2 spec-compliance review, which checked phases 3, 4 and 5 and T5.1 for an owner and found
none.

## Acceptance Criteria

System-level and **group-level, not 1:1**: 18 criteria here cover the PRD's 36. Every one of the
ten Must features is traced, which was verified mechanically rather than by
eye. Three PRD criteria had no counterpart on the first pass — the per-entry listing cost and the
baseline-not-surfaced rule from F2, and the "a second party can determine currency" rule from F6 —
and AC-16 and AC-17 were added to close them. The remaining compression is one SDD criterion
standing for two or three PRD criteria that assert the same behaviour from different angles.

| # | Criterion | PRD trace |
|---|---|---|
| AC-1 | After the relocation, a session's listing contains at most 2 `tcs-patterns` descriptions; the inventory walk falls from 98 entries to 77 with no `tcs-patterns` skill remaining, and `templates/patterns/` holds 21 `SKILL.md` files checked directly against the tree | F1 |
| AC-2 | All 80 pattern files are reported by git as renames at 100% similarity; no file cites a path above its own pattern directory, and every remaining relative link resolves | F1 |
| AC-3 | For every detection fixture, the normalised report equals `expected.json` exactly | F2, F3 |
| AC-4 | A fixture with a populated `node_modules` and an empty root `dependencies` still finds the nested signal, and does not report anything from the vendored tree | F2, trap 5 |
| AC-5 | A fixture with no server framework and no test framework yields all gates closed and no questions | F3 |
| AC-6 | For every fixture and every combination of answers to the open gates, the **four** outcome sets — installed, declined by question, excluded by stack fact, and **not reached because its gate stayed shut** — are pairwise disjoint and sum to 21. Said "three" until 2026-10-04, which no fixture could satisfy: a three-set partition covers the 21 in **zero** of the 26, because a pattern behind a closed gate falls outside all three `[ref: SDD/Runtime View/Complex Logic, "There are four outcomes, not three"]` | F3 |
| AC-7 | An install writes exactly the chosen patterns under `tcs-<name>`, each with `name: tcs-<name>` in its frontmatter, and the manifest records version, installed name and hash for each | F4, F6 |
| AC-8 | A pattern installed into a fixture repository appears in that repository's skill listing in a following session | F4 |
| AC-9 | The install reports its writes, states that it did not commit, and commits only when the user accepts | F4, ADR-8 |
| AC-10 | A selection containing one name already present in any of the three namespaces installs the others, writes nothing for the colliding one, and reports both locations | F5 |
| AC-11 | `patterns_drift.py` prints one `DRIFT:` line per behind pattern, `OK` when all are current, `MISSING` without a manifest, `UNKNOWN:` for a pattern the catalogue cannot account for (no usable `VERSION`, deleted upstream, or installed version ahead); the advisory shows drift and unknown, and suppresses `MISSING` | F7 |
| AC-12 | `update` refreshes only drifted patterns, asks nothing about the selection, and prompts per diverged file with skip as the default. The diff it prompts with runs **installed → catalogue**, so the user's own edit reads as a deletion and the incoming text as an addition, and both file labels are populated `[ref: SDD/Interface Specifications/Data model: the update path (C5's second verb), decision 4]` | F8, ADR-4 |
| AC-13 | A change to a pattern file without that pattern's `VERSION` in the same changeset fails the CI gate; with it, the gate passes; a change touching no pattern leaves the gate silent | F9, ADR-9 |
| AC-14 | The bash Obsidian gate and the Python Obsidian rule return the same verdict for every detection fixture **and for any write inside a nested plugin**; a write **outside** a nested plugin in a repository containing one elsewhere is an intentional, asserted exception, because the gate is file-scoped and the rule is repo-scoped | ADR-7 |
| AC-15 | The catalogue reader prints a named pattern's body and writes nothing; an unknown name lists the 21 | F10 |
| AC-16 | The proposal shows each entry's listing cost in characters, and lists baseline patterns separately from recommendations | F2 (4th, 5th) |
| AC-17 | After `update`, every refreshed pattern's manifest version equals its catalogue `VERSION`, and currency is determinable from the manifest alone without reading any pattern file | F6 (3rd), F8 (3rd) |
| AC-18 | The companion map derived from the catalogue equals the **seven measured pattern-to-pattern edges**; a cross-pattern reference to a new target fails the test rather than shipping a pattern whose citation dangles once installed alone. Said "nine measured pairs" until 2026-10-04, which is the distinct (pattern, cited *path*) count and not the edge count the map is made of | F4, ADR-10 |

## Risks and Technical Debt

### ADR-10: Cross-pattern references become co-recommendations, from a derived map — CONFIRMED (amended 2026-10-04)

> **Amendment.** The decision stands; its *Trade-offs accepted* paragraph was wrong in three
> places and is corrected at the end of this ADR. One of the three is a reversal rather than a
> clarification: companion expansion is the **transitive closure**, where this ADR said one hop.

**Context.** Pattern files cite each other — measured 2026-10-03 and re-measured 2026-10-04:
14 references, 9 distinct (pattern, cited path) pairs, **7** distinct pattern-to-pattern
edges, forming a cycle rather than a tree. The map is the 7. C5 copies one pattern
directory, so installing `ddd` alone leaves its citation of `reference/testing-hex-arch.md`, a file
living in `hexagonal/`, dangling in the consumer repository. Q2 is multiSelect, so that selection
is reachable rather than hypothetical.

The defect is created by this spec, not found by it. Shipping all 21 patterns made every one of
those citations resolve; selective installation is what breaks them. That is why it is in scope
despite "judging the 21 patterns on content" being out of scope — this is distribution, not
content.

**Decision.** When the interview settles on a pattern, C3 adds its companions **and their
transitive companions** to the proposal with the reason stated, and the user may decline any of
them. The map is **derived** from the catalogue by a resolution rule of its own — a code-span path
that does *not* resolve under its own pattern root, yet does resolve under exactly one other
pattern's root, is a companion edge — and a test asserts the derived map equals the seven known
edges. This paragraph attributed the rule to "the link test's resolution rule" until 2026-10-04:
the sixth and genuinely last instance of that misattribution, found by T2.4's spec-compliance
review after a sweep of mine had declared the fourth to be the last. The sweep missed it because
the sentence wrapped across a line break, so no single line contained the phrase and a line-wise
`grep` could not see it.

**Alternatives considered.**

- *Installer-side warning at write time (C5).* Technically the best-informed point, because it
  knows the actual selection rather than predicting it. Rejected as the primary mechanism because
  it tells the user about a problem after they have finished deciding, and the fix is to go back and
  re-run the interview. A proposal is the moment the information is actionable.
- *Issue plus a documented limitation.* Cheapest, and keeps a 26-task spec from growing. Rejected
  because the first repository to install `ddd` alone gets a dead reference that nothing detects —
  the catalogue link test checks the source tree, not consumer repositories, so the defect would
  surface as a reader's confusion rather than as a failure.
- *A hardcoded companion table.* Rejected on staleness: the table would be correct the day it was
  written and silently wrong the first time a pattern's references changed. Deriving it reuses the
  link test's extraction plumbing and needs a resolution rule of its own — **corrected 2026-10-04**,
  where this read "costs the same resolution code the link test already needs". That was the fifth
  and most load-bearing instance of the same misattribution, because it is the cost argument this
  rejection rests on: the plumbing is shared, the rule is not, so deriving costs a new rule rather
  than nothing. The rejection still holds — a new resolution rule is perhaps thirty lines and a
  hardcoded table goes stale silently, which is not a close call — but it is now priced honestly.

**Trade-offs accepted — amended 2026-10-04, three claims in this paragraph were wrong.** A derived
map is only as good as its resolution rule, and that rule resolves **bare** code-span paths against
every other pattern root `[ref: SDD/Interface Specifications/Data model: companion map]` — a
different and broader rule than the link test enforces, which keys on `../` climbs. So the map's
derivation and the link test's check are related but not identical, and the test asserting the
seven edges is what keeps them honest.

The three corrections, in the order they matter:

1. **Expansion is the transitive closure, not one hop.** This paragraph said "the cycle also
   forbids a transitive closure: companions are one hop, not a dependency graph to resolve", and
   both halves of that fail. A cycle does not *forbid* a closure; it requires a **visited set** —
   measured, the closure over both mutual pairs terminates immediately with one. And one hop does
   not achieve what this ADR is for: install `observability`, accept `hexagonal`, and
   `hexagonal`'s own citation of a file under `ddd/` dangles — the same defect this ADR exists to
   prevent, one step further out. Reversed by Marcus on 2026-10-04 with the blast radius measured
   first: at most three companions for any one selection. **This is a deliberate reversal of a
   CONFIRMED decision, not a clarification of it.** It was found because the orchestrator read the
   Data Model section, asked Marcus to settle a depth it described as unspecified, and a review
   then located this paragraph — so the first ruling was made without this text in view. The
   consequences are written out under *Expansion is the transitive closure*
   `[ref: SDD/Interface Specifications/Data model: companion map]`.
2. **The rule does not ignore paths lacking `../`** — it depends on them. This paragraph claimed
   the opposite and then, two sentences later, said the pairs "were found by resolving bare paths
   against other pattern roots", contradicting itself inside one breath. The measurement settles
   it: the real citations never climb, and a derivation built on the `../` rule finds **zero**
   edges.
3. **Seven edges, not nine pairs.** Nine is the distinct (source pattern, cited *path*) count;
   the map C3 consumes is the seven pattern-to-pattern edges, since a companion is a pattern and
   not a path.

### Known Technical Issues

- **`docs/about/principles.md:167` is wrong** and this work corrects it. It states that plugin
  skills do not support `disable-model-invocation`; measured this session, the flag removes a
  plugin skill's entry from the listing entirely (−628 tokens). The correction matters even though
  the flag is not the chosen mechanism, because the next person weighing these options will read
  that line.
- **`obsidian-plugin/SKILL.md:220` already points at nothing.** Its `../../../../docs/guides/…`
  reference does not resolve from the installed plugin cache today — issue #163's second instance.
  The relocation forces it to be fixed rather than merely moved.
- **The listing stays over budget.** 40191 characters against 8000–30000 depending on the model;
  this removes 5918. Out of scope by decision, and the three remaining large plugins are each
  comparable.
- **One provenance pointer survives into consumer repositories as a dead path.**
  `event-sourcing/reference/references.md:64` cites `docs/about/sources.md`, which resolves only
  from this repository's root and therefore points at nothing once C5 copies the pattern alone.
  Same class as the obsidian citation above, but without link syntax, so the catalogue link test
  does not see it — the test treats a bare code-span path as prose by design
  `[ref: SDD/Interface Specifications/Data model: companion map]`. It is one line, found by
  scanning for code-span paths that resolve from the repository root but not from the pattern:
  that scan returned 8 hits of which **7 were false positives** — `README.md`, `LICENSE`,
  `.DS_Store`, `tests/`, `conftest.py`, `.gitignore`, `venv`, all generic filenames mentioned in
  prose that happen to exist at this repository's root. One genuine instance, not a class, and the
  7-of-8 rate is further evidence that bare code-span paths cannot be classified mechanically.
  Left for Phase 5's documentation task rather than widening T1.3, whose scope named four sites.

- **Accepted edge cases of the Phase 4 advisory, recorded 2026-10-06.** The session-start hook
  exits before section 8c on a detached HEAD, so no patterns advisory appears there (pre-existing
  hook behaviour). Cache directories with a prerelease suffix (for example `2.0.0-rc1`) are skipped
  by the version filter, so a prerelease `tcs-patterns` gives silence. The shell resolves
  `_SCRIPT_DIR` with logical `pwd` while the reporter uses `Path(__file__).resolve()`, so symlinked
  plugin directories could see different parent trees. `drift_check_bundle` and `check_bundle`
  have no production caller yet: they are the generalisation T4.1 required, and patterns drift goes
  through `patterns_drift.py` instead.

### Technical Debt

- **Rolling the plugin back to `1.x` with patterns installed** leaves an installed `tcs-ddd` and a
  plugin `ddd` side by side: different names, no collision, duplicated content and two entries
  describing the same material. Accepted rather than solved; `remove` is the exit.
- **The content hash covers `SKILL.md` only** (ADR-4), so a locally edited reference file is
  replaced by `update` without a prompt.
- **The Obsidian rule exists twice** (ADR-7), kept honest by a test rather than by construction.
- **`VERSION` integers are maintainer-set**, so a forgotten bump is caught by CI only for changed
  files, not for a change that should have happened and did not.
- **The advisory runs `patterns_drift.py` without a timeout** (found in T4.3's code review,
  2026-10-06). A reporter that hangs would stall session start for as long as the hook's own
  limit allows. `timeout` is absent on macOS, so closing this needs a forking perl fallback. It is
  accepted for now: the reporter only reads two small files, and the segment runs only in a
  repository that holds a manifest. Medians measured 2026-10-06, 10 runs each: 89.5 ms in a repository
  without a manifest and 169 ms with one. The p99 with a manifest present is **not measured**
  against the 300 ms budget, and the existing perf test runs without a manifest, so it never times
  the Python path.

### Implementation Gotchas

Each of these has cost time in this repository before:

- **`$TMPDIR` and the repository are on different filesystems**, so `os.rename` from a temp file in
  `$TMPDIR` into the repository raises `Cross-device link` — and `shutil.move` silently falls back
  to copy-then-delete, which is not atomic. Create the temporary file in the destination directory.
- **A skill registers under its frontmatter `name:`, not its directory** (CON-4). Renaming the
  directory without rewriting the frontmatter installs the pattern under the unprefixed name and
  quietly defeats ADR-1. `install.py` raises instead.
- **A clause ending in `: ` inside a frontmatter value makes YAML read it as a key.** Ten skill
  descriptions in this repository stopped parsing this way, and `claude plugin validate` passed
  over all ten — it does not validate skill frontmatter. Parse the 21 frontmatter blocks with a
  YAML parser as part of the test suite.
- **A bare `[[ ]]` only fails a bats test as the body's last statement.** Relevant to the two shell
  edits; assert substrings through a `grep -qF` helper.
- **Read CI per leg, not from the run verdict.** A green aggregate hid a red Linux leg for four
  days in the previous spec.
- **The plugin cache is stale within the session that updated it**, so a skill run immediately
  after a plugin update loads the old version. Verification of the relocation must happen in a new
  session, or through the inventory walk, which reads the working tree.
- **`claude plugin details <name>` reads the installed cache copy**, never the working tree, so it
  cannot verify this change before publication.

## Glossary

### Domain Terms

| Term | Definition | Context |
|------|------------|---------|
| Pattern | One of the 21 bodies of guidance `tcs-patterns` ships — a stack convention or an architectural style | The unit of selection, versioning and installation |
| Catalogue | The 21 patterns as they live in the plugin, invisible to skill discovery | `templates/patterns/`, component C1 |
| Selection | The subset of the 21 a given repository installs | Recorded in the manifest |
| Stack fact | Something a repository's files state outright — a language, a dependency, a config key | Decides the 8 auto-proposed patterns |
| Architectural intent | Something no file states, which only the user knows | Decides the other 13, through the gated questions |
| Gate | A cheap existence check that decides whether a question is worth asking | Never decides what to install |
| Baseline pattern | A pattern that applies so widely it carries no information — `testing` | Installed when chosen, never surfaced as a recommendation |
| Drift | An installed pattern whose version is behind the catalogue | Reported per pattern |
| Divergence | An installed pattern whose content no longer matches its recorded hash | A local edit, handled by ADR-4 |

### Technical Terms

| Term | Definition | Context |
|------|------------|---------|
| Skill listing | The set of skill names and descriptions sent to the model each turn | The scarce resource; budgeted and truncated (CON-1) |
| `skillListingBudgetFraction` | Fraction of the context window, in characters, reserved for the listing. Default 0.01 | 8000 chars on a 200k model, 30000 observed at 1M |
| `skillListingMaxDescChars` | Per-description character cap in the listing. Default 1536 | Why a long description buys nothing |
| `skillOverrides` | Per-skill listing control: `on`, `name-only`, `user-invocable-only`, `off` | Works on repository skills, ignored for plugin skills (CON-2) |
| `disable-model-invocation` | Frontmatter flag removing a skill from the model's reach while keeping it typeable | Works on plugin skills; rejected here because it costs auto-routing |
| Repository skill | A skill at `<repo>/.claude/skills/<name>/SKILL.md`, exactly one level deep | What an installed pattern becomes |
| Bundle versioning | The spec-012 pattern: source of truth, mirrored marker, drift check, CI gate | Reused at per-pattern grain (CON-7) |
| Marker | The file carrying an installed bundle's version | Here: one `VERSION` per pattern, mirrored into the manifest |

### API/Interface Terms

| Term | Definition | Context |
|------|------------|---------|
| DetectionReport | The JSON `detect.py` returns: auto set, baseline, gates, evidence, flags | The entire scanning-to-asking contract; makes the scanner testable alone |
| Manifest | `.claude/skills/.tcs-patterns-manifest`, TOML, one section per installed pattern | Components C6; read by C5 and C7 |
| `OK` / `MISSING` / `DRIFT:<p>:<installed>:<catalogue>` / `UNKNOWN:<p>:<installed>` | The drift reporter's stdout contract | Mirrors `drift_check_hook_bundle`'s exit-0, caller-decides semantics; the line shapes differ (`DRIFT:<installed>` there, `DRIFT:<p>:<i>:<c>` here) |
| `expected.json` | A fixture's declared verdict, including `must_not_propose` | How a trap names what it defends |
