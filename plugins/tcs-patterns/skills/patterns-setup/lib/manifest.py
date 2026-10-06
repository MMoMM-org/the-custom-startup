"""The tcs-patterns manifest store (spec-020 T3.1, component C6).

`<repo>/.claude/skills/.tcs-patterns-manifest` is the one record naming every
installed pattern and the version it was installed at
`[ref: SDD/Interface Specifications/Data model: the manifest; PRD/F6 1st]`.
TOML, because `observability-sources.toml` and `startup.toml` already
establish that format in this repository, and a manifest reviewed in a pull
request should read like the rest of what a reviewer sees there.

**What this module returns, and what an unparseable manifest does -- settled
on 2026-10-05, before this task was dispatched, specifically because the two
sentences describing it elsewhere read as a contradiction**
`[ref: SDD/Interface Specifications/Data model: the manifest, "What C6
returns..."]`:

    read(repo_dir)   -> Manifest | raises ManifestUnparseableError
                        absent file -> an EMPTY manifest, not an error
    write(manifest, repo_dir) -> atomic: temp file in `.claude/skills/`, then os.replace
    upsert(repo_dir, name, ...) -> a new Manifest; prior entries byte-identical
    drop(repo_dir, name, *, bundle) -> the mirror of upsert (T5.1a); unlisted -> KeyError

A missing manifest and a corrupt one must stay distinguishable right here, at
the reader -- "never silently overwritten" (see the Error Handling table row
below) is only enforceable if `write()` can never be handed a value derived
from a file nobody could parse. `MISSING` is the *advisory*'s rendering of an
unparseable manifest, not this module's return value: this module refuses
instead, by raising, and leaves catching that exception to whichever caller
wants to present `MISSING` to a user
`[ref: SDD/Error Handling, "Manifest present but unparseable"]`.

**Writing is hand-serialised, and that is forced rather than chosen.**
`tomllib` is a reader -- it has no `dumps`/`dump` -- and neither `tomli_w`
nor `toml` is importable here; a plugin ships as files into whatever Python
the user's machine provides, with no install step, so a non-stdlib runtime
import is a failure on someone else's computer
`[ref: SDD/Interface Specifications/Data model: the manifest, "Writing the
TOML is hand-serialised..."]`. The value space this writer has to represent
is narrow by construction -- a pattern name from the catalogue, a `tcs-`
prefixed installed name (ADR-1), a catalogue `VERSION` (digits, ADR-3), and a
hex digest -- so `PatternEntry.__post_init__` and `_require_representable`
below **raise** on anything outside those shapes rather than attempting to
escape it cleverly. The round-trip test this module is built against (write,
then `tomllib.loads` the bytes back, then compare) is the standing guard
against a quoting mistake slipping past these checks.

**Byte-identical prior entries, on every `upsert`.** `write()` regenerates
the whole file -- there is no in-place patch, because `tomllib` cannot write
and a patch would need its own parser to find the right span. What keeps a
prior pattern's table block byte-for-byte unchanged across that regeneration
is that `_serialize_pattern` depends only on one pattern's own name and
entry, never on its neighbours or their count, and patterns are emitted in a
fixed (sorted) order -- so inserting a new pattern changes which blocks sit
next to it, never what any existing block's own text is.

The temp file for `write()`'s atomic replace is created inside
`.claude/skills/` itself, never under `$TMPDIR` -- a different filesystem
there would make `os.rename` raise `Cross-device link`, and `shutil.move`
would silently degrade to a non-atomic copy-then-delete
`[ref: SDD/Risks and Technical Debt/Implementation Gotchas]`.

`is_current()` is the `compare` half of this module's job (AC-17, PRD/F6
3rd): currency is determinable from the manifest and the catalogue's
`VERSION` string alone. It never opens the installed pattern's files --
reading those is what AC-17 forbids, precisely because a pattern could be
reinstalled, deleted, or edited locally and the manifest is the only record
a caller should need to trust.
"""

from __future__ import annotations

import os
import re
import tempfile
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

import paths

MANIFEST_DIR = (".claude", "skills")
MANIFEST_FILENAME = ".tcs-patterns-manifest"  # ADR-6

# The value space this writer accepts. Each is intentionally narrow -- see
# the module docstring's "Writing is hand-serialised" paragraph. A value
# outside these shapes is a bug upstream (something handed this module data
# it was never meant to carry), not a quoting problem, so it is refused
# rather than escaped.
# Apply every one of these four with `fullmatch`: `$` alone admits a trailing newline.
_NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")  # catalogue pattern names
_INSTALLED_AS_RE = re.compile(r"^tcs-[a-z0-9]+(-[a-z0-9]+)*$")  # ADR-1
_VERSION_RE = re.compile(r"^[0-9]+$")  # catalogue VERSION, ADR-3
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_UNSAFE_CHARS = re.compile(r'["\\\n]')  # would break the hand-written TOML quoting


class ManifestUnparseableError(Exception):
    """The manifest file exists but could not be read into a `Manifest`.

    Covers a TOML syntax error from `tomllib` and a document that parses but
    violates this module's schema (an unknown key, a missing field, a field
    of the wrong shape) -- both leave `read()` unable to produce a `Manifest`
    it can stand behind, and both must refuse rather than guess. Never
    `tomllib.TOMLDecodeError` itself, so a caller's `except` clause does not
    depend on `tomllib`'s own exception surface.
    """


def _require_representable(value: str, *, field_name: str) -> str:
    """Refuse a value that would break this module's hand-written TOML quoting.

    Called from five sites (`version`, `installed_as`, `sha256`, `name`,
    `bundle`), but reachable from only one. `PatternEntry.__post_init__`
    rejects anything outside `_VERSION_RE`/`_INSTALLED_AS_RE`/`_SHA256_RE`
    before its three fields ever reach here, and `Manifest.with_pattern`
    does the same for `name` via `_NAME_RE` -- none of those four regexes
    permits a quote, backslash, or newline -- provided they are applied with
    `fullmatch`, never `match`, because a trailing `$` also matches before a
    final newline -- so this guard can never actually fire for them. `bundle` has no regex of its own, so it is the only field
    this function still protects in practice. Kept at all five sites anyway
    (defence in depth is cheap here), but if `bundle` ever gains a regex too,
    this function becomes wholly unreachable -- which this comment is here
    to make legible to whoever notices that, rather than left to be
    rediscovered by reading all five call sites.
    """
    if _UNSAFE_CHARS.search(value):
        raise ValueError(
            f"{field_name}={value!r} cannot be represented in this manifest's hand-written "
            "TOML -- it contains a quote, backslash, or newline"
        )
    return value


@dataclass(frozen=True)
class PatternEntry:
    """One `[patterns.<name>]` table: the version installed, the name it was
    installed under, and the hash of its installed `SKILL.md` (ADR-4,
    divergence detection only -- not currency, see `is_current`)."""

    version: str
    installed_as: str
    sha256: str

    def __post_init__(self) -> None:
        if not _VERSION_RE.fullmatch(self.version):
            raise ValueError(f"version {self.version!r} is not a catalogue VERSION (digits only)")
        if not _INSTALLED_AS_RE.fullmatch(self.installed_as):
            raise ValueError(f"installed_as {self.installed_as!r} is not a tcs-prefixed pattern name")
        if not _SHA256_RE.fullmatch(self.sha256):
            raise ValueError(f"sha256 {self.sha256!r} is not a 64-character lowercase hex digest")


@dataclass(frozen=True)
class Manifest:
    """The whole record. `bundle` is `None` only for the empty manifest
    `read()` returns when no file exists yet -- `write()` refuses a `None`
    bundle, because a manifest is never written except as the result of an
    `upsert`, which always supplies one."""

    bundle: str | None
    patterns: dict[str, PatternEntry] = field(default_factory=dict)

    def with_pattern(self, name: str, entry: PatternEntry, *, bundle: str) -> "Manifest":
        """A new `Manifest` with `name` added or replaced. Never mutates `self` --
        `upsert` relies on the old value staying intact for its own return."""
        if not _NAME_RE.fullmatch(name):
            raise ValueError(f"pattern name {name!r} is not a catalogue pattern name")
        new_patterns = dict(self.patterns)
        new_patterns[name] = entry
        return Manifest(bundle=bundle, patterns=new_patterns)

    def without_pattern(self, name: str, *, bundle: str) -> "Manifest":
        """A new `Manifest` with `name`'s entry removed and `bundle` set to
        the plugin version doing the removing. Never mutates `self`, the
        mirror of `with_pattern`.

        **Raises `KeyError` for a name `self` does not list** -- decided in
        T5.1a, where the SDD was silent. `remove()` drops only a name its
        rule 1 found listed, so an unlisted one here is a caller bug; raising
        keeps `drop()` from writing (or creating) a manifest for a pattern it
        never recorded. Removing the last entry yields a manifest with zero
        patterns, which `write()` serialises like any other
        `[ref: SDD/remove, "Removing the last pattern leaves a manifest with
        zero patterns, not no manifest"]`."""
        if name not in self.patterns:
            raise KeyError(name)
        new_patterns = {k: v for k, v in self.patterns.items() if k != name}
        return Manifest(bundle=bundle, patterns=new_patterns)


def _manifest_path(repo_dir: Path) -> Path:
    return Path(repo_dir).joinpath(*MANIFEST_DIR, MANIFEST_FILENAME)


def read(repo_dir: Path) -> Manifest:
    """Read the manifest at `repo_dir`.

    An absent file reads as an EMPTY manifest (`bundle=None, patterns={}`),
    never an error -- the first `install` into a repository has nothing to
    read yet, and that is not a failure. A file that exists but cannot be
    parsed into a well-formed `Manifest` raises `ManifestUnparseableError`
    instead of returning anything -- see the module docstring for why an
    absent file and a corrupt one must stay distinguishable here.

    **A forward-compatibility hazard this strictness creates, named here
    rather than left implicit.** An unknown top-level or per-pattern key
    also raises `ManifestUnparseableError`, same as a syntax error -- so a
    manifest written by a NEWER plugin version that added a key reads as
    unparseable to an OLDER one. Chained through the rest of the system:
    `ManifestUnparseableError` -> the advisory renders `MISSING` -> a user
    is told to re-run setup -> that older plugin's `upsert` then calls
    `write()` with a manifest it rebuilt from an empty read, discarding the
    newer file's extra key for good. This module does not resolve that --
    no version negotiation is implemented -- but `bundle` (the plugin
    version that produced the file) is the field a future reader would need
    to inspect to tell "newer format, not actually corrupt" apart from
    "genuinely unparseable" before deciding whether to trust this error.
    """
    path = _manifest_path(repo_dir)
    if not path.is_file():
        return Manifest(bundle=None, patterns={})

    try:
        doc = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        raise ManifestUnparseableError(f"{path}: TOML syntax error: {e}") from e
    except UnicodeDecodeError as e:
        raise ManifestUnparseableError(f"{path}: not valid UTF-8: {e}") from e

    unknown_top = set(doc) - {"bundle", "patterns"}
    if unknown_top:
        raise ManifestUnparseableError(f"{path}: unknown top-level key(s): {', '.join(sorted(unknown_top))}")

    bundle = doc.get("bundle")
    if not isinstance(bundle, str) or not bundle:
        raise ManifestUnparseableError(f"{path}: 'bundle' is required and must be a non-empty string")

    raw_patterns = doc.get("patterns", {})
    if not isinstance(raw_patterns, dict):
        raise ManifestUnparseableError(f"{path}: 'patterns' must be a table")

    patterns: dict[str, PatternEntry] = {}
    for name, table in raw_patterns.items():
        if not _NAME_RE.fullmatch(name):
            raise ManifestUnparseableError(f"{path}: 'patterns.{name}' is not a catalogue pattern name")
        if not isinstance(table, dict):
            raise ManifestUnparseableError(f"{path}: 'patterns.{name}' must be a table")
        unknown = set(table) - {"version", "installed_as", "sha256"}
        if unknown:
            raise ManifestUnparseableError(
                f"{path}: 'patterns.{name}' has unknown key(s): {', '.join(sorted(unknown))}"
            )
        try:
            version = table["version"]
            installed_as = table["installed_as"]
            sha256 = table["sha256"]
        except KeyError as e:
            raise ManifestUnparseableError(f"{path}: 'patterns.{name}' is missing {e.args[0]!r}") from e
        if not isinstance(version, str) or not isinstance(installed_as, str) or not isinstance(sha256, str):
            raise ManifestUnparseableError(f"{path}: 'patterns.{name}' fields must all be strings")
        try:
            patterns[name] = PatternEntry(version=version, installed_as=installed_as, sha256=sha256)
        except ValueError as e:
            raise ManifestUnparseableError(f"{path}: 'patterns.{name}': {e}") from e

    return Manifest(bundle=bundle, patterns=patterns)


def _serialize_pattern(name: str, entry: PatternEntry) -> str:
    """The exact, self-contained text of one `[patterns.<name>]` block.

    Depends only on `name` and `entry` -- never on any other pattern in the
    manifest, which is what makes an untouched pattern's block survive an
    `upsert` byte-for-byte (see the module docstring)."""
    return (
        f"[patterns.{_require_representable(name, field_name='name')}]\n"
        f'version = "{_require_representable(entry.version, field_name="version")}"\n'
        f'installed_as = "{_require_representable(entry.installed_as, field_name="installed_as")}"\n'
        f'sha256 = "{_require_representable(entry.sha256, field_name="sha256")}"\n'
    )


def _serialize(manifest: Manifest) -> str:
    if manifest.bundle is None:
        raise ValueError("cannot write a manifest with no bundle version set")
    bundle = _require_representable(manifest.bundle, field_name="bundle")

    parts = [
        "# Written by /tcs-patterns:patterns-setup. Reviewed and committed like any other file.\n",
        f'bundle = "{bundle}"\n',
    ]
    # Sorted, fixed order: deterministic output, and the reason a prior
    # pattern's block stays byte-identical regardless of what else was added.
    for name in sorted(manifest.patterns):
        parts.append("\n")
        parts.append(_serialize_pattern(name, manifest.patterns[name]))
    return "".join(parts)


def write(manifest: Manifest, repo_dir: Path) -> None:
    """Write `manifest` to `repo_dir`, atomically.

    The temp file is created inside `.claude/skills/` (never `$TMPDIR`) so
    the final `os.replace` is a same-filesystem rename, not a copy -- see the
    module docstring. The directory is created if this is the first write.

    **Raises `ValueError` on a `None` bundle, which `read()` can hand you.**
    `read()` returns `Manifest(bundle=None, patterns={})` for an absent file,
    and `_serialize` refuses that -- so `write(read(repo), repo)` on a fresh
    repository raises. No caller reaches it today: the only `write()` call in
    this module is inside `upsert()`, which always builds a new `Manifest`
    through `with_pattern(..., bundle=...)` first. Named here because the type
    does not encode the constraint, so a future C5 or C7 doing read-then-write
    without an upsert in between is the one way to hit it. Found by T3.1's
    spec-compliance review and measured, 2026-10-05.
    """
    content = _serialize(manifest)
    path = _manifest_path(repo_dir)
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f".{MANIFEST_FILENAME}.", suffix=paths.TMP_SUFFIX)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def upsert(
    repo_dir: Path,
    name: str,
    *,
    version: str,
    installed_as: str,
    sha256: str,
    bundle: str,
) -> Manifest:
    """Add or replace `name`'s entry and write the result.

    Reads the current manifest first -- deliberately not inside a `try`
    that could catch `ManifestUnparseableError` and write anyway. A corrupt
    manifest's `ManifestUnparseableError` therefore propagates out of this
    function BEFORE `write()` is ever called, which is the whole mechanism
    behind "an unparseable manifest is never overwritten"
    `[ref: SDD/Error Handling, "Manifest present but unparseable"]`.
    """
    current = read(repo_dir)
    entry = PatternEntry(version=version, installed_as=installed_as, sha256=sha256)
    updated = current.with_pattern(name, entry, bundle=bundle)
    write(updated, repo_dir)
    return updated


def drop(repo_dir: Path, name: str, *, bundle: str) -> Manifest:
    """Remove `name`'s entry and write the result -- the mirror of `upsert`
    that `install.remove()` calls in its step 4
    `[ref: SDD/Process contract: the CLI the skill drives, remove, step 4]`.

    Same shape and the same guarantees: the read is outside any `try`, so a
    `ManifestUnparseableError` propagates before `write()` is reached; every
    other entry's block stays byte-identical because `_serialize_pattern`
    depends only on its own entry. An unlisted `name` raises `KeyError`
    from `without_pattern` before anything is written (see there).
    """
    current = read(repo_dir)
    updated = current.without_pattern(name, bundle=bundle)
    write(updated, repo_dir)
    return updated


def is_current(entry: PatternEntry, catalogue_version: str) -> bool:
    """True if `entry`'s manifest version matches the catalogue's `VERSION`.

    `catalogue_version` is a plain string the caller already read from the
    catalogue (e.g. the pattern's `VERSION` file) -- this function never
    reads it itself, and never opens anything under the *installed*
    pattern's own directory. That is AC-17's requirement made literal:
    currency is determinable from the manifest alone
    `[ref: SDD/Acceptance Criteria/AC-17; PRD/F6 3rd]`.
    """
    return entry.version == catalogue_version
