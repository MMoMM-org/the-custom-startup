"""The tcs-patterns installer (spec-020 T3.3, component C5).

`install(repo_dir, names, *, catalogue_dir) -> InstallReport` writes the
patterns named in `names` into `<repo_dir>/.claude/skills/tcs-<name>/`, each
renamed to its prefixed form in the installed `SKILL.md`'s frontmatter
(ADR-1), and records each write in the manifest (C6). **This module assumes
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
under `tcs-<name>/`** -- that is `update()`'s job (T3.4, not built yet), and
every F8 acceptance criterion is phrased in terms of what `update` does, not
`install`
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
is required there, with no default). `DEFAULT_BUNDLE_VERSION` -- this
plugin's own `plugin.json` version, read once at import time -- is kept as
the default, but a caller may override it `[ref: solution.md, point 7]`:
it is otherwise the one input to `install()` a test cannot drive, and CI
bumps `plugin.json` on every merge, which would make any test asserting
the manifest's `bundle` field against the real file break on a version
bump rather than on an actual regression.

Stdlib only, Python 3.11 floor `[ref: SDD/Architecture Decisions/ADR-2]`.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

import manifest

_PLUGIN_ROOT = Path(__file__).resolve().parents[3]
_PLUGIN_JSON = _PLUGIN_ROOT / ".claude-plugin" / "plugin.json"
DEFAULT_CATALOGUE_DIR = _PLUGIN_ROOT / "templates" / "patterns"


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


def _bundle_version() -> str:
    """The installed plugin's own version, for the manifest's top-level
    `bundle` field ("the plugin version that produced this selection")
    `[ref: solution.md, Data model: the manifest (C6)]`. Derived from this
    plugin's own `plugin.json`, the same `__file__`-relative pattern
    `DEFAULT_CATALOGUE_DIR` uses. Computed once, at import time, into
    `DEFAULT_BUNDLE_VERSION` below -- `install()`'s default for its
    `bundle` parameter, not the only route to a value
    `[ref: solution.md, point 7]`.
    """
    data = json.loads(_PLUGIN_JSON.read_text(encoding="utf-8"))
    return str(data["version"])


DEFAULT_BUNDLE_VERSION = _bundle_version()


def _read_catalogue_version(catalogue_dir: Path, name: str) -> str:
    try:
        return (catalogue_dir / name / "VERSION").read_text(encoding="utf-8").strip()
    except OSError as e:
        raise InstallError(f"could not read VERSION for catalogue pattern {name!r}: {e}") from e


def _hash_if_present(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


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
    tmp_dir = skills_root / f".{installed_as}.tmp"

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

        patched = rename_in_frontmatter(raw.decode("utf-8"), installed_as).encode("utf-8")
        skill_md.write_bytes(patched)

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
        installed_hash = _hash_if_present(dest / "SKILL.md")
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
    catalogue_dir: Path = DEFAULT_CATALOGUE_DIR,
    bundle: str = DEFAULT_BUNDLE_VERSION,
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
    """
    repo_dir = Path(repo_dir)
    catalogue_dir = Path(catalogue_dir)
    skills_root = repo_dir / ".claude" / "skills"

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
