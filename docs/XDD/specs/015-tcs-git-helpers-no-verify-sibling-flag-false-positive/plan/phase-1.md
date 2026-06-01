---
title: "Phase 1: Sibling-isolation fix (TDD)"
status: pending
version: "1.0"
phase: 1
---

# Phase 1: Sibling-isolation fix (TDD)

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Solution Strategy]` — per-clause matching approach
- `[ref: SDD/Building Block View/Interface Specifications]` — `_match_no_verify` contract
- `[ref: SDD/Implementation Examples]` — reference helper + dispatcher change
- `[ref: SDD/Runtime View/Complex Logic]` — traced walkthrough (expected behavior)
- `[ref: PRD/Feature Requirements]` — F1/F2/F3 acceptance criteria

**Key Decisions**:
- ADR-1 per-clause matching; ADR-2 `PATTERN_NO_VERIFY` unchanged; ADR-3 separator set & pure-bash split.

**Dependencies**:
- None. This is the first phase.

---

## Tasks

This phase delivers the corrected NO_VERIFY detection: legitimate compound commands with a
sibling `-n` are allowed, while genuine bypasses (including chained and piped forms) still deny.

- [ ] **T1.1 `_match_no_verify` helper + dispatcher swap** `[activity: backend-implementation]`

  1. Prime: Read the `_match_no_verify` contract and reference implementation `[ref: SDD/Building Block View/Interface Specifications]` `[ref: SDD/Implementation Examples]`, plus the existing `_strip_quoted`, `_match_command`, and `PATTERN_NO_VERIFY` in `plugins/tcs-git-helpers/scripts/lib/pattern_match.sh` and the NO_VERIFY dispatch line in `plugins/tcs-git-helpers/scripts/block-bad-git-ops.sh`.
  2. Test (RED): In `tests/bats/lib_pattern_match.bats`, add `_match_no_verify` unit cases — genuine `--no-verify`/`-n` → match; chained genuine bypass `git add . && git commit -n` → match; sibling `git commit -m "done" && echo -n ok` → no match; `; head -n 5` → no match; `| grep -n` → no match; `-n` inside `-m "..."` body → no match; newline-separated sibling → no match `[ref: PRD/Feature Requirements F1, F2, F3]`. Run bats and confirm the new cases FAIL against the current code.
  3. Implement (GREEN): Add `_match_no_verify` to `pattern_match.sh` (pure-bash: `_strip_quoted` → ordered separator normalization `&&|| | ; &` → here-string `read` loop running the unchanged `PATTERN_NO_VERIFY` per clause). Add a one-line pointer comment above `PATTERN_NO_VERIFY` directing readers to `_match_no_verify`. In `block-bad-git-ops.sh`, replace the `_match_command "$(_strip_quoted "$CMD")" "$PATTERN_NO_VERIFY"` line with `_match_no_verify "$CMD"`. Keep `PATTERN_NO_VERIFY` byte-identical `[ref: SDD/ADR-2]`.
  4. Validate: `bats plugins/tcs-git-helpers/tests/bats/` all green; `shellcheck` clean on both scripts; no other PATTERN_* dispatch line changed.
  5. Success:
     - [ ] Sibling `-n` after `git commit` (via `&&`, `;`, `|`, `&`, newline) does NOT raise NO_VERIFY `[ref: PRD/AC F1]`
     - [ ] Genuine `git commit --no-verify` / `-n`, incl. chained `git add . && git commit -n`, still denies `[ref: PRD/AC F2]`
     - [ ] `-n` inside the quoted message body still allowed `[ref: PRD/AC F3]`
     - [ ] `PATTERN_NO_VERIFY` constant is unchanged `[ref: SDD/ADR-2]`

- [ ] **T1.2 Dispatcher regression coverage + corpus** `[activity: testing]` `[parallel: true]`

  1. Prime: Read `tests/bats/block-bad-git-ops.bats` NO_VERIFY cases and `tests/fixtures/commands/bypass_corpus.txt` (note the existing `deny NO_VERIFY echo "fix" | git commit --no-verify -F -` line) `[ref: SDD/Implementation Context]`.
  2. Test (RED): Add dispatcher-level bats cases asserting that the full hook ALLOWS `git commit -m "done" && echo -n ok` (no deny) and DENIES `git add . && git commit -n`. Add an `allow NEGATIVE` corpus line for a sibling-`-n` compound and a `deny NO_VERIFY` line for a chained bypass; confirm the new allow-case fails before the fix.
  3. Implement (GREEN): No new production code — these pass once T1.1 lands. Adjust only if the corpus runner needs the new rows wired.
  4. Validate: dispatcher bats green; corpus runner green; `[ref: SDD/Acceptance Criteria]`.
  5. Success:
     - [ ] Hook-level allow for sibling-`-n` compound; hook-level deny for chained bypass `[ref: PRD/AC F1, F2]`
     - [ ] `bypass_corpus.txt` covers both a sibling-`-n` negative and a chained-bypass positive

- [ ] **T1.3 Phase Validation** `[activity: validate]`

  - Run the full `bats plugins/tcs-git-helpers/tests/bats/` suite and `shellcheck` on both modified scripts. Confirm the live false-positive set (`git commit ... && echo -n`) is now allowed and the genuine-bypass set still denies. Verify against SDD Runtime View traced walkthrough and PRD F1/F2/F3.
