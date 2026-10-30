# Plugin Evals

A pressure scenario that lives in a conversation is run once and lost. Written as a
`claude plugin eval` case, it runs again after every edit and answers whether the edit changed
behaviour or only text. Evals run locally, never in CI.

---

## Layout

```
plugins/<plugin>/evals/
  README.md                      # how to run, cost per case
  <case>/prompt.md               # frontmatter + the prompt, sent verbatim
  <case>/graders/<name>.md       # one grader per file; frontmatter type + options, body = rubric
```

`plugins/*/evals/results/` is gitignored. A case without graders is invalid. The runner also
accepts a single `case.yaml` per case; this repo uses `prompt.md` plus `graders/`.

Scaffold a case with `claude plugin eval init --bare <name>`. Without `--bare`, `init` runs an
authoring interview that needs an interactive terminal.

`prompt.md` frontmatter: `description`, `tags`, `runs` (default 3), `max_turns`, `timeout_seconds`,
`allowed_tools`, `expected_outcome`. Unknown keys are an error.

## Writing a Case

1. **Put every input in the prompt.** Each run starts in an empty directory, and `context.add_dirs`
   fixtures are not reliably visible. Inline a diff or spec in a fenced block.
2. **Decide what you measure: triggering or discipline.**
   - Discipline: start the prompt with the typed command (`/tcs-workflow:xdd-tdd …`). The skill
     loads inline, and no `Skill` tool call is recorded.
   - Triggering: phrase it the way a user would, without naming the skill, and add a `tool_used`
     grader with `tool: Skill`. It is reported as an indicator, not scored. Use a neutral request:
     when the user explicitly waives what the skill enforces ("tests after the demo"), the model
     follows the user and no description makes it invoke the skill. Pair it with a request the
     skill must stay out of, graded `min: 0, max: 0`, `arm: both`.
3. **Apply the pressure the skill exists to resist** — deadline, "it's trivial", "tests later".
4. **Grade behaviour with deterministic graders first:**
   - `regex` with `target: trace` and `match: not_contains` for "this was never written"; match the
     content that makes it real (a stub that only raises is legitimate TDD).
   - `file_exists` for "this was created". It sees only files created during the run.
   - `regex` on `last_message` for a verdict string.
5. **Point an `llm` grader at `focus: last_message`.** On the full trace the default judge has
   failed a correct run. Write PASS and FAIL conditions explicitly.

## Proving Signal

A suite that passes proves nothing until it has failed:

1. Run it: `claude plugin eval plugins/<plugin> --case <case> --runs 3 --trust-plugin --no-publish --max-cost-usd 5`.
   The default with/without arms report the plugin's delta.
2. Weaken the rule the case defends in the skill, re-run with `--ablation none`, and confirm the
   score drops. Restore the skill.
3. Record both scores in the plugin's `evals/README.md`.

Grant `Write`/`Edit` with `--allow-tools Write Edit` when a case needs them; `allowed_tools` in the
case cannot grant them. Set `--max-cost-usd` on every run, and `--no-publish`: the report is
published to claude.ai by default.
