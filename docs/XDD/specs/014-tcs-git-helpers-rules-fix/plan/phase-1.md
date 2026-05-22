---
title: "Phase 1: M1 — Squash-Merge-Trap Nuance"
status: pending
version: "1.0"
phase: 1
---

# Phase 1: M1 — Squash-Merge-Trap Nuance

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: PRD/Feature M1; lines: 129-149]` — M1 user story, acceptance criteria
- `[ref: PRD/Feature M1 details; lines: 206-238]` — business rules + edge cases
- `[ref: SDD/Building Block View; lines: 295-322]` — component diagram (CPCP, IAOM, PRCache)
- `[ref: SDD/Interface Specifications; lines: 345-416]` — `_is_ahead_of_merged` signature, cache schema extension
- `[ref: SDD/Implementation Examples; lines: 420-504]` — pseudocode for `_is_ahead_of_merged` and updated `_check_push_to_closed_pr`
- `[ref: SDD/Runtime View Path B; lines: 559-580]` — sequence diagram for ahead-of-merged allow path
- `[ref: SDD/Acceptance Criteria; lines: 1004-1025]` — M1-AC1, M1-AC2, M1-AC3 with EARS formulation

**Key Decisions**:
- **ADR-1**: Use `git merge-base --is-ancestor` (exit 0 → ancestor); no log walking `[ref: SDD/ADR-1]`
- **ADR-8**: Allow path emits informational stderr note: `tcs-git-helpers: PR was merged; HEAD has new commits. A new PR will be required for this push.` `[ref: SDD/ADR-8]`
- **Cache extension**: `merge_commit` field is optional in `branch_state` entries; readers use `jq '.merge_commit // empty'`; absent → ahead-check fails-safe to deny `[ref: SDD/Data Storage Changes; lines: 349-370]`

**Dependencies**:
- None. Phase 1 may execute in parallel with Phase 2 (disjoint files).

---

## Tasks

Phase 1 delivers the M1 capability: the closed-PR push guard distinguishes ghost branches (HEAD == merged SHA → deny preserved) from legitimate follow-up work (HEAD ahead → allow + stderr note). Three deliverables — cache schema extension, the ahead-check helper, and the `_check_push_to_closed_pr` integration — followed by phase validation.

- [ ] **T1.1 Cache schema extension — `merge_commit` field** `[activity: backend-api]` `[parallel: true]` `[ref: SDD/Data Storage Changes; lines: 349-370]`

  1. **Prime**: Read `plugins/tcs-git-helpers/scripts/lib/cache.sh` end-to-end. Understand existing atomicity convention (write-tmp-then-mv) and the current `_read_pr_state_cache` / `_write_pr_state_cache` shape. Cross-reference with `[ref: SDD/Building Block View; lines: 304-308]` (PRCache component).
  2. **Test (RED)** — extend `plugins/tcs-git-helpers/tests/bats/test_cache.bats` (or create if absent):
     - `_write_pr_state_cache` accepts optional `merge_commit` arg; persists alongside `state`/`checked_iso`/`number`.
     - `_read_pr_state_cache` emits two stdout lines when `merge_commit` is present (`state` line 1, SHA line 2).
     - `_read_pr_state_cache` emits one stdout line when `merge_commit` absent (backward compatibility — existing single-line readers must not break).
     - Reading a legacy cache entry (no `merge_commit` field) succeeds and produces one line on stdout.
  3. **Implement (GREEN)**: Extend cache.sh writer to accept an optional 4th positional arg (`merge_commit`); persist via existing jq write pattern. Extend reader to emit second stdout line when `merge_commit` is present in the cache JSON; use `jq '.merge_commit // empty'` so absence yields empty. Preserve write-tmp-then-mv atomicity. No new CLI deps (CON-6 — jq already in use).
  4. **Validate**: `bats tests/bats/test_cache.bats` passes; `shellcheck scripts/lib/cache.sh` clean; existing callers of `_read_pr_state_cache` (`block-bad-git-ops.sh`) that read only line 1 continue to work — verified by re-running the full `tests/bats/` suite.
  5. **Success**:
     - [ ] `merge_commit` field round-trips through writer/reader without loss `[ref: SDD/Data Storage Changes; lines: 349-370]`
     - [ ] Backward compatibility preserved — legacy entries without `merge_commit` produce a one-line read `[ref: SDD/Data Storage Changes; lines: 361-362]`
     - [ ] CON-6 honored — no new CLI deps beyond `jq` `[ref: SDD/Constraints; lines: 62-64]`

- [ ] **T1.2 `_is_ahead_of_merged` helper in `block-bad-git-ops.sh`** `[activity: backend-api]` `[parallel: true]` `[ref: SDD/Implementation Examples; lines: 420-448]`

  1. **Prime**: Re-read the pseudocode at `[ref: SDD/Implementation Examples; lines: 426-447]`. Internalize the 4-path logic: empty SHA → 2; HEAD == SHA → 1; ancestor → 0 (with stderr note); divergent → 1. Confirm wording for stderr note from `[ref: SDD/ADR-8]`.
  2. **Test (RED)** — add cases to `plugins/tcs-git-helpers/tests/bats/test_push_to_closed_pr.bats`:
     - Empty SHA argument → returns 2, no stderr output.
     - HEAD SHA equals provided SHA → returns 1 (genuine squash-merge-trap), no stderr note.
     - `git merge-base --is-ancestor SHA HEAD` exits 0 AND HEAD != SHA → returns 0 AND stderr contains the exact ADR-8 wording.
     - `git merge-base --is-ancestor SHA HEAD` exits non-zero (divergent history, e.g., post-rebase) → returns 1, no stderr note.
     - SHA not present in local object store (simulate shallow clone) → returns 1 (conservative fallback), no stderr note.
  3. **Implement (GREEN)**: Add `_is_ahead_of_merged <branch> <merged_sha>` to `block-bad-git-ops.sh` following the pseudocode at `[ref: SDD/Implementation Examples; lines: 426-447]`. Use only `git rev-parse HEAD`, `git merge-base --is-ancestor`, and string compare (CON-1: bash 3.2). Stderr note wording: exact match to ADR-8.
  4. **Validate**: `bats tests/bats/test_push_to_closed_pr.bats` cases for the new function pass; `shellcheck scripts/block-bad-git-ops.sh` clean; verify the stderr note does NOT corrupt the permissionDecision JSON on stdout (regression check: the existing M7 BATS run must still produce parsable JSON).
  5. **Success**:
     - [ ] All five return-code/side-effect scenarios produce the expected exit codes `[ref: SDD/Interface Specifications; lines: 375-383]`
     - [ ] M1-AC2 stderr wording matches ADR-8 exactly `[ref: SDD/ADR-8; lines: 917-918]` `[ref: PRD/AC-M1.2]`
     - [ ] CON-1 honored — bash 3.2 only `[ref: SDD/Constraints; lines: 36-40]`

- [ ] **T1.3 Integrate ahead-check into `_check_push_to_closed_pr`** `[activity: backend-api]` `[ref: SDD/Implementation Examples; lines: 473-504]` `[ref: SDD/Complex Logic; lines: 610-631]`

  1. **Prime**: Read the existing `_check_push_to_closed_pr` body (`block-bad-git-ops.sh:218-267`). Understand the current `CASE state` switch and where `_record_deny` is called. Re-read `[ref: SDD/Implementation Examples; lines: 478-504]` for the placement of the ahead-check.
  2. **Test (RED)** — add or update BATS cases in `test_push_to_closed_pr.bats`:
     - M1-AC1: Branch with MERGED PR, HEAD == merged SHA → push denied with existing squash-merge-trap message (no regression in deny path or wording).
     - M1-AC2: Branch with MERGED PR, HEAD ahead by N commits → push allowed (hook exits 0), stderr contains ADR-8 note.
     - M1-AC3: Branch with NO PR → guard does not fire (the `CLOSED|MERGED` block is not entered; allow path unchanged).
     - Cache-hit case: `merge_commit` already cached → no `gh pr view` invocation (verify via gh-mock spy).
     - Cache-miss case (MERGED, no `merge_commit`): single `gh pr view --json mergeCommit` invocation; result written back to cache.
     - SHA-resolution-fail case: `gh pr view` returns empty → `_is_ahead_of_merged` returns 2 → behavior falls through to existing override-or-deny path (no regression in deny).
  3. **Implement (GREEN)**: Modify `_check_push_to_closed_pr` body per `[ref: SDD/Implementation Examples; lines: 478-504]`. Order: (a) read merge_commit from cache; (b) if empty AND state==MERGED, call `gh pr view --json mergeCommit --jq '.mergeCommit.oid // empty'`, write back to cache via the extended writer from T1.1; (c) call `_is_ahead_of_merged(branch, sha)`; (d) on return 0, `return 0` immediately; on return 2, fall through to existing override/deny; on return 1, fall through to existing override/deny. Existing override-then-deny path remains the last fallback (no edits to `_check_and_consume_override` callsite — frozen per ADR-6).
  4. **Validate**: All M1 BATS cases pass; existing M7 / closed-PR deny cases pass without modification (regression guard); `shellcheck scripts/block-bad-git-ops.sh` clean.
  5. **Success**:
     - [ ] M1-AC1 deny path preserved exactly (message + exit code) `[ref: SDD/Acceptance Criteria; lines: 1004-1009]` `[ref: PRD/AC-M1.1]`
     - [ ] M1-AC2 allow path returns 0 with stderr note `[ref: SDD/Acceptance Criteria; lines: 1011-1018]` `[ref: PRD/AC-M1.2]`
     - [ ] M1-AC3 no-PR path unaffected by M1 edits `[ref: SDD/Acceptance Criteria; lines: 1020-1025]` `[ref: PRD/AC-M1.3]`
     - [ ] At most one `gh pr view` call per uncached MERGED-branch push; zero `gh` calls on cache hit `[ref: SDD/Quality Requirements; lines: 974-980]`

- [ ] **T1.4 Phase 1 Validation** `[activity: validate]`

  - Run all M1 BATS cases (`bats tests/bats/test_cache.bats tests/bats/test_push_to_closed_pr.bats`) — all pass.
  - Run the full `tests/bats/` suite — no regressions in other rule handlers.
  - `shellcheck scripts/block-bad-git-ops.sh scripts/lib/cache.sh` — clean.
  - Manual smoke: in a scratch repo, simulate ghost branch (HEAD == merge SHA) → deny; simulate ahead branch (HEAD has new commits) → allow with stderr note.
  - Verify against PRD M1 ACs (M1-AC1, M1-AC2, M1-AC3) and SDD Quality Requirements (latency budget, fail-open semantics).
