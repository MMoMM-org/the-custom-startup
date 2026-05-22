# Rule Enforcer — Self-Test Fixtures

Three scenario specifications to validate the `/enforce-rule` skill produces
the correct mechanism for known inputs. Each fixture traces Q1–Q4 and the
Step 4 Q3 label normalization, then states the expected Step 8 output.

Run each fixture in a fresh Claude Code session after the rule-enforcer skill
is indexed, answering Q1–Q4 exactly as specified. Record results in
`self-test-results.md`.

---

## Fixture 1: CI auto-bump (PR/merge to main, Auto-fix)

**Rule**: `"I keep forgetting to bump marketplace.json after plugin changes"`

### Triage trace

| Question | Expected Answer | Rationale |
|----------|----------------|-----------|
| Q1 — Recurrence | Recurring | The user says "keep forgetting" — this is an established pattern, not a first occurrence. |
| Q2 — Detectable boundary | Yes | marketplace.json changes are mechanically detectable in CI: diff the file, compare against plugin change set. |
| Q3 — Earliest intervention | `PR/merge to main` | The canonical enforcement point is the merge gate, not the local push, because PRs from contributors also need the check. Raw Q3 option selected: `PR/merge to main (e.g. CI auto-bump versions)`. |
| Q4 — Response style | Auto-fix | The fix is deterministic: re-read the plugin and rewrite the version field. No human judgment needed at fix time. |

**Step 4 — Q3 label normalization**

Raw option presented to user:
> `PR/merge to main (e.g. CI auto-bump versions)`

Parenthetical stripped → bare label used for matrix lookup:
> `PR/merge to main`

Matrix row matched: `## Q3 = PR/merge to main`

**Expected Mechanism**: `CI workflow (auto-PR or commit with [skip ci])`

### Expected Step 8 output

Step 8 reads:
- `plugins/tcs-helper/skills/rule-enforcer/templates/ci-auto-bump-style.yml.j2`
- `plugins/tcs-helper/skills/rule-enforcer/templates/ci-auto-bump-style.sh.j2`

Renders both templates with:
- `{{rule_description}}` = `bump marketplace.json after plugin changes`
- `{{workflow_name}}` = `enforce-marketplace-json-bump` (kebab-case slug)
- `{{script_name}}` = `enforce-marketplace-json-bump` (kebab-case slug)
- `{{detection_logic}}` = bash block that checks whether `marketplace.json`
  was updated in the commit set when plugin files changed
- `{{remediation_logic}}` = bash block that reads the plugin and rewrites the
  version field, then commits with `[skip ci]`

Presents a PREVIEW of rendered YAML and rendered .sh. Then asks:
> `{Write — commit the workflow + script, Refine — show changes I want to make, Cancel — abort}`

No files are written until the user selects "Write".

---

## Fixture 2: pre-push warn (Local git push, Nudge)

**Rule**: `"I keep forgetting to update CHANGELOG/README after shipping a feature"`

### Triage trace

| Question | Expected Answer | Rationale |
|----------|----------------|-----------|
| Q1 — Recurrence | Recurring | The user says "keep forgetting" — established pattern, escalation warranted. |
| Q2 — Detectable boundary | Yes | A pre-push hook can diff the commit set against `CHANGELOG` and `README` modification dates. |
| Q3 — Earliest intervention | `Local git push` | The earliest reliable boundary for doc checks is the local push: commits exist, branch is packaged. CI is later and slower; fixing docs locally before push is faster and less disruptive. Raw Q3 option selected: `Local git push (e.g. block push if CHANGELOG missing)`. |
| Q4 — Response style | Nudge | A hard block on documentation can obstruct urgent hotfixes. A nudge (warn-only, exits 0, lets push through) is honest about the stakes: the hook reminds you without being the last line of defense. If the team later decides to harden it, Q4 can be re-triaged to Block. |

**Step 4 — Q3 label normalization**

Raw option presented to user:
> `Local git push (e.g. block push if CHANGELOG missing)`

Parenthetical stripped → bare label used for matrix lookup:
> `Local git push`

Matrix row matched: `## Q3 = Local git push`

**Expected Mechanism**: `git pre-push hook (warn-only, lets push through)`

### Expected Step 8 output

Step 8 reads:
- `plugins/tcs-helper/templates/githooks/pre-push-rule-enforcer.sh.j2`

Determines `response_style` = `Nudge` (from Q4).

Authors:
- `{{detection_pattern}}` = bash conditional checking whether `CHANGELOG` or
  `README` was touched in the push commit set
- `{{warning_message}}` = human-readable reminder to update CHANGELOG and README
  before the PR is reviewed

Renders the template with four placeholders substituted. Also generates a sibling
version marker file (`tcs-helper-rule-enforcer-version`) per the bundle-versioning
pattern (ADR-2) for drift detection.

Presents rendered script as PREVIEW. Then asks the user to confirm installation
into `.githooks/`.

---

## Fixture 3: PostToolUse hook (After Claude calls a tool, Nudge)

**Rule**: `"I keep forgetting to run skill-author after editing skills"`

### Triage trace

| Question | Expected Answer | Rationale |
|----------|----------------|-----------|
| Q1 — Recurrence | Recurring | The user says "keep forgetting" — established pattern. |
| Q2 — Detectable boundary | Yes | Claude's Write/Edit tool calls on paths matching `skills/*/SKILL.md` are a discrete, observable event. |
| Q3 — Earliest intervention | `After Claude calls a tool` | The skill file must already exist before skill-author can audit it, so Pre is impossible. The correct hook point is immediately after the Write or Edit completes. Raw Q3 option selected: `After Claude calls a tool (e.g. run skill-author after editing skills/)`. |
| Q4 — Response style | Nudge | skill-author is an audit — it reads and reports. A PostToolUse reminder that says "You just edited a skill — run /skill-author to audit it" is appropriate. A hard block is not useful at PostToolUse (the write already happened). |

**Step 4 — Q3 label normalization**

Raw option presented to user:
> `After Claude calls a tool (e.g. run skill-author after editing skills/)`

Parenthetical stripped → bare label used for matrix lookup:
> `After Claude calls a tool`

Matrix row matched: `## Q3 = After Claude calls a tool`

**Expected Mechanism**: `Claude PostToolUse hook (post-tool reminder/correction)`

### Expected Step 8 output

Step 8 hands off to:
> `Skill(plugin-dev:hook-development)` with `hookEvent=PostToolUse` and the rule context.

The hook-development skill receives:
- Hook event type: `PostToolUse`
- Rule description: `run skill-author after editing skills`
- Q4 style: `Nudge`

It then authors a PostToolUse hook that fires when the matched tool is Write or Edit
and the file path matches `skills/*/SKILL.md`, printing a reminder to invoke
`/skill-author` for audit.

If the plugin-dev plugin is not installed, Step 8 falls back to an AskUserQuestion
explaining that the plugin is required for hook scaffolding.
