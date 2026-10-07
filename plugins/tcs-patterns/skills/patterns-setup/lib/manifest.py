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
    write(manifest, repo_dir) -> atomic: temp file in `.claude/skills/`, fsync, then os.replace;
                        raises ManifestNewerSchemaError for a schema it did not write
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
is narrow by construction -- a pattern name from the catalogue, `"tcs-"` plus
that same name (ADR-1), a catalogue `VERSION` (1-9 digits, ADR-3), a hex
digest, and a version-shaped `bundle` -- so `PatternEntry.__post_init__`,
`_require_bound` and `_require_bundle` below **raise** on anything outside
those shapes rather than attempting to escape it cleverly. None of the five
shapes admits a quote, backslash or control character, which is the whole of
what keeps the hand-written quoting sound. The round-trip test this module is built against (write,
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

**`schema` is the format version** (PR #176 M7). `write()` emits
`schema = 1`; a manifest without the key reads as schema 1, which is every
manifest written before the key existed. A manifest whose `schema` is a
larger integer was written by a newer tcs-patterns: `read()` still returns
it, tolerating the keys it does not know, so `status` and the drift reporter
keep reporting it -- but `write()` refuses it with `ManifestNewerSchemaError`,
because rewriting would discard whatever the newer format added. The file is
never touched; the remedy is to update the plugin.

`tempfile` is imported inside `write()`, not here: the read-only drift
reporter imports this module at every session start, and `tempfile` alone
cost ~33ms of that (PR #176 M4).

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
# Apply every one of these with `fullmatch`: `$` alone admits a trailing newline.
_NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")  # catalogue pattern names
_INSTALLED_AS_RE = re.compile(r"^tcs-[a-z0-9]+(-[a-z0-9]+)*$")  # ADR-1
# Bounded: `int()` refuses a string past 4300 digits, and `status` and the
# drift reporter compare versions as integers (PR #176 L1).
_VERSION_RE = re.compile(r"^[0-9]{1,9}$")  # catalogue VERSION, ADR-3
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_BUNDLE_RE = re.compile(r"^[0-9A-Za-z.+-]{1,64}$")  # a plugin version, semver-shaped

SCHEMA_VERSION = 1  # the manifest format this module writes (PR #176 M7)
_KNOWN_TOP_KEYS = frozenset({"schema", "bundle", "patterns"})
_KNOWN_PATTERN_KEYS = frozenset({"version", "installed_as", "sha256"})


class ManifestUnparseableError(Exception):
    """The manifest file exists but could not be read into a `Manifest`.

    Covers a TOML syntax error from `tomllib` and a document that parses but
    violates this module's schema (an unknown key, a missing field, a field
    of the wrong shape) -- both leave `read()` unable to produce a `Manifest`
    it can stand behind, and both must refuse rather than guess. Never
    `tomllib.TOMLDecodeError` itself, so a caller's `except` clause does not
    depend on `tomllib`'s own exception surface.
    """


class ManifestNewerSchemaError(Exception):
    """The manifest was written by a newer tcs-patterns (`schema` above
    `SCHEMA_VERSION`). Raised by `write()` -- and so by `upsert()` and
    `drop()` -- before anything touches the file, and by
    `refuse_newer_schema()`, which the CLI calls up front so a writing verb
    refuses before it copies anything. Not a `ManifestUnparseableError`: the
    file is readable and `read()` returns it."""


def refuse_newer_schema(manifest: "Manifest") -> None:
    """Raise `ManifestNewerSchemaError` if this module may not rewrite `manifest`."""
    if manifest.schema > SCHEMA_VERSION:
        raise ManifestNewerSchemaError(
            f"the manifest is schema {manifest.schema}, written by a newer tcs-patterns "
            f"(bundle {manifest.bundle}); this one writes schema {SCHEMA_VERSION} and will not "
            "rewrite it -- update the tcs-patterns plugin, then run this again"
        )


def _require_bound(name: str, entry: "PatternEntry") -> None:
    """Refuse a `name`/`installed_as` pair ADR-1 could not have produced.

    `installed_as` is always `"tcs-" + name`. `update` and `remove` act on
    the directory `installed_as` names, so an entry pointing `ddd` at
    `tcs-mine` would let them replace or delete a directory that is not the
    pattern's (PR #176 H1). Checked on read, in `with_pattern`, and again in
    `write()`, which a hand-built `Manifest` reaches without `with_pattern`.
    `_NAME_RE` also keeps the name safe for the unquoted `[patterns.<name>]`
    header."""
    if not _NAME_RE.fullmatch(name):
        raise ValueError(f"pattern name {name!r} is not a catalogue pattern name")
    if entry.installed_as != "tcs-" + name:
        raise ValueError(
            f"installed_as {entry.installed_as!r} is not 'tcs-{name}', the only name "
            f"pattern {name!r} is ever installed under (ADR-1)"
        )


def _require_bundle(bundle: str) -> str:
    """Refuse a `bundle` that is not version-shaped -- 1-64 of `[0-9A-Za-z.+-]`.
    A carriage return used to pass the old quote/backslash/newline check, be
    written, and then fail `tomllib` on every later read (PR #176 L3a)."""
    if not _BUNDLE_RE.fullmatch(bundle):
        raise ValueError(f"bundle {bundle!r} is not a plugin version (1-64 of [0-9A-Za-z.+-])")
    return bundle


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
            raise ValueError(f"version {self.version!r} is not a catalogue VERSION (1-9 digits)")
        if not _INSTALLED_AS_RE.fullmatch(self.installed_as):
            raise ValueError(f"installed_as {self.installed_as!r} is not a tcs-prefixed pattern name")
        if not _SHA256_RE.fullmatch(self.sha256):
            raise ValueError(f"sha256 {self.sha256!r} is not a 64-character lowercase hex digest")


@dataclass(frozen=True)
class Manifest:
    """The whole record. `bundle` is `None` only for the empty manifest
    `read()` returns when no file exists yet -- `write()` refuses a `None`
    bundle, because a manifest is never written except as the result of an
    `upsert`, which always supplies one. `schema` is the format version the
    file declared (1 when it declared none); `with_pattern` and
    `without_pattern` carry it over, so a newer manifest stays newer and
    `write()` refuses it."""

    bundle: str | None
    patterns: dict[str, PatternEntry] = field(default_factory=dict)
    schema: int = SCHEMA_VERSION

    def with_pattern(self, name: str, entry: PatternEntry, *, bundle: str) -> "Manifest":
        """A new `Manifest` with `name` added or replaced. Never mutates `self` --
        `upsert` relies on the old value staying intact for its own return."""
        _require_bound(name, entry)
        new_patterns = dict(self.patterns)
        new_patterns[name] = entry
        return Manifest(bundle=bundle, patterns=new_patterns, schema=self.schema)

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
        return Manifest(bundle=bundle, patterns=new_patterns, schema=self.schema)


def manifest_path(repo_dir: Path) -> Path:
    return Path(repo_dir).joinpath(*MANIFEST_DIR, MANIFEST_FILENAME)


def read(repo_dir: Path) -> Manifest:
    """Read the manifest at `repo_dir`.

    "Absent" means NOTHING at the manifest path (`os.path.lexists` is
    false): that reads as an EMPTY manifest (`bundle=None, patterns={}`),
    never an error -- the first `install` into a repository has nothing to
    read yet, and that is not a failure. Anything else that is not a regular
    file (a directory, a dangling symlink) raises `ManifestUnparseableError`
    naming the path; so does a file that cannot be parsed into a well-formed
    `Manifest`. See the module docstring for why an absent file and a corrupt
    one must stay distinguishable here. `lexists`, not `exists`, so a
    dangling symlink is "something there", not absent.

    **Unknown keys depend on `schema`.** At schema 1 (declared, or absent
    and so implied) an unknown top-level or per-pattern key raises
    `ManifestUnparseableError`, same as a syntax error. At a larger integer
    `schema` the file came from a newer tcs-patterns: unknown keys are
    skipped, the known fields are validated exactly as at schema 1, and the
    `Manifest` comes back with that `schema` -- readable for reporting,
    refused by `write()` (see the module docstring). A `schema` below 1, or
    not an integer (a bool included), is unparseable.
    """
    path = manifest_path(repo_dir)
    if not os.path.lexists(path):
        return Manifest(bundle=None, patterns={})
    if not path.is_file():
        raise ManifestUnparseableError(f"{path}: not a regular file")

    try:
        doc = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        raise ManifestUnparseableError(f"{path}: TOML syntax error: {e}") from e
    except UnicodeDecodeError as e:
        raise ManifestUnparseableError(f"{path}: not valid UTF-8: {e}") from e

    schema = doc.get("schema", SCHEMA_VERSION)
    if isinstance(schema, bool) or not isinstance(schema, int) or schema < 1:
        raise ManifestUnparseableError(f"{path}: 'schema' must be an integer of at least 1, not {schema!r}")
    newer = schema > SCHEMA_VERSION

    unknown_top = set(doc) - _KNOWN_TOP_KEYS
    if unknown_top and not newer:
        raise ManifestUnparseableError(f"{path}: unknown top-level key(s): {', '.join(sorted(unknown_top))}")

    bundle = doc.get("bundle")
    if not isinstance(bundle, str):
        raise ManifestUnparseableError(f"{path}: 'bundle' is required and must be a string")
    try:
        _require_bundle(bundle)
    except ValueError as e:
        raise ManifestUnparseableError(f"{path}: {e}") from e

    raw_patterns = doc.get("patterns", {})
    if not isinstance(raw_patterns, dict):
        raise ManifestUnparseableError(f"{path}: 'patterns' must be a table")

    patterns: dict[str, PatternEntry] = {}
    for name, table in raw_patterns.items():
        if not _NAME_RE.fullmatch(name):
            raise ManifestUnparseableError(f"{path}: 'patterns.{name}' is not a catalogue pattern name")
        if not isinstance(table, dict):
            raise ManifestUnparseableError(f"{path}: 'patterns.{name}' must be a table")
        unknown = set(table) - _KNOWN_PATTERN_KEYS
        if unknown and not newer:
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
            entry = PatternEntry(version=version, installed_as=installed_as, sha256=sha256)
            _require_bound(name, entry)
        except ValueError as e:
            raise ManifestUnparseableError(f"{path}: 'patterns.{name}': {e}") from e
        patterns[name] = entry

    return Manifest(bundle=bundle, patterns=patterns, schema=schema)


def _serialize_pattern(name: str, entry: PatternEntry) -> str:
    """The exact, self-contained text of one `[patterns.<name>]` block.

    Depends only on `name` and `entry` -- never on any other pattern in the
    manifest, which is what makes an untouched pattern's block survive an
    `upsert` byte-for-byte (see the module docstring). Every value here has
    passed a regex admitting no quote, backslash or control character:
    `entry`'s three in `PatternEntry.__post_init__`, `name` in
    `_require_bound`."""
    _require_bound(name, entry)
    return (
        f"[patterns.{name}]\n"
        f'version = "{entry.version}"\n'
        f'installed_as = "{entry.installed_as}"\n'
        f'sha256 = "{entry.sha256}"\n'
    )


def _serialize(manifest: Manifest) -> str:
    refuse_newer_schema(manifest)
    if manifest.bundle is None:
        raise ValueError("cannot write a manifest with no bundle version set")
    bundle = _require_bundle(manifest.bundle)

    parts = [
        "# Written by /tcs-patterns:patterns-setup. Reviewed and committed like any other file.\n",
        f"schema = {SCHEMA_VERSION}\n",
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

    **Raises `ManifestNewerSchemaError` for a newer-schema manifest**, before
    any file is created. The temp file is fsync'd before the rename, so a
    crash cannot leave the rename durable and the content not (PR #176 L3b).
    """
    import tempfile  # lazily: see the module docstring (PR #176 M4)

    content = _serialize(manifest)
    path = manifest_path(repo_dir)
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f".{MANIFEST_FILENAME}.", suffix=paths.TMP_SUFFIX)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
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
    `[ref: SDD/Error Handling, "Manifest present but unparseable"]`. A
    newer-schema manifest reads, and `write()` then refuses it.
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
