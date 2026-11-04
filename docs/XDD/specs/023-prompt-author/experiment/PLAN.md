# Experiment: Opus- vs Sonnet-authored prompts

Question: given the same authoring request, does a prompt written by Opus or by Sonnet perform better on its target — and which failure modes from research-corpus.md does each produce? Results feed the PRD of spec 023.

## Arms

| Arm | Author | Prompts per task |
|---|---|---|
| O | `claude -p --model claude-opus-5-5` | 3 independent authorings |
| S | `claude -p --model claude-sonnet-5-5` | 3 independent authorings |
| Q | status quo — the prompt currently in the repo | 1 |

Authoring isolation (verified 2026-11-04): empty temp dir, `--setting-sources "" --strict-mcp-config --disable-slash-commands --no-session-persistence --tools ""`. Context then holds only the account email and the environment block — no CLAUDE.md, memory, skills or plugins. Same day, pinned model IDs, default effort.

Agentic target runs (T2-T4) add `--restricted --tools <names> --allowedTools <allowlist>` and run in a scratchpad fixture repo. Verified 2026-11-04 with a haiku probe: commit inside the fixture succeeded; reading `/etc/hostname` and `ls /` were refused, and the child did not try to work around the refusal. Never `bypassPermissions`. Fixtures use stdlib `unittest` (no pytest in the container).

The authoring request states purpose, target environment and inputs, never the grading criteria (`tasks/<T>/request.md`).

## Tasks

| ID | Authors write | Target runs on | Inputs | Graded by |
|---|---|---|---|---|
| T1 | research system prompt for a chat assistant without web search (from corpus #1/#2) | `claude -p --model haiku`, no tools | 20 research questions | script: four required sections present, counterargument section non-empty, every URL either resolves (HEAD) or is absent, claims without source are flagged as unverified; judge: unsupported claim presented as fact |
| T2 | implementer subagent brief (corpus #13) | `claude -p --model sonnet` with Bash/Read/Edit/Write in a fixture git repo | 10 tasks (2 with a withheld SDD section) | script: final message contains a parseable status from the vocabulary; NEEDS_CONTEXT on the withheld cases; test commit precedes code commit; no file outside the task's scope changed |
| T3 | code-review perspective brief (corpus #14) | `claude -p --model sonnet`, Read/Grep/Glob/Bash in a fixture repo | 10 diffs, each with one planted bug and one uncommitted "teammate" file | script: every finding has location+severity+confidence; `git status`/reflog unchanged; teammate file not flagged; judge: planted bug identified |
| T4 | CLAUDE.md for a small fixture repo (corpus #6/#7) | `claude -p --model haiku` with tools in the fixture repo | 5 coding tasks | script: every path/command named in the CLAUDE.md exists/runs; documented test command used; size ≤ budget |
| T5 | port the PRD interview prompt (corpus #3) to a local model | Ollama `qwen3.5:35b-a3b` via host.docker.internal:11434 | 10 scripted simulated-user sessions (simulated user: `claude -p --model haiku`) | script: one question per assistant turn, final doc has all 8 sections, no undefined markers (`[NEEDS …]`, Claude Code idioms); judge: no implementation detail ("HOW") in PRD |

Status-quo prompts: T1 docs/templates/setup-perplexity-space.md system prompt; T2 implement-incremental 4d brief; T3 review SKILL.md brief + perspectives; T4 the fixture's hand-written CLAUDE.md baseline (none in repo fits — written by the experimenter, labelled); T5 docs/templates/prd-prompt.md.

## Judge

Script graders wherever possible. Semantic criteria use a non-Claude judge — Ollama `qwen2.5:32b-instruct` — so neither author family grades its own output. Judge sees one output at a time, blind to arm, with a binary PASS/FAIL rubric; graded output wrapped in `<output>` tags. Before trusting it, the judge is checked against ~20 hand labels per semantic criterion from the user (~60 total; decided 2026-11-04). Agreement below 85% on a criterion → that criterion is reported as unvalidated, not dropped silently.

## Analysis

- Unit: (prompt, input) pass/fail per criterion, plus all-criteria pass.
- Primary: paired O-vs-S difference in all-criteria pass rate per task, bootstrap 95% CI clustered by authored prompt; Q reported alongside.
- Secondary: failure-mode tally of the authored prompts themselves (lint + manual against research-corpus.md codes), prompt token length.
- Pilot first: 1 authoring per arm × 3 inputs per task → freeze criteria and graders, then full run. Criteria changes after the freeze are logged, not silently applied.

## Budget and safety

- Every `claude -p` call carries `--max-budget-usd`; a run ledger sums `total_cost_usd`; the whole experiment stops at a ceiling of $400 (estimate $100-400).
- No GEMINI_API_KEY, no external providers. Ollama local only.
- Runs, fixtures, grades and the ledger live in `~/.cache/spec023-runs/` (outside the repo, survives the session); only `results.md` and the authored prompts (`prompts/`) are committed.
- Fixture repos are built with `git -C` and `GIT_CONFIG_GLOBAL=/dev/null` (active.md).

## Confounds controlled / remaining

Controlled: session context (isolation flags), criteria leakage, author-as-judge (non-Claude judge), single-authoring variance (3 per arm), drift (same day). Remaining: target family = author family for T1-T4 (unavoidable for Claude-targeted prompts; judge is not Claude); task selection drawn from known failures — T4 fixture is new to both models as a partial counter.
