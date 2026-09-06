---
title: "Phase 1: Writer foundation, and the attribution question"
status: pending
version: "1.0"
phase: 1
---

# Phase 1: Writer foundation, and the attribution question

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Building Block View — Components]` — the writer's single responsibility
- `[ref: SDD/Data Storage Changes]` — path resolution and rotation contract
- `[ref: SDD/Application Data Models]` — the frozen record shape
- `[ref: SDD/Implementation Examples]` — the escape and `_field` extractors, with the traced walkthrough
- `[ref: SDD/Architecture Decisions — ADR-1, ADR-4, ADR-5, ADR-7, ADR-8]`
- `[ref: SDD/Constraints — CON-1..CON-7]`
- `plugins/tcs-git-helpers/scripts/lib/plugin_data.sh` and `audit_log.sh` — the contract being copied

**Key Decisions**:
- The resolver is duplicated on purpose (ADR-1); the parity test is what makes that safe.
- The writer forks nothing per field. `audit_log.sh` forks `sed` per field and `git` twice per line;
  that is correct there and over budget here (CON-7).
- Nothing in this phase is registered as a hook yet. Phase 1 delivers a library and its tests, so a
  defect cannot reach a real session.

**Dependencies**: none. This phase is the foundation for both others.

---

## Tasks

Establishes the storage contract, the writer, and the answer to whether Feature 7 can exist as
configuration rather than as code.

- [ ] **T1.1 Data-directory resolver with plugin parity** `[activity: infrastructure]`

  1. Prime: read `plugin_data.sh` in full, including the comment explaining why the fallback must
     reproduce the harness's shape rather than invent one `[ref: SDD/ADR-1]`
  2. Test: resolves from `$CLAUDE_OBSERVABILITY_DATA` when set, stripping trailing slashes; derives
     `$HOME/.claude/plugins/data/observability-<repo basename>` otherwise; returns non-zero outside a
     git repo; **produces the same directory shape as the plugin resolver for the same repo**
  3. Implement: `.claude/observability/logwrite.sh` — resolver portion only
  4. Validate: `bats tests/bats/observability-writer.bats` red→green; bash 3.2 dialect only
  5. Success: resolved path is outside the repository working tree `[ref: SDD/SDD-AC-10]`;
     parity with the plugin resolver holds `[ref: SDD/SDD-AC-19]`

- [ ] **T1.2 Append, escape and rotate — the durable write** `[activity: infrastructure]`

  1. Prime: read `audit_log.sh`'s rotation chain and printf builder, and the record shape
     `[ref: SDD/Application Data Models]`
  2. Test: one JSON object per line carrying `ts`, `kind`, `session`, `repo`; backslashes and quotes
     escaped without forking; rotation at 1024000 bytes through `.1`/`.2`/`.3` with **no `.4` ever
     created**; over-long fields shortened with `truncated: true` set; an unwritable directory,
     a full disk and a failed rotation each leave the caller's exit status, stdout and stderr
     untouched; no file is created at all while the enable switch is unset
  3. Implement: the append, escape, truncate and rotate portions of `logwrite.sh`
  4. Validate: bats green; `LC_ALL=C` set before any formatting (CON-3); `#!/usr/bin/env bash`
     present (CON-2)
  5. Success: `[ref: SDD/SDD-AC-1, SDD-AC-5, SDD-AC-6, SDD-AC-7, SDD-AC-12]`;
     `[ref: PRD/F2, PRD/F3]`

- [ ] **T1.3 Redaction, and the absent-key guard** `[activity: security]`

  1. Prime: read the reduced-mode keep/drop table and the traced `_field` walkthrough
     `[ref: SDD/Complex Logic]` `[ref: SDD/Implementation Examples]`
  2. Test: **a payload missing the requested key yields empty, never the whole payload** — the
     redaction-critical case, tested with a Bash `PreToolUse` payload whose command line contains a
     token-shaped string, asserting that string never appears in the record; reduced mode keeps a
     Bash call's program name and drops its arguments; reduced mode emits no file content, no hook
     command string, no `transcript_path` and no absolute home path; detail mode adds the extra
     fields and requires its own switch, separate from the enable switch
  3. Implement: the extraction and reduction portions of `logwrite.sh`
  4. Validate: bats green, including a deny-list scan over a produced record
  5. Success: `[ref: SDD/SDD-AC-8, SDD-AC-9, SDD-AC-11]`; `[ref: PRD/F3]`; both switches default off
     `[ref: SDD/ADR-4]`

- [ ] **T1.4 Answer the attribution question** `[activity: research]`

  1. Prime: read ADR-7 and the note that `tcs-helper` already registers two commands under one
     `UserPromptSubmit` matcher `[ref: SDD/ADR-7]` `[ref: SDD/Implementation Context — Code Context]`
  2. Test: construct a throwaway hook configuration in a scratch repo with two commands registered
     under the same event — once as two entries sharing a matcher string, once as two entries with
     distinct matcher strings that both match — and capture the harness's own
     `hook_execution_complete` records for each arrangement
  3. Implement: no production code. The deliverable is a recorded finding: does the harness produce
     one measurement group or two, and is a per-command matcher expressible at all?
  4. Validate: the finding is reproducible — state the exact configuration and the observed
     `hook_name` and `num_hooks` values, not a conclusion drawn from reading code
  5. Success: ADR-7 in `solution.md` is updated with the finding and Feature 7 is either scoped to
     configuration, routed to the wrapper, or dropped — **with the reason recorded either way**
     `[ref: SDD/SDD-AC-20]` `[ref: PRD/F7]`

  > This task gates nothing else in phase 1 and can run at any point in it. It is placed here
  > because its answer changes phase 3's scope, and finding that out late is the expensive case.

- [ ] **T1.5 Phase Validation** `[activity: validate]`

  - Run `bats tests/bats/observability-writer.bats` and the full `plugins/tcs-git-helpers/tests/bats/`
    suite — the latter must stay green, since ADR-1 duplicates one of its contracts. Verify the
    writer against `[ref: SDD/Quality Requirements]`: measure per-invocation overhead and confirm it
    is within the 1 ms budget **on macOS**, not only in the Linux container where the original
    figures were taken.
