---
title: "Phase 2: Reading the machine — environment, probe, layers, inventory"
status: in_progress
version: "1.0"
phase: 2
---

# Phase 2: Reading the machine — environment, probe, layers, inventory

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/External Interfaces; lines: 219-285]` sources, subprocesses, data interfaces
- `[ref: SDD/Integration Points; lines: 585-605]`
- `[ref: SDD/ADR-6, ADR-7, ADR-9; lines: 997-1023, 1034-1042]`
- `[ref: SDD/Error Handling; lines: 809-826]`
- `[ref: SDD/Implementation Gotchas; lines: 1191-1211]` local-file location, placeholders, `$TMPDIR`

**Key Decisions**:
- ADR-7: profile from filesystem markers; `CONTAINERIZED` only when no settings layer sets it; parent argv presence only, never values.
- ADR-6: probe binaries from fixed directories, minimal env, 10 s, pass only on exit 0, nested → inconclusive.
- ADR-9: git-helpers template newest by version sort, exact matches only.

**Dependencies**:
- Phase 1 (T1.1 `jsonio` for every file read; T1.3 not needed yet).
- T2.1 needs T2.3's settings `env` values for the `CONTAINERIZED` rule: T2.1 takes them as a parameter, so both can be built in parallel and wired in T3.6.

---

## Tasks

Establishes everything the audit knows about the machine: where it runs, whether the sandbox can run, which settings and MCP sources exist and what they contain, and which plugins and skills are installed.

- [ ] **T2.1 Environment detection (`environment.py`)** `[activity: backend-system]` `[parallel: true]`

  1. Prime: Environment model, ADR-7 `[ref: SDD/Application Data Models; lines: 496-583]` `[ref: SDD/ADR-7; lines: 1013-1023]`
  2. Test: Darwin → `macos-host`; Linux without markers → `linux-native`; `/.dockerenv` or `/run/.containerenv` or a container cgroup line → `container` with evidence (marker root injectable for tests); `CONTAINERIZED=1` with no layer setting it → container; with a layer `env` setting it → ignored and named in evidence; `--profile` → `explicit`; ancestor argv containing `--settings`, `--dangerously-skip-permissions`, `--permission-mode` → presence flags without values (fake `/proc` tree and fake `ps` output); unreadable `/proc` → `unknown`; `claude --version` output `2.1.332 (Claude Code)` parsed; missing binary, timeout, garbage → `None`; a `claude` on a relative, project-internal or world-writable PATH entry is skipped
  3. Implement: `lib/environment.py` — `detect(platform, roots, env, layer_env_keys, explicit_profile, proc_reader, which) -> Environment`, `Version` with comparison
  4. Validate: `.venv/bin/pytest -q tests/tcs-helper/test_security_baseline_environment.py`
  5. Success: profile cannot be spoofed by repo settings `[ref: PRD/F2 AC5]`; `--settings` presence reported `[ref: PRD/F2 AC6]` `[ref: SDD/F2.1-F2.6]`

- [ ] **T2.2 Sandbox probe (`probe.py`)** `[activity: security]` `[parallel: true]`

  1. Prime: ADR-6, ProbeResult model, error rows `[ref: SDD/ADR-6; lines: 997-1012]` `[ref: SDD/Error Handling; lines: 809-826]`
  2. Test: binaries found only in `/usr/bin`, `/bin`, `/usr/local/bin`, `/opt/homebrew/bin` (dirs injectable); a planted `bwrap` earlier on `PATH` is never run; world-writable or foreign-owned binary rejected; Linux missing `bwrap`/`socat` → `fail` with `missing` and install hint; exit 0 → `pass`; non-zero → `fail` "cannot run here"; timeout (fake binary sleeping) → `inconclusive`, process group killed; nested-sandbox stderr symptom → `inconclusive`; non-Linux/Darwin → `inconclusive`; argv is the constant from the SDD, `shell=False`, `cwd="/"`, env only `PATH` and `LANG=C`; no file created (tmp tree digest)
  3. Implement: `lib/probe.py` — `run_probe(platform, search_dirs, runner, timeout=10) -> ProbeResult`
  4. Validate: `.venv/bin/pytest -q tests/tcs-helper/test_security_baseline_probe.py`; on a Linux runner without bwrap the real call returns `fail` with `missing`
  5. Success: dependency and trial results distinguished `[ref: PRD/F6 AC2-AC4]`; probe executes nothing from settings and writes nothing `[ref: PRD/F6 AC7]` `[ref: SDD/F6.2-F6.4, F6.8]`

- [x] **T2.3 Settings and MCP sources (`layers.py`)** `[activity: backend-io]` `[parallel: true]`

  1. Prime: Source model, settings paths and precedence, MCP source table, local-file location gotcha `[ref: SDD/Interface Specifications; lines: 241-285]` `[ref: SDD/Implementation Gotchas; lines: 1191-1211]`
  2. Test (fixture home + repo per `World` convention, `HOME` and `CLAUDE_CONFIG_DIR` overrides): finds managed file and `managed-settings.d/*.json` alphabetically (hidden and non-json skipped) under an injectable system root; user via `CLAUDE_CONFIG_DIR`; project at `<project_dir>/.claude/settings.json`; local at repo root and, if present, the legacy start-directory file; `EACCES` → `denied`; each source carries status from `jsonio`; MCP: `.mcp.json`, `~/.claude.json` top-level `mcpServers` and `projects[<abs>].mcpServers`, approval keys from settings, managed `managed-mcp.json`; `~/.claude.json` per-project `enabledMcpjsonServers` read as observed-only; nothing written
  3. Implement: `lib/layers.py` — `discover(project_dir, repo_root, home, config_dir, system_root) -> list[Source]`, `mcp_servers(sources, plugin_servers) -> list[McpServer]`
  4. Validate: `.venv/bin/pytest -q tests/tcs-helper/test_security_baseline_layers.py`
  5. Success: all readable layers read, unreadable ones named `[ref: PRD/F1 AC1, AC5]`; servers listed with source `[ref: PRD/F8 AC4]` `[ref: SDD/F8.4]`

- [ ] **T2.4 Plugin inventory (`inventory.py`)** `[activity: backend-io]` `[parallel: true]`

  1. Prime: `guard.py` walk approach (copy, do not import), ADR-9 `[ref: SDD/Code Context; lines: 148-193]` `[ref: SDD/ADR-9; lines: 1034-1042]`
  2. Test: installed skills from `~/.claude/plugins/{cache,marketplaces}/*/*/*/skills/*/SKILL.md` frontmatter `name:` plus repo and user `.claude/skills/`; symlink loops survive via `(st_dev, st_ino)` dedup; dot-prefixed dirs skipped; plugin MCP servers from plugin `.mcp.json` and `plugin.json` `mcpServers`, `installPath` outside `~/.claude/plugins` rejected; git-helpers template: newest of versions `2.2.43`, `2.3.0`, `2.10.0` chosen by version order (not lexical), no repository-checkout fallback (ADR-9 amended 2026-11-28), marketplace layout `marketplaces/<mkt>/plugins/tcs-git-helpers/templates/...` ranked below versioned cache copies, sha256 recorded, absent → `None`
  3. Implement: `lib/inventory.py` — `scan(home, repo_root) -> Inventory(skills, plugin_mcp, git_template)`
  4. Validate: `.venv/bin/pytest -q tests/tcs-helper/test_security_baseline_inventory.py`
  5. Success: template is the single source for accepted excludes `[ref: PRD/F10 AC3-AC5]`; stale skills detectable `[ref: PRD/F12 AC1]` `[ref: SDD/ADR-9]`

- [ ] **T2.5 Phase Validation** `[activity: validate]`

  - Run `.venv/bin/pytest -q tests/tcs-helper/test_security_baseline_{environment,probe,layers,inventory}.py tests/tcs-helper/test_prompt_lint_repo.py` (E4: no interpolated values in prompt-shaped subprocess argv). Confirm a subprocess guard shows only the probe binaries, `claude --version` and `ps` are executed, no network socket is opened, and no test touches the real `$HOME`.
