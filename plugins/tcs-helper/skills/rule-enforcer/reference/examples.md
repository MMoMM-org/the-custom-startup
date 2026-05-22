# Rule Enforcer — Worked Examples

> Five real-case walkthroughs of the 4-question triage workflow.
> Examples 1–3 are the 3 session violations documented in PRD M7.
> Examples 4–5 come from the memory bank survey.
>
> Use these cases when answering Q2/Q3 in triage — recognize your rule by analogy, not by judging abstract properties.

---

### Example 1: Missing marketplace.json bump after plugin changes

**Rule description**: "I keep forgetting to bump marketplace.json after plugin changes"

**Q1 — Recurrence**: Recurring — memory exists but was ignored
**Rationale**: `feedback_no-manual-marketplace-sync.md` was written 2026-05-11; the same Claude that wrote it violated it 10 days later (PR #27 shipped without bumps, requiring PR #28 as a catch-up). Memory failed its recall-and-apply job.

**Q2 — Objectively detectable**: Yes
**Rationale**: The violation is structurally detectable — a merged PR that modifies `plugin.json` but leaves `marketplace.json` unchanged can be caught by diff inspection on the PR's changed files, no human judgment required.

**Q3 — Intervention point**: PR/merge to main
**Rationale**: The violation only matters when the PR lands; catching it before merge (not at commit time) allows the CI workflow to auto-fix the bump without blocking the developer mid-flow.

**Q4 — Strength**: Auto-fix
**Rationale**: Bumping a version number is fully mechanical — no human decision is required. Auto-fix is preferable to block because it eliminates the catch-up PR entirely (which is exactly the cost the PR #29 workflow was built to remove).

**Mechanism**: CI workflow (auto-bump style — PR #29 pattern)

**Hand-off / scaffolding**: Invoke M6 inline scaffolder with template hint `auto-bump-style patch`. Produces `.github/workflows/auto-bump-marketplace.yml` + `scripts/ci/bump_marketplace.sh` based on the proven PR #29 template, with detection logic scoped to `marketplace.json` vs `plugin.json` diff.

---

### Example 2: Missing CHANGELOG/README update after shipping a feature

**Rule description**: "I keep forgetting to update CHANGELOG and README after shipping a feature"

**Q1 — Recurrence**: Recurring — memory exists but was ignored
**Rationale**: Post-feature docs updates were missed when the Finalize step shipped in the 2026-05-21 session — fixed reactively in commit `5834976`. Memory entry for this pattern existed; recall failed at ship time.

**Q2 — Objectively detectable**: Yes
**Rationale**: The presence of a new feature commit without a CHANGELOG entry can be approximated mechanically — grep the staged diff for CHANGELOG/README modifications when the commit message starts with `feat:` or `chore(release):`. No judgment required to detect the absence.

**Q3 — Intervention point**: Local git operation (pre-push)
**Rationale**: Catch before PR creation so the violation is fixed in the branch, not in a follow-up PR. Pre-push is earlier than PR/merge CI and earlier than post-commit, giving the developer a chance to amend before the work is visible upstream.

**Q4 — Strength**: Nudge
**Rationale**: Per PRD M6 refinement (2026-05-21): nudge (exit 0 + clear warning) is the honest default for docs gates. Blocking with `--no-verify` available just teaches developers to bypass. A nudge makes the omission visible without creating an adversarial escape hatch.

**Mechanism**: git pre-push hook (docs-gate style, `.githooks/pre-push`)

**Hand-off / scaffolding**: Invoke M6 inline scaffolder with template hint `docs-gate-style`. Produces a `.githooks/pre-push` snippet that detects `feat:` commits in the push range without a matching CHANGELOG line, and prints a clear warning before exiting 0. User reviews and adds to `.githooks/pre-push` with confirmation.

---

### Example 3: Forgetting to run skill-author after editing skills/

**Rule description**: "I keep forgetting to run skill-author after editing skills in plugins/tcs-helper/skills/"

**Q1 — Recurrence**: Recurring — memory exists but was ignored
**Rationale**: `feedback_skill-author-on-creation.md` exists in the memory bank with an explicit "always run skill-author audit before committing any new skill" directive. The violation recurs because it's a post-edit step that has no automatic trigger.

**Q2 — Objectively detectable**: Yes
**Rationale**: A tool call that writes or edits a file under `plugins/tcs-helper/skills/` is a precise, mechanical signal. No judgment is needed — the path match alone identifies that a skill file was touched.

**Q3 — Intervention point**: After Claude calls a tool (PostToolUse)
**Rationale**: The Write/Edit tool call that modifies a skill file is the exact trigger point. Intercepting after the tool runs (PostToolUse) allows the audit reminder to fire immediately after the edit, at the earliest moment before the developer's attention moves to the next step.

**Q4 — Strength**: Nudge
**Rationale**: Skill-author is a review step, not a hard correctness gate. A nudge keeps the developer in control — they might be mid-edit with more changes coming, or the audit might already have run earlier in the session. Blocking would be too aggressive for a review workflow.

**Mechanism**: Claude PostToolUse hook (path-scoped nudge — existing `authoring.md` reminder pattern)

**Hand-off / scaffolding**: Invoke `Skill(plugin-dev:hook-development)` with event type `PostToolUse`, path filter `plugins/tcs-helper/skills/`, and action `nudge — suggest /skill-author`. The existing `authoring.md` hook in tcs-helper is the proven template; hook-development skill adapts it for the new path scope.

---

### Example 4: Using --break-system-packages instead of venv on macOS

**Rule description**: "I always use --break-system-packages on macOS when installing Python deps"

**Q1 — Recurrence**: Cross-cutting
**Rationale**: This is not one developer's habit — it's a systemic default. Any Claude agent operating in a macOS Python environment will reach for `--break-system-packages` without explicit constraint. One occurrence justifies mechanization because it affects every Python-related operation across sessions (per PRD BR-4: cross-cutting frequency overrides the Q1 = 1× short-circuit).

**Q2 — Objectively detectable**: Yes
**Rationale**: A Bash tool call containing `pip install --break-system-packages` is a syntactic match — no interpretation required. The flag is distinctive enough that a regex on the command string will not produce false positives.

**Q3 — Intervention point**: Before Claude calls a tool (PreToolUse)
**Rationale**: The violation occurs at the moment the `pip install --break-system-packages` command is constructed. Intercepting before the Bash tool executes prevents the environment from being polluted — after-the-fact correction requires environment cleanup, which is harder than prevention.

**Q4 — Strength**: Block
**Rationale**: Allowing the command through and nudging afterward leaves the system in a broken state. Block is justified because (a) the correct alternative (venv) is unambiguous and always available, and (b) the `--no-verify` bypass concern does not apply to Claude PreToolUse hooks — Claude cannot bypass a block by flag.

**Mechanism**: Claude PreToolUse hook (regex block on `--break-system-packages` in Bash calls)

**Hand-off / scaffolding**: Invoke `Skill(plugin-dev:hook-development)` with event type `PreToolUse`, tool name `Bash`, match pattern `--break-system-packages`, and action `block — print venv setup instructions`. Hook exits non-zero with a message showing the correct `python3 -m venv venv && source venv/bin/activate` alternative.

---

### Example 5: Forgetting the syntax for a specific CLI flag

**Rule description**: "I forget the syntax for jq's `--arg` flag every time"

**Q1 — Recurrence**: First — no memory yet (or: this is not a recurrence of a mechanizable rule)
**Rationale**: Forgetting CLI syntax is a knowledge-recall problem, not a process violation. There is no "wrong action" to intercept — the developer simply needs a reference. This does not match the pattern of a rule being violated at a predictable intervention point. Q1 short-circuits here.

**Q2 — Objectively detectable**: skipped (Q1 short-circuit)

**Q3 — Intervention point**: skipped (Q1 short-circuit)

**Q4 — Strength**: skipped (Q1 short-circuit)

**Mechanism**: Not a rule — defer to documentation lookup or `/memory-add` if the user wants to capture the syntax for future recall.

**Hand-off / scaffolding**: Invoke `Skill(tcs-helper:memory-add)` with a note capturing the correct `jq --arg name value` syntax, or point the user to `man jq` / online docs. No hook, no CI workflow, no git hook is warranted — there is no action to intercept.
