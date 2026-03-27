---
title: "Phase 5: Parallel Skills Expansion"
status: completed
version: "1.0"
phase: 5
---

# Phase 5: Parallel Skills Expansion

## Phase Context

**GATE**: Read all referenced files before starting this phase. Phase 2 and Phase 4 must be complete.

**Specification References**:
- `[ref: SDD/Interface Specifications/tcs-workflow:receive-review; lines: 389-411]` — receive-review item processing contract
- `[ref: SDD/Interface Specifications/tcs-workflow:parallel-agents; lines: 413-435]` — independence validation contract
- `[ref: SDD/Building Block View/Directory Map; lines: 184-218]` — skill paths for all new/modified skills
- `[ref: SDD/Building Block View/tcs-helper additions; lines: 220-232]` — docs, finish-branch, git-worktree
- `[ref: SDD/Building Block View/tcs-team addition; lines: 234-242]` — record-decision agent
- `[ref: SDD/Constraints/CON-4]` — skill-author for all skills, agent-creator for agents
- `[ref: PRD/Feature 4]` — receive-review
- `[ref: PRD/Feature 5]` — parallel-agents
- `[ref: PRD/Feature 7]` — brainstorm enhancement
- `[ref: PRD/Feature 8]` — debug enhancement (iron-law anti-shortcut)
- `[ref: PRD/Feature 9]` — review enhancement (SHA context)
- `[ref: PRD/Feature 12]` — git-worktree
- `[ref: PRD/Feature 13]` — finish-branch
- `[ref: PRD/Feature 14]` — docs skill
- `[ref: PRD/Feature 15/Feature 15 (note)]` — record-decision agent
- `[ref: PRD/Feature 17]` — CoD default-on for analyze and debug

**Key Decisions**:
- CON-4: All skills via skill-author; record-decision agent via agent-creator.
- All tasks in Phase 5 are fully independent of each other → `[parallel: true]`
- Phase 5 requires Phase 2 (xdd-sdd, xdd-plan exist for brainstorm to reference) and Phase 4 (guide + implement exist for finish-branch/receive-review to announce).

---

## Tasks

Builds out the remaining skills and one agent in three groups: (A) tcs-workflow enhancements (receive-review, parallel-agents, brainstorm+, debug+, review+, analyze CoD), (B) tcs-helper additions (git-worktree, finish-branch, docs), (C) tcs-team addition (record-decision). All tasks are independent.

### Group A: tcs-workflow Enhancements

- [x] **T5.1 Create receive-review skill** `[activity: backend-api]` `[parallel: true]`

  1. Prime: Read `[ref: SDD/Interface Specifications/tcs-workflow:receive-review; lines: 389-411]` for item processing contract (Parse → Classify → Act). Read `plugins/tcs-workflow/skills/review/SKILL.md` for context on review output format. `[ref: PRD/Feature 4]`
  2. Test: `plugins/tcs-workflow/skills/receive-review/SKILL.md` exists. Frontmatter: `name: receive-review`, `user-invocable: true`, `argument-hint` mentions paste/URL. Four classification tags present: Accept | Push Back | Defer | Question. Accept path: applies fix → invokes verify → marks resolved. Push Back path: requires technical reason (not preference). Defer path: records in `docs/ai/memory/context.md`. Output: structured summary table (Item | Classification | Action Taken | Status). YOLO=true: Accept items auto-fixed; Push Back and Defer listed for manual follow-up. `[ref: PRD/Feature 4/AC-4.1–4.6]`
  3. Implement: Invoke `/tcs-helper:skill-author` to create `plugins/tcs-workflow/skills/receive-review/SKILL.md`. Four-step per-item workflow. Output summary table template. YOLO branch. Conclude: announces next step (finish-branch if all resolved). `[ref: SDD/CON-4]`
  4. Validate: Four classification paths present. Push Back path requires technical reference (not preference). Accept path calls verify before marking resolved. Summary table format present. YOLO branch present. Size ≤ 25 KB. `[ref: SDD/CON-2]`
  5. Success: `receive-review` processes items with classify-then-respond `[ref: PRD/Feature 4/AC-4.1]`; Push Back requires technical reason `[ref: PRD/Feature 4/AC-4.4]`; YOLO auto-processes Accept items `[ref: PRD/Feature 4/AC-4.6]`; authored via skill-author `[ref: SDD/CON-4]`

- [x] **T5.2 Create parallel-agents skill** `[activity: backend-api]` `[parallel: true]`

  1. Prime: Read `[ref: SDD/Interface Specifications/tcs-workflow:parallel-agents; lines: 413-435]` for independence validation and conflict grouping contract. `[ref: PRD/Feature 5]`
  2. Test: `plugins/tcs-workflow/skills/parallel-agents/SKILL.md` exists and `reference/conflict-detection.md` exists. Frontmatter: `name: parallel-agents`, `user-invocable: true`. Independence validation: file write target extraction via rg/fd. Pairwise overlap check: same file → HIGH (suggest worktree), same dir different files → MEDIUM, disjoint → NONE. Options for HIGH: isolate in worktrees | serialize | proceed anyway. Dispatch: parallel Agent tool calls for approved tasks. Result collection: structured merge/discard decision per output. YOLO=true: dispatches without confirmation. `[ref: PRD/Feature 5/AC-5.1–5.6]`
  3. Implement: Invoke `/tcs-helper:skill-author` to create `SKILL.md` and `reference/conflict-detection.md`. Conflict detection reference contains centminmod batch-operations patterns: conflict grouping algorithm, HIGH/MEDIUM/NONE risk matrix. Main skill: independence validation step, dispatch step, result collection step. `[ref: SDD/CON-3, CON-4]`
  4. Validate: `SKILL.md` and `reference/conflict-detection.md` both exist. `rg`/`fd` used for file target extraction. Three risk levels documented. HIGH-risk path offers three options. YOLO branch dispatches without prompts. `[ref: PRD/Feature 5/AC-5.6]`
  5. Success: `parallel-agents` validates independence before dispatch `[ref: PRD/Feature 5/AC-5.1]`; conflict risk levels documented `[ref: PRD/Feature 5/AC-5.2]`; results presented for merge/discard decision `[ref: PRD/Feature 5/AC-5.3]`; authored via skill-author `[ref: SDD/CON-4]`

- [x] **T5.3 Enhance brainstorm — spec-review loop at conclusion** `[activity: backend-api]` `[parallel: true]`

  1. Prime: Read `plugins/tcs-workflow/skills/brainstorm/SKILL.md` in full. Focus on Step 5 (Conclude). Read `[ref: SDD/Building Block View/Directory Map; line: 183]` for change scope: "MODIFY: spec-review loop at conclusion". Read `[ref: PRD/Feature 7]`. `[ref: PRD/Feature 7]`
  2. Test: `brainstorm/SKILL.md` updated. Step 5 (Conclude) offers spec-review subagent dispatch after design approval. Spec-review subagent: dispatched with design context, outputs gaps as structured clarification prompts (not rejections). If no gaps: announces "Design validated. Run `/xdd` to write the PRD." If gaps: presents structured list and asks developer to refine design. Existing brainstorm flow (Steps 1-4) unchanged. `[ref: PRD/Feature 7/AC-7.1–7.3]`
  3. Implement: Invoke `/tcs-helper:skill-author` to add spec-review loop to Step 5 of `brainstorm/SKILL.md`. New content: optional dispatch of a spec-review subagent (sonnet), structured gap presentation, clean handoff to `/xdd`. Do not alter Steps 1-4. `[ref: SDD/CON-4]`
  4. Validate: Step 5 contains spec-review dispatch option. Gap output format is structured prompts (not rejections). Handoff message: "Design validated. Run `/xdd` to write the PRD." Steps 1-4 unchanged (check diff). `[ref: PRD/Feature 7/AC-7.3]`
  5. Success: Brainstorm offers spec-review at conclusion `[ref: PRD/Feature 7/AC-7.1]`; gaps presented as clarification prompts `[ref: PRD/Feature 7/AC-7.2]`; clean handoff to `/xdd` `[ref: PRD/Feature 7/AC-7.3]`; existing flow preserved; authored via skill-author `[ref: SDD/CON-4]`

- [x] **T5.4 Enhance debug — iron-law anti-shortcut section** `[activity: backend-api]` `[parallel: true]`

  1. Prime: Read `plugins/tcs-workflow/skills/debug/SKILL.md` in full. Note current investigation and fix flow. Read `[ref: SDD/Building Block View/Directory Map; line: 188]` for change scope: "MODIFY: iron-law anti-shortcut section". Read `[ref: PRD/Feature 8]`. `[ref: PRD/Feature 8]`
  2. Test: `debug/SKILL.md` updated. Anti-shortcut table present (retry without reason | force-pass | skip test | assume it's flaky → BLOCK). Hypothesis-before-fix gate: skill requires a stated hypothesis before any fix is written. Fix verification: after fix is written, verify is invoked to confirm root cause resolved. Conclude message: "Bug resolved. Run `/verify` to confirm, then `/review` if on a feature branch." Existing debug flow unchanged for non-shortcut paths. CoD mode applied to investigation phase. `[ref: PRD/Feature 8/AC-8.1–8.4, Feature 17/AC-17.3]`
  3. Implement: Invoke `/tcs-helper:skill-author` to update `debug/SKILL.md`. Add: anti-shortcut table, hypothesis gate, post-fix verify call, conclude announcement. Add CoD mode to search/investigation steps. `[ref: SDD/CON-4]`
  4. Validate: Anti-shortcut table present with at least 4 shortcut patterns. Hypothesis step precedes fix step. Fix step calls verify. Conclude message matches spec. CoD notation present in investigation steps. `[ref: PRD/Feature 17/AC-17.3]`
  5. Success: Debug enforces hypothesis before fix `[ref: PRD/Feature 8/AC-8.1]`; anti-shortcut table blocks common bypasses `[ref: PRD/Feature 8/AC-8.2]`; verify called after fix `[ref: PRD/Feature 8/AC-8.3]`; CoD default-on in investigation `[ref: PRD/Feature 17/AC-17.3]`; authored via skill-author `[ref: SDD/CON-4]`

- [x] **T5.5 Enhance review — BASE_SHA/HEAD_SHA dispatch** `[activity: backend-api]` `[parallel: true]`

  1. Prime: Read `plugins/tcs-workflow/skills/review/SKILL.md` in full. Read `[ref: SDD/Building Block View/Directory Map; line: 199]` for change scope: "MODIFY: BASE_SHA/HEAD_SHA dispatch". Read `[ref: PRD/Feature 9]`. `[ref: PRD/Feature 9]`
  2. Test: `review/SKILL.md` updated. SHA resolution: `git merge-base origin/main HEAD` for BASE_SHA; `git rev-parse HEAD` for HEAD_SHA. Subagent dispatch: receives diff bounded by BASE_SHA..HEAD_SHA. Review output: categorized by severity (Critical | Important | Suggestion). Conclude message: "Review complete. Run `/receive-review` to process feedback." `[ref: PRD/Feature 9/AC-9.1–9.4]`
  3. Implement: Invoke `/tcs-helper:skill-author` to update `review/SKILL.md`. Add SHA resolution bash block. Update subagent dispatch to include SHA-bounded diff. Add severity categorization to output template. Add conclude announcement. `[ref: SDD/CON-4]`
  4. Validate: SHA resolution uses `git merge-base` and `git rev-parse`. Subagent receives `BASE_SHA..HEAD_SHA` diff. Severity levels (Critical | Important | Suggestion) in output template. Conclude message matches spec. `[ref: PRD/Feature 9/AC-9.4]`
  5. Success: Review auto-resolves SHAs `[ref: PRD/Feature 9/AC-9.1]`; subagent bounded to relevant diff `[ref: PRD/Feature 9/AC-9.2]`; output categorized by severity `[ref: PRD/Feature 9/AC-9.3]`; announces next step `[ref: PRD/Feature 9/AC-9.4]`; authored via skill-author `[ref: SDD/CON-4]`

- [x] **T5.6 Enhance analyze — CoD default-on** `[activity: backend-api]` `[parallel: true]`

  1. Prime: Read `plugins/tcs-workflow/skills/analyze/SKILL.md` in full. Read `[ref: SDD/Building Block View/Directory Map; line: 185]` for change scope: "MODIFY: CoD default-on". Read `[ref: PRD/Feature 17]`. `[ref: PRD/Feature 17]`
  2. Test: `analyze/SKILL.md` updated. CoD mode: applied by default to codebase research phases. `--no-cod` flag: disables CoD, uses standard verbose output. CoD notation: structured, interpretable (not cryptic). Existing analyze flow unchanged for non-research steps. `[ref: PRD/Feature 17/AC-17.1, AC-17.2, AC-17.4]`
  3. Implement: Invoke `/tcs-helper:skill-author` to update `analyze/SKILL.md`. Add CoD mode section to research phases. Add `--no-cod` flag detection (argument parsing). Document CoD output format. `[ref: SDD/CON-4]`
  4. Validate: CoD mode documented in research phases. `--no-cod` path present. Output format described as structured and interpretable. `[ref: PRD/Feature 17/AC-17.4]`
  5. Success: Analyze uses CoD by default `[ref: PRD/Feature 17/AC-17.1]`; `--no-cod` disables it `[ref: PRD/Feature 17/AC-17.2]`; output interpretable `[ref: PRD/Feature 17/AC-17.4]`; authored via skill-author `[ref: SDD/CON-4]`

### Group B: tcs-helper Additions

- [x] **T5.7 Create tcs-helper:git-worktree skill** `[activity: backend-api]` `[parallel: true]`

  1. Prime: Read `plugins/tcs-helper/.claude-plugin/plugin.json` to understand current structure. Read `[ref: PRD/Feature 12]` for acceptance criteria. Reference: `superpowers:using-git-worktrees` skill for patterns. `[ref: PRD/Feature 12]`
  2. Test: `plugins/tcs-helper/skills/git-worktree/SKILL.md` exists. Frontmatter: `name: git-worktree`, `user-invocable: true`. Create path: `git worktree add <path> <branch>` with predictable path convention. Conflict detection: existing worktree → offer reuse or new. Cleanup: removes worktree directory, optionally deletes branch. YOLO=true: creates without confirmation prompts. Conclude: announces worktree path and next step. `[ref: PRD/Feature 12/AC-12.1–12.4]`
  3. Implement: Invoke `/tcs-helper:skill-author` to create `plugins/tcs-helper/skills/git-worktree/SKILL.md`. Path convention: `../[repo-name]-[branch-name]` (adjacent to current repo). Cleanup command uses `git worktree remove`. YOLO branch. `[ref: SDD/CON-4]`
  4. Validate: SKILL.md exists. Path convention documented. Conflict detection path present. Cleanup section present. YOLO branch present. `[ref: PRD/Feature 12/AC-12.4]`
  5. Success: `git-worktree` creates worktrees at predictable paths `[ref: PRD/Feature 12/AC-12.1]`; conflict detection present `[ref: PRD/Feature 12/AC-12.2]`; cleanup removes worktree and optionally branch `[ref: PRD/Feature 12/AC-12.3]`; authored via skill-author `[ref: SDD/CON-4]`

- [x] **T5.8 Create tcs-helper:finish-branch skill** `[activity: backend-api]` `[parallel: true]`

  1. Prime: Read `plugins/tcs-helper/.claude-plugin/plugin.json`. Read `[ref: PRD/Feature 13]` for acceptance criteria. Read `superpowers:finishing-a-development-branch` for patterns. `[ref: PRD/Feature 13]`
  2. Test: `plugins/tcs-helper/skills/finish-branch/SKILL.md` exists. Frontmatter: `name: finish-branch`, `user-invocable: true`. Flow: (1) run tests first — if failing, block and do not show options; (2) if passing, show exactly four options: merge locally | push and create PR | keep as-is | discard; (3) discard requires typed "discard" confirmation; (4) PR option returns PR URL. YOLO=true with `YOLO_FINISH=pr`: proceeds to PR without confirmation. `[ref: PRD/Feature 13/AC-13.1–13.6]`
  3. Implement: Invoke `/tcs-helper:skill-author` to create `plugins/tcs-helper/skills/finish-branch/SKILL.md`. Test-before-options gate. Four option paths. Discard double-confirmation. PR creation via `gh pr create`. YOLO env var detection. `[ref: SDD/CON-4]`
  4. Validate: Test gate present (failing tests → block). Exactly four options shown. Discard requires typed "discard". PR path returns URL. YOLO_FINISH var detection present. `[ref: PRD/Feature 13/AC-13.1–13.6]`
  5. Success: `finish-branch` blocks on failing tests `[ref: PRD/Feature 13/AC-13.2]`; four options shown `[ref: PRD/Feature 13/AC-13.3]`; discard requires confirmation `[ref: PRD/Feature 13/AC-13.4]`; PR returns URL `[ref: PRD/Feature 13/AC-13.5]`; authored via skill-author `[ref: SDD/CON-4]`

- [x] **T5.9 Create tcs-helper:docs skill** `[activity: backend-api]` `[parallel: true]`

  1. Prime: Read `plugins/tcs-helper/.claude-plugin/plugin.json`. Read `[ref: SDD/Building Block View/tcs-helper additions; lines: 224-228]` — cache path `docs/ai/external/claude/`. Read `[ref: PRD/Feature 14]` for acceptance criteria including MCP check. `[ref: PRD/Feature 14]`
  2. Test: `plugins/tcs-helper/skills/docs/SKILL.md` exists. Frontmatter: `name: docs`, `user-invocable: true`. MCP check: first checks if a docs MCP server is available; if yes, delegates. If no, uses WebFetch. Cache: saves fetched content to `docs/ai/external/claude/<topic>.md` with timestamp header. Cache freshness: serves cached if ≤ 7 days old unless `--refresh`. Unknown topic: lists available topic categories. `[ref: PRD/Feature 14/AC-14.1–14.5]`
  3. Implement: Invoke `/tcs-helper:skill-author` to create `plugins/tcs-helper/skills/docs/SKILL.md`. MCP check step. WebFetch fallback. Cache write with timestamp. 7-day freshness check (bash: compare file mtime). Topic index (built-in list). `--refresh` flag. `[ref: SDD/CON-3, CON-4]`
  4. Validate: MCP check step present. Cache path `docs/ai/external/claude/` correct. Timestamp header in cache format. 7-day check present. Unknown-topic listing present. `--refresh` flag parsed. `[ref: PRD/Feature 14/AC-14.3]`
  5. Success: Docs checks MCP before WebFetch `[ref: PRD/Feature 14/AC-14.1]`; cache with 7-day freshness `[ref: PRD/Feature 14/AC-14.3]`; gitignored cache dir (already done in T1.3) `[ref: PRD/Feature 14/AC-14.5]`; authored via skill-author `[ref: SDD/CON-4]`

### Group C: tcs-team Addition

- [x] **T5.10 Create tcs-team:the-architect/record-decision agent** `[activity: backend-api]` `[parallel: true]`

  1. Prime: Read `plugins/tcs-team/.claude-plugin/plugin.json`. Read `[ref: SDD/Building Block View/tcs-team addition; lines: 234-242]`. Read `[ref: PRD/Feature 15]` for ADR format and startup.toml integration. Read `plugins/tcs-team/agents/the-architect/design-system.md` for reference agent format. `[ref: PRD/Feature 15]`
  2. Test: `plugins/tcs-team/agents/the-architect/record-decision.md` exists. Agent frontmatter: `name: record-decision`, `user-invocable: true`. ADR format: Title, Status, Context, Decision, Consequences sections. Path resolution: reads `startup.toml` `docs_base` → places in `{docs_base}/adr/` with sequential prefix `ADR-NNN-*`. Default: `docs/XDD/adr/`. Supersede flow: updates old ADR status to "Superseded", adds link to new one. Conclude: announces file path, suggests `/guide` if context unclear. `[ref: PRD/Feature 15/AC-15.1–15.6]`
  3. Implement: Invoke `/plugin-dev:agent-creator` to create `plugins/tcs-team/agents/the-architect/record-decision.md`. ADR template with all 5 sections. startup.toml resolution (re-uses same bash logic as xdd-meta: grep/sed on `.claude/startup.toml`). Sequential numbering: `fd -t f "ADR-*.md" {adr_dir} | wc -l` + 1. Supersede flow. `[ref: SDD/CON-1, CON-4]`
  4. Validate: `record-decision.md` exists in `plugins/tcs-team/agents/the-architect/`. ADR template sections: Title, Status, Context, Decision, Consequences. startup.toml resolution bash block present. Sequential numbering present. Supersede path present. Conclude announcement present. `[ref: PRD/Feature 15/AC-15.6]`
  5. Success: `record-decision` produces standard ADR format `[ref: PRD/Feature 15/AC-15.1]`; places in `{docs_base}/adr/` `[ref: PRD/Feature 15/AC-15.2]`; custom `docs_base` from startup.toml respected `[ref: PRD/Feature 15/AC-15.3]`; supersede flow updates old ADR `[ref: PRD/Feature 15/AC-15.5]`; created via agent-creator `[ref: SDD/CON-4]`

- [x] **T5.11 Phase 5 Validation** `[activity: validate]`

  - `ls plugins/tcs-workflow/skills/` — `receive-review/`, `parallel-agents/` present; `brainstorm/`, `debug/`, `review/`, `analyze/` all modified.
  - `ls plugins/tcs-helper/skills/` — `git-worktree/`, `finish-branch/`, `docs/` present.
  - `ls plugins/tcs-team/agents/the-architect/` — `record-decision.md` present.
  - `parallel-agents/reference/conflict-detection.md` exists.
  - All new skills: size ≤ 25600 bytes (`wc -c`).
  - All enhanced skills: existing flow structure preserved (check via `git diff`).
  - `rg "YOLO" plugins/tcs-workflow/skills/receive-review/SKILL.md` — YOLO branch present.
  - `finish-branch/SKILL.md` — typed "discard" confirmation present.
  - `docs/SKILL.md` — MCP check step and 7-day cache check present.
  - `record-decision.md` — startup.toml resolution and sequential numbering present.
  - All Phase 5 PRD acceptance criteria: Features 4, 5, 7, 8, 9, 12, 13, 14, 15, 17 verifiably met.
