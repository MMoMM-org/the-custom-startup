# Spec 020 — T5.5 End-to-end validation

**Status: complete (2026-10-07).** The offline half below was run before release. The live half
(P1-P4) ran after tcs-patterns 2.0.0 and tcs-git-helpers 2.2.23 shipped (#176, `40f983e`); see
[Live validation](#live-validation-2026-10-07). All 18 acceptance criteria are verified.

Run 2026-10-07 on branch `spec/020-tcs-patterns-selective-install` at `86027da`, against
`origin/main` = `984f76e`. macOS (Darwin 25.6), Python 3.14.3, zsh, inside the Claude Code Bash
sandbox. Every command below ran from this checkout; nothing in `plugins/` or `templates/` was edited.

**Verdict:** the nine-step flow, the drift advisory, `update`, `remove` and `status` all behave as
specified in a fixture repository. **No defect found.** Two T5.5 items need a released
`tcs-patterns` 2.0.0 and a new Claude Code session; they are listed under
[Pending release](#pending-release) with the exact steps.

## Fixture

`$TMPDIR/t55/fixture-api` (`/private/tmp/claude-501/t55/fixture-api`), created with
`git -C <dir> init -b main` under `GIT_CONFIG_GLOBAL=/dev/null`, one commit `746f389 initial fixture`:

- `pyproject.toml` — `dependencies = ["fastapi>=0.110", "uvicorn>=0.29"]`, `dev` extra with
  `pytest`, `httpx`, and a `[tool.pytest.ini_options]` table
- `app/main.py` (one FastAPI route), `tests/test_main.py` (one TestClient test), `.gitignore`

A second directory, `$TMPDIR/t55/layout/plugins/{tcs-git-helpers,tcs-patterns}`, is an `rsync` copy
of this checkout's two plugins (`diff -r -x __pycache__` against the checkout: identical; `cmp` of
`session-start-brief.sh` and `patterns_drift.py`: identical). Its `templates/patterns/` is the
**catalogue copy** bumped below. A copy was needed because the hook passes no `--catalogue`: it
finds `patterns_drift.py` relative to its own location (`$_SCRIPT_DIR/../../tcs-patterns/scripts/`),
and the reporter defaults to the catalogue relative to *its* location — the same repo layout the
bats suite builds (`_fx_repo_layout`), here with the real reporter instead of a stub.

`CLI` below is `/Volumes/Moon/Coding/the-custom-startup/plugins/tcs-patterns/skills/patterns-setup/lib/cli.py`;
`R` is the fixture's toplevel as the CLI reported it, `/private/tmp/claude-501/t55/fixture-api`.

## Walk log — the nine steps

Followed `plugins/tcs-patterns/skills/patterns-setup/SKILL.md` literally. Step 1's CLI location is
this checkout's (the third fallback in the skill's step 1; the harness "Base directory" line does
not exist outside a skill invocation, and the plugin cache holds only `tcs-patterns` 1.4.4, which
has no `patterns-setup`). Steps 1–9 used the **real** catalogue (no `--catalogue`); it was
byte-identical to the copy until the bump.

| # | Step | Command | Exit | Key output |
|---|---|---|---|---|
| 1 | Resolve | `python3 "$CLI" scan /tmp/claude-501/t55/fixture-api` | 0 | `repo` = `/private/tmp/claude-501/t55/fixture-api` (git toplevel, `/tmp` symlink resolved); used for every later call |
| 1′ | Resolve, refusal | `python3 "$CLI" scan /tmp/claude-501` | 3 | stderr `cli.py scan: not inside a git repository: /tmp/claude-501`, stdout empty |
| 2 | Scan | (same call as 1) | 0 | `manifests_walked: ["pyproject.toml"]`, `unreadable: []`, `unrecognised_stack: false`, `outcomes: null`; nothing written (`git status --porcelain` empty) |
| 3 | Propose | — (rendered from the scan) | — | Recommended: `python-project` (evidence `pyproject.toml`, +200 chars). Baseline, listed separately: `testing` (`pyproject.toml: [tool.pytest.ini_options]`, +236 chars, `surface: false`) |
| 4 | Ask | — | — | All three gates open: q1 (`pyproject.toml: dependencies.fastapi`), q2 (same, q2 opens with q1), q3 (`[tool.pytest.ini_options]`). Answers chosen: q1 = `api-design`, `observability`; q2 = `ddd`; q3 = `mutation-testing` |
| 5 | Confirm | `python3 "$CLI" scan "$R" --answers '{"q1_backend": ["api-design", "observability"], "q2_architecture": ["ddd"], "q3_test_quality": ["mutation-testing"]}'` | 0 | **Will install** (6): api-design, ddd, mutation-testing, observability, python-project, testing. **Companion** offered: `hexagonal` (+214) — "you declined `hexagonal`; `ddd` cites it" at `ddd/reference/testing-by-layer.md:3`, and `observability` cites it at `observability/SKILL.md:70`, `:71` and `observability/reference/testing-telemetry.md:85`. `ambiguous: []`. Not installed: `declined_by_question` 9, `excluded_by_stack_fact` 6 (frontend-testing, go-idiomatic, mcp-server, obsidian-plugin, react-testing, typescript-strict), `not_reached` 0. 6 + 9 + 6 + 0 = 21. **Accepted** the companion. Still nothing written |
| 6–8 | Guard, write, manifest | `python3 "$CLI" install "$R" api-design ddd hexagonal mutation-testing observability python-project testing` | 0 | `installed` 7, `refused {}`, `failed {}`, `skipped []`, `unchanged {}`, `committed: false`. `.claude/skills/tcs-<p>/` for all 7, each `SKILL.md` with `name: tcs-<p>`; manifest has `[patterns.<p>]` with `version = "1"`, `installed_as`, `sha256` for each; `bundle = "1.4.4"` (see note 1) |
| 9 | Commit offer | — | — | Offered with the paths `.claude/skills/.tcs-patterns-manifest` and the 7 `.claude/skills/tcs-*`; **declined**. `git status --porcelain` = `?? .claude/`; `git log` still `746f389` only |

Installed copies differ from the catalogue only by the intended rewrites: frontmatter
`name: <p>` → `name: tcs-<p>`, the persona marker `tcs-patterns:<p>` → `tcs-<p>`, and
`tcs-patterns:<q>` mentions → `tcs-<q>` in reference files (`diff -r` of `hexagonal` and
`functional` against their installs). Reference files are copied in full.

### Extra checks during the walk

| Check | Command | Exit | Result |
|---|---|---|---|
| Idempotency | same `install` call again | 0 | `installed []`, all 7 `unchanged`; manifest `shasum` identical before and after |
| Guard collision | clone `fixture-guard`, hand-written `.claude/skills/tcs-twelve-factor/SKILL.md`, then `install "$G" twelve-factor functional api-design` | 0 | `functional`, `api-design` installed; `twelve-factor` refused with `namespace: repo`, `path` = the existing `SKILL.md`, `intended_path` = `.../tcs-twelve-factor`; the user's file untouched |
| Commit offer, yes branch | in `fixture-guard`, with an unrelated `README.md` staged first: 3g's `git status --porcelain -- <3 paths>`, `git add -A -- <paths>`, `git commit -m "chore: install tcs patterns api-design functional" -- <paths>` (identity via `-c` because `GIT_CONFIG_GLOBAL=/dev/null`) | 0 | Commit `1352959` holds exactly the manifest and the two installed directories (7 files); `README.md` stays staged (`A`) and `tcs-twelve-factor/` stays untracked |

### Drift advisory, update, remove, status

| Step | Command | Exit | Result |
|---|---|---|---|
| Hook before bump | `cd "$R" && printf '{}' \| $TMPDIR/t55/layout/plugins/tcs-git-helpers/scripts/session-start-brief.sh` | 0 | `systemMessage: "[tcs-git-helpers] run /tcs-git-helpers:git-setup"` — no patterns segment (all current) |
| Reporter before bump | `python3 plugins/tcs-patterns/scripts/patterns_drift.py "$R" --catalogue <copy>` | 0 | `OK` |
| Bump | `printf '2\n' > <copy>/ddd/VERSION`; appended `<!-- T5.5 fixture bump -->` to `<copy>/ddd/SKILL.md` | — | `git status --porcelain -- plugins/tcs-patterns/templates` in this checkout: empty (real catalogue untouched) |
| **Hook after bump (real hook)** | same hook call | 0 | `systemMessage: "[tcs-git-helpers] patterns ddd v1 → v2; run /tcs-patterns:patterns-setup update • run /tcs-git-helpers:git-setup"` — names **exactly** `ddd`. The trailing git-setup segment is the hook's existing hint for a repo without `.githooks/`, unrelated to patterns |
| Reporter after bump | layout copy's reporter (default catalogue = copy), and checkout reporter `--catalogue <copy>` | 0, 0 | `DRIFT:ddd:1:2` both; checkout reporter against the real catalogue: `OK` |
| Local edit | appended a line to `R/.claude/skills/tcs-api-design/SKILL.md` | — | — |
| `update` | `python3 "$CLI" --catalogue <copy> update "$R"` | 0 | `refreshed: ddd 1 → 2`; `current`: hexagonal, mutation-testing, observability, python-project, testing; `declined: api-design` with diff `--- installed` / `+++ catalogue`, the local line shown as `-`; `failed {}`. `tcs-api-design/SKILL.md` byte-identical (sha256); `tcs-ddd/SKILL.md` carries the bump marker |
| Manifest vs catalogue | `tomllib` read of the manifest against each `<copy>/<p>/VERSION` | — | 7 of 7 match (ddd 2/2, others 1/1); 0 mismatches |
| `update` again | same | 0 | `refreshed []`, 6 `current`, `api-design` still `declined` |
| Reporter after update | `patterns_drift.py "$R" --catalogue <copy>` | 0 | `OK` |
| `status` | `python3 "$CLI" --catalogue <copy> status "$R"` | 0 | `manifest.state: present`; 7 patterns all `state: OK`, ddd installed 2 / catalogue 2; `api-design diverged: true`, others `false`; `unlisted []`, `debris []` |
| `remove`, diverged | `... remove "$R" api-design` | 0 | `refused.api-design.reason`: "diverged from what was installed; local edits would be lost -- re-run with --discard-edits api-design", with the same signed diff; directory still present |
| `remove`, approved | `... remove "$R" api-design --discard-edits api-design` | 0 | `removed.api-design` (`directory_existed: true`); `tcs-api-design/` gone; no `[patterns.api-design]` in the manifest (`grep -c` = 0) |
| `remove`, bad flag | `... remove "$R" ddd --discard-edits testing` | 2 | stderr `--discard-edits names patterns not being removed: testing`; nothing written |
| `status` after | `... status "$R"` | 0 | 6 patterns, all `OK`, `diverged: false`; `unlisted []`, `debris []`; fixture still uncommitted (`?? .claude/`) |

## Acceptance criteria

The SDD's table has **18** criteria (AC-18, the companion map, was added on 2026-10-04); the T5.5
plan text still says "all 17". All 18 are walked here. Test paths are relative to the repository
root; a test named without a parameter id ran for every parameter.

| AC | Criterion (short) | Evidence | Status |
|---|---|---|---|
| AC-1 | ≤ 2 `tcs-patterns` descriptions in a session; inventory 98 → 77, no pattern skill left; 21 `SKILL.md` in `templates/patterns/` | Re-measured with `report.walk_skill_agent_inventory` over `git archive` trees: `2a5f192^` 98 entries (80 skills, 18 agents, 21 `tcs-patterns`), `2a5f192` 77 (59, 18, 0). At `HEAD` 79 = 77 + the two Phase-5 skills `tcs-patterns:pattern` and `tcs-patterns:patterns-setup` (≤ 2), `unreachable ()`. Catalogue: 21 dirs, 21 with `SKILL.md` + `VERSION`, 21 `SKILL.md` at any depth. `tests/test_tcs_patterns_catalogue_relocation.py::test_catalogue_holds_21_skill_md_each_tracked_by_git`, `::test_no_pattern_skill_reachable_in_inventory`. A live session's listing: pending release | VERIFIED (inventory and live listing, see Live validation) |
| AC-2 | 80 renames at 100 %; no path above its pattern dir; links resolve | `git diff -M --name-status 2a5f192^ 2a5f192`: 80 `R100` + 1 `A` (the test file). `tests/test_tcs_patterns_catalogue_links.py::test_no_markdown_link_in_the_catalogue_escapes_or_dangles`, `::test_no_code_span_path_in_the_catalogue_escapes_or_dangles` | VERIFIED |
| AC-3 | Every fixture's normalised report equals `expected.json` | `tests/test_patterns_detect.py::test_detector_matches_expected` — 27 of 27 fixtures pass | VERIFIED |
| AC-4 | Populated `node_modules` + empty root deps: nested signal found, vendored tree ignored | Fixture `trap-05-nested-manifest-and-node-modules` (repo has `node_modules/`, `packages/`; expects `auto: [mcp-server]`, `must_not_propose: [obsidian-plugin]`) via `test_detector_matches_expected[trap-05-…]`; `::test_excluded_segments_matches_skip_dirs` | VERIFIED |
| AC-5 | No server and no test framework → all gates closed, no questions | Fixture `edge-bare-repository` (all three gates `false`) via `test_detector_matches_expected`; `tests/test_patterns_outcomes.py::test_not_reached_is_non_empty_for_a_fixture_where_no_gate_opens_all_three`; skill text `tests/test_patterns_setup_skill.py::test_at_most_three_questions_closed_gates_skipped_multiple_answers` | VERIFIED |
| AC-6 | Four outcome sets pairwise disjoint, summing to 21, for every fixture × answer combination | `tests/test_patterns_outcomes.py::test_every_answer_combination_decides_each_of_the_21_exactly_once` (27 fixtures), `::test_invariant_fails_on_a_seeded_double_assignment`, `::test_invariant_fails_on_a_seeded_omission`. Walk step 5: 6 + 9 + 6 + 0 = 21 | VERIFIED |
| AC-7 | Install writes exactly the chosen `tcs-<name>` dirs with `name: tcs-<name>`; manifest has version, name, hash | Walk steps 6–8 (7 chosen, 7 written, all renamed; manifest complete). `tests/test_patterns_installer.py::test_chosen_pattern_lands_with_tcs_prefix_and_full_subtree`, `::test_nothing_unchosen_is_written`, `::test_manifest_records_version_installed_name_and_hash_for_each` | VERIFIED |
| AC-8 | An installed pattern appears in the repo's skill listing in a following session | Live: a new session in the `testing` repo listed `tcs-python-project` and `tcs-testing` (listing 97 → 99 skills) — see Live validation, P2 | VERIFIED |
| AC-9 | Install reports writes, says it did not commit, commits only on a yes | Walk: no commit performed (the report's `committed` field was later removed as always-false, #176 review L8); decline left `?? .claude/` and no commit; yes branch in `fixture-guard` committed exactly the verb's 3 paths, leaving a staged `README.md` alone. `tests/test_patterns_installer.py::test_report_lists_writes_and_carries_no_committed_field`, `tests/test_patterns_setup_skill.py::test_commit_is_offered_and_never_performed_unasked`, `::test_the_commit_offer_commits_only_the_paths_the_verb_changed` | VERIFIED |
| AC-10 | One colliding name (any namespace) refused with both locations, others installed | Walk: `fixture-guard` repo-namespace collision. `tests/test_patterns_guard.py::test_one_call_partitions_four_names_across_three_namespaces`, `::test_refusal_in_user_namespace_names_the_colliding_skill_md`, `::test_refusal_in_plugin_cache_names_the_colliding_skill_md`, `::test_enabled_plugins_false_still_refused`; `tests/test_patterns_cli.py::test_install_a_user_namespace_collision_is_refused_with_both_locations` | VERIFIED |
| AC-11 | Reporter prints `DRIFT:` / `OK` / `MISSING` / `UNKNOWN:`; advisory shows drift and unknown, suppresses `MISSING` | Walk: `OK` → bump → `DRIFT:ddd:1:2` → real hook names exactly `ddd v1 → v2`. `tests/test_patterns_drift.py` (27 tests, e.g. `::test_two_behind_prints_two_drift_lines_naming_both_versions_and_no_ok`, `::test_no_manifest_prints_missing`, `::test_installed_ahead_of_catalogue_is_unknown_not_drift_and_suppresses_ok`, `::test_pattern_directory_gone_from_catalogue_is_unknown`); `plugins/tcs-git-helpers/tests/bats/session-start-brief.bats` "patterns advisory: …" (17 tests incl. "MISSING alone is suppressed"). The advisory in a live session: pending release | VERIFIED (offline, real hook, and live session, see Live validation) |
| AC-12 | `update` refreshes only drifted, asks nothing about selection, per-file prompt default skip, diff installed → catalogue, labels populated | Walk: only `ddd` refreshed; `api-design` declined byte-identical; diff `--- installed` / `+++ catalogue`, local line as `-`. `tests/test_patterns_installer.py::test_diverged_pattern_hands_decide_a_signed_and_labelled_diff`, `::test_default_decide_declines_so_an_unanswered_prompt_destroys_nothing`, `::test_update_acts_on_every_manifest_pattern_and_has_no_names_parameter`; `tests/test_patterns_cli.py::test_update_without_accept_declines_a_diverged_pattern_byte_identical` | VERIFIED |
| AC-13 | Pattern file changed without its `VERSION` fails the gate; with it passes; no pattern touched is silent | `plugins/tcs-git-helpers/tests/bats/bundle-gate-patterns.bats` (7 tests: without bump, with bump, other pattern's bump, no pattern, regression, delete, whole-dir delete). Live: `check-hook-bundle-version.sh "56ae369^..56ae369"` exit 1 naming ddd, hexagonal, obsidian-plugin with "Fix: bump …/VERSION"; branch range `origin/main..HEAD` exit 0, silent | VERIFIED |
| AC-14 | Bash Obsidian gate and Python rule agree on every fixture and nested-plugin writes; the outside-write divergence is asserted | `tests/test_obsidian_rule_agreement.py::test_corpus_agreement` (27), `::test_constructed_tree_agreement`, `::test_nested_manifest_file_outside_plugin_diverges_deliberately` — 34 pass | VERIFIED |
| AC-15 | Reader prints a named body, writes nothing; unknown name lists the 21 | `plugins/tcs-patterns/skills/pattern/SKILL.md` has `allowed-tools: Read, Glob` (no write tool). `tests/test_patterns_reader_skill.py::test_allowed_tools_grant_nothing_write_capable`, `::test_known_name_shows_full_body_and_lists_companion_files`, `::test_unknown_or_invalid_name_lists_available_never_empty`, `::test_catalogue_has_exactly_21_directories`. Step-2 glob of the catalogue: 21 names | VERIFIED (skill contract, tool scope, and live invocation P4) |
| AC-16 | Proposal shows per-entry listing cost; baseline listed separately | Walk step 3 (`listing_cost` for all 21; `baseline` separate, `surface: false`). `tests/test_patterns_setup_skill.py::test_proposal_shows_per_entry_listing_cost_and_baseline_separately`; `tests/test_patterns_cli.py::test_scan_listing_cost_against_the_real_catalogue` | VERIFIED |
| AC-17 | After `update`, manifest version = catalogue `VERSION`; currency from the manifest alone | Walk: 7 of 7 manifest versions equal the copy's `VERSION`; `status`/reporter read only manifest + `VERSION`. `tests/test_patterns_install.py::test_currency_determinable_without_installed_pattern_files`, `tests/test_patterns_installer.py::test_version_behind_with_matching_hash_refreshes_without_ever_calling_decide` | VERIFIED |
| AC-18 | Derived companion map equals the seven measured edges; a new cross-reference fails the test | `companions.companion_map()`: ddd→hexagonal, event-driven→{event-sourcing, hexagonal}, event-sourcing→{event-driven, hexagonal}, hexagonal→ddd, observability→hexagonal = 7. `tests/test_tcs_patterns_companion_map.py::test_companion_map_equals_the_seven_measured_edges`, `::test_a_new_cross_pattern_reference_is_picked_up_not_missed`. Walk step 5 offered `hexagonal` from `ddd` and `observability` | VERIFIED |

## Test legs

Reported per leg from each runner's own counts, never from a combined verdict.

**pytest** — `python3 -m pytest -q` (repo root `pytest.ini`, `addopts = -m "not perf"`):
**1416 passed, 1 failed, 1 skipped, 1 deselected** (52.4 s).

- Failed: `tests/test_check_changelog_version_sync.py::test_repository_is_currently_consistent` —
  the expected one: `plugins/tcs-patterns: CHANGELOG documents 2.0.0 but plugin.json carries 1.4.4`,
  resolved when PR #179 bumps the manifest. It is the **only** failure.
- Skipped: `tests/test_spec_tier.py:199` ("scaffold does not write README.md; the skill does that
  from template.md").
- Deselected: `plugins/tcs-helper/scripts/test_intercept_rule_recurrence.py::TestPerformance::test_p95_latency_under_50ms` (`perf` marker).

**bats** — `bats --tap <suite>`, each suite separately, inside the sandbox (no
`Operation not permitted`, so no unsandboxed re-run was needed):

| Suite | Plan | ok | not ok | skip | Exit |
|---|---|---|---|---|---|
| `plugins/tcs-git-helpers/tests/bats` | `1..860` | 860 | 0 | 0 | 0 |
| `plugins/tcs-helper/tests/bats` | `1..330` | 330 | 0 | 0 | 0 |
| `plugins/tcs-issues/tests/bats` | `1..7` | 7 | 0 | 0 | 0 |
| `plugins/tcs-patterns/tests/bats` | `1..15` | 15 | 0 | 0 | 0 |

Each plan line equals its `ok` count, so no test was lost to a `setup_file` abort.

## CI gates, run locally

| Gate | Command | Exit | Result |
|---|---|---|---|
| Hook bundle + per-pattern `VERSION` | `plugins/tcs-git-helpers/scripts/ci/check-hook-bundle-version.sh "origin/main..HEAD"` | 0 | Silent pass. 101 changed paths under `templates/patterns/`, and all 21 `VERSION` files are added in the same range, so every pattern is satisfied. Not vacuous: the single commit `56ae369` fails it (exit 1) |
| docs-sync | `scripts/ci/check-docs-sync.sh --changed-files <file of git diff --name-only origin/main...HEAD>` (261 paths) | 0 | `check-docs-sync: every affected surface is accounted for` |
| changelog-version-sync | `scripts/ci/check-changelog-version-sync.sh --allow-ahead 1` | 1 | Only failure: `plugins/tcs-patterns: CHANGELOG documents 2.0.0 but plugin.json carries 1.4.4` (expected until #179). The other five plugins print `ok` |

## Findings

**Defects: none.**

Notes, none of which needs a change in this spec's components:

1. `bundle = "1.4.4"` in the fixture manifest. `install._bundle_version()` reads `plugin.json`,
   which still carries 1.4.4 on this branch; after #179 it records 2.0.0. Drift uses each
   pattern's own `version`, never `bundle`, so nothing is affected.
2. **Plan text says 17 ACs; the SDD has 18.** `plan/phase-5.md` T5.5's success line "All 17 SDD
   acceptance criteria verified" predates AC-18. A wording mismatch only; this file covers all 18.
3. AC-1's "no `tcs-patterns` skill remaining" was true at the relocation commit (measured: 0) and
   is 2 at `HEAD` by design — the two Phase-5 skills. Its first clause (≤ 2) is the one that
   still holds as stated.
4. An installed `tcs-hexagonal` mentions `tcs-event-sourcing`, which this fixture did not
   install. That is a mention, not a resolving path, so it is not a companion edge (ADR-10); the
   skill already says not to claim every citation resolves.
5. On this branch range the per-pattern CI rule is trivially satisfied because every `VERSION` is
   new in the range. Its real bite starts on the first change after 2.0.0 ships.

## Pending release

These need `tcs-patterns` 2.0.0 and `tcs-git-helpers` 2.2.23 (the release carrying the section-8c
advisory) **published to the marketplace** and a **new** Claude Code session — the plugin cache is
stale inside the session that updated it. Today the cache holds `tcs-patterns` 1.4.4 and
`tcs-git-helpers` 2.2.21 / 2.2.22.

**P1. Update the plugins.** After this branch and #179 merge and the marketplace is published:
in Claude Code, `/plugin` → update `tcs-patterns` to 2.0.0 and `tcs-git-helpers` to ≥ 2.2.23.
Confirm `ls ~/.claude/plugins/cache/the-custom-startup/tcs-patterns/` shows `2.0.0`. Quit the session.

**P2. AC-8 and AC-1 (listing).** Recreate the fixture (or reuse any throwaway repo with a
`pyproject.toml` declaring `fastapi` and a `[tool.pytest.ini_options]` table), start a **new**
session there, run `/tcs-patterns:patterns-setup install`, accept `python-project` and `testing`,
decline the commit. Quit, start **another new** session in the same repo, then:
- Check the `/` skill menu (or ask "list your skills") lists `tcs-python-project` and `tcs-testing`
  as project skills → AC-8.
- Check the listing has exactly two `tcs-patterns:` entries — `tcs-patterns:pattern` and
  `tcs-patterns:patterns-setup` — and none of the 21 pattern names as `tcs-patterns:<name>` → AC-1.

**P3. AC-11 (live advisory).** In that repository, lower one manifest entry instead of touching
the released catalogue: edit `.claude/skills/.tcs-patterns-manifest` so `[patterns.testing]` has
`version = "0"` (checked offline: the reporter then prints `DRIFT:testing:0:1`). Start a **new**
session. The session-start `systemMessage` must contain exactly
`patterns testing v0 → v1; run /tcs-patterns:patterns-setup update` and name no other pattern.
Then run `/tcs-patterns:patterns-setup update`: `testing` is refreshed 0 → 1, and the manifest
entry reads `version = "1"` again. Start one more session: no patterns segment.

**P4. Optional — AC-15 live.** In any session, `/tcs-patterns:pattern ddd` shows the full body
and the `reference/` file list; `/tcs-patterns:pattern nope` lists the 21 names. `git status`
in that repository stays clean.

When P2 and P3 pass, tick T5.5's two pending success lines in `plan/phase-5.md`.

## After PR #179 merged (2026-10-07)

#179 (`1d2eb85`) taught CI to honour a next-major or next-minor CHANGELOG heading. `origin/main`
was then merged into this branch (`efbaecd`). It was merged rather than rebased, because a rebase
would need a forced push and this repository's safety hook blocks that. Re-measured per leg on the
merged branch:

| Leg | Result |
|---|---|
| pytest | 1465 passed, 0 failed, 1 skipped, 1 deselected (perf) |
| bats tcs-git-helpers | 1..860, 860 ok, 0 not ok, 0 skip |
| bats tcs-helper | 1..330, 330 ok, 0 not ok, 0 skip |
| bats tcs-issues | 1..7, 7 ok |
| bats tcs-patterns | 1..15, 15 ok |
| `check-changelog-version-sync.sh --allow-ahead 1` | exit 0; tcs-patterns CHANGELOG 2.0.0 against manifest 1.4.4 now passes |
| `check-docs-sync.sh` | every affected surface is accounted for |
| `check-hook-bundle-version.sh origin/main..HEAD` | exit 0 |

The one failure recorded above, `test_repository_is_currently_consistent`, now passes. On merge,
CI will set tcs-patterns to 2.0.0 from the heading.

P1-P4 ran after release; see the next section.

## Live validation (2026-10-07)

Run by Marcus in the throwaway repository `/Volumes/Moon/Coding/testing` (no source files, so the
scan proposes nothing, which ADR-5 intends). The installed patterns were named explicitly. The evidence
was read from the session transcripts under `~/.claude/projects/-Volumes-Moon-Coding-testing/`
and from the repository itself.

| Step | Session | Evidence | Result |
|---|---|---|---|
| P1 update | `b22f3a2b`, `3b747727` | Plugin cache holds `tcs-patterns/2.0.0` and `tcs-git-helpers/2.2.23` | PASS |
| Install | `a7c79c2f` | `install python-project testing`: both written as `tcs-<name>`, manifest `schema = 1`, `bundle = "2.0.0"`; committed on a yes as `a8c4e5b` (path-limited, 9 files); `status` both `OK` | PASS |
| P2, AC-8 | `d1133ecf` (new session) | Skill listing: 99 skills against 97 in the install session, including `tcs-python-project` and `tcs-testing` with their descriptions | PASS |
| P2, AC-1 | `d1133ecf` | The only `tcs-patterns:` entries were `tcs-patterns:pattern` and `tcs-patterns:patterns-setup`; none of the 21 pattern names appears as a plugin skill | PASS |
| P3, AC-11 | `d1133ecf` | With the manifest's `testing` lowered to `"0"`, the session-start `systemMessage` was exactly `patterns testing v0 → v1; run /tcs-patterns:patterns-setup update` (plus the unrelated git-setup segment). `additionalContext` carried only the git-setup segment, so the #176 review's M2 routing holds live | PASS |
| P3 update | `d1133ecf` | `update` refreshed `testing` 0 → 1, left `python-project` current; afterwards the files matched the committed copy byte for byte | PASS |
| P3 after | this checkout | The released reporter (`python3 -I …/2.0.0/scripts/patterns_drift.py`) prints `OK`, which the advisory suppresses, so the next session shows no patterns segment | PASS |
| P4, AC-15 | `d1133ecf` | `/tcs-patterns:pattern ddd` showed the full body and the five `reference/` files; `nope` listed the 21 names; `git status` clean | PASS |

**Observed, not a defect:**

- **The sandbox blocks the first write.** Claude Code's sandbox denies writes under
  `.claude/skills`, so the first `install` and the first `update` each returned a per-pattern
  `Operation not permitted` in `failed`, with exit 0 and valid JSON. The model re-ran them outside
  the sandbox and they succeeded. Marcus chose to leave the skill as it is (2026-10-07).
- **tcs-git-helpers refused to create the commit branch** because the working tree was dirty.
  The model inspected the tree first, then used the documented override.
