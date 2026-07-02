# Rule Enforcer — Installed Enforcement Catalog (hint layer)

Maps rule *concepts* that are **already guarded** by the version-pinned
`tcs-git-helpers` bundle to their owning hooks. Consumed by the CLAUDE.md-sweep
batch dedup step (B6) to recognize a candidate rule that a shipped hook already
covers, so the sweep does not propose a redundant new mechanism.

> **HINT LAYER ONLY — NOT AUTHORITATIVE.** This file can drift. LIVE inspection
> of the target repo's `.githooks/`, the plugin's `hooks/hooks.json`, and the
> per-rule slug files (`scripts/*.sh`, `scripts/lib/pattern_match.sh`) is the
> **authoritative** source of what is enforced. This catalog only reflects the
> `tcs-git-helpers` bundle **as of spec 016**, and only the hooks that ship in
> it — a repo may pin an older/newer bundle, disable a hook, or add its own.
> When in doubt, read the scripts.

## How to dedup (B6)

**Dedup key = mechanism + target-pattern, NOT rule text.** Memory prose and
hook wording describe the same guard in different words (e.g. CLAUDE.md says
"Committing to git main branch is disabled by githooks"; the hook denies
`Edit|Write` on `main`/`master`). Match a candidate rule to an entry below by
what it *mechanically intercepts and where*, not by string-comparing the
sentences. If mechanism + target-pattern already appears here, the concept is
already guarded → do **not** propose a new enforcement for it in the sweep.

---

## PreToolUse: Edit | Write | NotebookEdit

| Concept | Owning hook | Target-pattern | CLAUDE.md / standards phrasings covered |
|---------|-------------|----------------|------------------------------------------|
| No edits on the default branch | `pre-edit-branch-check.sh` (deny) | `Edit`/`Write`/`NotebookEdit` on branch `main`\|`master`; gitignored paths exempt; `CLAUDE_ALLOW_MAIN_EDITS=1` escape | "Before editing any file … create a new branch and start editing"; "Write/Edit/NotebookEdit on main/master is denied"; "Committing to git main branch is disabled by githooks" |
| Editing on a stale squash-merged branch | `pre-edit-branch-check.sh` (**warn only**, not a deny) | orphan-branch detection via `git cherry` + `merge-base --is-ancestor` | squash-merge-trap guidance; "branch fresh after spec PR" |
| Tampering with git internals | `protect-git-internals.sh` (deny) | file paths matching `*/.githooks/*`, `*/.githooks/.config`, `*/.git/config`, `*/.git/hooks/*`; `TCS_GIT_HELPERS_SETUP_ACTIVE=1` escape | "githooks enforce …" / do-not-subvert-hooks; protect `.git`/`.githooks` config |

## PreToolUse: Bash — `block-bad-git-ops.sh` (deny; cascading)

Each row is one granular override slug from the dispatcher. Override form:
`CLAUDE_ALLOW_<SLUG>=1` as the command's first token (master: `CLAUDE_ALLOW_GIT_BAD_OPS=1`).

| Concept (slug) | Target-pattern (matched command) | Phrasings covered |
|----------------|----------------------------------|-------------------|
| `RESET_HARD` | `git reset --hard` | never hard-reset; don't destroy working tree |
| `CLEAN_FORCE` | `git clean -f` | don't delete untracked files (dry-run with `-n`) |
| `DESTRUCTIVE_CHECKOUT` | `git checkout .` / `git checkout -- <path>` | don't discard working-tree changes silently |
| `DESTRUCTIVE_RESTORE` | `git restore --worktree` / `--source` / `--staged` | don't destroy changes via restore |
| `FORCE_BRANCH_DELETE` | `git branch -D` | use `-d` not `-D`; recover via reflog |
| `STASH_DESTROY` | `git stash drop` / `git stash clear` | don't drop/clear stash; use `pop` |
| `REFLOG_EXPIRE` | `git reflog expire` | don't kill the recovery net |
| `NO_VERIFY` | `--no-verify` (commit/push) | "`--no-verify` bypasses `.githooks/` — defeats the purpose" |
| `PUSH_TO_CLOSED_PR` | `git push` when the branch's PR is `CLOSED`/`MERGED` (gh fail-open; ahead-check exemption) | don't push to a closed/merged PR; squash-merge trap; "new PR required" |
| `FORCE_PUSH` | `git push --force` | "use `--force-with-lease`, not `--force`" |
| `REMOTE_BRANCH_DELETE` | `git push --delete`, `git push <remote> :<branch>`, `gh api DELETE …/git/refs/…` | don't delete remote branches |
| `BRANCH_FROM_UNFINISHED` | `git checkout -b` / `switch -c` while tree dirty or ahead of `origin/<default>` with no PR | "limit each change to one feature/fix"; don't branch from unfinished work |
| `RESUME_MERGED_BRANCH` | `git checkout`/`switch <branch>` when `<branch>` was squash-merged | don't resume a squash-merged branch; branch fresh after spec PR |
| `HOOKSPATH_OVERRIDE` | `git -c core.hooksPath=…` and write-form `git config core.hooksPath …` (read-form `--get*` exempt; `TCS_GIT_HELPERS_SETUP_ACTIVE=1` escape) | don't subvert `.githooks/` via `core.hooksPath` |

## PostToolUse: Bash — `nudge-hook.sh` (advisory only)

**Not a block, not a dedup target for "must"/"block" rules.** Emits a one-line
stderr reminder after a matching git/gh command *succeeds* (60s per-repo dedup;
at most one nudge per invocation). A candidate rule whose desired response is a
hard block is **not** deduplicated by these nudges — only treat a candidate as
covered here if its intended response style is itself an advisory nudge.

| Nudge (rule key) | Fires after (target-pattern) |
|------------------|------------------------------|
| `verify-base` | `git checkout -b` / `git switch -c` |
| `verify-pr-title` | `gh pr create`; first `git push -u <remote> <branch>` |
| `cleanup-after-merge` | `gh pr merge` |
| `verify-history` | `git rebase` |
| `verify-orig-cleanup` | `git stash pop` |

---

## Memory-enforced (not a hook)

Some recurrence rules are guarded by **memory rules**, not git-helpers hooks —
do NOT list these as hook dedup entries:

- **`skill-author-on-creation`** — "always run the skill-author audit before
  committing a new skill" is a memory rule (`feedback_skill-author-on-creation`),
  a layer-1 prompt-level defense. There is no PreToolUse/PostToolUse hook for it
  in `tcs-git-helpers`. If a candidate rule matches this concept, the dedup
  target is the memory entry, not a hook.

## Not enforced by this bundle (other hook events)

`tcs-git-helpers` also registers `PreToolUse:ExitWorktree` (`worktree-exit-guard.sh`)
and `SessionStart` (`session-start-brief.sh`); these are workflow aids, not rule
guards, and are out of scope for CLAUDE.md rule dedup. Rules enforced at the
`git pre-push`, CI, `UserPromptSubmit`, or `SessionStart` boundary are **not**
covered by this catalog — see `mechanism-matrix.md` for choosing a mechanism
when a candidate is *not* already guarded here.

---

**Drift caveat:** every entry above reflects the `tcs-git-helpers` bundle as of
spec 016. Slugs, matched patterns, and escape-hatch env-vars can change between
bundle versions. Before treating a rule as already-guarded, confirm against the
live `hooks.json` + `scripts/*.sh` in the target repo's pinned bundle.
