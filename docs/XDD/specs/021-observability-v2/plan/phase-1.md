---
title: "Phase 1: Writer hardening and git parsing"
status: in_progress
version: "1.0"
phase: 1
---

# Phase 1: Writer hardening and git parsing

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Data Storage Changes]` — owner-only creation
- `[ref: SDD/Building Block View/Components]` — `logwrite.sh`, `git_ops.sh` rows
- `[ref: SDD/Implementation Examples]` — decoding `tool_input.command`, parsing one command (traced), read-only predicate
- `[ref: SDD/Runtime View/Complex Logic]` — executor rule, command position
- `[ref: SDD/Architecture Decisions; ADR-2, ADR-3, ADR-4, ADR-9]`
- `[ref: 018 SDD/Complex Logic/The reduction mechanism]` — `detail:` prefix and deny list

**Key Decisions**:
- ADR-2: copy `_strip_heredocs`, `_strip_quoted` and the executor predicate (with #213's fix) from `plugins/tcs-git-helpers/scripts/lib/pattern_match.sh`; no `source` across plugins (CON-12).
- ADR-3: short flags reduce to their first letter.
- ADR-4: new directories 0700, files 0600 via `umask 077` around the writer's `mkdir` and append.
- CON-13: names only.

**Dependencies**: none.

---

## Tasks

Establishes the two pieces every new adapter stands on: a writer that creates owner-only files and drops the new free-text field names, and a pure git parser that turns a decoded command into zero or more name-only descriptions.

- [x] **T1.1 Writer: owner-only creation and deny-list backstop** `[activity: backend]` `[parallel: true]`

  1. Prime: `logwrite.sh` `_observability_write` (:601), its single `mkdir` (:643), the deny list (:557) and `_observability_field_is_detail_only` (:562) `[ref: SDD/Data Storage Changes]` `[ref: 018 SDD/Complex Logic]`
  2. Test: a fresh data dir is created 0700 and `events.jsonl` 0600; the caller's `umask` is unchanged afterwards; with detail off, unprefixed `args`, `command_args`, `description`, `tool_input` are dropped and the record still writes; with detail on, `detail:description` survives; existing deny-listed names still drop; an unwritable dir still returns 0 silently
  3. Implement: set and restore `umask 077` around the `mkdir -p` and the append in `logwrite.sh`; add the four names to the deny list
  4. Validate: `bats plugins/tcs-helper/tests/bats/observability-writer.bats` and the redaction suites green; shellcheck clean; mutate (drop the `umask`; drop one deny name) and watch a test fail
  5. Success: new record files are owner-only `[ref: PRD/F6 AC1]`; tool-route `args` never reaches a reduced record `[ref: PRD/F6 AC3]`; `[ref: SDD/Acceptance Criteria/F6]`

- [x] **T1.2 Copied clause stripping with a parity test** `[activity: backend]` `[parallel: true]`

  1. Prime: `pattern_match.sh` `_strip_quoted` (:385), `_strip_heredocs` (:462), `_clausify` (:516) incl. the #213 executor check on stripped text; `observability-setup/lib/drift_check.sh:18-25` (mirror the contract) `[ref: SDD/ADR-2]` `[ref: SDD/Runtime View/Complex Logic]`
  2. Test: a shared corpus (commit/PR bodies naming git ops, `<<'EOF'` and `<<-EOF` heredocs, heredoc into `bash`, `bash -c '…'`, `eval`, `$( … )` with inner quotes, `<<<`, unterminated heredoc) produces byte-identical stripped output and the same executor decision from the bundle copy and from tcs-git-helpers; the bats file sources each implementation in its own subshell
  3. Implement: `plugins/tcs-helper/scripts/observability/git_ops.sh` with the copied functions under `_git_ops_` names; `plugins/tcs-helper/tests/bats/observability-git-parity.bats`
  4. Validate: parity suite green; mutate one copied line (e.g. drop the dq `$(` handling) and the parity test fails; shellcheck clean
  5. Success: the bundle strips exactly as the guard does, without sourcing it `[ref: SDD/ADR-2]` `[ref: SDD/Constraints/CON-12]`

- [ ] **T1.3 Git invocation parser** `[activity: backend]`

  1. Prime: decoder and traced parse example, read-only predicate, command position, executor fallback `[ref: SDD/Implementation Examples]` `[ref: SDD/Runtime View/Complex Logic]` `[ref: SDD/ADR-3, ADR-9]`
  2. Test: decoder handles `\"`, `\\`, `\n`, `\t`, missing key and unterminated string (→ empty); the traced example yields exactly the two descriptions in the SDD; every always-read-only subcommand yields nothing; each flag-dependent form is nothing when read-only and recorded otherwise (`branch` vs `branch -D x` vs `branch newname`; `stash list` vs `stash pop`; `config --get` vs `config user.name x`; `tag` vs `tag v1`); an unknown subcommand is recorded; `git $X` gives `?`; global options (`-C dir`, `-c k=v`, `--git-dir=…`) are skipped with their values; `--opt=value` → `--opt`; `-mfoo` → `-m`, `-fd` → `-f`; `--` ends flags; `bash -c 'git reset --hard'` yields `reset`; a commit message mentioning `git reset` yields only `commit`; wrappers `env`/`sudo`/`command`/`nohup`/`time`/`exec` and leading assignments are skipped; `CLAUDE_ALLOW_*=1` names and `override_first` (the name, or empty) follow the guard's first-token rule incl. one leading `cd`/`pushd`, and `=0`/`=yes` are not overrides; `stash pop`/`stash drop`/`stash push`, `worktree remove`, `remote set-url` give their `action` and a positional outside the ACTIONS list gives none; global options with and without values (`-c x=y -C d commit`, `--git-dir x reset`, `-p log`, `--no-pager reset`); wrappers with options (`sudo -u u git push`, `env -i git …`, `env -u V git …`, `time -p git push`, `nice -n 5 git gc`, `timeout 5 git fetch`; `command -v git` is no invocation); openers (`x=$(git reset --hard)`, `` `git pull` ``, `(git reset)`, `if git pull; then`, `! git push`); newline-separated commands; `<<<` here-string; `git`, `git --version`, `git --help` give nothing; `checkout -- file` records `--` as a flag name; executor fallback gives `flags: (executor)` and the executor cases join the secrets corpus; a secrets corpus (token assignments, `https://u:p@h`, `Authorization:` headers, `-mSECRET`, `--with-token`, `set-url` with a token) leaves no value in any description
  3. Implement: in `git_ops.sh`, `_git_ops_command` (decoder) and a parse function that prints one line per non-read-only invocation: `subcommand<TAB>action<TAB>flags<TAB>overrides<TAB>override_first`; no writing, no `git` calls
  4. Validate: `plugins/tcs-helper/tests/bats/observability-git.bats` green; mutate the read-only list (drop `status`), the short-flag reduction, the ACTIONS list and the executor fallback — each fails a named test; shellcheck clean
  5. Success: parsing meets every F3 rule on names, scope and edge cases `[ref: PRD/F3 AC6, AC7, AC8, AC9]` `[ref: PRD/Detailed Feature Specifications/Business Rules 2, 3, 4, 6]` `[ref: SDD/Acceptance Criteria/F3]`

- [ ] **T1.4 Phase Validation** `[activity: validate]`

  - Run the writer, parity and git suites plus all existing observability suites; shellcheck every touched script. Check against SDD CON-13 and ADR-2/3/4/9.
