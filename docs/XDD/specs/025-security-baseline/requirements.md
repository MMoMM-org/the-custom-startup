---
title: "security-baseline — audit and set up a Claude Code security baseline"
status: approved
version: "1.0"
---

# Product Requirements Document

## Validation Checklist

### CRITICAL GATES (Must Pass)

- [x] All required sections are complete
- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Problem statement is specific and measurable
- [x] Every feature has testable acceptance criteria (Gherkin format)
- [x] No contradictions between sections

### QUALITY CHECKS (Should Pass)

- [x] Problem is validated by evidence (not assumptions)
- [x] Context → Problem → Solution flow makes sense
- [x] Every persona has at least one user journey
- [x] All MoSCoW categories addressed (Must/Should/Could/Won't)
- [x] Every metric has corresponding tracking events
- [x] No feature redundancy (check for duplicates)
- [x] No technical implementation details included
- [x] A new team member could understand this PRD

---

## Output Schema

### PRD Status Report

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| specId | string | Yes | Spec identifier (NNN-name format) |
| title | string | Yes | Feature title |
| status | enum: `DRAFT`, `IN_REVIEW`, `COMPLETE` | Yes | Document readiness |
| sections | SectionStatus[] | Yes | Status of each PRD section |
| clarificationsRemaining | number | Yes | Count of `[NEEDS CLARIFICATION]` markers |
| acceptanceCriteria | number | Yes | Total testable acceptance criteria defined |
| openQuestions | string[] | No | Unresolved items requiring stakeholder input |

### SectionStatus

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| name | string | Yes | Section name |
| status | enum: `COMPLETE`, `NEEDS_CLARIFICATION`, `IN_PROGRESS` | Yes | Current state |
| detail | string | No | What clarification is needed or what's in progress |

---

## Product Overview

### Vision
A solo developer can tell, in one command, whether Claude Code on this machine can read their
credentials, run arbitrary code without a prompt, or reach the network unchecked — and close
each gap with a reviewed change that never breaks their working setup.

### Problem Statement
Claude Code's security posture is decided by up to five settings layers (managed, command-line
`--settings`, local, project, user) whose lists merge and whose single values override each
other. Each protection layer has blind spots: a Read deny rule does not stop a subprocess from
reading the file, the sandbox's read deny does not stop the Read tool, and the sandbox does not
cover web fetches or MCP tools. A manual review therefore easily believes a hole is closed when
it is not.

Evidence — an inventory of this repository's development container on 2026-11-27 (Claude Code
2.1.330) found **six of six** baseline items unmet:

1. sandbox not enabled, and its Linux dependencies missing;
2. no Read deny for `~/.ssh`, `~/.aws`, `~/.config/gh` or `.env*` in any layer;
3. bypass-permissions mode not disabled anywhere;
4. 18 broad allow rules, including `Bash(python3:*)`, `Bash(curl:*)`, `Bash(git:*)`,
   `Bash(gh api:*)` and package-manager installs;
5. no MCP server allow or deny lists;
6. web fetches limited to four domains, but bypassable through the `Bash(curl:*)` allow.

Broad allows accumulate without review: `/fewer-permission-prompts` and "always allow" answers
add them one at a time. Nothing in the TCS ecosystem reports this today, so the gaps persist
until something leaks.

### Value Proposition
- **One honest answer** — the audit reports the effective result across every layer it can
  read, including where a fix in one file is overridden by another, and marks protections that
  are only half in place.
- **Safe to run** — audit never writes; setup never writes without a shown diff and an explicit
  yes, and never makes Claude Code fail to start.
- **Fits how the developer works** — it knows the difference between the macOS host and a
  per-repo container running in YOLO mode, so it does not flag a deliberate choice as a gap or
  propose a change that breaks it.

## User Personas

### Primary Persona: Host developer
- **Demographics:** Solo developer, senior technical expertise, works on a macOS host with
  several repositories and Claude Code plugins installed.
- **Goals:** Credentials and machine-wide secrets out of the agent's reach; no permission
  prompts beyond what is necessary; confidence that a settings change will not break the next
  session.
- **Pain Points:** Settings spread across several files whose interaction is hard to reason
  about; allow rules added in a hurry and never revisited; no way to tell whether a protection
  actually takes effect.

### Secondary Personas

#### Container developer
- **Demographics:** The same person working inside a per-repo Linux development container with
  its own home directory, often launched in YOLO mode (`--dangerously-skip-permissions`) through
  an entrypoint that also passes `--settings`.
- **Goals:** Keep YOLO mode for speed while knowing exactly what still protects the container;
  never have a baseline change stop the container from starting.
- **Pain Points:** The sandbox often cannot run in the container; a host-oriented baseline would
  disable the YOLO workflow; credentials may be mounted into the container without anyone
  noticing.

## User Journey Maps

### Primary User Journey: Harden the host
1. **Awareness:** The developer reads a security guide, or notices a broad allow rule, and
   wonders what Claude Code can reach on this machine.
2. **Consideration:** Alternatives are a manual read of four settings files against the docs,
   or asking Claude ad hoc; both miss layer interactions and leave no repeatable result.
3. **Adoption:** The skill is already installed with tcs-helper; the audit is read-only, so
   trying it costs nothing.
4. **Usage:** Runs `audit` → reads the ranked gap list → runs `setup` → reviews one diff per
   file, choosing which broad allow rules to remove → answers yes → re-runs `audit` and sees no
   HIGH findings.
5. **Retention:** Re-runs the audit after adding allow rules, installing an MCP server, or
   upgrading Claude Code; a second setup run proposing nothing confirms nothing has drifted.

### Secondary User Journeys

#### Harden a YOLO container
1. **Awareness:** The developer wants to know what still protects a container that runs with
   bypass mode.
2. **Consideration:** Turning YOLO off is not acceptable; ignoring the question is not either.
3. **Adoption:** The audit detects the container profile on its own.
4. **Usage:** Runs `audit` → sees bypass listed as an accepted exception, a caveat that the
   entrypoint's `--settings` layer is not audited, and — if the sandbox cannot run and
   credentials are mounted — a HIGH finding with the two ways to close it → runs `setup` for
   the remaining fixes → the container still starts and YOLO still works.
5. **Retention:** Re-audits when the container image or its mounts change.

#### Recover from a declined or failed setup
1. **Awareness:** The developer answers no to a diff, or a write cannot complete (e.g. the
   target file is protected by the sandbox).
2. **Usage:** Nothing is written for a declined diff; for a protected target the developer is
   told the apply step must run outside the sandbox; an interrupted write leaves the original
   file intact and a backup outside the repository.
3. **Retention:** Re-running setup picks up exactly the changes that were not applied.

## Feature Requirements

### Must Have Features

#### Feature 1: Read-only audit report
- **User Story:** As a host or container developer, I want one command that reports every
  security gap in the settings that apply here, ranked by severity, so that I know what to fix
  first without reading the docs myself.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] Given settings in managed, user, project and local files, When the developer runs
    `audit`, Then each finding shows check, severity (HIGH/MED/LOW), protection layer, file and
    scope, evidence, and fix
  - [ ] Given any state, When `audit` runs, Then no file is created, changed or deleted
  - [ ] Given a value fixed in one file but overridden by a higher-precedence file, When `audit`
    runs, Then the finding names both files and reports the effective value
  - [ ] Given a check that needs two protection layers and only one takes effect, When `audit`
    runs, Then the finding is reported as PARTIAL, not as passed
  - [ ] Given a settings file that is not valid JSON, When `audit` runs, Then that file is
    named as unreadable and the remaining files are still audited
  - [ ] Given no gaps, When `audit` runs, Then it reports that the baseline is met

#### Feature 2: Environment profiles
- **User Story:** As a container developer, I want the audit to recognise where it runs, so
  that deliberate choices such as YOLO mode are reported as accepted exceptions rather than
  gaps.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] Given a macOS machine, When `audit` runs, Then the profile is reported as `macos-host`
  - [ ] Given a Linux machine without container markers, When `audit` runs, Then the profile is
    `linux-native`
  - [ ] Given a container, When `audit` runs, Then the profile is `container`, bypass mode is
    listed in a separate ACCEPTED block, and a caveat states that a `--settings` layer may
    exist and is not audited
  - [ ] Given any machine, When the developer passes `--profile <name>`, Then that profile is
    used and the report says it was set explicitly

#### Feature 3: Credential paths unreadable (check 1)
- **User Story:** As a developer, I want my credential files denied to both the file tools and
  sandboxed commands, so that neither the agent nor a script it runs can read them.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] Given no deny for a path on the credential list, When `audit` runs, Then a HIGH finding
    names each missing path
  - [ ] Given file-tool denies but no sandbox read deny (or the reverse), When `audit` runs,
    Then the finding is PARTIAL and names the missing layer
  - [ ] Given both denies but a sandbox that cannot run, When `audit` runs, Then the finding is
    PARTIAL and says the sandbox half has no effect
  - [ ] Given a credential path that does not exist on this machine, When `audit` runs, Then a
    missing deny is still reported

#### Feature 4: Bypass mode disabled (check 2)
- **User Story:** As a host developer, I want bypass-permissions mode disabled, so that no
  session can silently skip every permission check.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] Given a non-container profile and bypass mode not disabled, When `audit` runs, Then a
    HIGH finding is reported
  - [ ] Given the `container` profile, When `setup` runs, Then it never proposes disabling
    bypass mode
  - [ ] Given the `container` profile, bypass mode enabled, the sandbox unable to run and a
    credential path present, When `audit` runs, Then a HIGH finding is reported with the fixes
    "do not mount credentials" and "make the sandbox run"

#### Feature 5: Broad allow rules (check 3)
- **User Story:** As a developer, I want allow rules that let the agent run any interpreter,
  shell, network tool, package manager or command wrapper without a prompt flagged, so that I
  can remove the ones I did not mean to grant.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] Given `Bash(python3:*)`, `Bash(curl:*)` or `Bash(git:*)` in any file, When `audit`
    runs, Then each is a HIGH finding naming the file it lives in
  - [ ] Given `Bash(git status)`, When `audit` runs, Then it is not flagged as broad
  - [ ] Given a wrapper such as `Bash(npx:*)` or `Bash(env:*)`, When `audit` runs, Then it is
    flagged as broad

#### Feature 6: Sandbox on and fail-closed (check 4)
- **User Story:** As a developer, I want the sandbox enabled and refusing to fall back to
  unsandboxed execution, so that every shell command is contained — but only where the sandbox
  can actually run.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] Given the sandbox not enabled, When `audit` runs, Then a HIGH finding is reported
  - [ ] Given Linux with the sandbox's dependencies missing, When `audit` runs, Then the finding
    names the missing dependencies and how to install them
  - [ ] Given dependencies present but a trial run of the sandbox failing, When `audit` runs,
    Then the finding says the sandbox cannot run here, not that it is ready
  - [ ] Given a failing trial run, When `setup` runs, Then it does not propose `sandbox.enabled`,
    `failIfUnavailable` or `allowUnsandboxedCommands: false`
  - [ ] Given any state, When `setup` runs, Then it never proposes `enableWeakerNestedSandbox`

#### Feature 7: Web fetch scoped (check 5)
- **User Story:** As a developer, I want web fetches limited to named domains with no shell
  route around them, so that the agent cannot send data to an arbitrary host.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] Given web fetches allowed without a domain restriction, When `audit` runs, Then a HIGH
    finding is reported
  - [ ] Given domain-scoped web fetch rules and `Bash(curl:*)` allowed, When `audit` runs, Then
    the finding is PARTIAL and names the bypassing rule

#### Feature 8: MCP approvals by name (check 6)
- **User Story:** As a developer, I want project MCP servers approved by name instead of all at
  once, so that a newly added server cannot start without my approval.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] Given `enableAllProjectMcpServers` on, When `audit` runs, Then a HIGH finding lists the
    servers it currently approves
  - [ ] Given that finding, When `setup` runs, Then it proposes replacing the setting with named
    approvals for exactly those servers
  - [ ] Given no MCP server allowlist, When `setup` runs, Then the gap is reported but no
    allowlist is proposed
  - [ ] Given MCP servers from the project, user configuration and plugins, When `audit` runs,
    Then all are listed with their source

#### Feature 9: Reviewed setup
- **User Story:** As a developer, I want each proposed fix shown as a diff per file with
  choices I can decline one by one, so that nothing changes my settings without my consent.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] Given open findings, When `setup` runs, Then one diff per target file is shown before
    anything is written
  - [ ] Given the shown diffs, When the developer does not answer an explicit yes, Then nothing
    is written
  - [ ] Given several broad allow rules, When `setup` runs, Then each is a separate removal
    choice and none is rewritten or narrowed
  - [ ] Given a fix for credentials, bypass or sandbox, When `setup` proposes it, Then the
    default target is the user settings file; given a broad-allow removal, the target is the
    file the rule lives in
  - [ ] Given a proposed fix, When the developer picks the committed project file as its target,
    Then setup writes it there; it never writes there unless picked
  - [ ] Given a value set deliberately to differ from the baseline, When `setup` runs, Then it is
    flagged in the diff and kept unless the developer selects it
  - [ ] Given an approved write, When it completes, Then a backup of the previous file exists
    outside the repository and the written file is valid
  - [ ] Given a completed setup, When `setup` runs again, Then it proposes no changes
  - [ ] Given a target protected by the sandbox, When the developer approves, Then the
    developer is told the apply step runs outside the sandbox and nothing is half-written
  - [ ] Given a key the installed Claude Code version does not support, When `setup` runs, Then
    it is not proposed and the audit says which version is needed
  - [ ] Given any state, When `setup` runs, Then it never writes a managed settings file

### Should Have Features

#### Feature 10: Hardening extras (checks 7–9)
- **User Story:** As a developer who has met the Must checks, I want the remaining hardening
  options reported, so that I can tighten further where it costs me nothing.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] Given reads outside the working directories not blocked, When `audit` runs, Then a MED
    finding is reported
  - [ ] Given the sandbox enabled with no network domain list, When `audit` runs, Then a MED
    finding is reported
  - [ ] Given commands excluded from the sandbox, When `audit` runs, Then each is listed as a MED
    finding, except entries installed by tcs-git-helpers' own template, which are listed as
    accepted
  - [ ] Given tcs-git-helpers is not installed, When `audit` runs, Then every excluded command is
    an ordinary finding

### Could Have Features

#### Feature 11: Allow-list hygiene (check 10)
- **User Story:** As a developer, I want one-off and stale allow rules listed, so that I can
  prune rules that only accumulated.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] Given an allow rule for a skill that is no longer installed, When `audit` runs, Then it
    is a LOW finding
  - [ ] Given those findings, When `setup` runs, Then each stale rule is a separate removal
    choice

### Won't Have (This Phase)
- Writing managed settings or managed-only keys, and managed-settings templates for teams
  (baseline vs locked tiers).
- Auditing the `--settings` command-line layer.
- Credential masking through the sandbox proxy (depends on an experimental option).
- Suggesting narrower replacements for broad allow rules.
- A session-start drift advisory, or a re-audit prompt after `/fewer-permission-prompts`.
- Rolling the baseline out across other repositories.
- A user-side override of the credential or broad-command lists.

## Detailed Feature Specifications

### Feature: Reviewed setup
**Description:** Setup turns the audit's findings into proposed changes, groups them per target
file, shows them, and writes only what the developer approves. It is the only part of the skill
that writes.

**User Flow:**
1. Developer runs `setup` (optionally with a path and `--profile`).
2. System runs the audit, then lists the proposed changes per target file as a diff, with each
   broad or stale allow rule as its own choice and deliberately differing values flagged.
3. Developer selects or deselects choices, may move a fix to another target file, and answers
   yes or no.
4. System writes each approved file with a backup first, confirms the result, and reports what
   was written and what was skipped.
5. Developer re-runs `audit` to confirm.

**Business Rules:**
- Rule 1: No write without an explicit yes given after the diff is shown. Silence, an earlier
  "go ahead", or an agent's report is not consent.
- Rule 2: Only additions and selected removals; values are never narrowed or rewritten.
- Rule 3: Never write managed settings; never write the committed project file unless the
  developer picks it.
- Rule 4: In the `container` profile, never propose disabling bypass mode.
- Rule 5: Never propose sandbox enablement or fail-closed options unless a trial run of the
  sandbox passed; never propose the weaker nested sandbox.
- Rule 6: Never build an MCP server allowlist from the servers currently enabled.
- Rule 7: Never propose a key the installed Claude Code version does not support.
- Rule 8: Leave the rules tcs-git-helpers installed intact.

**Edge Cases:**
- Target file missing → Expected: created with only the approved keys.
- Target file is not valid JSON → Expected: no write to it; reported; other files proceed.
- Target protected by the sandbox → Expected: developer told to run the apply step outside the
  sandbox; no partial write.
- Write interrupted → Expected: original file intact; backup present.
- Developer moves a fix to another file → Expected: the diff is regenerated for both files
  before the yes.
- Two findings target the same key in the same file → Expected: one change in the diff.

## Success Metrics

### Key Performance Indicators

- **Adoption:** The audit has been run on the macOS host and in at least one development
  container within two weeks of release.
- **Engagement:** The audit is re-run after each settings change that adds allow rules or MCP
  servers; a second setup run proposes nothing.
- **Quality:** After setup, a re-audit shows **zero HIGH findings** on the host and in the
  container, apart from profile-accepted exceptions. The "container + bypass + no sandbox +
  credentials present" finding is not an accepted exception. Zero sessions broken by a setup
  write: Claude Code starts in both environments, YOLO mode still works, tcs-git-helpers' rules
  are intact.
- **Business Impact:** The six baseline gaps found on 2026-11-27 are closed or explicitly
  accepted on the developer's machines.

### Tracking Requirements

| Event | Properties | Purpose |
|-------|------------|---------|
| Skill invoked | mode (audit/setup), profile, explicit-profile flag | Adoption and engagement (recorded by the existing observability hooks where installed) |
| Audit completed | count of findings per severity, count of PARTIAL, count of ACCEPTED | Quality KPI: zero HIGH after setup |
| Setup diff shown | target files, number of proposed changes per file | Proposal volume; idempotency (zero on re-run) |
| Setup answered | yes/no, changes selected vs proposed | Consent and declined-change rate |
| Setup write completed | file, backup written, result valid | Zero broken writes |

---

## Constraints and Assumptions

### Constraints
- Solo developer scope: no team distribution, no managed settings writes.
- Must work on the macOS host and in Linux development containers; tcs-helper tests run on
  ubuntu and macOS CI.
- Shell code must stay compatible with bash 3.2 (macOS default).
- The committed project settings file is protected by the sandbox, so writing it needs a step
  outside the sandbox.
- Setting names and minimum versions follow the official Claude Code documentation as of
  2026-11-27 (Claude Code 2.1.330); several keys need a minimum version (e.g. blocking reads
  outside the working directories needs 2.1.257).

### Assumptions
- The developer reads the diff before answering yes.
- Container detection markers (`/.dockerenv`, `/run/.containerenv`, `CONTAINERIZED`) are present
  in the development containers; `--profile` covers the cases where they are not.
- Each development container has its own home directory per repository, so user-scope writes in
  a container affect only that repository's container.
- tcs-git-helpers' settings template remains the single source for the rules it installs.

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| A setup write stops Claude Code from starting (sandbox fail-closed where it cannot run) | High | Medium | Fail-closed options only after a passing trial run; manual container check before release |
| Claude Code renames or removes a setting | Medium | Medium | Version guard; setting names held in one reference list, checked against the docs at each release |
| "Zero HIGH" reads as safe while the unaudited `--settings` layer overrides fixes | High | Low | Explicit caveat in the container profile; success metric excludes what cannot be seen |
| Broad-allow findings are noisy (e.g. `Bash(git:*)`) and get ignored | Medium | Medium | Per-rule removal choices; narrowing suggestions parked for a follow-up |
| Removing an allow rule raises prompt volume and frustrates the developer | Low | High | Each removal is opt-in; nothing removed by default |
| A write corrupts a settings file | High | Low | Backup outside the repository before each write; result validated after the write |

## Open Questions

- [x] Solo or team scope? → Solo first; managed templates deferred (Decisions Log, 2026-11-27).
- [x] Container interaction? → Profile-aware; bypass accepted in the container profile, with the
  credential-exposure exception rated HIGH.
- [x] Sandbox on Linux? → Proposed only after a passing trial run; never the weaker nested
  sandbox.
- [x] Default write targets? → User settings; local or wherever the rule lives for removals;
  project only when picked.

No open questions remain.

---

## Supporting Research

### Competitive Analysis
No existing tool covers this inside the TCS ecosystem. Claude Code's `/fewer-permission-prompts`
works in the opposite direction (it broadens allow rules). Claude Code's own docs give a managed
settings example and recommend combining permissions with the sandbox, but provide no audit.
tcs-git-helpers' `git-setup` writes sandbox rules for git and is the precedent for a reviewed,
diff-first settings write; `observability-setup` and `patterns-setup` are the precedents for a
plan-then-confirm setup flow.

### User Research
Inventory of the developer's container on 2026-11-27: six of six baseline items unmet (see
Problem Statement); 76 allow rules in the local settings file, about 25 of them one-off and
several for skills that no longer exist; security hooks present only in the container home and
only for shell commands. The developer's decisions on scope, profiles, sandbox handling, write
targets, report shape, broad-allow handling, cadence and success are recorded in the spec
README Decisions Log and in `docs/XDD/ideas/2026-11-27-security-baseline.md`.

### Market Data
Source of the baseline items: an enterprise guide to securing coding agents, chapters 4
(permissions, sandboxing) and 5 (policy table, baseline vs locked). Setting semantics verified
against the official Claude Code documentation (settings, permissions, sandboxing, managed
settings, MCP pages) on 2026-11-27.
