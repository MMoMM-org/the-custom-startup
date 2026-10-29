# Walkthrough — both journeys (T4.2)

The shipped skill text, walked step by step as an orchestrator would follow it. The skill files
were the only source; the SDD was not used to fill gaps. Line numbers are those **after** the
fixes below. Paths are relative to `plugins/tcs-workflow/skills/`.

Status per step: **OK** (followable from the text), **GAP** (cannot follow / ambiguous /
contradicts another file; fixed here), **OPEN** (needs a design decision; not decided here).

| Journey | Steps | OK | GAP (fixed) | OPEN |
|---|---|---|---|---|
| A. xdd step 6 on spec 022 | 9 | 9 | 0 | 0 |
| B. xdd step 6 on a doc-only stub | 5 | 5 | 0 | 0 |
| C. implement-incremental, five cases | 19 | 17 | 1 | 1 |
| D. implement-direct, two cases | 8 | 5 | 3 | 0 |

Plus one item found off the walked path (O2), now DECIDED.

---

## A. xdd step 6 on spec 022 (expected: Incremental, `hard` via `adr_count >= 3`)

Inputs: `docs/XDD/specs/022-model-tier-classification/requirements.md` and `solution.md`, as data.

| # | Orchestrator does | Told by | Status |
|---|---|---|---|
| A1 | Reads the classifier and applies it to the two documents only | `xdd/SKILL.md:124` | OK |
| A2 | Extracts the five decomposition signals: `change_type=feature` (framed as a feature: vision, user stories); `feature_count=6` (Must-Have Features 1–6); `ac_count=27`; `component_count=1` (Building Block View: only the model ladder is **new**, six rows are modified); `parallel_markers=false` (no parallel/concurrent work called out) | `xdd/SKILL.md:126`; `xdd/reference/classifier.md:23-29` (modified components do not count, `:28`) | OK |
| A3 | Extracts the model-tier signals: `high_risks=0` (Risks table Impact cells: Medium ×3, Low ×2); `novel_pattern=false` ("New patterns created" holds no entry, only a comment reading "none"); `adr_count=7` (ADR-1 … ADR-7) | `xdd/SKILL.md:126`; `classifier.md:130-135` | OK — the "none" is a YAML comment, not an entry; either reading gives `false` |
| A4 | Decomposition rules top to bottom: rule 1 fires on `feature_count >= 2` → **Incremental** | `xdd/SKILL.md:127`; `classifier.md:41-46` | OK — matches expected and the README Status row |
| A5 | Model-tier rules: rule 1 no (`feature`), rule 2 no (no novel pattern), rule 3 fires on `adr_count >= 3` → **hard** | `classifier.md:141-147` | OK — matches expected |
| A6 | Surfaces both with signals: "Model tier **hard** — adr_count=7 (>= 3); no High risks; no new patterns." | `xdd/SKILL.md:128`; `classifier.md:165` | OK |
| A7 | One question round, two questions ("Decompose", "Model"); the `frontier` option carries the cost sentence copied from the ladder; nothing else is asked before routing | `xdd/SKILL.md:129-135`; `xdd/reference/model-ladder.md:129` | OK — AC-1.2 holds. The only other question in step 6 is the pre-existing finalize/revisit gate after routing (`xdd/SKILL.md:153`) |
| A8 | Records both tiers via xdd-meta: Status rows `Decomposition tier` + `Model tier` and one Decisions Log row each | `xdd/SKILL.md:136`; `xdd-meta/SKILL.md:73`, `:137-139`; `classifier.md:175-185` | OK — note: spec 022's README predates the template's `Model tier` row (`xdd-meta/template.md:10`); "write to the Status table row" reads as inserting it |
| A9 | Routes Incremental: invokes xdd-plan, then validate | `xdd/SKILL.md:142-148` | OK |

## B. xdd step 6 on a doc-only stub (expected: routine)

Constructed in memory, not on disk: a doc rewrite; requirements has one feature with 2 ACs and
one risk of Impact Medium; solution modifies an existing README (no new component), Pattern
Documentation lists "New patterns created: None", one ADR.

| # | Orchestrator does | Told by | Status |
|---|---|---|---|
| B1 | Signals: `change_type=doc`, `feature_count=1`, `ac_count=2`, `component_count=0`, `parallel_markers=false`; `high_risks=0`, `novel_pattern=false` ("None" counts as empty), `adr_count=1` | `classifier.md:23-29`, `:130-135` | OK |
| B2 | Decomposition: rule 1 no; rule 2 fires (`change_type` in {fix, refactor, doc}) → **Direct** | `classifier.md:44-49` | OK |
| B3 | Model tier: rule 1 fires (`change_type == doc`) → **routine** | `classifier.md:144` | OK — matches expected |
| B4 | Same single round; the `frontier` option still carries the cost sentence although routine is recommended | `xdd/SKILL.md:129-135` | OK |
| B5 | Records both tiers; routes Direct: no artifact, `plan/` row `skipped` | `xdd/SKILL.md:136`, `:140-141`; `classifier.md:99` | OK |

## C. implement-incremental, on paper

Paths: `implement-incremental/SKILL.md` = **II**, `xdd/reference/model-ladder.md` = **L**.

### C1. Two FAILs in a row at sonnet → opus, count reset

| # | Orchestrator does | Told by | Status |
|---|---|---|---|
| C1.1 | Tier absent or `routine`, no tag → selects by complexity → `sonnet` | II:168-173; L:30, L:34-35 | OK |
| C1.2 | Dispatches with alias `sonnet`; runs the Served Model check | II:175; L:113-121 | OK |
| C1.3 | 4f FAIL → counter 1 → re-dispatch at sonnet with the fix list | II:243; L:59-62 | OK |
| C1.4 | Second FAIL in a row (4f or 4g, one counter) → counter 2 → escalate | II:243, II:251; L:61 | OK |
| C1.5 | `escalate`: counter reset to 0; next = rung after sonnet = `opus`; not fable → set rung, log `Model escalation: T… sonnet → opus` (Trigger: second review FAIL) via xdd-meta step 4 | L:64-70, L:140, L:146; II:175 | OK |
| C1.6 | Re-dispatch at opus with the fix list, then the reviewer again | II:243; L:61 | OK |

### C2. Complexity BLOCKED at opus@max → fable consent question

| # | Orchestrator does | Told by | Status |
|---|---|---|---|
| C2.1 | 4e BLOCKED, complexity → escalate one rung | II:214; L:49, L:56 | OK |
| C2.2 | Not at fable, fable not unavailable → next = `fable`; someone can be asked → ask one question carrying the cost sentence, before any dispatch | L:66-72, L:88-93, L:129; II:175 | OK — AC-5.3 holds |
| C2.3 | Yes → rung fable, log `Fable consent` and the escalation, re-dispatch `model: fable`. No → log decline, report BLOCKED at opus@max | L:73-74, L:141 | OK |

### C3. YOLO → BLOCKED at opus@max

| # | Orchestrator does | Told by | Status |
|---|---|---|---|
| C3.1 | `YOLO=true` means nobody can be asked | II:267; L:95 | OK |
| C3.2 | Escalation from opus@max: next = fable → nobody can be asked → log "fable not reached: no one to ask", report BLOCKED at opus@max; no fable dispatch | L:71 | OK — AC-5.4 holds |
| C3.3 | After the BLOCKED report: does the **run** halt, or does the loop move to the next task? `stop` (L:67) and "report BLOCKED" (L:71, L:74) do not say; II's 4e has no rule for it either | — | **DECIDED (O1)** |

### C4. Planned frontier task, fable dispatch errors → opus@max, run continues

| # | Orchestrator does | Told by | Status |
|---|---|---|---|
| C4.1 | `model_tier=frontier` from step 1; Starting Rung → `fable`; the confirmed tier is the consent | II:83, II:168; L:37, L:41, L:88 | OK |
| C4.2 | Dispatches `model: fable` | II:175; L:19 | OK |
| C4.3 | Dispatch error → Fable Failure: fable off for the run; planned → re-dispatch `opus` + `effort: max`, log `Requested fable, ran opus@max: dispatch error <reason>`, continue | L:101-104, L:18, L:142 | OK — AC-6.1 holds |
| C4.4 | The run continues to the **next** planned frontier task. Before the fix: Starting Rung (L:37) still says `fable`, Fable Failure said only "never try it again", and the pseudocode's `run.fable_unavailable` (L:66) was set by no sentence | L:103 (after fix) | **GAP → fixed** |

### C5. Failing twice at the highest rung → BLOCKED, no further retry

| # | Orchestrator does | Told by | Status |
|---|---|---|---|
| C5.1 | At fable (after consent): second FAIL → escalate → `T.rung == fable` → log "highest reachable rung", report BLOCKED, stop | L:61, L:66-67; II:243 ("no further retry") | OK — AC-5.7 holds |
| C5.2 | At opus@max after a fable failure: same check through `run.fable_unavailable` | L:66, L:103 | OK |
| C5.3 | At opus@max with fable available but declined or nobody to ask: BLOCKED at opus@max | L:71, L:74, L:81 | OK |

## D. implement-direct, on paper

Paths: `implement-direct/SKILL.md` = **ID**, ladder = **L**.

### D1. Absent tier, complexity BLOCKED twice → inherited → opus → opus@max

| # | Orchestrator does | Told by | Status |
|---|---|---|---|
| D1.1 | Step 1 reads `model_tier = ""` → absent | ID:73 | OK |
| D1.2 | 3b, Direct column, absent → dispatch with no `model` parameter | ID:116; L:34 | OK |
| D1.3 | Runs the served-model check, which compares served models with the *requested alias* — there is none. Before the fix the text gave no answer (compare to what? log a substitution?) | L:121 (after fix) | **GAP → fixed** |
| D1.4 | 3c BLOCKED complexity → escalate: rung unset → next = `opus`; re-dispatch `model: opus` | ID:133, ID:138; L:68, L:70 | OK |
| D1.5 | Logs the escalation row, which must name the task and the rung before. Before the fix: no name for an unset rung, and Direct has delivery units, not `T2.1` ids | L:146 (after fix) | **GAP → fixed** |
| D1.6 | Second complexity BLOCKED → `opus@max`; dispatch `opus` + `effort: max` | L:69-70, L:18; ID:116 | OK |

### D2. Frontier Direct spec, fable dispatch errors → opus@max, continue

| # | Orchestrator does | Told by | Status |
|---|---|---|---|
| D2.1 | `model_tier=frontier` → Direct column `fable`; confirmed tier, no consent | ID:116; L:37, L:41 | OK |
| D2.2 | The fable dispatch errors at 3b. Before the fix, 3b named only the served-model check; the fable-failure rule was named only inside 3c's *complexity escalation* paragraph (ID:138), which a dispatch error at 3b does not reach. After the fix: planned → opus@max, log, continue | ID:116 (after fix); L:101-104 | **GAP → fixed** — AC-6.1 holds |

---

## Fixes

Each fix: failing test first (run red), minimal text change, run green.

| Gap | Test (red, then green) | Fix |
|---|---|---|
| C4.4 later planned frontier task after fable failure | `tests/test_model_ladder.py::test_fable_failure_names_the_run_flag_and_the_start_rung_of_later_planned_tasks` (+ reference-model case `test_a_later_planned_frontier_task_starts_at_opus_max_once_fable_is_off`) | L:103 — names `run.fable_unavailable`; a later planned task that would start on `fable` starts at `opus@max` and logs a substitution with reason `fable off for this run`. Follows from "never try it again" plus the planned-task rule; no new decision |
| D1.3 served-model check with no requested alias | `tests/test_model_ladder.py::test_served_model_check_is_skipped_for_a_dispatch_without_a_model_parameter` | L:121 — a dispatch without a `model` parameter requested no alias, so the check is skipped |
| D1.5 escalation row for an unset rung / Direct unit | `tests/test_model_ladder.py::test_escalation_row_names_an_unset_rung_and_a_direct_unit` | L:146 — the rung before is written `inherited`; in implement-direct the task is named by its delivery unit's title |
| D2.2 fable failure not reachable from 3b | `tests/test_implement_direct_ladder.py::test_3b_routes_a_failed_fable_dispatch_to_the_fable_failure_rule` | ID:116 — one sentence: a failed `fable` dispatch follows the ladder's Fable Failure section |

`implement-incremental/SKILL.md` was not changed (stays at 306 lines). Rules stay in
`model-ladder.md`; implement-direct only points to them.

## Decided (formerly open)

- **O1 — what "BLOCKED … stop" stops. DECIDED (2026-10-29, maintainer):** the run halts at the
  blocked task, also under YOLO; no dependent task runs; the plan stays resumable via `/implement`.
  Implemented at `model-ladder.md:83`. Original question: L:67, L:71, L:74 end a task's escalation with "report
  BLOCKED (to the user); stop". Neither the ladder nor II/ID says whether the run halts there or
  the loop moves on to the next task (and what happens to tasks that depend on the blocked one).
  It matters most in YOLO, where nobody reads the report until the run ends. Today's BLOCKED
  handling ("Plan is wrong → escalate to user") is equally silent. AC-5.4 and AC-5.7 hold either
  way; choosing halt-run vs skip-task is a design decision.
- **O2 — a `[model: frontier]` tag in a non-frontier spec once fable is off. DECIDED (2026-10-29,
  maintainer):** no consent is asked; the task starts at the `hard` rung and logs a substitution
  "fable off for this run". Implemented at `model-ladder.md:96` and `:105`. Original question: Consent (L:88-93)
  asks before the dispatch; Fable Failure (L:103) now covers planned tasks only. Asking consent
  for a model already known unavailable is pointless, but whether the task then runs at the `hard`
  rung (as on a decline) or at `opus@max` (as a consented planned task would) is a design decision.

## Acceptance criteria check

| AC | Holds in | Verdict |
|---|---|---|
| AC-1.2 both tiers in one round, nothing else asked | `xdd/SKILL.md:126` ("ask the user nothing"), `:129-135` | holds |
| AC-5.3 fable escalation asks first, with the cost sentence | L:72, L:88-93, L:129; II:175 | holds |
| AC-5.4 nobody can be asked → BLOCKED at opus@max | L:71, L:95; II:267 | holds |
| AC-5.7 highest reachable rung → BLOCKED, no retry | L:66-67, L:81; II:243 | holds |
| AC-6.1 planned frontier fable failure → opus@max, run continues | L:103-104; ID:116 (Direct) | holds (after the D2.2 fix for Direct; C4.4 fix for later tasks) |
