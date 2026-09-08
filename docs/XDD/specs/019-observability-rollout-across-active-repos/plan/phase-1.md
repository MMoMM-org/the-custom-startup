---
title: "Phase 1: The bundle and its versioning"
status: completed
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

**Dependencies**: none within this spec, but one outside it — **the observability scripts must be
published in a released `tcs-helper` version before setup can run against a repository other than
this one.** Until then they exist only in this repository's working tree and there is nothing for
the installer to copy. Phases 1 to 3 can be built and tested before that; T4.2's rollout cannot.

---

## Tasks

Establishes an installable, versioned copy of the recorder's scripts, and the ability to tell when
an installed copy has fallen behind.

- [x] **T1.1 The bundle source of truth and its version marker** `[activity: backend-api]`

  1. Prime: read the spec-012 pattern's definition of a version marker and where it lives
     `[ref: SDD/ADR-3]`; read `plugins/tcs-git-helpers/templates/githooks/tcs-git-helpers-version`
     as the canonical example.
  2. Test: the marker file exists, contains a single `h<N>` bundle-version line and nothing else (same convention as `tcs-git-helpers-version`, deliberately not the plugin semver); a helper reads it
     and returns that version; a malformed or absent marker yields a clear error rather than an
     empty string that later compares equal to everything.
  3. Implement: `plugins/tcs-helper/templates/observability/tcs-helper-observability-version`, plus the
     read helper. The bundle's *sources* stay where they are — this task adds the version, not a
     copy of the scripts.
  4. Validate: `bats` green; the marker's format matches the existing git-helpers marker exactly, so
     one convention covers both.
  5. Success: a version exists that a drift check can compare against `[ref: SDD/ADR-3]`

- [x] **T1.2 Bundle installation into `$HOME/.claude/observability/`** `[activity: backend-api]`

  1. Prime: read `plugins/tcs-git-helpers/skills/git-setup/lib/install_files.sh:104-141` for the
     copy-and-substitute pattern and `:130-132` for the atomic marker write `[ref: SDD/ADR-2]`.
     Note the **source**: `../../scripts/observability/` relative to this skill's own base
     directory, which the harness names on load. Not `$CLAUDE_PLUGIN_ROOT`, which does not reach
     a Bash-tool subprocess — the mistake spec-018's ADR-1 exists to prevent.
  2. Test: installing into an empty home creates the directory, every adapter plus `logwrite.sh`,
     and the version marker; the copied adapters run correctly *from their new location* (this is
     the test that actually exercises the `${BASH_SOURCE[0]}` self-location, and it is the one that
     would catch a bundle that copies the adapters but forgets the writer they source); installing
     twice at the same version changes nothing; installing over an older version replaces the
     scripts and updates the marker; the marker is written atomically — run the installer with the
     marker write replaced by a failing stub and assert no marker claims a version that is not on
     disk. Naming the injection point matters: the same property stated abstractly in an earlier
     draft would have been tested three different ways by three developers.
     **Test seam, pinned 2026-09-08.** The clause above names *what* to inject but not *how*, and a
     TDD gate blocked the task for exactly that. Maintainer ruling: the marker write is performed by
     `_write_bundle_marker <version> <marker_path>` in `bundle_install.sh`, which writes
     `<marker_path>.tmp` and `mv`s it into place. Tests inject failure by sourcing the lib and
     redefining that function to `return 1` — **not** by shimming `mv` on `PATH` (which would hit
     every other move in the installer and stop isolating the seam), and **not** by `trap` (which
     tests interruption, a different property). Assert both: install exits non-zero, and no marker
     file exists on disk.

     **Idempotence assertion:** compare `sha256` sums of every file in the bundle tree before and
     after a second same-version install. Not mtimes (sub-second granularity is unreliable) and not
     inodes (copy-and-replace changes them legitimately). The upgrade case in the same step is what
     keeps this honest: an installer that no-ops on *every* second run passes idempotence and fails
     the upgrade.

     **Adapter execution:** the "runs correctly from their new location" case must execute a copied
     adapter and read back the record it wrote, matching step 4. An exit-code-only assertion would
     still pass with `logwrite.sh` absent, which is the exact bundle defect this case exists to
     catch.

  3. Implement: `plugins/tcs-helper/skills/observability-setup/lib/bundle_install.sh`
  4. Validate: `bats` green, including a case that executes a copied adapter end-to-end and reads
     back the record it wrote.
  5. Success: `[ref: SDD/SDD-AC-8]`; `[ref: SDD/ADR-2]`

- [x] **T1.3 Drift detection against the plugin's current version** `[activity: backend-api]`
      `[parallel: true]`

  1. Prime: read `plugins/tcs-git-helpers/scripts/lib/drift_check.sh:25-41` — the generic
     `OK` / `MISSING` / `DRIFT:` comparator this should reuse rather than reimplement
     `[ref: SDD/ADR-3]` `[ref: PRD/F5]`.
  2. Test: an installed bundle matching the marker reports `OK`; an older installed version reports
     drift naming both versions; no bundle at all reports `MISSING` and is distinguished from drift;
     the check never writes anything.

     **Pinned 2026-09-08 after a TDD gate blocked this task.** Three things the wording above left
     open, each of which two developers would have resolved differently:

     - **A malformed installed marker reports `DRIFT:<raw content>`** (maintainer ruling). The
       mirrored comparator accepts anything (`head -n 1 | tr -d '[:space:]'`), while T1.1's
       `_read_observability_bundle_version` *rejects* malformed markers with exit 1 — the two are
       inconsistent and an implementer would silently pick one. Faithful mirroring wins: garbage is
       not the expected version, so `DRIFT:` is truthful and the remedy (reinstall) is identical to
       the stale case. T1.1's strictness existed so a broken marker could never compare *equal* to
       the expected version; `DRIFT:` never compares equal, so that hazard does not arise here. The
       contract stays exactly three states. Assert this case explicitly, so it reads as a decision
       rather than an oversight.
     - **The read-only assertion must exercise a read path.** Running the check against a
       write-protected directory containing *no* marker only proves the `MISSING` branch does not
       write — the branch that opens no file at all. The write-protected case must contain a *valid*
       marker and assert a successful `OK` (or `DRIFT:`) result, so the branch that actually reads
       is the one proven not to write. Note also that a test running as root can write to a
       `chmod 555` directory regardless; the test must not silently pass in that case. Guard it
       with a write canary rather than an `EUID` check — proving the protection holds beats
       assuming that non-root implies unwritable, and it also catches a permissive filesystem
       (this repository lives on a mounted volume, where permission semantics diverge):

           if echo "canary" > "$protected_dir/test-write" 2>/dev/null; then
             skip "write-protected directory is actually writable (running as root?)"
           fi
           rm -f "$protected_dir/test-write" 
     - **Assert the output shapes, not merely that they differ.** `MISSING` carries no colon;
       `DRIFT:` is followed immediately by the installed version and nothing else. "Distinguished
       from drift" is satisfied by `MISSING:none` or `DRIFT_h1`, both wrong.
  3. Implement: **mirror the contract, not the code — corrected 2026-09-08 (maintainer ruling).**
     Step 1's "reuse rather than reimplement" cannot be satisfied as written, for two reasons found
     during implementation. First, `drift_check_hook_bundle` only *looks* generic: its signature
     takes `<repo_path> <expected_version> [<version_filename>]`, but its body hardcodes
     `${repo_path}/.githooks/${version_filename}`. It is generic over the marker's *filename* within
     `.githooks/`, not over its directory — and this bundle lives at `$HOME/.claude/observability/`,
     which has no `.githooks` segment, so no argument combination reaches our marker. Second,
     `drift_check.sh` belongs to `tcs-git-helpers` and this code to `tcs-helper`. A repository-wide
     search found **zero** cross-plugin `source` lines: all six plugins carry their own
     `.claude-plugin` manifest and are independently installable, so sourcing across the boundary
     would create the repository's first cross-plugin runtime dependency and would break
     `tcs-helper` for anyone who installs it without `tcs-git-helpers`.
     Therefore: implement the comparator in this skill's own `lib/`, reproducing the
     `OK` / `MISSING` / `DRIFT:<installed>` contract **exactly**, read-only, exit 0 always (the
     caller decides what to do). Comment it with a pointer to
     `plugins/tcs-git-helpers/scripts/lib/drift_check.sh` as the contract's source of truth, so the
     duplication is visibly deliberate rather than accidental. The contract is reused; the code is
     not.
  4. Validate: `bats` green; the check is read-only, asserted by running it against a
     write-protected directory.
  5. Success: `[ref: SDD/SDD-AC-15]` — the comparator half only; that drift reaches the `status` verb is asserted in T4.1; `[ref: PRD/F5]`

- [x] **T1.4 The CI gate on the maintainer contract** `[activity: devops]` `[parallel: true]`

  1. Prime: read `plugins/tcs-git-helpers/scripts/ci/check-hook-bundle-version.sh` and
     `.github/workflows/hook-bundle-version-check.yml` `[ref: SDD/ADR-3]`.
  2. Test: a PR touching a bundle source without bumping the marker fails; the same PR with a bump
     passes; a PR touching neither is unaffected. Test the gate's logic directly rather than through
     CI, so it is verifiable locally.
     **Gate scope, pinned 2026-09-08 (maintainer ruling).** The observability bundle's gated
     sources are the **executable scripts only** — `logwrite.sh`, `log_agent.sh`,
     `log_instructions.sh`, `log_skill.sh`, `selfcheck.sh`, `timed-wrapper.sh`. `README.md` is
     installed into the bundle (so anyone who finds `$HOME/.claude/observability/` learns what is
     recording them) but is **not** a gated source: a prose fix must not force a marker bump,
     because that would make every installed bundle report `DRIFT:` and prompt an "upgrade" that
     ships byte-identical scripts. Drift that fires on documentation trains people to ignore drift.

     **Shape difference from the git-helpers gate — read before extending it.** The existing gate
     derives its marker from its sources directory:

         readonly HOOKS_DIR="plugins/tcs-git-helpers/templates/githooks"
         readonly VERSION_FILE="${HOOKS_DIR}/tcs-git-helpers-version"

     That derivation does not hold for this bundle. Its sources live in
     `plugins/tcs-helper/scripts/observability/` while its marker lives in
     `plugins/tcs-helper/templates/observability/`. "One gate, two bundles" therefore means the gate
     takes a `(sources_dir, marker_file, [excluded_paths])` triple per bundle rather than deriving
     one path from the other. Preserve the existing bundle's behaviour exactly while generalising.

     **Pinned 2026-09-08 after a TDD gate blocked this task.**

     - **Gated sources are matched by extension under the sources directory, not by a list**
       (maintainer ruling). The existing gate already works by directory prefix — "any file under
       `templates/githooks/` changed" — not by enumerating filenames. Extend that shape: gated =
       any `*.sh` under `plugins/tcs-helper/scripts/observability/`. `README.md` is then excluded
       *by extension*, with no exclusion list to maintain, and a newly added adapter is gated the
       day it lands. So the triple above is really `(sources_dir, marker_file)` plus a glob; no
       `excluded_paths` is needed. Note this means T1.2's `_BUNDLE_INSTALL_SCRIPTS` is **not**
       consumed here — the gate needs no filename list from anywhere, and must not reach across the
       plugin boundary to get one.
     - **The glob is PER-BUNDLE, and git-helpers' pattern must stay match-everything.** Verified
       2026-09-08: 6 of the 8 files in `plugins/tcs-git-helpers/templates/githooks/` are NOT `.sh` —
       `commit-msg`, `post-merge`, `pre-commit`, `pre-push`, `exclude-paths.example` and the version
       marker itself; only `lib-bundle.sh` and `lib-config-parser.sh` carry the extension. If the
       `*.sh` filter leaked onto that bundle during generalisation, the gate would keep protecting
       two library files and silently stop protecting **every actual git hook**, while still passing
       its own tests and exiting 0 in CI. That is this spec's own failure mode aimed at the
       mechanism meant to prevent it.
     - **A regression test for the EXISTING bundle is mandatory, and must touch a non-`.sh` file.**
       Specifically: modify `plugins/tcs-git-helpers/templates/githooks/pre-commit` without bumping
       `tcs-git-helpers-version`, and assert the gate still fails. A regression test that only
       touches `lib-bundle.sh` would pass even with the filter wrongly applied, and would therefore
       prove nothing about the hazard above. Generalising a `readonly`
       constant into a per-bundle parameter is exactly where a silent regression hides. Assert that
       touching `plugins/tcs-git-helpers/templates/githooks/*` without bumping
       `tcs-git-helpers-version` still fails, and that bumping it still passes — unchanged from
       today's behaviour. This gate protects a shipped bundle; breaking it is worse than not
       extending it.
     - **The README exclusion needs its own test.** Assert that a diff touching only the
       observability bundle's `README.md` requires no marker bump. Without it the ruling above is
       unenforced and the drift-noise it prevents comes back silently.
     - **Fixture construction.** The gate reads `git diff --name-only <range>`, so tests must build
       a temporary git repository rather than depend on this repository's history. Use
       `git -C "$tmpdir"` plus `GIT_CONFIG_GLOBAL=/dev/null` — a failed `git init` in a bats fixture
       otherwise falls back to the parent `.git/` and leaks commits onto the working branch.
       Related bats trap: `! cmd` only fails a test as the body's LAST command; a non-final negation
       passes silently. Since this gate's whole purpose is asserting non-zero exits, use a helper
       that returns 1 so `set -e` fires, never a bare mid-body `!`.

  3. Implement: extend the existing check to cover the observability bundle, rather than adding a
     second workflow — one gate, two bundles.
  4. Validate: `bats` green; the gate's own failure output names which file changed and which marker
     to bump.
  5. Success: the pattern's maintainer contract is enforced mechanically, not by memory
     `[ref: SDD/ADR-3]`

- [x] **T1.5 Phase Validation** `[activity: validate]`

  - Run the full suites: `pytest -q` and `bats plugins/*/tests/bats`.
  - **Run the new bats suite under `/bin/bash` explicitly** — CON-1 requires bash 3.2 and this
    repository has no `BASH_VERSINFO` guard anywhere; the `macos-latest` CI leg is the only gate,
    and its two failure modes (`\s`/`\b` in `[[ =~ ]]`, bounded `^.{m,n}$`) match nothing
    *silently* rather than erroring, so an unchecked CON-1 fails open.
  - Verify a copied adapter, run from `$HOME/.claude/observability/`, writes a record readable by
    `report.py`.
  - Confirm no file in this phase writes to any target repository — phase 1 touches only this
    repository and the installing user's home.

---

## Phase Acceptance Criteria

- The bundle installs, upgrades and reports drift, and an installed adapter works from its new home.
- The CI gate fails a bundle change with no version bump.
- Nothing in this phase reads or writes a target repository's configuration.
