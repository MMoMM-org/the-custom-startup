# Internal Inventory + Integration Research — prompt-author (2026-11-04)

Read-only research agent. SA = plugins/tcs-helper/skills/skill-author, AA = plugins/tcs-helper/skills/agent-author, MO = plugins/tcs-helper/skills/memory-claude-md-optimize, RX = research-external.md. Spot-checked by the orchestrator: ADR-4 quote, SA conventions:356-366, SA conventions:124, decision-tree.md byte-identical copies — all confirmed.

## (A) Rule inventory

| Rule | Source | Class | Note |
|---|---|---|---|
| Strip rationale/history/spec refs/negative existence/past tense | SA/reference/conventions.md:341-354; SA/reference/common-failures.md:88-116 (rationale row :99); AA/reference/anti-patterns.md:197-241 ("Rationale Dilution" :213); AA/reference/output-formats.md:149,165-166; AA anti-patterns reject checklist :259-260 | Portable; **rationale part contradicted** | Stated 5×. History, dead refs, negative existence still valid |
| Exception: rationale load-bearing in discipline skills (superpowers 8/10 → 5/10) | SA conventions:356-366 | Portable | Internal evidence agreeing with vendors; missing from AA |
| "Measure a cut, do not judge it redundant" | SA conventions:364 | Portable | Agrees with research §6 |
| "YOU MUST" / "No exceptions" in discipline skills | SA conventions:301-307 (repeated :311-318); SA/reference/persuasion-principles.md:15-22,126 | **Contradicted** | Stated twice in conventions. Meincke 2025 (:9,135) — agent's unchecked recollection: study measured compliance with objectionable requests, not instruction-following |
| Commitment / scarcity / social-proof | persuasion :30-75 | Portable, untested | No vendor source either way |
| `Use PROACTIVELY` / `MUST BE USED` in descriptions | AA/SKILL.md:41,145,173; AA/reference/description-patterns.md:15-17,47; AA/reference/conventions.md:140; docs/about/principles.md:43 | Harness-specific, **contested** | RX: "CRITICAL: You MUST use this tool…" / "If in doubt" → overtriggering. ADR-4 depends on it |
| Description = triggers only, no workflow summary | SA/SKILL.md:42; SA conventions:70,88-100; common-failures:45-57,158; AA anti-patterns:96-101; description-patterns:162; output-formats:139; docs/about/skill-and-agent-design.md:218 | Harness-specific | Stated 8× |
| Front-load trigger ~50 chars, third person | AA conventions:138-139; principles:41-42 | Harness-specific | |
| Imperative over declarative | common-failures:7-25 | Portable | |
| Mention tools explicitly in workflow | common-failures:27-43 | Harness-specific | |
| Entry point / numbered steps / no fences around instructions | common-failures:61-85; SA conventions:200-240 | Portable (structure) | |
| Each rule once, no mirrored Always/Never | SA conventions:181,326-339; common-failures:159 | Portable | |
| Always/Never lists | SA conventions:179-191; AA conventions:260-275 | Portable, mild tension | RX favors positive framing |
| "One excellent example beats five mediocre ones" | SA conventions:124 | **Contradicted** | Anthropic 3-5 diverse; Google always |
| TS-style output contracts / typed `## Output` | SA conventions:175; AA conventions:309-319; output-formats:3 | Portable | |
| Decision tables carry a Rationale column | AA conventions:290-299 | Portable | Contradicts AA's own purity rule |
| No persona cosplay; identity 1-2 sentences | AA anti-patterns:62-70; AA conventions:252-258 | Portable | |
| Parent context invisible; brief is the only channel | principles:80-81; AA anti-patterns:114-118; AA conventions:351 | Portable to any brief | |
| No repo-vacuum; filtered returns | AA anti-patterns:120-136 | Portable | |
| Size budgets (SKILL.md <500 / orchestrators <200; agent ≤25 KB) | SA conventions:10,114-118; principles:61; AA conventions:361-372 | Numbers harness-specific, idea portable | IFScale supports budgets |
| Progressive disclosure, one level deep | SA conventions:368-375; principles:47-63 | Harness-specific | |
| Iron Law / evaluation-first | SA conventions:280-292; SA/SKILL.md:38; principles:134-146 | Portable | principles:146 "No plugin ships eval coverage" is **stale** (plugins/tcs-workflow/evals/ exists) |
| Parse CLI JSON in-tool; no `!` | SA conventions:242-265 | Harness-specific | |
| No TTY wait; display label ≠ lookup key | common-failures:120-145 | Harness-specific | |
| CLAUDE.md rubric rewards "rationale behind significant design choices" + architecture overview | MO/reference/scoring-rubric.md:35-49 | Rationale portable; **overview contradicted** | ETH: overviews don't help. Also conflicts with SA strip-rationale |
| Rubric actionability (directive not descriptive) | scoring-rubric:108-122,163 | Portable | |
| Rubric conciseness, every line load-bearing | scoring-rubric:72-86 | Portable | Fits "minimal ≠ short" |
| Line warnings 150/200 | scoring-rubric:143-147 | Harness-specific numbers | |
| Memory entry = rule → tell → consequence, ≤250 chars | plugins/tcs-helper/skills/memory-add/reference/category-formats.md:5-29; docs/ai/CLAUDE.md | Portable | Already a sanctioned one-clause why |

## (B) Extraction threshold

docs/about/skill-and-agent-design.md:48-50 (mirrored decision-tree.md:147-152): "ROI-positive if **at least one** of these is true: 1. **Multi-consumer**: Two or more agents (or workflows) genuinely need the same procedure. 2. **Progressive-disclosure benefit** … roughly **>200 lines including reference files**…"

- Shared reference passes both (≥3 consumers; catalogs >200 LOC).
- Strictly, Q-Extract governs skill-out-of-agent, not shared reference files. Precedent: implement-direct (SKILL.md:116,138) and implement-incremental (SKILL.md:168) consume `../xdd/reference/model-ladder.md`, guarded by tests/test_model_ladder.py.
- Counter-precedent: decision-tree.md is a byte-identical copy in both author skills; no sync test.
- Skill vs mode: decision-tree Q1/Q4 → Skill. skill-evaluate U1 (docs/XDD/adr/0002-citypaul-skill-absorption-verdicts.md): "Does TCS already have a skill/agent that covers this? YES = overlap exists → score 0", absorption preferred; SA/SKILL.md:53,104 ">50% overlap → update existing". Targets (API prompts, briefs, AGENTS.md, non-Claude) lie outside skill-author's In-scope → separate skill defensible; PRD must argue overlap against U1 explicitly.

## (C) Constraints

- **ADR-4** (decisions.md:12): three-layer enforcement incl. "(3) `MUST BE USED` in descriptions. Each layer covers the others' failure modes." Softening description authority language reopens ADR-4 → superseding ADR needed.
- **Declined 2026-09-05** (declined.md:34-45): no `@`-import of category files into every agent context → shared core must be read on demand, never `@`-imported.
- **Declined evals.json** (declined.md:88-95): evals use `case.yaml` or `prompt.md` + `graders/*.md`.
- **Pilot-memory CONDITION MET** (declined.md:79-86): `plugin eval` works → before/after measurement possible.
- **SA/SKILL.md:38**: new plugin skill ships with ≥1 eval shown to fail.
- **principles.md:250**: update when contradicted by newer Anthropic guidance.
- **Pending (user auto-memory, not repo)**: one-line `(Why: <failure>)` exception deferred "until it bites" — this spec resolves it.
- **Local testing procedure** (CLAUDE.md): copies single skill dirs; a `../shared/` reference breaks local testing unless the procedure changes. Marketplace survival of cross-skill `../` refs unverified (model-ladder precedent suggests it works within a plugin).
- Only docs/XDD/adr/0001, 0002 exist; no docs/adr/.

## (D) Other consumers / duplicates

- Dispatch-brief guidance: plugins/tcs-workflow/skills/parallel-agents/SKILL.md:53,61,181-187; implement-direct/SKILL.md:62,116-140; implement-incremental/SKILL.md:60,189-225; plugins/tcs-workflow/skills/brainstorm/reference/spec-reviewer-prompt.md.
- Strong-language rule: plugins/tcs-helper/skills/rule-enforcer/SKILL.md:123,209,278-288 + reference/mechanism-matrix.md:115 (memory-add told to use MUST/NEVER/ALWAYS).
- Memory-entry rules: memory-add/reference/category-formats.md; docs/ai/CLAUDE.md.
- Non-Claude target prompts: docs/templates/{research,prd,brainstorm,constitution}-prompt.md, setup-perplexity-space.md; scripts/export-spec.sh; docs/guides/multi-ai-workflow.md.
- Prompt in code: plugins/tcs-helper/scripts/lib/semantic_detector.py:128-135 — `claude -p` prompt with untrusted session text inline in quotes, no delimiter/provenance → real injection/spotlighting target.
- the-chief: no brief-writing guidance beyond description.

## (E) Existing mechanical checks touching prompt text

plugins/tcs-helper/scripts/authoring_reminder.py (PostToolUse, only SKILL.md + agents/**.md); tests/tcs-helper/test_authoring_reminder.py; tests/test_claude_md_imports.py; tests/test_patterns_setup_skill.py; tests/test_patterns_reader_skill.py; plugins/tcs-git-helpers/tests/bats/skill_git_audit.bats, skill_git_setup.bats; plugins/tcs-workflow/evals/ (six cases); agent-author/evals/pressure-scenarios.md (manual). No linter checks rationale or caps.

## (F) Proposed rule changes

1. SA conventions:341-354, common-failures:99: "strip rationale" → "keep one clause naming the failure a non-obvious rule prevents; strip history, provenance, dead refs".
2. AA anti-patterns:213-226, output-formats:149,166, reject checklist :259: same; let `(Why: …)` pass.
3. SA conventions:301-307 + 311-318: merge; drop YOU MUST / No exceptions; keep Red Flags + excuse→reality tables; allow a restated terminal constraint at the end.
4. persuasion-principles.md: demote Authority to "unverified for current models", add vendor counter-evidence, re-check what Meincke measured.
5. Description `MUST BE USED` (AA conventions:140, description-patterns:47, principles:43): mark contested; measure trigger/overtrigger with `plugin eval` before changing (ADR-4).
6. SA conventions:124 → "3-5 diverse examples, each behavior backed by a stated rule".
7. scoring-rubric:35-49: stop rewarding generic architecture overview; reward only what README/code lack.
8. rule-enforcer/SKILL.md:123,209,279: "strong wording" → "state the rule plus its failure".
9. principles.md:146: fix stale eval-coverage claim.
10. Point the 8 description-rule and 5 purity-rule copies at the shared core with a link/mirror test like tests/test_model_ladder.py.

Unverified: Meincke study scope; cross-skill `../` refs after marketplace install; full contents of docs/templates/*.
