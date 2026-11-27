---
title: "Phase 1: Foundations — strict JSON, reference data, untrusted rendering"
status: completed
version: "1.0"
phase: 1
---

# Phase 1: Foundations — strict JSON, reference data, untrusted rendering

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Building Block View/Components; lines: 332-378]` K5, K8, K15
- `[ref: SDD/Directory Map; lines: 380-435]`
- `[ref: SDD/Implementation Examples; lines: 651-711]` credential spellings and command classes the data must hold
- `[ref: SDD/ADR-5, ADR-8, ADR-10; lines: 990-996, 1024-1053]`
- `[ref: SDD/Implementation Gotchas; lines: 1191-1211]`

**Key Decisions**:
- ADR-10: strict parse, never repair; byte-faithful rewrite (order, indent, newline).
- ADR-5: three JSON data files validated at load; each entry carries a `doc` anchor.
- ADR-8: one `render_untrusted()`; fix texts only from templates; secrets always redacted.

**Dependencies**:
- None. T1.1, T1.2 and T1.3 are independent.

**Test conventions (all phases)**:
- Tests live only in `tests/tcs-helper/` — a `test_*.py` under the skill's `lib/` would be collected by CI.
- Load lib modules in-process with `importlib.util.spec_from_file_location` under a unique name (e.g. `sb_jsonio`) — `tests/tcs-helper/` shares a pytest process with patterns-setup, whose `cli` module would otherwise shadow ours; drive `cli.py` only by subprocess with `sys.executable -I -B`.
- The `World`/`_run` helpers are new, modelled on `tests/test_patterns_cli.py` (which has no `root`, no `-I -B`, returns `CompletedProcess`).
- No secret-shaped literals (`sk-ant-…`, `AKIA…`, `-----BEGIN … PRIVATE KEY-----`) in lib code or fixtures committed as `.py` — build them at runtime in tests (prompt_lint E1).

---

## Tasks

Establishes the three leaf modules every later component builds on: reading and writing settings JSON safely, the shipped reference data, and the only path by which file content reaches output.

- [x] **T1.1 Strict JSON I/O (`jsonio.py`)** `[activity: backend-io]` `[parallel: true]`

  1. Prime: ADR-10, Source/Format data models, error-handling rows for unreadable files `[ref: SDD/ADR-10; lines: 1043-1053]` `[ref: SDD/Application Data Models; lines: 496-583]` `[ref: SDD/Error Handling; lines: 809-826]`
  2. Test: valid object parses with detected `Format` (2-space, 4-space, tab, CRLF, missing trailing newline); duplicate key → `ambiguous`; BOM, `NaN`, `Infinity`, `//` comment, trailing comma, depth > 64, round-trip mismatch, top-level array → `unreadable` with fixed-vocabulary reason; 1 MiB + 1 byte → `too-large`; FIFO and directory → `not-regular` without hanging; symlink opened with `O_NOFOLLOW` fails for project scope; missing file → `absent`; `dumps(obj, fmt)` reproduces the original bytes for an unchanged object and preserves key order after an append; `ensure_ascii=False` in file bytes (explicit argument at every `json.dump(s)`, per `tests/test_json_dump_ensure_ascii.py`)
  3. Implement: `plugins/tcs-helper/skills/security-baseline/lib/jsonio.py` — `read_json(path, follow_symlink: bool) -> (status, data, fmt, reason)`, `dumps(obj, fmt) -> bytes`; no I/O at import
  4. Validate: `.venv/bin/pytest -q tests/tcs-helper/test_security_baseline_jsonio.py`; only 3.11 stdlib APIs
  5. Success: an unreadable file is never treated as empty `[ref: PRD/F1 AC5]`; rewrite preserves everything outside the change `[ref: PRD/F9 AC7]` `[ref: SDD/F1.5, F9.7]`

- [x] **T1.2 Reference data (`refdata.py` + `reference/*.json`)** `[activity: domain-modeling]` `[parallel: true]`

  1. Prime: keys and minimum versions from the research report recorded in the SDD; credential spelling table and command classifier walkthroughs `[ref: SDD/Implementation Examples; lines: 609-711]` `[ref: SDD/ADR-5; lines: 990-996]` `[ref: SDD/Implementation Gotchas; lines: 1191-1211]`
  2. Test: each file loads and validates (unknown field rejects with the file and entry named); every `keys.json` entry has `type`, `merge` ∈ {union, highest, strict-wins} (deviation: strict-wins with a per-key `strict` value replaced true-wins, 7daa2b25), `doc`, and `min` where the docs give one (`blockReadsOutsideWorkingDirectories` 2.1.257, `WebFetch` wildcards 2.1.172); `credentials.json` holds the ten PRD paths with Read-rule and sandbox spellings and `linux_enforceable` (`.env*` false); `commands.json` holds classes interpreter / shell / network / pkg-manager / wrapper / exec with the PRD and review lists (python*, node, sh, bash, zsh, curl, wget, pip/npm/brew install, uv run, npx, env, git, gh api, find, xargs, awk, sed, make, ruby, perl, lua, php, deno, bun, go run, cargo run, eval, source, nohup, timeout, nice, watch, sudo, busybox, ssh, scp, rsync, docker, kubectl), a narrow list (git status, git diff, git log, ls, pwd, …) and normalisation aliases
  3. Implement: `lib/refdata.py` (`load_keys()`, `load_credentials()`, `load_commands()`, frozen dataclasses), `reference/keys.json`, `reference/credentials.json`, `reference/commands.json`
  4. Validate: `.venv/bin/pytest -q tests/tcs-helper/test_security_baseline_refdata.py`
  5. Success: lists match the PRD's named commands and paths `[ref: PRD/F3 AC1, F5 AC1-AC5]`; one source for names and versions `[ref: PRD/Risks "setting renamed"]` `[ref: SDD/ADR-5]`

- [x] **T1.3 Untrusted rendering and redaction (`render.py`)** `[activity: security]` `[parallel: true]`

  1. Prime: ADR-8, AuditReport `untrusted_notice` and `evidence` placement `[ref: SDD/ADR-8; lines: 1024-1033]` `[ref: SDD/Application Data Models; lines: 496-583]`
  2. Test: ANSI/OSC sequences, bidi and zero-width characters escaped; 10 KB string truncated to 80 chars with `+N chars`; list > 50 items → 50 plus `N more`; whole report capped at 32 KB with a truncation marker; names outside `^[A-Za-z0-9_.@:/-]{1,64}$` → `<non-conforming #n sha8>`; `env` values and values of keys matching token|key|secret|password redacted; instruction-shaped text ("ignore previous instructions…") only ever appears inside `evidence`; fix templates reject interpolation of evidence strings
  3. Implement: `lib/render.py` — `render_untrusted(value)`, `redact(pointer, value)`, `cap_report(doc)`, fix-template registry
  4. Validate: `.venv/bin/pytest -q tests/tcs-helper/test_security_baseline_render.py`
  5. Success: hostile content only as marked, shortened evidence `[ref: PRD/F1 AC8]`; env values never shown `[ref: PRD/F11 AC3]` `[ref: SDD/F1.8, F11.3]`

- [x] **T1.4 Phase Validation** `[activity: validate]`

  - Run `.venv/bin/pytest -q tests/tcs-helper/test_security_baseline_{jsonio,refdata,render}.py tests/test_json_dump_ensure_ascii.py tests/tcs-helper/test_prompt_lint_repo.py`. Confirm no module performs I/O at import and none imports another plugin. Check every data entry against the SDD tables.
