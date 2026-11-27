# Brainstorm: security-baseline skill (issue #298, spec 025)

> Validated design from the brainstorm for `docs/XDD/specs/025-security-baseline/`.
> Feeds the PRD; implementation details are indicative and settled in the SDD.

## Problem

Claude Code's security posture on a solo developer's machines is set by four settings layers
(user, project, local, managed) plus a `--settings` flag layer, and today nobody checks them.
An inventory of this repo's container (2026-11-27, Claude Code 2.1.330) found:
the sandbox not enabled and its Linux dependencies (bubblewrap, socat) missing; no Read deny for
`~/.ssh`, `~/.aws`, `~/.config/gh`, `.env*`; bypass mode not disabled; broad allows such as
`Bash(python3:*)`, `Bash(curl:*)`, `Bash(git:*)`, `Bash(gh api:*)` and package-manager installs;
no MCP allow/deny lists; WebFetch domain-scoped but bypassable through `Bash(curl:*)`.
The protections are layered and each layer has blind spots (Read deny does not stop
subprocesses; `sandbox.filesystem.denyRead` does not stop the Read tool; the sandbox does not
wrap WebFetch, Read or MCP), so a manual review easily believes a hole is closed when it is not.

## Users

- **Solo developer on a macOS host** — wants the machine-wide baseline, without breaking daily
  work.
- **Same developer inside a per-repo Linux container** — separate home (`/home/coder`, one per
  repo), may run with `YOLO=true` (`--dangerously-skip-permissions`), and the entrypoint passes
  `--settings` JSON that outranks every settings file.

Teams and managed-settings rollout are out of scope (see Parking lot).

## Approaches considered

| Approach | Verdict |
|---|---|
| **A. Python CLI in `skills/security-baseline/lib/` owns audit/plan/apply; skill narrates and gates the write** | **Chosen** — deterministic, pytest-testable, follows `patterns-setup` / `observability-setup` |
| B. Model-driven skill with a reference checklist (`memory-setup` style) | Rejected — untestable and non-deterministic for a security audit and a "never silent" write |
| C. Bash + jq (git-setup `sandbox_settings.sh` style) | Rejected — per-rule removal and multi-file merge are awkward; repo rule: no JSON parsing in shell |

## Design

### Modes

- `/tcs-helper:security-baseline audit [path]` — read-only. Run on demand only.
- `/tcs-helper:security-baseline setup [path]` — proposes fixes from the audit and writes only
  after a shown diff and an explicit yes.

### Profiles

Detected automatically, overridable with `--profile`:

| Profile | Detection | Effect |
|---|---|---|
| `macos-host` | Darwin | full baseline |
| `linux-native` | Linux, no container marker | full baseline |
| `container` | `/.dockerenv`, `/run/.containerenv` or `CONTAINERIZED` set | bypass mode is an accepted exception; setup never writes `disableBypassPermissionsMode`; audit prints a caveat that a `--settings` layer may exist and is not audited |

### Audit

- Reads managed, user, project and local settings and every MCP server source (project
  `.mcp.json`, user `~/.claude.json` MCP keys, plugin-provided servers where discoverable).
- Computes the **effective** value of each checked key across the readable layers. Arrays merge;
  a deny at any layer wins; scalars come from the highest layer that sets them. A value fixed in
  one file but overridden at a higher layer is reported as such.
- Checks sandbox availability by a **trial run** of the sandbox mechanism, not by binary presence.
- Output: a severity-ranked gap list (HIGH / MED / LOW). Each finding names the check, severity,
  layer it closes (permissions / sandbox / WebFetch / MCP), the file and scope, the evidence and
  the fix. A finding can be **PARTIAL** when one of two required layers is in place but the other
  is inert (e.g. `denyRead` set while the sandbox cannot run). Profile-accepted exceptions are
  listed in a separate ACCEPTED block, never as gaps.

### Checks

**Must (v1)**
1. **Credential paths denied on both layers** — `permissions.deny` Read rules **and**
   `sandbox.filesystem.denyRead` for a fixed reference list: `~/.ssh`, `~/.aws`, `~/.config/gh`,
   `~/.npmrc`, `~/.docker/config.json`, `~/.kube`, `~/.netrc`, `~/.config/gcloud`, `.env*`,
   `.envrc`. Deny always, whether the path exists or not.
2. **Bypass mode disabled** — `permissions.disableBypassPermissionsMode: "disable"`. Accepted
   exception in the `container` profile. However: **container + bypass + sandbox unable to run +
   credential paths present** is a HIGH finding (only deny rules remain and they do not stop
   subprocess reads); fix hint: do not mount credentials, or get the sandbox running.
3. **Broad Bash allows** — a rule is broad when it allows an interpreter, shell, network tool,
   package manager or command wrapper (`python*`, `node`, `sh`, `bash`, `zsh`, `curl`, `wget`,
   `pip|npm|brew install`, `uv run`, `npx`, `env`, `bash -c`, `git:*`, `gh api:*`, …) with any
   arguments. `Bash(git:*)` is broad; `Bash(git status)` is not. The list is a data file shipped
   with the skill, extended by editing that file (no user-side override in v1).
4. **Sandbox on and fail-closed** — `sandbox.enabled`, dependencies present and the trial run
   passing, `allowUnsandboxedCommands: false`, `failIfUnavailable: true`. Setup offers the
   last two only after a passing trial run, so Claude Code can never fail to start. Never
   `enableWeakerNestedSandbox`.
5. **WebFetch scoped** — WebFetch limited to `WebFetch(domain:…)` rules, and no allow for
   `curl`/`wget` that bypasses the domain list.
6. **MCP approvals named** — no `enableAllProjectMcpServers`; project servers approved by name.
   Setup only offers to replace `enableAllProjectMcpServers` with named approvals of the
   currently approved servers, shown in the diff. It never builds an `allowedMcpServers` list
   from what is enabled now (that would silently grandfather a bad server); an unset allowlist is
   a finding without an automatic fix.

**Should**
7. `permissions.blockReadsOutsideWorkingDirectories: true`.
8. `sandbox.network.allowedDomains` set.
9. `sandbox.excludedCommands` reviewed — each is an unsandboxed hole. Entries that git-setup's
   template installs are recognised by reading that template (single source) and reported as
   accepted. When tcs-git-helpers is not installed, they are ordinary findings.

**Could**
10. Allow-list hygiene — one-off and stale rules (e.g. skills that no longer exist).

**Won't (this phase)** — writing managed-only keys or managed files; `sandbox.credentials` mask
(needs experimental `tlsTerminate`).

### Setup

- Plan built from the audit: one diff per target file. Each broad allow rule is a separate
  removal choice; nothing is narrowed or rewritten.
- **Default target per fix:** credential denies, bypass and sandbox keys → user settings;
  broad-allow removals and hygiene → the file the rule lives in; project (committed) settings only
  when the user picks it in the diff.
- Nothing written without an explicit yes after the diff ("silence is not consent").
- Writes are atomic with a backup stored **outside the repo**; additive; a second run proposes
  nothing.
- A value that differs from the baseline (e.g. `allowUnsandboxedCommands: true` set on purpose) is
  flagged in the diff and never overwritten unless the user selects it.
- Version guard: a key is proposed only when the installed Claude Code version supports it
  (e.g. `blockReadsOutsideWorkingDirectories` ≥ 2.1.257). The file is re-parsed after each
  write.
- `.claude/settings.json` is sandbox-protected: the CLI detects a protected target and the apply
  step runs outside the sandbox (git-setup precedent). git-setup's sandbox rules stay intact;
  `allowUnsandboxedCommands` governs only the `dangerouslyDisableSandbox` retry, not
  `excludedCommands`.
- Never writes managed settings.

### Testing

- pytest over fixture settings trees for each profile (host, native Linux, container), covering
  effective-value computation, each check, plan generation and idempotency.
- A manual container check script (git-setup `tests/manual` precedent) for what fixtures cannot
  prove: Claude Code still starts after setup, YOLO still works, a real bwrap trial run.

## Success criteria

- After setup on the macOS host and in the container, a re-audit shows **zero HIGH findings**
  apart from profile-accepted exceptions. The "container + bypass + no sandbox + credential paths
  present" finding (check 2) is **not** an accepted exception: the container passes only once
  credentials are not mounted or the sandbox runs. Findings the audit cannot see (a `--settings`
  layer) are outside this criterion and named in the caveat.
- **Nothing breaks**: Claude Code still starts in both environments, YOLO container mode still
  works, git-setup's sandbox rules stay intact.
- **Idempotent**: a second setup run proposes no changes; no settings file is ever written without
  a shown diff and an explicit yes.

## Parking lot (not v1)

- SessionStart drift advisory.
- Managed-settings templates for teams (baseline vs locked tiers) → record in `declined.md` with a
  reopen condition.
- `sandbox.credentials` masking.
- Suggesting narrower replacements for broad allow rules.
- Rollout across the active MiYo repos.
- Re-audit prompt after `/fewer-permission-prompts`.
