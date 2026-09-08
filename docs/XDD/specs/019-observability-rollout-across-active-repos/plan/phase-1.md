---
title: "Phase 1: The bundle and its versioning"
status: pending
version: "1.0"
phase: 1
---

# Phase 1: The bundle and its versioning

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/ADR-2]` — the bundle lives at `$HOME/.claude/observability/`, referenced by `$HOME`
- `[ref: SDD/ADR-3]` — bundle versioning rather than an absolute path into this repository
- `[ref: SDD/Building Block View — Bundle installer]`
- `[ref: PRD/F1]`, `[ref: PRD/F5]`
- `docs/XDD/specs/012-tcs-git-helpers-hook-runtime-contract/solution.md` — the pattern's own ADRs

**Key Decisions**:
- The bundle path is expressed as `$HOME/.claude/observability/`, never as an absolute path. Inside
  a container `$HOME` is the repository's gitignored docker home; on the host it is the real home.
  One expression, both shapes — the same trick spec-018 found for the record locations.
- **Verified, not assumed (2026-09-08)**: `$HOME` expands inside a hook command string, and `$0`
  inside the invoked script resolves to the fully expanded path. A throwaway hook registered as
  `"$HOME/…/probe.sh"` fired and recorded its own `$0`. If this had been false the whole design
  would collapse, so it was measured before the design was written down.
- The adapters are already relocatable: each resolves its own directory from `${BASH_SOURCE[0]}` and
  sources `logwrite.sh` relative to itself, never via an environment variable
  (`log_instructions.sh:38`). Copying them elsewhere is therefore safe by construction, and this is
  the property the whole bundle approach rests on.

**Dependencies**: none. This phase is the foundation for phase 2 and can start immediately.

---

## Tasks

Establishes an installable, versioned copy of the recorder's scripts, and the ability to tell when
an installed copy has fallen behind.

- [ ] **T1.1 The bundle source of truth and its version marker** `[activity: backend-api]`

  1. Prime: read the spec-012 pattern's definition of a version marker and where it lives
     `[ref: SDD/ADR-3]`; read `plugins/tcs-git-helpers/templates/githooks/tcs-git-helpers-version`
     as the canonical example.
  2. Test: the marker file exists, contains a single semver line and nothing else; a helper reads it
     and returns that version; a malformed or absent marker yields a clear error rather than an
     empty string that later compares equal to everything.
  3. Implement: `plugins/tcs-helper/templates/observability/tcs-observability-version`, plus the
     read helper. The bundle's *sources* stay where they are — this task adds the version, not a
     copy of the scripts.
  4. Validate: `bats` green; the marker's format matches the existing git-helpers marker exactly, so
     one convention covers both.
  5. Success: a version exists that a drift check can compare against `[ref: SDD/ADR-3]`

- [ ] **T1.2 Bundle installation into `$HOME/.claude/observability/`** `[activity: backend-api]`

  1. Prime: read `plugins/tcs-git-helpers/scripts/lib/install_files.sh:104-141` for the
     copy-and-substitute pattern and `:130-132` for the atomic marker write `[ref: SDD/ADR-2]`.
  2. Test: installing into an empty home creates the directory, every adapter plus `logwrite.sh`,
     and the version marker; the copied adapters run correctly *from their new location* (this is
     the test that actually exercises the `${BASH_SOURCE[0]}` self-location, and it is the one that
     would catch a bundle that copies the adapters but forgets the writer they source); installing
     twice at the same version changes nothing; installing over an older version replaces the
     scripts and updates the marker; the marker is written atomically, so an interrupted install
     never leaves a marker claiming a version that is not on disk.
  3. Implement: `plugins/tcs-helper/skills/observability-setup/lib/bundle_install.sh`
  4. Validate: `bats` green, including a case that executes a copied adapter end-to-end and reads
     back the record it wrote.
  5. Success: `[ref: SDD/SDD-AC-8]`; `[ref: SDD/ADR-2]`

- [ ] **T1.3 Drift detection against the plugin's current version** `[activity: backend-api]`
      `[parallel: true]`

  1. Prime: read `plugins/tcs-git-helpers/scripts/lib/drift_check.sh:25-41` — the generic
     `OK` / `MISSING` / `DRIFT:` comparator this should reuse rather than reimplement
     `[ref: SDD/ADR-3]` `[ref: PRD/F5]`.
  2. Test: an installed bundle matching the marker reports `OK`; an older installed version reports
     drift naming both versions; no bundle at all reports `MISSING` and is distinguished from drift;
     the check never writes anything.
  3. Implement: reuse the existing comparator; add only what is specific to this bundle.
  4. Validate: `bats` green; the check is read-only, asserted by running it against a
     write-protected directory.
  5. Success: `[ref: SDD/SDD-AC-15]` — the comparator half only; that drift reaches the `status` verb is asserted in T4.1; `[ref: PRD/F5]`

- [ ] **T1.4 The CI gate on the maintainer contract** `[activity: devops]` `[parallel: true]`

  1. Prime: read `plugins/tcs-git-helpers/scripts/ci/check-hook-bundle-version.sh` and
     `.github/workflows/hook-bundle-version-check.yml` `[ref: SDD/ADR-3]`.
  2. Test: a PR touching a bundle source without bumping the marker fails; the same PR with a bump
     passes; a PR touching neither is unaffected. Test the gate's logic directly rather than through
     CI, so it is verifiable locally.
  3. Implement: extend the existing check to cover the observability bundle, rather than adding a
     second workflow — one gate, two bundles.
  4. Validate: `bats` green; the gate's own failure output names which file changed and which marker
     to bump.
  5. Success: the pattern's maintainer contract is enforced mechanically, not by memory
     `[ref: SDD/ADR-3]`

- [ ] **T1.5 Phase Validation** `[activity: validate]`

  - Run the full suites: `pytest -q` and `bats plugins/*/tests/bats`.
  - Verify a copied adapter, run from `$HOME/.claude/observability/`, writes a record readable by
    `report.py`.
  - Confirm no file in this phase writes to any target repository — phase 1 touches only this
    repository and the installing user's home.

---

## Phase Acceptance Criteria

- The bundle installs, upgrades and reports drift, and an installed adapter works from its new home.
- The CI gate fails a bundle change with no version bump.
- Nothing in this phase reads or writes a target repository's configuration.
