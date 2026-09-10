#!/usr/bin/env python3
"""scripts/observability/sources.py -- spec-019 T3.2: the locations config and its reader.

ADR-6: the locations config is TOML, at `.claude/observability-sources.toml`
in THIS repository, holding `label`, `repo_root` and an optional `homes`
list. `.claude/` is gitignored wholesale (`.gitignore:2`, with a single
carve-out for `startup.toml`), so the config is uncommittable by
construction rather than by someone remembering an ignore rule -- verified
by a test running `git check-ignore` against this repository in place.

This module is PURE and imports nothing outside the standard library, and
nothing local to this repository -- not even `report.py`. Two separate
reasons, both binding:

  - CON-3: no new runtime dependency. TOML parsing uses `tomllib` (stdlib
    since 3.11); a test walks this file's own AST and asserts every
    imported top-level package is in `sys.stdlib_module_names`, so a future
    `import tomli` or `import yaml` fails that test rather than passing by
    accident of what happens to be installed.
  - A genuine module-level circular import: T3.3 makes `report.py` import
    THIS module (to feed its output to `_resolve_events_path`,
    `report.py:1603-1614`). If this module imported `report` back, that
    would be a real cycle, not style debt. `_resolve_events_path` therefore
    stays private to `report.py` -- this module never calls it, and never
    exposes a resolved record path as part of its public data. What it
    exposes is `repo_root` and each home directory, which is exactly what
    `_resolve_events_path` already accepts as `--repo-root` and `--home`.
    The formula IS duplicated below (`_record_base_path`), deliberately
    (CON-6: the record's location and the instruction-inventory walk both
    derive from `$HOME`, and any design touching one must touch the other
    consistently) -- but only as a PRIVATE implementation detail this
    module uses to classify a home's state from the filesystem, never as a
    path handed to a caller in place of `_resolve_events_path`'s own job.

Three states, per home, classified from the filesystem alone (R7 of the
dispatching task, matching SDD/Error Handling and SDD-AC-17/18):

  - **missing**    -- `repo_root` or the home itself does not exist on disk.
    Checked FIRST, deliberately: `_resolve_events_path`'s directory name is
    built from `repo_root.name`, a basename string that is never existence-
    checked, so a defunct `repo_root` can still resolve to a stale record
    file that happens to exist. Checking records before paths would report
    a dead source as recording.
  - **not_yet_recording** -- both exist, but no record file (any rotation
    generation) is there yet.
  - **recording**  -- both exist, and a record file (base file or any of
    `.1`/`.2`/`.3`) is present. Reuses `report.py`'s rotation semantics
    conceptually (`rotation_chain`, `report.py:108-121`: a record counts as
    present if any generation survives) without importing it, per the
    no-local-imports rule above.

A source with two `homes` (SDD-AC-25, the case the schema exists for -- a
single optional `home` could not express a repository worked on in both a
container and the host) reports ONE headline verdict plus a per-home
breakdown: `Source.verdict` is `recording` if ANY home is recording, else
`not_yet_recording` if any home is that, else `missing`. Collapsing to one
verdict with no per-home detail was rejected (a source whose second home
died months ago would look identical to a fully healthy one at per-home
scale, echoing ADR-7's reason for keeping per-repository detail). This
module hands back the per-home states alongside the verdict so a caller can
render the sub-lines without recomputing anything.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

CONFIG_FILENAME = "observability-sources.toml"  # relative to a repo's .claude/, ADR-6

MISSING = "missing"
NOT_YET_RECORDING = "not_yet_recording"
RECORDING = "recording"


class ConfigError(Exception):
    """Base class for every error this module raises reading the config.

    Never `tomllib.TOMLDecodeError` itself, and never one of its attributes
    read directly by a caller: measured on both interpreters this task must
    run under, `TOMLDecodeError.lineno`/`.colno`/`.msg` exist on 3.14 but
    NOT on 3.11 (the version CI pins, `.github/workflows/tests.yml:61,101`)
    -- reading `.lineno` there raises `AttributeError`. Callers and tests
    assert against this module's own error types and their messages, never
    against tomllib's version-dependent surface.
    """


class ConfigSyntaxError(ConfigError):
    """The TOML document itself does not parse.

    `lineno` names the offending line when one could be determined, and is
    `None` when it could not (spec-019 T3.2 -- see `_syntax_error` for why
    `None` is a legitimate outcome on every interpreter, not a 3.11
    artifact).
    """

    def __init__(self, message: str, *, lineno: int | None):
        super().__init__(message)
        self.lineno = lineno


class ConfigSchemaError(ConfigError):
    """The document parsed, but a `[[source]]` table violates the schema.

    Named by source (its position, and its label when one was found) rather
    than by line: tomllib reports a position only while parsing, and a
    document that parses successfully into a dict has no line left to name
    -- getting one would need a span-preserving TOML parser, which would
    violate CON-3.
    """


@dataclass(frozen=True)
class HomeStatus:
    """One configured (or defaulted) home, classified from the filesystem.

    `home` is never `None`: a source that omits `homes` in the config still
    resolves to exactly one `HomeStatus`, carrying the caller's
    `default_home` (SDD/Interface Specifications: "no `homes` -- the real
    $HOME applies").
    """

    home: Path
    state: str


@dataclass(frozen=True)
class Source:
    """One `[[source]]` table, resolved: a label, a repo root, and every home's state.

    `homes` always has at least one entry once loaded (see `HomeStatus`).
    """

    label: str
    repo_root: Path
    homes: list[HomeStatus]

    @property
    def verdict(self) -> str:
        """The source's single headline state (recording if ANY home is)."""
        states = {h.state for h in self.homes}
        if RECORDING in states:
            return RECORDING
        if NOT_YET_RECORDING in states:
            return NOT_YET_RECORDING
        return MISSING


# ---------------------------------------------------------------------------
# Classifying a home from the filesystem.
# ---------------------------------------------------------------------------


def _record_base_path(repo_root: Path, home: Path) -> Path:
    """Sources.py's own, private mirror of `_resolve_events_path`'s formula.

    Deliberately duplicated rather than imported -- see the module
    docstring. `_resolve_events_path` (`report.py:1603-1614`) computes the
    same path from the same two inputs when `--data-dir` is not overridden;
    this module never overrides it, so the two formulas must stay
    byte-identical by hand (CON-6). Used only internally, to check whether a
    record exists for classification -- never returned to a caller.
    """
    data_dir = home / ".claude" / "plugins" / "data" / f"observability-{repo_root.name}"
    return data_dir / "observability" / "events.jsonl"


def _record_present(base_path: Path) -> bool:
    """True if the base record file or any rotated generation exists.

    Conceptually `report.py`'s `rotation_chain` (`report.py:108-121`): a
    record counts as present if `.3`, `.2`, `.1` or the base file survives.
    Reused as a concept, not imported (no local imports, per the module
    docstring).
    """
    if base_path.is_file():
        return True
    return any(base_path.with_name(base_path.name + suffix).is_file() for suffix in (".1", ".2", ".3"))


def _classify_home(repo_root: Path, home: Path) -> str:
    """`missing` / `not_yet_recording` / `recording` -- path existence first (R7)."""
    if not repo_root.is_dir():
        return MISSING
    if not home.is_dir():
        return MISSING
    return RECORDING if _record_present(_record_base_path(repo_root, home)) else NOT_YET_RECORDING


# ---------------------------------------------------------------------------
# Parsing and validating the config document.
# ---------------------------------------------------------------------------

_ALLOWED_SOURCE_KEYS = {"label", "repo_root", "homes"}
_SYNTAX_LINE_RE = re.compile(r"at line (\d+)")


def _schema_error(index: int, label: object, message: str) -> ConfigSchemaError:
    if isinstance(label, str) and label:
        return ConfigSchemaError(f"source #{index} (label={label!r}): {message}")
    return ConfigSchemaError(f"source #{index}: {message}")


def _parse_source_table(index: int, table: object) -> tuple[str, Path, list[Path]]:
    if not isinstance(table, dict):
        raise _schema_error(index, None, f"a [[source]] entry must be a table, got {type(table).__name__}")

    unknown = set(table) - _ALLOWED_SOURCE_KEYS
    if unknown:
        raise _schema_error(index, table.get("label"), f"unknown key(s): {', '.join(sorted(unknown))}")

    label = table.get("label")
    if not isinstance(label, str) or not label:
        raise _schema_error(index, None, "label is required and must be a non-empty string")

    repo_root = table.get("repo_root")
    if not isinstance(repo_root, str) or not repo_root:
        raise _schema_error(index, label, "repo_root is required and must be a non-empty string")

    homes_value = table.get("homes")
    if homes_value is None:
        homes: list[Path] = []
    elif not isinstance(homes_value, list):
        raise _schema_error(index, label, f"homes must be a list, got {type(homes_value).__name__}")
    elif not all(isinstance(h, str) and h for h in homes_value):
        raise _schema_error(index, label, "homes must be a list of non-empty strings")
    else:
        homes = [Path(h).expanduser() for h in homes_value]

    return label, Path(repo_root).expanduser(), homes


def _parse_document(doc: dict) -> list[tuple[str, Path, list[Path]]]:
    unknown_top = set(doc) - {"source"}
    if unknown_top:
        raise ConfigSchemaError(f"unknown top-level key(s): {', '.join(sorted(unknown_top))}")

    raw_sources = doc.get("source", [])
    if not isinstance(raw_sources, list):
        raise ConfigSchemaError("'source' must be an array of tables ([[source]])")

    parsed: list[tuple[str, Path, list[Path]]] = []
    seen_labels: dict[str, int] = {}
    for i, table in enumerate(raw_sources, start=1):
        label, repo_root, homes = _parse_source_table(i, table)
        if label in seen_labels:
            raise _schema_error(i, label, f"duplicate label (also used by source #{seen_labels[label]})")
        seen_labels[label] = i
        parsed.append((label, repo_root, homes))
    return parsed


def _syntax_error(config_path: Path, error: "tomllib.TOMLDecodeError") -> ConfigSyntaxError:
    """Build our own error from tomllib's, naming the line when possible.

    spec-019 T3.2 (maintainer ruling, correcting an earlier `getattr`-first
    design): the line number is read ONLY from `str(error)`, via regex --
    `TOMLDecodeError.lineno` is deliberately never touched, not even as a
    preferred path with a text fallback. Measuring both interpreters this
    task must run under found the two are NOT "attribute present vs
    attribute absent with the same value" -- `.lineno` exists only on
    Python 3.14+ (cpython gh-126175) and, for an end-of-document error, it
    returns a line number (e.g. `2`) even though that same error's own
    MESSAGE says "at end of document" and names no line at all. Preferring
    the attribute when present would make this function's output depend on
    which interpreter runs it for the identical malformed input --
    reintroducing, inside the fix for it, the exact locally-green/CI-red
    split this whole function exists to prevent. The message text, by
    contrast, was measured byte-identical between 3.11.14 and 3.14.3 for
    every malformed-document shape tried. Do NOT "simplify" this to
    `error.lineno` -- see
    `test_malformed_toml_at_end_of_document_has_no_lineno`, which pins the
    case that distinguishes the two designs.

    `None` is a legitimate, real result on BOTH interpreters: "at end of
    document" is a genuine TOML error shape tomllib produces when nothing
    follows an `=`, not a version artifact of either Python.
    """
    match = _SYNTAX_LINE_RE.search(str(error))
    lineno = int(match.group(1)) if match else None
    if lineno is None:
        message = f"{config_path}: TOML syntax error (could not determine the line): {error}"
    else:
        message = f"{config_path}: TOML syntax error at line {lineno}: {error}"
    return ConfigSyntaxError(message, lineno=lineno)


# ---------------------------------------------------------------------------
# Public entry point.
# ---------------------------------------------------------------------------


def load_sources(config_path: Path, *, default_home: Path) -> list[Source]:
    """Load, validate and classify every source in `config_path`.

    An absent config file is not an error: returns `[]`, which the caller
    (`report.py`, T3.3) reads as "fall back to single-record behaviour" --
    deciding that fallback is the caller's job, not this function's.

    `default_home` stands in for the real `$HOME` when a source omits
    `homes` ("no `homes` -- the real $HOME applies", SDD/Interface
    Specifications). Passed explicitly rather than read from `Path.home()`
    internally, matching `report.py`'s own convention of taking every path
    as an argument so the module stays pure and testable without a real
    session (see `report.py`'s module docstring, ADR-6).
    """
    if not config_path.is_file():
        return []

    try:
        doc = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        raise _syntax_error(config_path, e) from e

    parsed = _parse_document(doc)

    sources: list[Source] = []
    for label, repo_root, homes in parsed:
        effective_homes = homes or [default_home]
        statuses = [HomeStatus(home=h, state=_classify_home(repo_root, h)) for h in effective_homes]
        sources.append(Source(label=label, repo_root=repo_root, homes=statuses))
    return sources
