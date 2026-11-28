---
title: "Phase 3: Evaluation and the audit verb"
status: in_progress
version: "1.0"
phase: 3
---

# Phase 3: Evaluation and the audit verb

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Implementation Examples; lines: 609-711]` effective-value, credential and broad-allow walkthroughs (turn each table into tests)
- `[ref: SDD/Complex Logic; lines: 828-865]` verdict algorithm and check catalogue
- `[ref: SDD/Internal API Changes; lines: 467-494]` audit verb contract
- `[ref: SDD/Application Data Models; lines: 496-583]` Effective, Finding, AuditReport
- `[ref: SDD/ADR-1, ADR-4; lines: 943-952, 982-989]`
- `[ref: SDD/Acceptance Criteria; lines: 1069-1170]`

**Key Decisions**:
- ADR-4: verdict computed from per-layer states; PARTIAL and UNKNOWN keep base severity; ACCEPTED only for the listed profile exceptions.
- ADR-1: `audit` exits 0 whether or not gaps exist; verdict line produced by the CLI.
- Bypass via project/local `defaultMode` is ignored by Claude Code since 2.1.257 — not a C2 finding.

**Dependencies**:
- Phase 1 and Phase 2. T3.1 first; T3.2–T3.5 in parallel after T3.1; T3.6 last.

---

## Tasks

Delivers a working, read-only `audit`: effective values, every check, verdicts and the JSON report, runnable end to end against fixture trees.

- [ ] **T3.1 Effective values and verdict (`effective.py`, `verdict.py`)** `[activity: domain-modeling]`

  1. Prime: effective-value walkthrough and verdict algorithm `[ref: SDD/Implementation Examples; lines: 609-649]` `[ref: SDD/Complex Logic; lines: 828-865]`
  2. Test: the `sandbox.enabled` walkthrough (user true, local false → false, winner local, user shadowed); unreadable local → UNKNOWN contribution; union for `permissions.deny` with provenance; `strict-wins` for `blockReadsOutsideWorkingDirectories` (strict true from any scope) and `allowUnsandboxedCommands` (user false beats project/local true from 2.1.285; older version or unknown → highest); `defaultMode: bypassPermissions` ignored in project/local; managed outranks local; verdict table rows 1–8 each as a case; PARTIAL/UNKNOWN keep base severity; a check raising → UNKNOWN `check-error`; summary counts and verdict line ≤ 160 chars, "no gaps in the audited layers" plus unaudited list when nothing remains
  3. Implement: `lib/effective.py` — `effective(key, sources, rule) -> Effective`; `lib/verdict.py` — `status(states)`, `finalise(findings, profile, accepted_rules) -> (findings, accepted, info, summary, coverage)`
  4. Validate: `.venv/bin/pytest -q tests/tcs-helper/test_security_baseline_effective.py tests/tcs-helper/test_security_baseline_checks.py -k verdict`
  5. Success: override names both files `[ref: PRD/F1 AC3]`; PARTIAL never downgraded `[ref: PRD/F1 AC4]`; qualified "no gaps" `[ref: PRD/F1 AC7]` `[ref: SDD/F1.3, F1.4, F1.6, F1.7]`

- [ ] **T3.2 Credential and sandbox checks C1, C4, C7, C8 (`checks_credentials.py`)** `[activity: security]` `[parallel: true]`

  1. Prime: credential-equivalence walkthrough, catalogue rows C1/C4/C7/C8 `[ref: SDD/Implementation Examples; lines: 651-679]` `[ref: SDD/Complex Logic; lines: 828-865]`
  2. Test: every row of the credential walkthrough table; `~/.aws` missing everywhere and absent on disk → FAIL HIGH; `{home}` substitution; Read deny complete + sandbox off → PARTIAL HIGH "commands can still read"; + `allowUnsandboxedCommands` effective true → sandbox half not EFFECTIVE; `.env*` on Linux → PARTIAL; unknown spelling → PARTIAL "equivalence unverified"; C4 sandbox off → HIGH; probe fail/inconclusive reflected; `enableWeakerNestedSandbox` true reported; C7 missing or version < 2.1.257 → MED / UNKNOWN; C8 sandbox on without `allowedDomains` → MED
  3. Implement: `check_credentials`, `check_sandbox`, `check_read_outside`, `check_network_domains` in `lib/checks_credentials.py`
  4. Validate: `.venv/bin/pytest -q tests/tcs-helper/test_security_baseline_checks_credentials.py`
  5. Success: `[ref: PRD/F3 AC1-AC5]` `[ref: PRD/F6 AC1]` `[ref: PRD/F10 AC1-AC2]` `[ref: SDD/F3.1-F3.5, F6.1, F10.1-F10.2]`

- [ ] **T3.3 Bypass checks C2, C2x** `[activity: security]` `[parallel: true]`

  1. Prime: catalogue rows C2/C2x, ACCEPTED rules `[ref: SDD/Complex Logic; lines: 828-865]`
  2. Test: host profile without `disableBypassPermissionsMode: "disable"` → HIGH; user `defaultMode: bypassPermissions` → HIGH naming the file; same in project/local → no C2 finding; container → bypass in ACCEPTED; container + bypass active + probe ≠ pass + `~/.ssh` exists → C2x HIGH, not accepted, both fix texts; container with probe pass → no C2x
  3. Implement: `check_bypass`, `check_container_exposure` in `lib/checks_bypass.py`
  4. Validate: `.venv/bin/pytest -q tests/tcs-helper/test_security_baseline_checks_bypass.py`
  5. Success: `[ref: PRD/F4 AC1, AC3, AC4]` `[ref: PRD/F2 AC3]` `[ref: SDD/F4.1, F4.3, F4.4]`

- [ ] **T3.4 Allow-rule checks C3, C5** `[activity: security]` `[parallel: true]`

  1. Prime: broad-allow walkthrough and normaliser `[ref: SDD/Implementation Examples; lines: 681-711]`
  2. Test: every row of the broad-allow table; `Bash(curl *)`, `Bash(curl:*)`, `Bash(/usr/bin/curl:*)`, `Bash(FOO=1 curl *)` classify identically; bare `Bash`, `Bash(*)`, `Write`, `Edit`, `WebFetch`, `mcp__srv` → HIGH; `Bash(jq *)` → MED unclassified; `Bash(git status)` → not flagged; allow shadowed by a deny or ask in another layer → shadowed; each finding names its file; C5: `WebFetch` without domain or `domain:*` → HIGH; domain-scoped + `Bash(curl:*)` → PARTIAL naming the rule
  3. Implement: `normalise`, `check_broad_allows`, `check_webfetch` in `lib/checks_allows.py`
  4. Validate: `.venv/bin/pytest -q tests/tcs-helper/test_security_baseline_checks_allows.py`
  5. Success: `[ref: PRD/F5 AC1-AC6]` `[ref: PRD/F7 AC1-AC2]` `[ref: SDD/F5.1-F5.6, F7.1-F7.2]`

- [ ] **T3.5 MCP, excludes, hygiene, clone risk C6, C6x, C9, C10, CR** `[activity: security]` `[parallel: true]`

  1. Prime: catalogue rows C6/C6x/C9/C10/CR; MCP source table `[ref: SDD/Complex Logic; lines: 828-865]` `[ref: SDD/Interface Specifications; lines: 241-285]`
  2. Test: `enableAllProjectMcpServers` effective true → HIGH listing approved servers; no `allowedMcpServers` → MED "no automatic fix"; container + bypass + `.mcp.json` servers not in `disabledMcpjsonServers` → C6x HIGH naming them; `excludedCommands` exact template match → ACCEPTED, near-miss spelling → MED, no template → all MED; `Skill(gone)` with no installed skill → LOW; skill names failing the regex never joined to a path; CR: project/local `hooks`, `statusLine`, `apiKeyHelper`, `env`, `enableAllProjectMcpServers` → one INFO each with key and file, env values absent from output
  3. Implement: `check_mcp`, `check_container_mcp`, `check_excluded_commands`, `check_hygiene`, `check_clone_risk` in `lib/checks_mcp.py`
  4. Validate: `.venv/bin/pytest -q tests/tcs-helper/test_security_baseline_checks_mcp.py`
  5. Success: `[ref: PRD/F8 AC1, AC3, AC5]` `[ref: PRD/F10 AC3-AC5]` `[ref: PRD/F11 AC1, AC3]` `[ref: PRD/F12 AC1]` `[ref: SDD/F8.1, F8.3, F8.5, F10.3-F10.5, F11.1, F11.3, F12.1]`

- [ ] **T3.6 CLI skeleton and the `audit` verb (`cli.py`)** `[activity: backend-api]`

  1. Prime: patterns-setup `cli.py` docstring and `main()`; audit contract; primary flow audit `[ref: SDD/Internal API Changes; lines: 467-494]` `[ref: SDD/Primary Flow; lines: 761-771]` `[ref: SDD/ADR-1; lines: 943-952]`
  2. Test (`World` fixtures for host, linux-native, container; subprocess with `sys.executable -I -B`): exit 0 with one JSON document (`schema_version: 1`) and findings sorted HIGH→LOW; each finding has check, severity, layer, file, scope, evidence, fix; `_digest()` of home, repo and the skill directory equal before and after the run (earlier in-process tests may already have created `lib/__pycache__`; that is compared, not forbidden); a run against a fresh copy of the skill directory in `tmp_path` creates no `__pycache__`; unknown verb → 2 with help on stderr; Python < 3.11 path → 3 (simulated); `--profile container` → EXPLICIT; `coverage.unaudited` present in every profile; a malformed project file → named unreadable, others audited; a fixture with no gaps → qualified verdict line
  3. Implement: `lib/checks.py` — `ALL_CHECKS` registry over the four `checks_*.py` modules in catalogue order; `lib/cli.py` — argparse with stderr help, version check before sibling imports, `LIB_DIR` on `sys.path`, `audit` wiring T2.x → T3.1–T3.5 → `render`, JSON to `sys.stdout.buffer`
  4. Validate: `.venv/bin/pytest -q tests/tcs-helper/test_security_baseline_cli.py -k audit`
  5. Success: `[ref: PRD/F1 AC1-AC7]` `[ref: PRD/F2 AC4]` `[ref: SDD/F1.1-F1.7, F2.4]`

- [ ] **T3.7 Phase Validation** `[activity: validate]`

  - Run `.venv/bin/pytest -q tests/tcs-helper/test_security_baseline_*.py tests/test_json_dump_ensure_ascii.py tests/tcs-helper/test_prompt_lint_repo.py`. Run `audit` against this container (read-only) and compare its findings with the six gaps of the 2026-11-27 inventory in the PRD Problem Statement; every one must appear (or be ACCEPTED for the container profile with its reason).
