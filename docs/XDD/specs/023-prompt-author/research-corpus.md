# Real-Prompt Corpus + Experiment Design — prompt-author (2026-11-04)

Read-only research agent; line numbers from `cat -n`. Spot-checked by the orchestrator: AGENTS.md `the-meta-agent.md` (l.29, 37) absent from tree; implement-incremental 4d brief (l.189-205) never asks for the DONE/DONE_WITH_CONCERNS/NEEDS_CONTEXT/BLOCKED status the orchestrator branches on (l.209-219) — both confirmed.

Scope: `/Volumes/Moon/Coding/` holds only this repo (no siblings). No API system prompt in code found in repo, `modules/satori` or `~/Kouzou` (rg system_prompt / messages.create / chat.completions). Closest: Perplexity Space / Claude.ai Project system prompts. `~/Kouzou` is not a git repo; its `multi-ai/templates/*` are byte-identical to `docs/templates/*` (co-authored Opus 4.6 + Sonnet 4.6: a8f76a8f, 40ff4da7).

Codes (research-external.md): OP over-prescription, EE enumerated edge cases, EM emphasis/caps, RH rationale missing / history noise, NO negative-only, CO contradiction, OC no output contract, EX example over-anchoring, UI untrusted input, CX assumes absent context, LL long instruction list. NEW codes below.

## Corpus

| # | Path:lines | Kind / target | Failures |
|---|---|---|---|
| 1 | docs/templates/research-prompt.md:19-143 | other / Perplexity, Claude.ai, ChatGPT | EX "respected engineering teams (Stripe, Netflix, Shopify, etc.)"; CX no no-search fallback though l.282 recommends Claude.ai → citations may be invented. Good: role, numbered asks, fixed output sections |
| 2 | docs/templates/setup-perplexity-space.md:245-259 | api-system / Perplexity | RD "Cite sources…" repeated as "Never: Present a finding without a source"; counterargument rule twice. PL l.282 "they work identically" untested |
| 3 | docs/templates/prd-prompt.md:154-224 | other / Claude.ai, ChatGPT | RD/NO no-"HOW" ban ×3 (l.154, 169, 173-180); EM "Ask ONE clarifying question"; PL/CX `[NEEDS CLARIFICATION]` never defined (xdd-prd idiom) |
| 4 | docs/templates/brainstorm-prompt.md:10-87 | other / Claude.ai, ChatGPT | RD/EM "one question" ×5; PL/OP "Red Flags — Stop If You Catch Yourself Thinking" table (skill-author idiom in a chat); EM "Apply YAGNI ruthlessly"; CO with user "Urgency cues don't override design discipline" |
| 5 | docs/templates/setup-claude-project.md:21-35 | api-system / Claude.ai Project | Mostly good (framework context, short). SC project-wide "Wait for my approval" + "one question at a time" also hit dialogue-free research queries; RD PRD ban repeated from #3 |
| 6 | AGENTS.md:1-262 | claude-md | ST: `the-meta-agent.md` absent; "v2.0.0" vs manifest 4.4.8; skills `setup/`,`docs/` are memory-setup, doc-product; `writing-skills/reference/conventions.md` missing; `docs/patterns|interfaces|domain` missing; tcs-git-helpers, tcs-issues absent from tree. CO "prefixing… only applies to commands, not skills" (l.107) false. LL mostly overview (ETH: doesn't help) |
| 7 | CLAUDE.md:15-63 | claude-md | CX/ST `~/.claude/includes/` absent in container; CO "sync changes back" (l.57) copies repo→cache again; RD cp block duplicated; SC/LL 30-line procedure always loaded, paid by every subagent. Good: "Cache-only does not work — Claude Code validates against the marketplace source" |
| 8 | docs/ai/CLAUDE.md:18-43 | claude-md | Mostly good: positive entry template, measurable budget with reason ("wc -c, not wc -l"). RH/NO l.38 bans without reason |
| 9 | ~/Kouzou/standards/general.md:7-20 | standard (always loaded) | CX "Use Plan Mode…" impossible for subagent/headless; CX "Consider macOS-specific deviations" vague on Linux container; EM/RH "in ANY command… (Recurs ≥1×/session.)" ~700-char bullet; CO l.16 tracked-in-git vs gitignored allowed; mixed altitude |
| 10 | ~/Kouzou/standards/tone-behavior.md:8 + code-conduct.md:4-16 | standard | Cross-file CO "When in doubt, ask" vs "default to information and recommendations"; in-file CO "Add a short description… into any file" vs "Prefer self-documenting code"; EM "NEVER create files"; RH maintainer note "(Mirror in workflows.md…)" |
| 11 | ~/Kouzou/standards/guardrails.md:4-73 | standard | RH dates, commit SHAs ("`024f277` post-mortem"), repo names in Why lines; EE one rule per incident; SC Obsidian/React rules in a shell-scripts file; cross-file CO `venv/` vs repo `.venv/`; EM "non-negotiable" |
| 12 | plugins/tcs-workflow/skills/brainstorm/reference/spec-reviewer-prompt.md:16-50 | subagent-brief | Good: calibration of what is *not* an issue; status + issues contract. Weak: VP "Approve unless there are serious gaps"; UI spec not marked as data; ST "Task tool (general-purpose)" (unverified) |
| 13 | implement-incremental/SKILL.md:189-205 (+ implement-direct/SKILL.md:116-123) | subagent-brief | OC/CA orchestrator branches on DONE/DONE_WITH_CONCERNS/NEEDS_CONTEXT/BLOCKED (inc l.209-217, direct l.129-140), brief never requests a status; RD/CO "Fresh subagent… no session history bleed" (l.60) vs "Never: Pass session history… scene-setting only" (l.70); EM ALL/ONLY/ALWAYS; LL ~22 constraints. Last commit co-authored by Opus 5.5 |
| 14 | plugins/tcs-workflow/skills/review/SKILL.md:111-118 | subagent-brief | OC/CA synthesis dedupes by location, sorts by severity then confidence (l.123-125), brief asks no finding format; CX no read-only-git fence (cf. implement 4f, #156) and no commit-range scoping (active.md); EM perspectives.md "Aggressively challenge" |
| 15 | plugins/tcs-team/agents/the-chief.md:46-118 | subagent-brief (agent def; upstream origin) | OP four 1-5 scores summed to route judgment; CO "Tests \| Parallel with \| Implementation (TDD)" vs test-first, "Launch all simultaneously" vs sequencing table; EM PROACTIVELY/MUST BE USED; CX "internalize Project CLAUDE.md" already loaded. Good: typed output schema |
| 16 | docs/ai/memory/active.md, general.md | claude-md (always loaded) | Best in corpus: rule + tell + "→ action", mechanism not incident, ≤250 chars, positive. Weak: jargon-dense, several entries at the cap |

## Failure frequency (16 items)

| Mode | Count | Where |
|---|---|---|
| EM | 8 | every kind |
| CO in-file | 6 | 4, 7, 9, 10, 13, 15 |
| CX | 6 | 1, 3, 7, 9, 14, 15 |
| RD (NEW) | 5 | 2, 3, 4, 5, 13 |
| CO cross-file (NEW) | 2 (+1 borderline) | 10, 11 (5) |
| ST (NEW) | 3 | only claude-md/AGENTS (+ one stale tool name in 12) |
| PL (NEW) | 3 | only cross-environment templates |
| SC (NEW) | 3 | 5, 7, 11 |
| RH history noise | 3 | only standards (9, 10, 11) |
| LL | 3 | 6, 9, 13 |
| OC/CA | 2 | only subagent briefs (2 of 4) |
| OP | 2 | 4, 15 |
| UI | 2 (low severity) | 12, 14 |
| EX, NO, EE | 1 each | |

Not observed: few-shot over-anchoring. Missing rationale rarer than expected; the bigger problem is rationale written as incident history.

What good prompts do: one-clause mechanism reasons; explicit "what is not an issue" calibration; positive templates; fixed output sections/schema.

## NEW failure modes

- **RD redundant restatement** — same rule as Always/Never mirror or 3-5× in one prompt; acts as emphasis, costs instruction budget.
- **CA contract asymmetry** — consumer parses fields/vocabulary the producer's brief never requests; visible only when auditing dispatch site and parsing site together.
- **ST stale facts** — paths, counts, versions drift; checkable against the tree; dominant CLAUDE.md/AGENTS.md failure (matches ETH finding).
- **PL port leakage** — Claude Code skill idioms/markers carried into another environment; untested portability claims.
- **SC scope mismatch** — rule at the wrong load level (global/always-loaded carries domain rules; project-wide rule breaks one session type).
- **Cross-file CO** — conflicts between co-loaded files; invisible to single-prompt audit.
- **VP verdict prior** — reviewer brief presets the answer ("Approve unless…"); 1 item, weak.

## Opus-vs-Sonnet experiment design (not run)

Tasks (current prompt = third, status-quo arm):
- T1 Perplexity research system prompt (#2): every claim cited, counterargument section, four sections, URLs resolve (script).
- T2 Implementer brief (#13): parseable status, test commit precedes code commit, no out-of-scope file, NEEDS_CONTEXT when an SDD section is withheld.
- T3 Reviewer brief (#14): each finding has location/severity/confidence; git status + reflog unchanged; planted uncommitted "teammate" file not flagged; planted bug caught.
- T4 CLAUDE.md for a fixture repo (#6/#7): no false path/command claim (script); target agent uses documented test command on 5 tasks; size budget.
- T5 Port PRD chat prompt to GPT/Gemini (#3): scripted simulated user; one question/turn, no HOW, 8 sections, no undefined markers.

Author input: identical realistic request (purpose, target, inputs) without grading criteria; fresh `claude -p --model opus|sonnet` in empty temp dir, no CLAUDE.md/plugins/memory (isolation flags unverified); same effort, pinned IDs, same day; 3 authorings per model per task.

Evaluation: fixed target model (ideally not author family); same 20-30 inputs per task across arms (paired; pilot → power analysis); binary per-criterion grading, script wherever possible; LLM judge = third model, blind, randomized, single-output; validate vs ~50 labels from the user per semantic criterion; freeze criteria after pilot on held-out inputs; report paired pass-rate difference with bootstrap CI clustered by authored prompt + prompt token length.

Cost (unverified): authoring negligible; ~750 target runs; ~$100-400; 1-2 days, mostly fixtures. T2/T3 can drop to 10 inputs.

Confounds: authoring session loading repo rules/memory; author-as-judge or author family as target; criteria leakage; verbosity bias; model drift/temperature; task selection bias (add one unseen-failure task); plugin skill auto-trigger during authoring; single authoring per model.

Unverified: `~/Kouzou` authorship beyond repo copies; `~/.claude/includes/` on macOS host; the-chief original author; "Task tool" naming.
