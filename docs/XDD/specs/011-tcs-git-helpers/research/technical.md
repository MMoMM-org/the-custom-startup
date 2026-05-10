# Technical Lens — `tcs-git-helpers` PRD Findings

## 1. Feasibility per Goal (G1–G12)

| # | Status | Rationale |
|---|---|---|
| G1 | 🟢 | `PreToolUse:Bash` regex on `tool_input.command` + `gh pr list` is straightforward; same shape as existing `block-main-edits.sh`. |
| G2 | 🟡 | "Clean-but-unmerged" detection requires `git cherry origin/$default..HEAD` + open-PR lookup → multiple subprocesses; tight but achievable (<300ms typical). |
| G3 | 🟡 | `git cherry` algorithm sound (§7.4), but matcher must distinguish `git checkout <branch>` from `checkout -b`, `checkout --`, `checkout <sha>`, `checkout -- <path>` — bash POSIX ERE without lookaheads is fragile; needs negative-test discipline. |
| G4 | 🟢 | `SessionStart` event exists; local-only commands hit <300ms easily. |
| G5 | 🟢 | Repo-side `commit-msg` is pure bash regex over `$1`. No Claude Code surface needed. |
| G6 | 🟢 | `post-merge` hook is standard git; cache file in `${CLAUDE_PLUGIN_DATA}` is documented. |
| G7 | 🟢 | All listed patterns detectable in a single regex dispatcher. Compound commands (`cd x && git …`) handled by matching the whole `command` string — same as existing hook. |
| G8 | 🟡 | Per integration-researcher's verification: lock event = `PreToolUse:ExitWorktree` (Boucle pattern, native blockable Claude Code tool). `WorktreeRemove` and `SessionEnd` are non-blockable per docs. |
| G9 | 🟢 | `PostToolUse:Bash` carries command + exit status; stderr → "additional context" pattern is standard. |
| G10 | 🟢 | Plugin hooks load via `hooks/hooks.json` → `${CLAUDE_PLUGIN_ROOT}`. Setup skill copies `.githooks/` per-repo; pattern matches `tcs-helper`'s plugin layout. |
| G11 | 🟢 | Pure git-side; copy-with-version-marker pattern is mechanically simple. |
| G12 | 🟡 | `gh api -X PUT …/branches/<b>/protection` works but JSON payload verbose; preset must be locked (deferred). Skill must handle "not authenticated" / "not admin" failures cleanly. |

## 2. Hook Event Mapping

| Component | Event | Matcher | Justification |
|---|---|---|---|
| `block-bad-git-ops.sh` | `PreToolUse` | `Bash` | Only event where `tool_input.command` is mutable-deniable pre-execution. |
| `pre-edit-branch-check.sh` | `PreToolUse` | `Edit\|Write\|NotebookEdit` (pipe-list) | Mirrors `block-main-edits.sh`; both fire and aggregate (cached docs: hooks from all sources merge). |
| `session-start-brief.sh` | `SessionStart` | `startup\|resume\|clear\|compact` | All four matchers — Claude needs orientation after compact too. |
| `nudge-hook.sh` | `PostToolUse` | `Bash` | Stderr surfaces as additional context only on success. |
| `worktree-exit-guard.sh` | **`PreToolUse:ExitWorktree`** | `""` | Resolved per integration findings (C1): blockable native tool, Boucle-validated pattern. |

## 3. Architecture Concerns

1. **Bash-vs-Python split.** Brainstorm mixes bash with `git_status_audit.py`. `tcs-helper` is fully python3. Hot-path hooks (`block-bad-git-ops`, `session-start-brief`) **must stay bash** — python3 cold-start on macOS is ~80–150ms, eats budget. Python only for `git_status_audit.py` (skill backend, latency-tolerant). Confirm in PRD.
2. **Single dispatcher per event/matcher.** Don't register N script entries for N patterns. One `block-bad-git-ops.sh` for Bash PreToolUse; one `pre-edit-branch-check.sh` for Edit/Write/NotebookEdit.
3. **Overlap with `block-main-edits.sh`.** Both run, both can deny → risk of double-fire on main edits. Plugin's `pre-edit-branch-check.sh` MUST scope itself to *added value only* (squash-merge orphan warning); user-global hook owns the main/master deny. Brainstorm §6.2.2 says "deny semantics aggregate" — PRD must clarify the non-overlap.
4. **`${CLAUDE_PLUGIN_DATA}` cache key.** Use `git rev-parse --git-common-dir` not `--git-dir`, otherwise each worktree of the same repo gets its own cache (not what we want).
5. **`.config` parser language.** MUST be bash (called per commit from `pre-commit`/`commit-msg`/`pre-push`); python overhead would be felt.
6. **Bash 3.2 compat.** Macos default `/bin/bash` is 3.2.57. No `${var,,}`, no `mapfile`/`readarray`, no associative arrays, careful with `\b` in `[[ =~ ]]` (use `[[:<:]]`/`[[:>:]]` or bracket-class workarounds).
7. **Sandbox + Bash-permission system are different layers.** Tomo's `.claude/settings.local.json` had to explicitly allowlist `Bash(git -C ... config core.hooksPath .githooks)` — this is the *permission prompt* system (separate from filesystem sandbox). Setup skill should anticipate the prompt; document the allowlist string repos can pre-add.

## 4. Constraints to Surface in PRD

- **Bash 3.2 compat** for all hook scripts (per `~/Kouzou/standards/guardrails.md`).
- **Python entry: `python3`** (matches `tcs-helper/hooks/hooks.json`).
- **Cache root: `${CLAUDE_PLUGIN_DATA}`** — never `~/.cache` or `$XDG_CACHE_HOME`.
- **Hook JSON shape:** three-level nested (`hooks` → event → `[{matcher, hooks: [{type, command}]}]`).
- **Denial mechanism:** Claude hooks emit `hookSpecificOutput.permissionDecision` JSON via stdout (mirrors `block-main-edits.sh` lines 56–62). NOT exit-code. `.githooks/` use exit-code; different layer.
- **Aggregation:** plugin hooks merge with user-global; never assume sole authority.
- **Performance:** SessionStart ≤300ms; local-only git commands; no `gh` calls in hot path.
- **macOS-only**; coreutils `timeout` in `pre-push` may be missing → reference doc must note `brew install coreutils` OR provide bash-only fallback.
- **Regex literal:** **all command-matchers MUST use `\s+` not literal space** — confirmed: brainstorm §6.2.1 already does (e.g., `git\s+push\b`). PRD should hard-call this so implementer doesn't regress to literal spaces and miss `git  push` or tab-separated forms.

## 5. Cross-Cutting Hints from Security — Addressed

### 5.1 Regex `\s+` vs literal space
Confirmed. All §6.2.1 patterns already use `\s+`. Will be enforced in PRD acceptance criteria + implementation tests must cover tab- and multi-space variants.

### 5.2 Sandbox blocks `.git/config` writes?
**Verified — partial concern.** Two layers conflated:
- **Filesystem sandbox** (this session's config): `.git/config` is inside `.` (project root, in `allowOnly`); not in `denyWithinAllow`. Direct file writes via Write/Edit are sandbox-allowed.
- **Bash permission prompt system** (orthogonal): Tomo's `settings.local.json` had to allowlist `Bash(git -C /Volumes/Moon/Coding/MiYo/Tomo config core.hooksPath .githooks)` — this is the per-command Claude permission prompt, not sandbox. Setup skill **will hit a permission prompt** the first time it runs `git config core.hooksPath` in a new repo.

**Implication for `/tcs-git-helpers:setup`:** the skill must (a) print the exact `git config` command before running it, so Marcus can pre-allowlist if running headless, and (b) gracefully handle the prompt-denied case. Document the allowlist string repos can pre-add.

### 5.3 `.config` Parser — Bash Implementation Sketch

```bash
# lib/config_parser.sh — sourced by pre-commit, commit-msg, pre-push
# Reads .githooks/.config; pure-string assignment, no eval/source.
parse_tcs_config() {
  local config_file="${1:-.githooks/.config}"
  [ -f "$config_file" ] || return 0

  local allowed_keys="TCS_PROTECTED_BRANCHES TCS_HOOK_EXCLUDE_PATHS_FILE TCS_ALLOWED_COMMIT_TYPES TCS_REQUIRE_SCOPE TCS_MAX_SUBJECT_LENGTH TCS_ENABLE_CONVENTIONAL_CHECK TCS_ENABLE_PR_PUSH_CHECK TCS_ALLOW_AMEND_ON_PROTECTED"

  local lineno=0
  while IFS= read -r line || [ -n "$line" ]; do
    lineno=$((lineno + 1))
    line="${line%%#*}"
    line="$(printf '%s' "$line" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
    [ -z "$line" ] && continue

    if ! printf '%s' "$line" | grep -qE '^[A-Z_][A-Z0-9_]*=.*$'; then
      echo "tcs-git-helpers: ignoring malformed .config line $lineno: $line" >&2
      continue
    fi

    local key="${line%%=*}"
    local val="${line#*=}"

    case "$val" in
      \"*\") val="${val#\"}"; val="${val%\"}" ;;
      \'*\') val="${val#\'}"; val="${val%\'}" ;;
    esac

    case " $allowed_keys " in
      *" $key "*) ;;
      *) echo "tcs-git-helpers: unknown key '$key' at line $lineno (ignored)" >&2; continue ;;
    esac

    printf -v "$key" '%s' "$val"
    export "$key"
  done < "$config_file"
}
```

**Properties:**
- No `source`, no `eval`. `printf -v` is bash-builtin assignment-by-name and does not parse `$val`.
- Allowlist enforced; unknown keys logged.
- Comments and blank lines tolerated; malformed lines logged but don't abort.
- Bash 3.2 compatibility: `printf -v` is bash 3.1+ ✅.

### 5.4 Block edits to `.githooks/*`, `.git/config`, `.git/hooks/*` — context detection

**Mechanism: env-var sentinel set by the skill, checked by the hook.**

The setup skill exports `TCS_GIT_HELPERS_SETUP_ACTIVE=1` for the duration of its run (in a subshell to prevent leakage). PreToolUse:Edit/Write/NotebookEdit hook checks the target `file_path`:

```bash
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // ""')
case "$FILE_PATH" in
  */.githooks/*|*/.git/config|*/.git/hooks/*)
    if [ "${TCS_GIT_HELPERS_SETUP_ACTIVE:-0}" != "1" ]; then
      # deny via hookSpecificOutput
      ...
    fi
    ;;
esac
```

**Why env-var, not parent-process detection:**
- Parent PID inspection is fragile.
- Env vars propagate through skill invocation reliably.
- Skill controls its own scope: subshell guarantees cleanup.

**`.git/config` write path:** `git config core.hooksPath .githooks` writes via the `git` binary, not via Claude's Edit/Write tool, so the PreToolUse:Edit hook doesn't see it. That command path is policed by the **PreToolUse:Bash** hook instead — needs an exception there too (allow `git config core.hooksPath …` only when the sentinel is set).

## 6. Open Technical Questions for Marcus

1. **Does `WorktreeRemove` accept `permissionDecision: deny`?** RESOLVED — use `PreToolUse:ExitWorktree` per integration; `WorktreeRemove` is non-blockable.
2. **`PostToolUse:Bash` JSON includes exit status?** Brainstorm §6.6 assumes yes. Cached docs don't show stdin schema. If only `command` is present, nudges fire on failed commands too. Runtime probe in PLAN.
3. **`if` permission-rule filters in `hooks/hooks.json`?** Could push pattern logic into Claude Code's matcher engine; one prototype worth doing.
4. **PR/branch rename timing:** rename `feat/tcs-git-safety` → `feat/tcs-git-helpers` before PRD writes spec dir, or after? `docs/XDD/specs/011-tcs-git-helpers/` already created.
5. **`coreutils timeout` dependency** in `.githooks/pre-push`: assume installed (homebrew default), or include bash-only fallback (`(cmd) & sleep 5; kill $!`)?
