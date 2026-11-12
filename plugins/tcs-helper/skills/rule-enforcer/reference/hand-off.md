# Hand-off (step 8)

Loaded at step 8 of `SKILL.md`. Here `$ARGUMENTS` means the arguments passed to the TARGET skill, not the ones this skill received; build them from `State.rule` and `triage`.

Match on `triage.mechanism` (set in Step 6). Invoke the target skill with the
rule context formatted as `$ARGUMENTS` so the target skill receives it as its
`**Request**: $ARGUMENTS` input.

**Mechanism match:**

- Any mechanism starting with `Skill with discipline language` →
  `Skill(tcs-helper:skill-author)` with `$ARGUMENTS` =
  `"Create or update a skill that enforces: [State.rule]. Q4 style: [triage.q4]."`

- Any mechanism starting with `Claude PreToolUse hook` →
  `Skill(plugin-dev:hook-development)` with hook event = `PreToolUse` and rule context.
  If plugin-dev plugin not installed, fall back to AskUserQuestion described in Fallback block.

- Any mechanism starting with `Claude PostToolUse hook` →
  `Skill(plugin-dev:hook-development)` with hook event = `PostToolUse` and rule context.
  If plugin-dev plugin not installed, fall back to AskUserQuestion described in Fallback block.

- Any mechanism starting with `Claude UserPromptSubmit hook` →
  `Skill(plugin-dev:hook-development)` with hook event = `UserPromptSubmit` and rule context.
  If plugin-dev plugin not installed, fall back to AskUserQuestion described in Fallback block.

- Any mechanism starting with `Claude SessionStart hook` →
  `Skill(plugin-dev:hook-development)` with hook event = `SessionStart` and rule context.
  If plugin-dev plugin not installed, fall back to AskUserQuestion described in Fallback block.

- `Memory rule` →
  `Skill(tcs-helper:memory-add)` with `type=feedback` and a strong-language hint:
  prepend the rule with `MUST`, `NEVER`, or `ALWAYS` to maximise enforcement weight.

- Any mechanism starting with `CI workflow` →
  1. Read both template files:
     `plugins/tcs-helper/skills/rule-enforcer/templates/ci-auto-bump-style.yml.j2`
     `plugins/tcs-helper/skills/rule-enforcer/templates/ci-auto-bump-style.sh.j2`
  2. Compute `workflow_name` and `script_name` as kebab-case slugs derived from the rule
     (e.g., "CHANGELOG must be touched when feat: commits land" → `enforce-changelog`).

  **Slug validation gate**: Before any Write, assert both computed slugs match the regex
  `^[a-z0-9][a-z0-9-]{0,62}$`. If either does not (contains `/`, `.`, `..`, special chars, or
  exceeds 63 chars): abort the hand-off via AskUserQuestion `{Edit slug manually / Cancel}`.
  This prevents path-traversal via crafted rule descriptions.

  3. Generate the `detection_logic` bash block and `remediation_logic` bash block
     for the specific rule — Claude authors these from the rule description and Q4 style.
  4. Render both templates via string substitution, replacing all five placeholders:
     `{{rule_description}}`, `{{workflow_name}}`, `{{script_name}}`,
     `{{detection_logic}}`, `{{remediation_logic}}`.
  5. Present the rendered YAML and rendered .sh as a PREVIEW to the user — do not
     write any files yet.
  6. AskUserQuestion `{Write — commit the workflow + script, Refine — show changes I want to make, Cancel — abort}`:
     - `Write` → Write the rendered YAML to `.github/workflows/{{workflow_name}}.yml`
       AND the rendered .sh to `scripts/ci/{{script_name}}.sh`
     - `Refine` → prompt the user for specific changes, regenerate, and return to step 5
     - `Cancel` → exit with no files written

- Any mechanism starting with `git pre-push hook` →
    1. Read template file:
       `plugins/tcs-helper/templates/githooks/pre-push-rule-enforcer.sh.j2`
    2. Determine `response_style` from `triage.q4`:
       - `Block` → response_style = `Block`
       - `Nudge` or `Auto-fix` → response_style = `Nudge`
    3. Author `detection_pattern` (bash conditional using `$commits_file` / `$diff_file`) and
       `warning_message` from the rule description and Q4 style.
    4. Render the template via string substitution, replacing all four placeholders:
       `{{rule_description}}`, `{{detection_pattern}}`, `{{response_style}}`, `{{warning_message}}`.
    5. Compute target filename: `.githooks/pre-push-rule-enforcer-<slug>.sh`
       where slug = kebab-case derived from the rule description.

  **Slug validation gate**: Before any Write, assert the computed slug matches the regex
  `^[a-z0-9][a-z0-9-]{0,62}$`. If it does not (contains `/`, `.`, `..`, special chars, or
  exceeds 63 chars): abort the hand-off via AskUserQuestion `{Edit slug manually / Cancel}`.
  This prevents path-traversal via crafted rule descriptions.

    6. **Collision check**: read `.githooks/tcs-helper-rule-enforcer-version` if it exists;
       compare to the plugin's current marker (read from
       `plugins/tcs-helper/templates/githooks/tcs-helper-rule-enforcer-version`).
       - Marker missing → fresh install: proceed.
       - Marker matches → AskUserQuestion: append a new hook vs replace existing.
       - Marker differs → AskUserQuestion: suggest re-install
         (offer `Skill(tcs-git-helpers:git-setup)` hand-off for full bundle refresh).
    7. Present the rendered `.sh` as a PREVIEW — do not write any files yet.
    8. AskUserQuestion `{Write — install hook, Refine — show changes I want to make, Cancel — abort}`:
       - `Write` →
         - Write rendered script to `.githooks/pre-push-rule-enforcer-<slug>.sh`
         - Copy `plugins/tcs-helper/templates/githooks/tcs-helper-rule-enforcer-version`
           to `.githooks/tcs-helper-rule-enforcer-version` (sibling marker)
         - `chmod +x .githooks/pre-push-rule-enforcer-<slug>.sh`
         - Remind user to run `git config core.hooksPath .githooks` if not already configured
       - `Refine` → prompt user for specific changes, regenerate, return to step 7
       - `Cancel` → exit with no files written

**Fallback (target plugin not installed):**

AskUserQuestion with options:
- `Install plugin first — I will install plugin-dev and retry`
  → Instruct user to install the plugin, then abort triage (do not attempt hand-off).
- `Use Memory rule instead — add to memory with strong wording`
  → `Skill(tcs-helper:memory-add)` with `type=feedback` + strong-language hint.
- `Cancel — exit triage, no action taken`
  → Exit skill immediately with no further action.
