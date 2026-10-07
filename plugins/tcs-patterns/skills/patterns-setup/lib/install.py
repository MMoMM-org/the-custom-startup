"""The tcs-patterns installer (spec-020 T3.3, component C5).

`install(repo_dir, names, *, catalogue_dir) -> InstallReport` writes the
patterns named in `names` into `<repo_dir>/.claude/skills/tcs-<name>/`, each
renamed to its prefixed form in the installed `SKILL.md`'s frontmatter
(ADR-1), with every `tcs-patterns:<catalogue pattern>` marker in the copied
UTF-8 files rewritten to `tcs-<pattern>` (`rewrite_pattern_refs`, ADR-1's
2026-10-07 amendment), and records each write in the manifest (C6). **This module assumes
every name it is given has already cleared the collision guard (C4) --
it never imports `guard` and never rescans the three namespaces itself**
`[ref: docs/XDD/specs/020-tcs-patterns-selective-install/solution.md,
"Data model: the install plan and report (C5)", point 1]`. C4 and C5 are
deliberately separate components so a refusal is testable without any write
happening; the caller (C3, not yet built) runs `check()`, takes
`GuardReport.approved`, and passes those names here. AC-10 is satisfied by
C4 and C5 *together* and by neither alone.

```
install(repo_dir, names, *, catalogue_dir, bundle) -> InstallReport

InstallReport (frozen, named channels)
    installed:  name -> (installed_as, version, sha256)   newly written
    unchanged:  name -> (installed_as, version, sha256)   already current
    failed:     name -> reason                            raised internally, caught, skipped
    committed:  always False
```

**No `report_only` parameter.** An earlier revision of this signature
carried one, defined nowhere, and it was removed rather than given
semantics -- nothing in `[ref: PRD/F4]` asks for a dry run, and the proposal
a user sees before an install is C3's, not a rehearsal of this function
`[ref: solution.md, "No report_only parameter"]`.

**Who raises, and who catches.** `InstallError` is raised by
`rename_in_frontmatter`, by the catalogue reads around it, and -- wrapped --
by a failing `manifest.upsert()` call too (the directory has already landed
by the time that call happens; see point 3). `install()` catches
`InstallError` **per pattern**, records `failed[name] = reason`, and
continues to the next name -- a fault in one pattern never escapes this
function, which is what makes "a write failing mid-selection leaves earlier
patterns in place" true at all
`[ref: solution.md, "Who raises, and who catches"]`.

**Idempotency is content, decided by a hash of the INSTALLED file, not the
catalogue's.** For each requested name: if `tcs-<name>/` is absent, it is
written and reported under `installed`. If present, and the manifest's
entry has `version == catalogue VERSION` *and* `sha256 ==
sha256(installed SKILL.md)`, nothing is touched and it is reported under
`unchanged`. If present and anything else -- stale, locally edited, or the
manifest has no entry for it at all -- **nothing is touched either**; it is
reported under `failed` with a reason naming `update` as the path forward.
**`install()` is purely additive. It never removes or overwrites anything
under `tcs-<name>/`** -- that is `update()`'s job (see its own section
below), and every F8 acceptance criterion is phrased in terms of what
`update` does, not `install`
`[ref: solution.md, "install() is purely additive. It never removes or
overwrites anything under tcs-<name>/"]`. The one directory this function
*may* remove is its own leftover `.tcs-<name>.tmp/` from a crashed earlier
run -- never a user's installed pattern.

**Each pattern appears atomically.** A fresh install copies the catalogue
directory into `<repo_dir>/.claude/skills/.tcs-<name>.tmp/` -- inside the
destination, never under `$TMPDIR` -- rewrites the frontmatter there, then
`os.rename`s it into place. The temp directory must share a filesystem with
its destination for the rename to be atomic; the catalogue and a consumer
repository need not share one with each other, and a copy may cross
filesystems freely where a rename may not
`[ref: SDD/Risks and Technical Debt/Implementation Gotchas]`.

**The manifest is upserted per pattern, after that pattern's directory
lands** -- directory first, so a crash between the two leaves recoverable
debris (files with no record) rather than a lie (a record with no files)
`[ref: solution.md, point 3]`.

**C5 reports; C3 offers.** `InstallReport.committed` is always `False`.
Stating "nothing was committed" and offering to commit is C3's rendering of
this report (ADR-8) -- no `AskUserQuestion` belongs in this module, and no
test here should look for a prompt.

**`catalogue_dir` is a parameter**, defaulting to this plugin's own
`templates/patterns/` directory, derived from `__file__` rather than
`CLAUDE_PLUGIN_ROOT` -- measured, that variable is `None` in a Bash-tool
subprocess, which is exactly where this module runs
`[ref: solution.md, point 5]`. It is a parameter for the same reason
`home_dir` is one on `guard.check()`: a test that cannot point it at a
fixture cannot test it.

**`bundle` is also a parameter**, added after T3.3's first review round
found the signature had no legal way to call `manifest.upsert()` (`bundle`
is required there, with no default). This plugin's own `plugin.json`
version is kept as the default, but a caller may override it
`[ref: solution.md, point 7]`: it is otherwise the one input to `install()`
a test cannot drive, and CI bumps `plugin.json` on every merge, which would
make any test asserting the manifest's `bundle` field against the real
file break on a version bump rather than on an actual regression.
**Resolved lazily, `if bundle is None`, inside `install()` -- never as a
module-level constant.** A second review round found that a module-level
`DEFAULT_BUNDLE_VERSION = _bundle_version()` reads `plugin.json` at IMPORT
time, which made this module impossible to import from a copy (a mutation
harness using `importlib.util.spec_from_file_location` against a scratch
copy, as `manifest.py`, `guard.py` and `detect.py` all already support).
The catalogue default, `paths.DEFAULT_CATALOGUE_DIR`, stays a module-level
constant because it is a path expression with no I/O -- wrong when loaded
from a copy, but never fatal; only the file read needed to move. It lives in
`paths.py` with the plugin root and the debris suffixes, the leaf this module
and the read-only `status.py` share (T5.1a); this module no longer re-exports
it under a name of its own.

---

**`update()` -- C5's second verb (T3.4).** The only component that may
replace a user's file, and only with consent. The deliberate asymmetry
against `install()` above.

```
update(repo_dir, *, catalogue_dir, bundle, decide=_decline) -> UpdateReport

UpdateReport (frozen, named channels)
    refreshed:  name -> (installed_as, version_before, version_after, sha256)
    declined:   name -> (version, unified_diff)           diverged, decide() said no
    current:    name -> (installed_as, version, sha256)   nothing to do
    failed:     name -> reason                            raised internally, caught, skipped
    committed:  always False

decide(name, unified_diff) -> bool                        defaults to False
```

**No `names` parameter.** F8's first criterion is "no scan, no questions"
`[ref: PRD/F8 1st]`, so `update()` may not re-derive a selection: the
manifest is its only input about what to act on
`[ref: solution.md, "Data model: the update path (C5's second verb)",
decision 1]`. That is the sharpest difference from `install()`, which is
handed a list someone else chose.

**Three states per installed pattern, and only one of them asks**
`[ref: decision 2]`:

| manifest `version` vs catalogue `VERSION` | installed hash vs manifest `sha256` | `update()` does |
|---|---|---|
| equal | equal | nothing; reports `current` |
| **behind** | equal | **refreshes without asking** -- nothing local can be lost |
| any | **differs** | diffs, calls `decide`; `True` refreshes, `False` reports `declined` |

The middle row is the one worth stating, because "ask before replacing" read
naively would ask there too -- and a prompt that interrupts for a change the
user cannot have made is how a prompt becomes noise that gets clicked
through. The hash is what buys the distinction and the whole reason ADR-4
records one.

**`decide` defaults to declining** (`_decline`), which is where ADR-4's "an
unanswered prompt cannot destroy local work" actually lives: in this module,
reachable by a test, rather than in C3's prose `[ref: decision 3]`. No
`AskUserQuestion` belongs here any more than it does in `install()` -- C3
supplies a `decide` that prompts.

**The diff's direction and labels are normative; its context width is not**
`[ref: decision 4]`. See `_divergence_diff`.

**ADR-4's stated limit is accepted here, not worked around.** The hash
covers `SKILL.md` only, so a locally edited `reference/` file never reaches
the row where consent is asked -- it stays in the middle row and is replaced
without a prompt `[ref: decision 6; SDD/ADR-4, "Trade-offs accepted"]`. That
is a limit on *detection* only: once a refresh happens, by either route, the
**whole subtree** is replaced `reference/` included, because a half-applied
update is not an outcome anything asked for.

**Two different `failed` rows, and the reasons are not interchangeable.** A
pattern the catalogue no longer carries is `failed` with **nothing touched**
-- it is not stale, refreshing from a source that no longer exists is
impossible, and deleting would destroy a working skill the user still has
`[ref: decision 7]`. A manifest entry whose *installed* directory is missing
is also `failed` -- the record claims a pattern is installed and it is not,
which is a different problem from being out of date, and naming it tells the
user to reach for `install` `[ref: decision 8]`. Checked catalogue-side
first, so each reports its own cause: when **both** sides are absent the
catalogue reason wins, because "run install" is advice that cannot succeed
against a catalogue with nothing to copy `[ref: decision 7, "When both sides
are absent"]`.

**Either `failed` reason names a `.<installed_as>.replaced` stash when the
directory is absent and one is sitting there.** On the catalogue-absent path
that stash holds the only copy of the content *anywhere* -- the user's edits
and the pattern itself, which the catalogue no longer has -- so the reason
names it and drops the "left exactly as it is" clause, which is false once
the directory is gone `[ref: decision 7, "And when a .replaced stash is ALSO
present"]`. The precedence is unchanged: the catalogue cause stays the
headline, because "the pattern is gone upstream" is still the actionable
fact.

**On the missing-directory path the reason names the stash instead of
`install`.** That stash is
how `_replace_subtree` holds the user's copy while the replacement lands, so
one sitting there means a refresh was killed between its two renames and the
user's own edits are in it, unreferenced by anything. `update()` does not
move it back -- an unrequested restore is exactly what ADR-4 forbids this
verb from doing -- but it says where the copy is, which turns a silent trap
into a decision `[ref: decision 8, "Unless a .replaced stash"]`.

Both clauses are gated on the directory being **absent**, and the asymmetry
is deliberate rather than an oversight. A kill *after* the new directory
lands leaves `dest` present with a stash beside it; `_replace_subtree`
deletes a pre-existing stash before refreshing, so that debris has a known
expiry and nothing is at risk either way. The directory-absent state is the
one that cannot heal, precisely because the cleanup site is unreachable once
these guards fire `[ref: decision 8, "Only the directory-ABSENT state needs
this, because the other stash state heals itself"]`.

Every other write-safety rule carries over unchanged: the refreshed
directory appears via a temp directory inside `<repo>/.claude/skills/`, the
manifest is upserted per pattern after that pattern's directory lands, and a
fault in one pattern is caught into `failed` without escaping `update()`
`[ref: decision 5]`.

Stdlib only, Python 3.11 floor `[ref: SDD/Architecture Decisions/ADR-2]`.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import os
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

import manifest
import paths


class InstallError(Exception):
    """One pattern could not be installed. Raised by `rename_in_frontmatter`
    and by the catalogue/manifest reads in `_install_one`; caught per
    pattern inside `install()` and never allowed to escape it."""


@dataclass(frozen=True)
class InstallReport:
    """The whole result of one `install()` call. Named channels, not a
    tuple, for the same reason `guard.GuardReport` is -- three maps of
    different shapes make an unpacked-wrong return stay silently wrong.

    installed: name -> (installed_as, version, sha256), newly written.
    unchanged: name -> (installed_as, version, sha256), already current.
    failed:    name -> a human-readable reason, nothing written for it.
    committed: always False -- see the module docstring, "C5 reports; C3 offers".
    """

    installed: dict[str, tuple[str, str, str]] = field(default_factory=dict)
    unchanged: dict[str, tuple[str, str, str]] = field(default_factory=dict)
    failed: dict[str, str] = field(default_factory=dict)
    committed: bool = False


def rename_in_frontmatter(text: str, new_name: str) -> str:
    """Rewrite the first `name:` line inside `text`'s frontmatter block to
    `new_name`, leaving everything else -- including everything below the
    block -- byte-identical. Raises `InstallError` rather than guessing
    whenever the rewrite cannot be done safely.

    The corrected sample from `solution.md`'s Implementation Examples,
    verified there against 15 inputs -- see that section for why each of
    the three corrections below exists
    `[ref: solution.md, "The name rewrite (ADR-1 against CON-4)"]`.
    """
    if not re.match(r"^---\r?\n", text):
        raise InstallError("SKILL.md does not open with a frontmatter block")
    m = re.search(r"(?m)^---[ \t]*\r?$", text[4:])
    if m is None:
        raise InstallError("SKILL.md frontmatter block never closes")
    end = 4 + m.start()
    head, body = text[:end], text[end:]
    # Reject a `name:` this rewriter cannot safely replace, rather than
    # replacing its first line and orphaning the rest.
    value = re.search(r"(?m)^name:(.*)$", head)
    if value is None or not value.group(1).strip():
        raise InstallError("no `name:` line in frontmatter; refusing to install unprefixed")
    if value.group(1).strip()[0] in ">|!&*%":
        raise InstallError("`name:` is not a plain scalar; refusing to rewrite it")
    # `.` does not match \n but DOES match \r, so `^name:.*$` spans the
    # carriage return on a CRLF file and the replacement silently drops it
    # -- measured, a 5-line CRLF input came out with 4 CRLF lines and 1 bare
    # LF line. Mixed line endings in a file this tool generates is a
    # defect, not a contract guarantee. Fourth correction to this sample,
    # found by this task's own implementer; `[^\r\n]*` excludes both line
    # terminator characters from the match, so the original line's ending
    # survives untouched
    # `[ref: solution.md, "The rewrite preserves every line ending,
    # including the one it rewrites"]`.
    patched, count = re.subn(r"(?m)^name:[^\r\n]*", "name: " + new_name, head, count=1)
    if count != 1:  # unreachable given the checks above; kept as a tripwire
        raise InstallError("no `name:` line in frontmatter; refusing to install unprefixed")
    return patched + body


# This plugin's own skills. They are still plugin skills after 2.0, so a
# `tcs-patterns:<one of these>` marker resolves as written and is never
# rewritten -- excluded by name, so a catalogue directory of the same name
# could not redirect it `[ref: solution.md, ADR-1, "Amended 2026-10-07"]`.
PLUGIN_SKILL_NAMES = frozenset({"patterns-setup", "pattern"})

_PATTERN_REF_RE = re.compile(r"tcs-patterns:([A-Za-z0-9_-]+)")


def catalogue_names(catalogue_dir: Path) -> frozenset[str]:
    """Every pattern directory directly under `catalogue_dir`, hidden
    entries excluded -- the same set `companions._pattern_names` reads."""
    return frozenset(p.name for p in Path(catalogue_dir).iterdir() if p.is_dir() and not p.name.startswith("."))


def rewrite_pattern_refs(text: str, names) -> str:
    """Rewrite each `tcs-patterns:<name>` marker to `tcs-<name>` when `<name>`
    -- the maximal `[A-Za-z0-9_-]` run after the colon -- is in `names` and
    is not one of `PLUGIN_SKILL_NAMES`. Every other byte is left alone.

    After 2.0 the plugin address names nothing: an installed pattern is the
    repository skill `tcs-<name>` (ADR-1). The ONE function both the copy
    path and `_catalogue_as_installed` use, so the installed file and the
    text a divergence diff compares it against cannot disagree
    `[ref: solution.md, ADR-1, "Amended 2026-10-07"]`."""
    rewritable = frozenset(names) - PLUGIN_SKILL_NAMES

    def replace(m: re.Match) -> str:
        return f"tcs-{m.group(1)}" if m.group(1) in rewritable else m.group(0)

    return _PATTERN_REF_RE.sub(replace, text)


def _skill_md_as_installed(text: str, installed_as: str, names) -> str:
    """A catalogue `SKILL.md` as installed: frontmatter renamed, markers
    rewritten. Shared by `_fresh_install` and `_catalogue_as_installed`."""
    return rewrite_pattern_refs(rename_in_frontmatter(text, installed_as), names)


def _rewrite_copied_text_files(root: Path, names) -> None:
    """Apply `rewrite_pattern_refs` to every file under `root` except
    `SKILL.md` (rewritten by its caller together with the rename). A file
    whose bytes are not strict UTF-8 is left byte-for-byte as copied; one
    with no marker is not rewritten at all."""
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or not path.is_file() or path == root / "SKILL.md":
            continue
        try:
            text = path.read_bytes().decode("utf-8")
        except UnicodeDecodeError:
            continue
        except OSError as e:
            raise InstallError(f"could not read {path}: {e}") from e
        rewritten = rewrite_pattern_refs(text, names)
        if rewritten != text:
            path.write_bytes(rewritten.encode("utf-8"))


def _bundle_version() -> str:
    """The installed plugin's own version, for the manifest's top-level
    `bundle` field ("the plugin version that produced this selection")
    `[ref: solution.md, Data model: the manifest (C6)]`. Derived from this
    plugin's own `plugin.json` (`paths.PLUGIN_JSON`), the same
    `__file__`-relative derivation `paths.DEFAULT_CATALOGUE_DIR` uses --
    `install()`'s fallback when `bundle` is
    omitted, not the only route to a value `[ref: solution.md, point 7]`.

    **Called lazily, from inside `install()`, never at module import.**
    `paths.DEFAULT_CATALOGUE_DIR` is a path expression with no I/O, so it is safe
    as a module-level constant even when loaded from a copy whose `parents[3]`
    resolves to nowhere real -- the value would be wrong there, but nothing
    raises. A `plugin.json` *read*, unlike a path expression, is fatal: a
    module-level `DEFAULT_BUNDLE_VERSION = _bundle_version()` made `install.py`
    impossible to import from anywhere but its installed location, breaking
    the `importlib.util.spec_from_file_location`-on-a-copy technique
    `manifest.py`, `guard.py` and `detect.py` all support. `bundle` is one
    field in one manifest; a missing or malformed `plugin.json` should
    surface when the value is actually needed, not prevent the module from
    loading at all.
    """
    data = json.loads(paths.PLUGIN_JSON.read_text(encoding="utf-8"))
    return str(data["version"])


def _read_catalogue_version(catalogue_dir: Path, name: str) -> str:
    try:
        return (catalogue_dir / name / "VERSION").read_text(encoding="utf-8").strip()
    except OSError as e:
        raise InstallError(f"could not read VERSION for catalogue pattern {name!r}: {e}") from e


def _fresh_install(name: str, *, installed_as: str, dest: Path, skills_root: Path, catalogue_dir: Path) -> str:
    """Copy `catalogue_dir/name` into `dest` atomically, rewriting the
    frontmatter along the way. Returns the installed `SKILL.md`'s sha256.

    The temp directory is created INSIDE `skills_root` -- never under
    `$TMPDIR` -- so the final `os.rename` is always a same-filesystem
    rename `[ref: solution.md, point 3]`. Any leftover temp directory from
    an earlier crashed attempt at this same pattern is removed before this
    attempt starts, and the temp directory this attempt creates is removed
    on any failure too -- both are this installer's own debris, never a
    user's installed pattern `[ref: solution.md, point 6]`.
    """
    source = catalogue_dir / name
    tmp_dir = skills_root / f".{installed_as}{paths.TMP_SUFFIX}"

    skills_root.mkdir(parents=True, exist_ok=True)
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)

    try:
        try:
            shutil.copytree(source, tmp_dir)
        except OSError as e:
            raise InstallError(f"could not read catalogue pattern {name!r}: {e}") from e

        skill_md = tmp_dir / "SKILL.md"
        try:
            raw = skill_md.read_bytes()
        except OSError as e:
            raise InstallError(f"catalogue pattern {name!r} has no readable SKILL.md: {e}") from e

        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as e:
            raise InstallError(f"catalogue pattern {name!r} has a SKILL.md that is not valid UTF-8: {e}") from e

        names = catalogue_names(catalogue_dir)
        patched = _skill_md_as_installed(text, installed_as, names).encode("utf-8")
        skill_md.write_bytes(patched)
        _rewrite_copied_text_files(tmp_dir, names)

        os.rename(str(tmp_dir), str(dest))
        return hashlib.sha256(patched).hexdigest()
    except BaseException:
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir, ignore_errors=True)
        raise


@dataclass(frozen=True)
class _Outcome:
    changed: bool
    installed_as: str
    version: str
    sha256: str


def _install_one(
    name: str,
    *,
    repo_dir: Path,
    skills_root: Path,
    catalogue_dir: Path,
    manifest_before: "manifest.Manifest",
    bundle: str,
) -> _Outcome:
    installed_as = f"tcs-{name}"
    dest = skills_root / installed_as
    catalogue_version = _read_catalogue_version(catalogue_dir, name)

    if dest.is_dir():
        entry = manifest_before.patterns.get(name)
        installed_hash = paths.sha256_or_none(dest / "SKILL.md")
        if (
            entry is not None
            and manifest.is_current(entry, catalogue_version)
            and installed_hash is not None
            and installed_hash == entry.sha256
        ):
            return _Outcome(
                changed=False, installed_as=entry.installed_as, version=entry.version, sha256=entry.sha256
            )
        # Present, and anything else -- stale, locally edited, or never
        # recorded at all. `install()` never overwrites it; `update()`
        # (T3.4) is where that question belongs.
        raise InstallError(f"{installed_as!r} is already installed and not current; run update to refresh it")

    sha256 = _fresh_install(name, installed_as=installed_as, dest=dest, skills_root=skills_root, catalogue_dir=catalogue_dir)
    # Directory already landed above -- this is the "then manifest" half of
    # "directory first, then manifest" (point 3). Any failure here (a
    # corrupt pre-existing manifest, or anything else `manifest.upsert`
    # raises) must still be a PER-PATTERN fault, not one that escapes
    # `install()`: the directory stays on disk, uncatalogued, and the next
    # `install()` call simply retries this pattern. Wrapped rather than left
    # to propagate, because "a per-pattern fault never escapes install()" is
    # the contract for every step, not only the frontmatter rewrite.
    try:
        manifest.upsert(
            repo_dir,
            name,
            version=catalogue_version,
            installed_as=installed_as,
            sha256=sha256,
            bundle=bundle,
        )
    except Exception as e:
        raise InstallError(f"{installed_as!r} installed but manifest update failed: {e}") from e
    return _Outcome(changed=True, installed_as=installed_as, version=catalogue_version, sha256=sha256)


def install(
    repo_dir: Path,
    names,
    *,
    catalogue_dir: Path = paths.DEFAULT_CATALOGUE_DIR,
    bundle: str | None = None,
) -> InstallReport:
    """Install `names` (already cleared by `guard.check()`) into
    `<repo_dir>/.claude/skills/`. See the module docstring for the full
    contract. Never rescans the three namespaces; never raises for a fault
    in a single pattern -- see `failed`.

    `bundle` defaults to this plugin's own `plugin.json` version, but is a
    parameter -- like `catalogue_dir` -- because it is otherwise the one
    input a test cannot drive, and because CI bumps `plugin.json` on merge,
    which would make a test asserting the manifest's `bundle` field against
    the real file break on every version bump `[ref: solution.md, point 7]`.

    The default is resolved HERE, lazily, with `bundle is None` -- never as
    a module-level `_bundle_version()` call -- because that read must not
    happen at import time. See `_bundle_version`'s own docstring for why.
    """
    repo_dir = Path(repo_dir)
    catalogue_dir = Path(catalogue_dir)
    skills_root = repo_dir / ".claude" / "skills"
    if bundle is None:
        bundle = _bundle_version()

    manifest_before = manifest.read(repo_dir)

    installed: dict[str, tuple[str, str, str]] = {}
    unchanged: dict[str, tuple[str, str, str]] = {}
    failed: dict[str, str] = {}

    for name in names:
        try:
            outcome = _install_one(
                name,
                repo_dir=repo_dir,
                skills_root=skills_root,
                catalogue_dir=catalogue_dir,
                manifest_before=manifest_before,
                bundle=bundle,
            )
        except InstallError as e:
            failed[name] = str(e)
            continue

        channel = installed if outcome.changed else unchanged
        channel[name] = (outcome.installed_as, outcome.version, outcome.sha256)

    return InstallReport(installed=installed, unchanged=unchanged, failed=failed)


# =============================================================================
# `update()` -- C5's second verb (T3.4)
# =============================================================================


def _decline(name: str, unified_diff: str) -> bool:
    """The default `decide`. Declines, always.

    This is where ADR-4's "an unanswered prompt cannot destroy local work"
    actually lives. Making the default a decliner puts that guarantee in
    this module, where a mutation test can reach it, instead of in C3's
    prose where nothing can check it
    `[ref: solution.md, "Data model: the update path (C5's second verb)",
    decision 3]`. Both parameters are deliberately unused -- a real `decide`
    needs them, and the signature is the contract.
    """
    return False


@dataclass(frozen=True)
class UpdateReport:
    """The whole result of one `update()` call. Four named channels, same
    reason `InstallReport` has three.

    refreshed: name -> (installed_as, version_before, version_after, sha256)
    declined:  name -> (version, unified_diff), diverged and `decide` said no
    current:   name -> (installed_as, version, sha256), nothing to do
    failed:    name -> a human-readable reason, nothing written for it
    committed: always False -- see "C5 reports; C3 offers" above.

    `declined` carries the diff because that value is what a later advisory
    shows the user `[ref: SDD/Runtime View/Primary Flow, step 9]`, so it is
    part of this report's external surface rather than an internal detail
    of the prompt that already happened.
    """

    refreshed: dict[str, tuple[str, str, str, str]] = field(default_factory=dict)
    declined: dict[str, tuple[str, str]] = field(default_factory=dict)
    current: dict[str, tuple[str, str, str]] = field(default_factory=dict)
    failed: dict[str, str] = field(default_factory=dict)
    committed: bool = False


def _read_text_or_raise(path: Path, *, what: str) -> str:
    try:
        return path.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as e:
        raise InstallError(f"could not read {what} at {path}: {e}") from e


def _catalogue_as_installed(catalogue_dir: Path, name: str, installed_as: str) -> str:
    """The catalogue's `SKILL.md` as it would appear once installed -- that
    is, after the frontmatter rename.

    Both the diff's `to` side and the refreshed file's content come from
    here, so the file the user is shown and the file they would get are the
    same text by construction. Doing the rename before diffing is also what
    keeps the `name:` line out of the diff: without it, every diverged
    pattern reports a spurious `name:` difference the user cannot act on
    `[ref: solution.md, decision 4]`.

    The `tcs-patterns:<name>` markers are rewritten here too, through the
    same `_skill_md_as_installed` the copy uses: without it every marker
    line would show in every divergence diff as an edit the user never made
    `[ref: solution.md, ADR-1, "Amended 2026-10-07"]`.
    """
    return _skill_md_as_installed(
        _read_text_or_raise(catalogue_dir / name / "SKILL.md", what=f"catalogue SKILL.md for {name!r}"),
        installed_as,
        catalogue_names(catalogue_dir),
    )


def _divergence_diff(installed_text: str, catalogue_text: str) -> str:
    """The unified diff the user decides on.

    **Direction and labels are the contract; the context width `n` is not**
    `[ref: solution.md, decision 4]`. The installed file is the `from` side,
    so the user's own edit appears as a deletion and the incoming upstream
    text as an addition -- reversing it produces a diff that is well-formed,
    contains the same two lines, and tells the user their own work is the
    change being introduced, in the one prompt where that reading decides
    whether their file survives. The two labels are populated because
    `difflib` defaults both to the empty string, which renders the header as
    a bare `---`/`+++` and leaves the user to infer which side is theirs.
    `n` is left at `difflib`'s default on purpose: it changes the output's
    length without changing what the diff means, so it is presentation, and
    no test may assert it.
    """
    return "".join(
        difflib.unified_diff(
            installed_text.splitlines(keepends=True),
            catalogue_text.splitlines(keepends=True),
            fromfile="installed",
            tofile="catalogue",
        )
    )


def _stash_path(skills_root: Path, installed_as: str) -> Path:
    """Where `_replace_subtree` moves a pattern's current directory while
    the replacement lands.

    One function rather than the expression written twice, because the
    second reader of it is `_update_one`'s missing-directory branch, which
    has to recognise a stash left by a hard kill in order to name it
    `[ref: solution.md, decision 8, "Unless a .replaced stash"]`. Two
    copies of the name would let that branch drift into looking for a
    directory nothing creates.
    """
    return skills_root / f".{installed_as}{paths.REPLACED_SUFFIX}"


def _replace_subtree(
    name: str, *, installed_as: str, dest: Path, skills_root: Path, catalogue_dir: Path
) -> str:
    """Replace `dest` wholesale with the catalogue's version of `name`.
    Returns the refreshed `SKILL.md`'s sha256.

    **The WHOLE subtree, `reference/` included.** The hash covering
    `SKILL.md` only is a limit on *detection*, never on *replacement*: once
    the refresh is approved (or is unconditional), leaving a stale
    `reference/` file behind would be a half-applied update
    `[ref: solution.md, decision 6; SDD/ADR-4]`. Implemented by delegating
    the copy to `_fresh_install`, which is also why the frontmatter rename,
    the temp-directory-inside-the-destination rule and the hash are shared
    with `install()` rather than reimplemented here.

    `_fresh_install` renames its temp directory onto a destination that must
    not exist, so the current directory is first moved aside to
    `.<installed_as>.replaced` and only deleted once the new one has landed.
    If anything fails in between, the user's directory is moved back. Like
    `.<installed_as>.tmp`, that stash is this installer's own debris and is
    the only directory removed here `[ref: solution.md, decision 5]`.
    """
    stash = _stash_path(skills_root, installed_as)
    if stash.exists():
        shutil.rmtree(stash)
    os.rename(str(dest), str(stash))
    try:
        sha256 = _fresh_install(
            name, installed_as=installed_as, dest=dest, skills_root=skills_root, catalogue_dir=catalogue_dir
        )
    except BaseException:
        if not dest.exists():
            os.rename(str(stash), str(dest))
        raise
    shutil.rmtree(stash, ignore_errors=True)
    return sha256


@dataclass(frozen=True)
class _UpdateOutcome:
    channel: str  # "refreshed" | "declined" | "current"
    installed_as: str
    version_before: str
    version_after: str
    sha256: str
    unified_diff: str


def _update_one(
    name: str,
    *,
    repo_dir: Path,
    skills_root: Path,
    catalogue_dir: Path,
    entry: "manifest.PatternEntry",
    bundle: str,
    decide,
) -> _UpdateOutcome:
    installed_as = entry.installed_as
    dest = skills_root / installed_as

    # The catalogue side first, because a pattern the catalogue has dropped
    # must report THAT rather than whatever the installed side happens to
    # look like -- the two `failed` reasons are not interchangeable
    # `[ref: solution.md, decision 7]`.
    if not (catalogue_dir / name).is_dir():
        # Three independent failures can co-occur here: upstream dropped
        # the pattern, a prior refresh was hard-killed, and the manifest
        # still records it. Then the stash holds the ONLY copy of the
        # content anywhere -- the user's edits and the pattern itself,
        # which the catalogue no longer has, so unlike decision 8's case
        # `install` has no source to recreate it from. Naming it is not
        # optional, and the "left as it is" clause has to go: the directory
        # it describes does not exist `[ref: solution.md, decision 7, "And
        # when a .replaced stash is ALSO present"]`.
        #
        # Gated on `dest` being ABSENT. With the directory present the
        # clause is TRUE, and a stash there is debris that costs the user
        # nothing, so naming it would raise an alarm about a state where
        # `dest` holds a working pattern `[ref: decision 8, "Only the
        # directory-ABSENT state needs this"]`.
        stash = _stash_path(skills_root, installed_as)
        if not dest.is_dir() and stash.is_dir():
            raise InstallError(
                f"the catalogue no longer carries pattern {name!r}, and an interrupted refresh "
                f"left the only copy of it at {stash} -- the catalogue cannot recreate it"
            )
        raise InstallError(
            f"the catalogue no longer carries pattern {name!r}; "
            f"{installed_as!r} was left exactly as it is"
        )
    catalogue_version = _read_catalogue_version(catalogue_dir, name)

    if not dest.is_dir():
        # A stash beside the absent directory means a refresh was killed
        # between its two renames, so the user's own copy -- edits included
        # -- is the ONLY copy and sits somewhere nothing names. Say where it
        # is, and do NOT name `install`: following that advice writes a
        # fresh copy and orphans their work for good. Nothing is moved back
        # -- an unrequested restore is what ADR-4 forbids this verb from
        # doing, and naming the stash turns a silent trap into a decision
        # the user can make `[ref: solution.md, decision 8, "Unless a
        # .replaced stash"]`.
        stash = _stash_path(skills_root, installed_as)
        if stash.is_dir():
            raise InstallError(
                f"the manifest records {name!r} as installed at {installed_as!r} but that "
                f"directory is missing; an interrupted refresh left your copy at {stash}, "
                "which has been left exactly as it is"
            )
        raise InstallError(
            f"the manifest records {name!r} as installed at {installed_as!r} but that directory "
            "is missing; run install to write it"
        )
    installed_hash = paths.sha256_or_none(dest / "SKILL.md")
    if installed_hash is None:
        raise InstallError(f"{installed_as!r} has no readable SKILL.md; run install to rewrite it")

    if installed_hash == entry.sha256:
        # Not diverged. Either current, or behind with nothing local to
        # lose -- and the second case refreshes WITHOUT asking, because a
        # prompt the user cannot have caused is noise that gets clicked
        # through `[ref: solution.md, decision 2, middle row]`.
        if manifest.is_current(entry, catalogue_version):
            return _UpdateOutcome(
                channel="current",
                installed_as=installed_as,
                version_before=entry.version,
                version_after=entry.version,
                sha256=entry.sha256,
                unified_diff="",
            )
        diff = ""
    else:
        # Diverged. The version comparison does not enter into it: the
        # third row of the table is "any" version with a differing hash.
        diff = _divergence_diff(
            _read_text_or_raise(dest / "SKILL.md", what=f"installed SKILL.md for {installed_as!r}"),
            _catalogue_as_installed(catalogue_dir, name, installed_as),
        )
        if not decide(name, diff):
            return _UpdateOutcome(
                channel="declined",
                installed_as=installed_as,
                version_before=entry.version,
                version_after=entry.version,
                sha256=entry.sha256,
                unified_diff=diff,
            )

    sha256 = _replace_subtree(
        name, installed_as=installed_as, dest=dest, skills_root=skills_root, catalogue_dir=catalogue_dir
    )
    # Directory first, then manifest -- the same order and the same
    # per-pattern wrapping as `_install_one`, for the same reason: a crash
    # between the two must leave recoverable debris rather than a lie.
    try:
        manifest.upsert(
            repo_dir,
            name,
            version=catalogue_version,
            installed_as=installed_as,
            sha256=sha256,
            bundle=bundle,
        )
    except Exception as e:
        raise InstallError(f"{installed_as!r} refreshed but manifest update failed: {e}") from e
    return _UpdateOutcome(
        channel="refreshed",
        installed_as=installed_as,
        version_before=entry.version,
        version_after=catalogue_version,
        sha256=sha256,
        unified_diff=diff,
    )


def update(
    repo_dir: Path,
    *,
    catalogue_dir: Path = paths.DEFAULT_CATALOGUE_DIR,
    bundle: str | None = None,
    decide=_decline,
) -> UpdateReport:
    """Refresh every pattern the manifest records. See the module docstring's
    `update()` section for the full contract.

    **There is no `names` parameter, and that is a requirement rather than
    an omission.** F8's first criterion is "only those patterns are
    refreshed and the selection is otherwise unchanged -- no scan, no
    questions" `[ref: PRD/F8 1st]`, so `update()` is not allowed to
    re-derive a selection: the manifest is its only input about what to act
    on `[ref: solution.md, decision 1]`. A catalogue pattern the manifest
    does not record is not touched and appears in no channel.

    `decide(name, unified_diff) -> bool` is asked once per DIVERGED pattern
    and nothing else -- never for a pattern that is current, and never for
    one that is merely behind. It **defaults to declining**; see `_decline`.
    """
    repo_dir = Path(repo_dir)
    catalogue_dir = Path(catalogue_dir)
    skills_root = repo_dir / ".claude" / "skills"
    if bundle is None:
        bundle = _bundle_version()

    # Read once, up front: `version_before` must be the version as recorded
    # before this call, and `manifest.upsert` rewrites the file per pattern.
    manifest_before = manifest.read(repo_dir)

    refreshed: dict[str, tuple[str, str, str, str]] = {}
    declined: dict[str, tuple[str, str]] = {}
    current: dict[str, tuple[str, str, str]] = {}
    failed: dict[str, str] = {}

    for name in sorted(manifest_before.patterns):
        entry = manifest_before.patterns[name]
        try:
            outcome = _update_one(
                name,
                repo_dir=repo_dir,
                skills_root=skills_root,
                catalogue_dir=catalogue_dir,
                entry=entry,
                bundle=bundle,
                decide=decide,
            )
        except InstallError as e:
            failed[name] = str(e)
            continue

        if outcome.channel == "refreshed":
            refreshed[name] = (
                outcome.installed_as,
                outcome.version_before,
                outcome.version_after,
                outcome.sha256,
            )
        elif outcome.channel == "declined":
            declined[name] = (outcome.version_before, outcome.unified_diff)
        else:
            current[name] = (outcome.installed_as, outcome.version_before, outcome.sha256)

    return UpdateReport(refreshed=refreshed, declined=declined, current=current, failed=failed)


# =============================================================================
# `remove()` -- C5's third verb (T5.1a)
# =============================================================================


@dataclass(frozen=True)
class RemoveReport:
    """The whole result of one `remove()` call. Named channels, as above.

    removed:   name -> (installed_as, version, directory_existed)
    refused:   name -> (reason, unified_diff | None), a rule said no; nothing
               touched. The diff is a str for rule 5 (diverged) and None for
               every other rule
    failed:    name -> reason, an OSError (or a failed manifest write); rolled
               back where possible
    committed: always False -- see "C5 reports; C3 offers" above.
    """

    removed: dict[str, tuple[str, str, bool]] = field(default_factory=dict)
    refused: dict[str, tuple[str, str | None]] = field(default_factory=dict)
    failed: dict[str, str] = field(default_factory=dict)
    committed: bool = False


def _removing_path(skills_root: Path, installed_as: str) -> Path:
    """Where `remove()` moves a pattern aside before deleting it."""
    return skills_root / f".{installed_as}{paths.REMOVING_SUFFIX}"


def _discard_diff(dest: Path, name: str, installed_as: str, catalogue_dir: Path) -> str:
    """The diff a rule-5 refusal carries: `update`'s own, installed ->
    catalogue, so the user's edit reads as a deletion `[ref: SDD/Process
    contract: the CLI the skill drives, remove]`.

    Neither side may turn the refusal into a failure. An absent or unreadable
    installed `SKILL.md` is the empty file (rule 5 already counts both as
    diverged); undecodable bytes are shown with replacement characters. A
    catalogue that no longer carries the pattern -- or whose `SKILL.md`
    cannot be read or renamed -- is the empty file too: then nothing can be
    reinstalled, every installed line is the user's to lose, and the diff
    shows each one as `-`."""
    try:
        installed_text = (dest / "SKILL.md").read_bytes().decode("utf-8", errors="replace")
    except OSError:
        installed_text = ""
    try:
        catalogue_text = _catalogue_as_installed(catalogue_dir, name, installed_as)
    except InstallError:
        catalogue_text = ""
    return _divergence_diff(installed_text, catalogue_text)


def _refusal(
    name: str,
    entry: "manifest.PatternEntry | None",
    *,
    skills_root: Path,
    catalogue_dir: Path,
    discard_edits: frozenset,
) -> tuple[str, str | None] | None:
    """Rules 1-5 of the SDD's table; the first that applies decides, as
    `(reason, diff)` -- the diff only for rule 5. `None` means rule 6: remove
    it `[ref: SDD/Process contract: the CLI the skill drives, remove]`."""
    # Rule 1. `remove` never deletes a directory the manifest does not own --
    # a hand-made `tcs-foo/` is someone's skill, not ours.
    if entry is None:
        return "not recorded in the manifest; remove deletes only what the manifest records", None
    # Rule 2. A hand-edited manifest pointing `ddd` at `tcs-hexagonal` would
    # otherwise delete the wrong pattern.
    expected = f"tcs-{name}"
    if entry.installed_as != expected:
        return (
            f"the manifest records {name!r} as installed at {entry.installed_as!r}, not {expected!r}; "
            "refusing to delete a directory under another name"
        ), None
    dest = skills_root / entry.installed_as
    stash = _stash_path(skills_root, entry.installed_as)
    # Rule 3. With the directory ABSENT the stash is the user's only copy
    # (update path, decision 8). A stash beside a PRESENT directory is debris,
    # deleted in step 2 -- not this rule's case.
    if os.path.lexists(stash) and not os.path.lexists(dest):
        return (
            f"an interrupted refresh left your copy at {stash}; move it back to {entry.installed_as}/ "
            "and run remove again, or delete it yourself if you do not want it"
        ), None
    # Rule 4. `install()` never creates either, so it is not ours as written.
    if os.path.lexists(dest) and (dest.is_symlink() or not dest.is_dir()):
        return f"{dest} is a symlink or not a directory; install never writes either, so remove leaves it alone", None
    # Rule 5. Only SKILL.md is hashed: an edit confined to `reference/` is
    # deleted without asking -- ADR-4's accepted limit. Per name, never a
    # blanket flag. The refusal carries the diff, so consent is given to a
    # loss the user can see (ADR-4).
    if dest.is_dir() and paths.sha256_or_none(dest / "SKILL.md") != entry.sha256 and name not in discard_edits:
        return (
            f"diverged from what was installed; local edits would be lost -- re-run with --discard-edits {name}",
            _discard_diff(dest, name, entry.installed_as, catalogue_dir),
        )
    return None


def _remove_one(
    name: str, entry: "manifest.PatternEntry", *, repo_dir: Path, skills_root: Path, bundle: str
) -> bool:
    """Rule 6's five steps. Returns `directory_existed`; raises `InstallError`
    with the failing step's exception text.

    **Order: clear the stash, move aside, then the manifest, then delete**, so
    every interrupted state is one `status` can name -- finished by a re-run,
    or debris it calls safe to delete. No step before step 3 uses
    `ignore_errors`, and a failure in step 1 or 2 goes no further."""
    installed_as = entry.installed_as
    dest = skills_root / installed_as
    removing = _removing_path(skills_root, installed_as)
    stash = _stash_path(skills_root, installed_as)
    directory_existed = dest.is_dir()

    try:
        # Step 1: this verb's own debris from an earlier interrupted run.
        if os.path.lexists(removing):
            shutil.rmtree(removing)
        # Step 2: a stash beside a present directory, BEFORE anything else
        # moves, so no interrupted remove leaves an old stash that `status`
        # would call "your copy".
        if directory_existed and os.path.lexists(stash):
            shutil.rmtree(stash)
        # Step 3: out of the skill listing in one atomic, same-directory rename.
        if directory_existed:
            os.rename(str(dest), str(removing))
    except OSError as e:
        raise InstallError(str(e)) from e

    # Step 4: the manifest, without the entry.
    try:
        manifest.drop(repo_dir, name, bundle=bundle)
    except Exception as e:
        reason = str(e)
        # Only if step 3 renamed a directory. On the resume path there is
        # nothing to put back: a `.removing` found there was deleted in step 1.
        if directory_existed:
            try:
                os.rename(str(removing), str(dest))
            except OSError as back:
                reason += f"; and moving {removing} back to {dest} failed: {back}"
        raise InstallError(reason) from e

    # Step 5: a leftover is reported by `status` as debris.
    shutil.rmtree(removing, ignore_errors=True)
    return directory_existed


def remove(
    repo_dir: Path,
    names,
    *,
    catalogue_dir: Path = paths.DEFAULT_CATALOGUE_DIR,
    bundle: str | None = None,
    discard_edits: frozenset = frozenset(),
) -> RemoveReport:
    """Delete each named pattern and its manifest entry -- only what the
    manifest records, never a diverged pattern unless its name is in `discard_edits`.

    Reads the manifest once, up front; `ManifestUnparseableError` and
    `OSError` propagate before anything is touched. Then, per pattern in
    sorted order, the first rule that applies decides (see `_refusal`), and
    rule 6 runs `_remove_one`'s five steps. One pattern's refusal or failure
    never stops the others. The catalogue is read only to diff a rule-5
    refusal (see `_discard_diff`).

    The manifest's `bundle` becomes the removing plugin's version (decision 9
    of the update path). Removing the last pattern leaves a manifest with zero
    patterns, not no manifest `[ref: SDD/Process contract: the CLI the skill
    drives, remove]`.
    """
    repo_dir = Path(repo_dir)
    skills_root = repo_dir / ".claude" / "skills"
    if bundle is None:
        bundle = _bundle_version()
    discard_edits = frozenset(discard_edits)
    catalogue_dir = Path(catalogue_dir)

    manifest_before = manifest.read(repo_dir)

    removed: dict[str, tuple[str, str, bool]] = {}
    refused: dict[str, tuple[str, str | None]] = {}
    failed: dict[str, str] = {}

    for name in sorted(set(names)):
        entry = manifest_before.patterns.get(name)
        refusal = _refusal(
            name, entry, skills_root=skills_root, catalogue_dir=catalogue_dir, discard_edits=discard_edits
        )
        if refusal is not None:
            refused[name] = refusal
            continue
        try:
            directory_existed = _remove_one(name, entry, repo_dir=repo_dir, skills_root=skills_root, bundle=bundle)
        except InstallError as e:
            failed[name] = str(e)
            continue
        removed[name] = (entry.installed_as, entry.version, directory_existed)

    return RemoveReport(removed=removed, refused=refused, failed=failed)
