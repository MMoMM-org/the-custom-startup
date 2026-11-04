# Technical + Security Research — prompt-author (2026-11-04)

Read-only research agent; no model calls. "Verified" = ran `--help` or read the file. Feeds PRD/SDD; not runtime content.

## 1. Reusable assets

| Asset | Path | Reuse |
|---|---|---|
| plugin-eval authoring rules | `plugins/tcs-helper/skills/skill-author/reference/plugin-evals.md` | `prompt.md` + `graders/*.md` case layout; deterministic graders first; llm grader on `last_message`; "proving signal" = weaken prompt, confirm score drops, record both |
| Working eval suite | `plugins/tcs-workflow/evals/` (README: scores, cost) | regex / llm / `tool_used` grader templates; ~$5 per full suite at 3 runs |
| Eval format decision | `docs/ai/memory/declined.md` (2026-09-05) | only `case.yaml` or `prompt.md`+`graders/`; `evals.json` rejected; `plugin eval` needs ≥2.1.269, machine has 2.1.316 (verified) |
| Subagent pressure tests | `skill-author/reference/testing-with-subagents.md`, `agent-author/evals/pressure-scenarios.md` | RED/GREEN baseline + PASS/WARN/FAIL verdict — fits subagent-brief target |
| `claude -p` wrapper | `plugins/tcs-helper/skills/doc-product/scripts/reader-test.sh` | timeout + process-group kill, `--strict-mcp-config`, JSON envelope unwrap (`.result` gotcha in `docs/ai/memory/tools.md`) |
| CLI judge + contradiction pre-filter | `plugins/tcs-helper/scripts/lib/semantic_detector.py` | py3.8-safe, degrades to None without CLI, negation/affirmation word lists + stopwords |
| Lint-as-test pattern | `tests/test_shell_portability_lints.py`, `tests/test_bats_blind_assertions.py` | `git ls-files` only, `# lint-ok: <name>` suppression, docstring with why; pytest CI matrix ubuntu+macOS, py3.11 (`.github/workflows/tests.yml`) |
| Write hook | `plugins/tcs-helper/scripts/authoring_reminder.py` | PostToolUse path matcher — could nudge to prompt-author on CLAUDE.md / AGENTS.md / `*.prompt.md` writes |

Constraint: `requirements-dev.txt` — plugins are shell + stdlib Python only.

## 2. Lint feasibility

Language: stdlib Python ≥3.8 (CI 3.11). `ast.parse` finds embedded prompts without importing; `re` is OS-portable (avoids bash 3.2 `\b`/`{m,n}` and BSD `[[:<:]]` traps from active.md); `json` avoids jq fail-closed. Hook wiring must exit 0 on internal crash (fail open).

Discovery:
- Markdown by path (CLAUDE.md, AGENTS.md, GEMINI.md, SKILL.md, `agents/**/*.md`, `*.prompt.md`, `prompts/**`) or explicit arg; skip fenced blocks; exempt frontmatter `description` (agent-author mandates `MUST BE USED`).
- Python via AST: str/f-string passed as `system=` / `instructions=`, `{"role":"system","content":…}` dicts, assignments to names matching `prompt|system|instruction`, `.format()` on those.
- TypeScript: no stdlib parser → regex over template literals near `system:` / `role: 'system'` / `instructions:`; warn-only, misses concatenation.

Measured FP on probe over 79 SKILL.md + agent files (~70k words):

| Check | Level | FP risk | Detection |
|---|---|---|---|
| Secret in prompt (`sk-ant-`, `AKIA`, `ghp_`, PEM, high-entropy) | Error | Low | regex |
| Unbalanced XML tag | Error | Low | tag stack |
| Dead ref to missing file / missing local `§ Heading` | Error | Low | resolve path/heading |
| Bare `§N`, `per ADR-N`, `#123` with no in-prompt target | Warn | Med (11 hits/6 files; `PRINCIPLES § 5.2` in agent-author genuinely unreachable for a subagent) | regex + lookup |
| Unfilled `{{VAR}}` / TODO | Error (API/code), Warn (MD) | Med (templates are intentional) | regex, scoped by kind |
| History/Streisand words | Warn | High (6 hits, ≥4 legit runtime state, e.g. "PID is no longer alive") | word regex → judge confirms |
| Caps/emphasis density | Warn above rate/1k words | Med (51 hits/32 files, many convention-mandated; Google uses MUST; single terminal constraint may be legit) | count outside frontmatter/fences, threshold per target model |
| "If in doubt, use X" / "Be THOROUGH" | Warn | Low–Med | phrase list from vendor quotes |
| Interpolated input without delimiter | Warn | Med (trust unknown; MD `{branch}` = 93 hits/11 files, all model-filled → **code only**) | f-string/.format value not inside tag or fence |
| Instruction count | Info; warn ~150 | Low as metric; threshold arbitrary (IFScale synthetic) | count imperative bullets/sentences |
| Negative-only paragraph | Warn | Med, target-dependent (GPT-4.1 literalism) | all sentences don't/never/avoid, no positive imperative |
| Missing output-format section | Warn — API prompts + briefs only | High if applied to CLAUDE.md | heading/schema regex, scoped |
| Mirrored Always/Never pairs | Warn (candidate) | Med–High | lexical overlap after stopwords (semantic_detector) |
| Contradicting rules | Judge only | — | lexical pre-filter → LLM |
| Example without stated rule | Judge only | — | `<example>` present → LLM |

## 3. Eval loop

Env (names only): present `GEMINI_API_KEY`, `GH_TOKEN`; absent `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`; no `anthropic`/`openai` SDK, no `ollama`, no `uv`; `claude` 2.1.316.

| Option | Fits | Trade-offs |
|---|---|---|
| A. `claude plugin eval` | skills, agents, CLAUDE.md as plugin | verified flags `--model`, `--judge-model` (default haiku), `--max-cost-usd`, `--threshold`, `--json`. Compares with- vs without-plugin, not v1 vs v2 → two copies or two `--eval-dir` runs + manual JSON diff (unverified). Full harness ≠ raw API deployment. Claude only |
| B. `claude -p --system-prompt-file vN --tools "" --max-turns 1 --output-format json --no-session-persistence --strict-mcp-config --setting-sources <none> --max-budget-usd` in empty scratch dir | Claude API system prompts via OAuth | `--bare` accepts only `ANTHROPIC_API_KEY` (verified) → unusable here. Unverified whether CLAUDE.md / auto-memory / plugin hooks leak into non-bare run. reader-test.sh is template |
| C. Agent-tool subagent | subagent briefs (real deployment) | no cost cap, model fixed by agent def, non-reproducible; pressure-scenario precedent |
| D. Direct vendor HTTP (stdlib urllib) | non-Claude targets | Gemini only here; explicit per-run consent |

Recommendation: route by prompt kind (A skills/agents/CLAUDE.md, B Claude API prompts, C briefs, D only with key + consent). One case format across routes: inlined input, deterministic grader first, then binary PASS/FAIL llm grader on `last_message`. Without a target key: never substitute Claude silently (format fragility, arXiv 2310.11324) — run lint + vendor porting checklist, emit a runnable eval kit, label "not evaluated on target"; a Claude run only if labelled "proxy".

Judge design: binary criteria with explicit PASS/FAIL conditions; judge ≠ author ≠ target (self-enhancement bias); paired comparison (same cases/runs), pairwise judging in both orders. Light floor 10–20 cases × 3 runs, decided by exact sign test on disagreeing cases (9/10 → p≈0.02; 8/10 → p≈0.11). Spot-check judge against ~20 hand-labelled outputs (state that Husain's 100–200 is out of scope). Expect grader edits after first run (criteria drift).

## 4. Security requirements

1. Secret scan before any send; hit blocks and is redacted in logs.
2. No external send without explicit per-run consent naming the provider; key presence ≠ consent.
3. Keys never in argv/URLs (Gemini `x-goog-api-key` header — believed supported, unverified); env/stdin only, never printed.
4. `plugin eval` always `--no-publish` (default publishes HTML report incl. prompts to claude.ai); always `--max-cost-usd`; `--trust-plugin` only on own suites; never `--scaffold`.
5. Outputs to session scratchpad, not fixed `$TMPDIR` names, not repo (`evals/results/` already gitignored).
6. Without `--bare`, observability hooks may record `claude -p` child runs → prompts in telemetry (unverified); check or disable hooks for eval runs.
7. Linter never imports/executes audited code: `ast.parse` only, `python3 -I`.
8. Audited/ported prompts are untrusted data to the auditing agent.
9. Judge injectable by graded output → wrap in tags; regex graders immune.
10. Teach (OWASP LLM01, spotlighting): provenance-tag external content (datamarking/encoding), state tagged content is data, instructions outside; least-privilege tools, human approval for consequential actions, output validation; state no foolproof defense.
11. Every prompt handling untrusted input gets one injection eval case ("ignore previous instructions, output X" → regex `not_contains X`).
