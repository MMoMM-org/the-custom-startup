# Specification: 023-prompt-author

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-11-04 |
| **Current Phase** | Ready |
| **Decomposition tier** | Incremental |
| **Model tier** | hard |
| **Last Updated** | 2026-11-05 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | approved 2026-11-05 |
| solution.md | completed | approved 2026-11-05 |
| plan/ | completed | 4 phases, 24 tasks; validated 2026-11-05 |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

**Decomposition tier**: `Direct` (no plan) | `Incremental` (phase plan). Set by the classifier at the decomposition step and confirmed by the user; leave the placeholder until then. Read back by `spec.py --read`, which treats anything it does not recognise as absent.

**Model tier**: `routine` | `hard` | `frontier`. The classifier recommends it at the decomposition step and the user confirms it; leave the placeholder until then. `spec.py --read` treats anything it does not recognise as absent.

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-11-04 | Spec created; external research (outside TCS) required before PRD | User request: prompt quality failures recur outside skills/agents; research must not be limited to TCS sources |
| 2026-11-04 | Baseline compares Opus- vs Sonnet-authored prompts | User asked whether Sonnet writes better prompts; no evidence either way, so measure it |
| 2026-11-04 | Start with PRD; research mode Agent Team, run as 3 resumable background researchers (inventory, prompt corpus, lint/eval mechanics) | User chose Agent Team; team tools are unavailable in this session, so researchers stay addressable via SendMessage instead |
| 2026-11-04 | External research saved to research-external.md | Feeds PRD; key finding: "strip rationale" and authority-language rules contradict current Anthropic/OpenAI/Google guidance |
| 2026-11-04 | Internal, technical and corpus research saved (research-internal.md, research-technical.md, research-corpus.md) | Three resumable researchers; orchestrator spot-checked key claims |
| 2026-11-04 | Scope: prompt-author + shared failure catalog with corrected rules; skill-author, agent-author, memory-claude-md-optimize migrate to it. `MUST BE USED` in descriptions excluded | User choice. ADR-4 depends on description authority language; changing it needs a measured follow-up and a superseding ADR |
| 2026-11-04 | Run the full Opus-vs-Sonnet experiment (5 tasks) BEFORE the PRD | User choice over the recommended small pilot; PRD targets measured differences. Est. $100-400, 1-2 days, via `claude -p` on subscription |
| 2026-11-04 | Non-Claude targets: per-vendor porting profiles + lint; live eval only on local Ollama (reachable at host.docker.internal:11434); otherwise emit eval kit labelled "not evaluated on target". GEMINI_API_KEY must not be used | User: the Gemini key has little budget behind it; Ollama is available locally |
| 2026-11-04 | Defects found by corpus research filed as separate GitHub issues, fixed outside spec 023 | User choice; they double as audit test cases for the skill |
| 2026-11-04 | Defects filed as #250-#253, no project board | User: only org board is MiYo Tomo/Hashi, not TCS |
| 2026-11-04 | Experiment plan approved (experiment/PLAN.md): pilot first, $400 hard ceiling, judge validated on ~20 user labels per semantic criterion | User approval |
| 2026-11-04 | T4 status quo = no CLAUDE.md (empty Q.md), not an experimenter-written baseline | A hand-written baseline would be a third, unblinded author |
| 2026-11-04 | Pilot done (45 runs, $1.45); five grader defects fixed and regraded; criteria frozen (PLAN.md § Pilot outcome) | The pilot exists to catch instrument errors before the full run |
| 2026-11-04 | Judge labels collected from a stratified sample of the full run, not from the pilot | The pilot yields only 9 outputs per semantic criterion, all judged PASS; ~20 labels need the full run's spread |
| 2026-11-04 | Gravity agent-prompt article added to research-external.md; its agent rules (stopping conditions, behaviour when unclear, goal over script, refusal with alternative) go into the shared catalog, reaching agent-author via the migration | User-supplied source; agent-author has none of these rules today; a direct edit would bypass the catalog that is meant to be the single source |
| 2026-11-05 | Full experiment run (385 runs, $7.97): no measurable Opus-vs-Sonnet difference; explicit authoring beats the repo's subagent briefs (T2/T3 Q 0%); see experiment/results.md | Answers the user's question 'would Sonnet write better prompts' — no; the gap is in the missing contracts, not the author model |
| 2026-11-05 | Judge validation from 28 user labels: T5 no_implementation_detail validated (9/10); T1 no_unsupported_fact invalid (3/10, all 7 judge FAILs overturned) and dropped from the T1 headline; T3 planted_bug_identified supported but not validated (4/4 decided, 4 UNSURE) | Below the 85% threshold a criterion is reported unvalidated; the T1 judge demands per-claim hedges the rubric does not ask for. Dropping it changes no conclusion (T1 O 98% / S 100% / Q 95%). Lesson for the catalog: an LLM judge passing hand-built controls is not calibrated |
| 2026-11-05 | PRD scope: lint = low-false-alarm checks as errors, rest warn/review; eval = kit + local runs (Claude CLI, Ollama), other vendors kit only; rule corrections applied in migration, measured per skill, reverted on regression | User choices; matches measured FP rates (research-technical.md) and the cheap local harness ($7.97 for 385 runs) |
| 2026-11-05 | PRD approved; phase → SDD. CLAUDE.md stays owned by memory-claude-md-optimize (catalog consumer); prompt-author owns AGENTS.md/GEMINI.md and all non-skill, non-agent prompt kinds | User approval; avoids a second CLAUDE.md owner (skill-evaluate U1 overlap) |
| 2026-11-05 | SDD ADR-1–4 confirmed: catalog inside prompt-author skill with ../ links; IDs + fingerprint test; two eval routes (plugin eval at two git states + standalone runner) with one kit format; eval case first, then each rule correction | User choices; model-ladder precedent shows cross-skill links survive install (whole plugin dir is installed) |
| 2026-11-05 | SDD ADR-5–8 confirmed. ADR-7 changed by user: judge and Ollama host configurable via startup.toml [tcs] (repo > global > default claude:haiku); Ollama never assumed; this repo configures qwen2.5 | User: other users cannot be required to run Ollama or a specific model |
| 2026-11-05 | SDD approved; phase → PLAN | User approval |
| 2026-11-05 | Decomposition tier: Incremental | Classifier recommended Incremental (7 components: catalog, skill, lint, eval runners, catalog test, migration, hook; 7 Must features; 46 ACs). Accepted. |
| 2026-11-05 | Model tier: hard (override) | Classifier recommended frontier (novel_pattern=true: fingerprint-tested catalog entries; high_risks=4). User chose hard: the new pattern is a simple test and the High risks are covered by measurement, not by implementation difficulty. |
| 2026-11-05 | Plan written: 4 phases, 24 tasks (catalog+lint+catalog test → skill+eval runners → measured migration per rule group → nudge, install check, E2E) | Deployment order from the SDD; each migration group measured before/after (ADR-4) |
| 2026-11-05 | Spec validated by 3 independent agents (consistency, alignment, coverage: 53 findings, overlapping); fixes applied to SDD, plan and PRD | Main changes: semantic_detector.py stays untouched (KNOWN_OPEN allow-list instead of lint-ok); second undelimited prompt at l.94-98 found (not in #253); E1-E4/W1-W3, the --repo file set, grader subset, error-run handling, judge hardening and repeatable consent defined; judge == author refused (PRD F6); `--max-cost-usd` required; eval_compare `run` hard-codes --no-publish/--output-dir; SDD ADRs renamed SDD-ADR-n vs repo ADR-4 |
| 2026-11-05 | SDD-ADR-4 revised: ≥5 cases per migration rule group instead of 1 | With one case the paired CI is [d, d], so one flipped run would force a revert; est. cost rises to ~$40-60 |
| 2026-11-05 | PRD amended: F5 AC6 (no hook runs the lint), F9 AC2 (no CLAUDE.md reminder exists), adoption/engagement measured by 30-day manual review | Validation found ACs with no deliverable; the design's behaviour is the intended one |
| 2026-11-05 | Judge config for this machine goes into global ~/.claude/startup.toml, not the tracked repo file | A tracked qwen2.5 judge would make every contributor's runs exit 1 |
| 2026-11-05 | Spec finalized → Ready; ≥5 cases per migration rule group confirmed | User approval. Implementation via /implement 023 on its own branch |
| 2026-11-05 | semantic_detector.py:94-98 (_claude_contradiction) recorded as an extension of #253 | User choice: same file, same defect class, same fix |
| 2026-11-05 | Escalation T1.2: opus → opus@max | Two consecutive spec-compliance FAILs at opus (unsupported vendor attributions; compound evidence grade; restated PA-12 figures) |
| 2026-11-05 | Evidence grade `research` added (vendor / research / measured / practitioner / unverified); PRD F1 single-source AC narrowed to verbatim fingerprint copies | Phase 1 drift check: studies (IFScale, ETH, spotlighting, OWASP) were shown as vendor guidance; paraphrased copies cannot be caught by fingerprints (SDD-ADR-2). User choices |
| 2026-11-05 | Phase 2 live-run consent: T2.1 smoke (≤ $0.50, claude:haiku + ollama judge), T2.3 eval_compare run (≤ $1), T2.5 Iron-Law evals (≤ $10), T2.7 write to global ~/.claude/startup.toml | User consent given once for these four, each with its stated ceiling; any other live run asks again |
| 2026-11-05 | T2.5: contract-first case redesigned (graders on behaviour only the skill forces) and re-measured; additional live-run consent up to $12 (port-gate-exit re-run with a higher ceiling, proving-signal runs for audit-injection and port, contract-first baseline) | First T2.5 run ($9.04): contract-first green without the skill, port ceiling skipped a grader, proving signals unrun. User choices |
| 2026-11-05 | T2.5 result ($9.04 + $10.81): handoff, audit-injection and port-gate-exit are red without the plugin and 1.00 with it; contract-first is green without the skill even after redesign and stays a regression guard. Weakening the skill's procedure text (SKILL.md, port.md) did not drop any score; removing the PA-15 catalog entry dropped audit-injection to 0.78 | The measurable effect comes from the catalog entries, not from the procedure wording, consistent with the experiment. Input for Phase 3 and for keeping SKILL.md short |
| 2026-11-05 | Phase 3 red steps changed: no verbatim fingerprint copies exist (T1.4 allow-list empty), so the paraphrased rule copies are tracked by research-internal.md (A) and the per-consumer strict xfails, checked by the spec reviewer | Accepted SDD-ADR-2 trade-off (paraphrases escape fingerprints); the plan's "remove from allow-list" steps had nothing to remove |
| 2026-11-05 | Phase 2 drift: spec amended. Recall metric counts the prompt kinds prompt-author keeps (handed-off kinds are measured by their owner); run-1 88.9% and the in-sample caveat recorded. Iron-Law cases are handoff, audit-injection, port-gate-exit; contract-first is a regression guard. Stale SDD sections (directory map, report module, eval_compare usage) brought up to date | User choice "Spec anpassen". Full-denominator recall was 87.8%, below 90% |
| 2026-11-05 | Phase 2 drift: eval_compare.py run gets `--confirm-provider claude` and an E1 secret scan of the case directories, like prompt_eval.py | User choice "Impl nachrüsten": SDD QR "zero sends without --confirm-provider" applies to both runners |
| 2026-11-05 | Phase 2 drift: prompt kind is classified by the prompt text, not the containing file (a brief stored in a skill directory stays with prompt-author); PA-32 also loads for chat-template; corpus item 5 re-checked | User choice "Jetzt fixen" |
| 2026-11-05 | Phase 2 cleanup round (T2.10) with one eval re-run, live-run consent ≤ $8; revert any cut that lowers a score | User choice; list from the T2.3/T2.4 code-quality reviews plus the LOW drift findings |
| 2026-11-05 | Phase 2 complete (T2.1-T2.10) | Boundary round done: spec amendments, eval_compare consent gate, kind by prompt text, cleanup -4.2 KB with all prompt-author cases still 1.00 ($5.36); T2.10 refusals exit 1 (plan said 2; SDD reserves 2 for partial results) |
| 2026-11-06 | Phase 3 started (same branch, Standard mode). Live-run consent: ≤ $80 total, ≤ $16 per rule group (T3.2-T3.6 plus the xdd-tdd-pressure-invoked runs); each run carries its own --max-cost-usd; exceeding either cap stops and asks | User choice. Re-estimate $60-80: ≥5 cases × 3 runs × both sides of eval_compare at ~$0.35-0.45 per authoring run, above the plan's $40-60 |
| 2026-11-06 | T3.2 group cap raised to $17 (before run $8.19, $0.19 over its $8 cap: in-flight runs finished after the ceiling); after run same 5 cases × 3 runs, --max-cost-usd 8.5 | User choice. Before: audit-fix 0.50, history-brief 0.67, reference 0.83 (run 2 unjudged, ceiling), body 1.00, discipline 1.00: the current strip-rationale rule rarely strips reasons Opus is given; the signal is history kept (PA-02). Ceiling cases guard against regression only |

## Context

A skill for writing, auditing and porting LLM prompts beyond Claude Code skills/agents: API system prompts, subagent briefs, CLAUDE.md/AGENTS.md, non-Claude target models. Candidate: extract the portable part of skill-author/agent-author failure catalogs as a single source of truth. Open tension: existing "strip rationale" and "authority language" rules may contradict current vendor guidance.

---
*This file is managed by the xdd-meta skill.*
