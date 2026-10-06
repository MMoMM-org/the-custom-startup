"""What is installed, at which version, and what has drifted -- read-only (spec-020 T5.1a).

    status(repo_dir, *, catalogue_dir) -> StatusReport
    drift_verdict(installed, catalogue) -> "OK" | "DRIFT" | "UNKNOWN"
    catalogue_version(catalogue_dir, name) -> str | None

The verb the advisory's `UNKNOWN` segment points users to
`[ref: SDD/Interface Specifications/Process contract: the CLI the skill
drives, "status"]`. A module of its own so that "status writes nothing" is
checkable from its source rather than argued: among this plugin's modules it
imports only `manifest` and `paths`, each as a plain `import`, and uses only
`manifest.read`, `_manifest_path`, `ManifestUnparseableError`,
`MANIFEST_FILENAME`, `Manifest` and `PatternEntry`. A test parses this file
with `ast` and fails on anything else, so keep every use spelled
`manifest.<attr>`.

**The drift rule lives here, and the reporter imports it.** `drift_verdict`
and `catalogue_version` were extracted unchanged from
`scripts/patterns_drift.py` (its `_catalogue_version` and the integer
comparison inline in `drift_lines`), so `status` reuses the rule rather than
restating it -- a rule already corrected once (string equality to integers)
is exactly the kind a second copy keeps wrong. `manifest.is_current` stays
string equality, because `update()` calls it; neither function here touches
it.

**An unparseable or unreadable manifest is reported, not raised.** `status`
is the one verb that must still work when the manifest is broken: the
exception's text goes into `manifest_error` verbatim, `patterns` is empty, and
every `tcs-*` directory is `unlisted` `[ref: SDD/Error Handling, "Manifest
present but unparseable"]`.

Stdlib only, Python 3.11 floor `[ref: SDD/ADR-2]`.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import manifest
import paths

_NUMERIC = re.compile(r"^[0-9]+$")


@dataclass(frozen=True)
class Debris:
    """One entry inside `.claude/skills/` that a writer of this plugin left
    behind (or that looks like one). `kind` is `install-tmp`, `replaced`,
    `removing`, `manifest-tmp` or `unknown`; `resolution` is the text the
    skill renders."""

    name: str
    kind: str
    resolution: str


@dataclass(frozen=True)
class PatternStatus:
    """One manifest entry against the catalogue and the working tree.

    `catalogue_version` is `None` when the catalogue `VERSION` is absent,
    unreadable or non-numeric. `diverged` is `None` -- not `False` -- when the
    directory or its `SKILL.md` is absent or unreadable: nothing was compared.
    """

    installed_as: str
    installed_version: str
    catalogue_version: str | None
    state: str
    directory_present: bool
    diverged: bool | None


@dataclass(frozen=True)
class StatusReport:
    """`manifest_state` is `present`, `absent`, `unparseable` or `unreadable`;
    `manifest_error` is `str(exception)`, verbatim, for the last two."""

    manifest_state: str
    manifest_error: str | None
    bundle: str | None
    patterns: dict[str, PatternStatus] = field(default_factory=dict)
    unlisted: tuple[str, ...] = ()
    debris: tuple[Debris, ...] = ()


def catalogue_version(catalogue_dir: Path, name: str) -> str | None:
    """The pattern's catalogue VERSION, or None if absent, unreadable or non-numeric."""
    try:
        text = (Path(catalogue_dir) / name / "VERSION").read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        return None
    return text if _NUMERIC.match(text) else None


def drift_verdict(installed: str, catalogue: str | None) -> str:
    """`UNKNOWN` when the catalogue cannot account for what is installed (no
    usable catalogue version, or the installed one is AHEAD, as after a
    rollback); `DRIFT` when installed is behind; else `OK`. Integers
    throughout, so `01` against `1` is current
    `[ref: SDD/Process contract: drift reporter (C7)]`."""
    if catalogue is None or int(installed) > int(catalogue):
        return "UNKNOWN"
    if int(installed) < int(catalogue):
        return "DRIFT"
    return "OK"


def _resolution_for(
    kind: str, pattern: str, installed_as: str, *, directory_present: bool, finishable: bool
) -> str:
    """The resolution column of the SDD's debris table."""
    if kind == "install-tmp":
        return f"safe to delete; the next `install` of {pattern} deletes it itself"
    if kind == "replaced":
        if directory_present:
            return f"safe to delete; a refresh or a successful `remove {pattern}` also deletes it"
        return f"this is your copy of {pattern}; move it back to {installed_as}/"
    # kind == "removing"
    if finishable:
        return f"run `remove {pattern}` to finish"
    return "safe to delete"


_DEBRIS_SUFFIXES = (
    (paths.TMP_SUFFIX, "install-tmp"),
    (paths.REPLACED_SUFFIX, "replaced"),
    (paths.REMOVING_SUFFIX, "removing"),
)


def _classify(name: str, skills_root: Path, listed: dict[str, "manifest.PatternEntry"]) -> Debris | None:
    """`None` when `name` is not debris at all."""
    manifest_tmp_prefix = "." + manifest.MANIFEST_FILENAME + "."
    if name.startswith(manifest_tmp_prefix) and name.endswith(paths.TMP_SUFFIX):
        return Debris(
            name=name,
            kind="manifest-tmp",
            resolution="safe to delete; a manifest write was interrupted before its rename, "
            "and the manifest itself is intact",
        )
    if not name.startswith(".tcs-") or name == manifest.MANIFEST_FILENAME:
        return None

    for suffix, kind in _DEBRIS_SUFFIXES:
        if not name.endswith(suffix):
            continue
        installed_as = name[1 : -len(suffix)]  # ".tcs-<p><suffix>" -> "tcs-<p>"
        pattern = installed_as[len("tcs-") :]
        if not pattern:
            break
        directory_present = (skills_root / installed_as).is_dir()
        entry = listed.get(pattern)
        finishable = entry is not None and entry.installed_as == installed_as and not directory_present
        return Debris(
            name=name,
            kind=kind,
            resolution=_resolution_for(
                kind, pattern, installed_as, directory_present=directory_present, finishable=finishable
            ),
        )
    return Debris(name=name, kind="unknown", resolution="not a name this tool writes; left alone")


def _entries(skills_root: Path) -> list[str]:
    try:
        return sorted(os.listdir(skills_root))
    except (FileNotFoundError, NotADirectoryError):
        return []


def status(repo_dir: Path, *, catalogue_dir: Path = paths.DEFAULT_CATALOGUE_DIR) -> StatusReport:
    """Report the manifest, each listed pattern, the unlisted `tcs-*`
    directories and the debris in `<repo_dir>/.claude/skills/`. Writes
    nothing."""
    repo_dir = Path(repo_dir)
    manifest_path = manifest._manifest_path(repo_dir)
    skills_root = manifest_path.parent

    manifest_error: str | None = None
    current: manifest.Manifest | None = None
    if not manifest_path.is_file():
        manifest_state = "absent"
    else:
        try:
            current = manifest.read(repo_dir)
            manifest_state = "present"
        except manifest.ManifestUnparseableError as e:
            manifest_state, manifest_error = "unparseable", str(e)
        except OSError as e:
            manifest_state, manifest_error = "unreadable", str(e)

    listed: dict[str, manifest.PatternEntry] = dict(current.patterns) if current is not None else {}

    patterns: dict[str, PatternStatus] = {}
    for name in sorted(listed):
        entry = listed[name]
        directory = skills_root / entry.installed_as
        directory_present = directory.is_dir()
        installed_hash = paths.sha256_or_none(directory / "SKILL.md") if directory_present else None
        cat_version = catalogue_version(catalogue_dir, name)
        patterns[name] = PatternStatus(
            installed_as=entry.installed_as,
            installed_version=entry.version,
            catalogue_version=cat_version,
            state=drift_verdict(entry.version, cat_version),
            directory_present=directory_present,
            diverged=None if installed_hash is None else installed_hash != entry.sha256,
        )

    owned = {entry.installed_as for entry in listed.values()}
    names = _entries(skills_root)
    unlisted = tuple(
        n for n in names if n.startswith("tcs-") and n not in owned and (skills_root / n).is_dir()
    )
    debris = tuple(d for d in (_classify(n, skills_root, listed) for n in names) if d is not None)

    return StatusReport(
        manifest_state=manifest_state,
        manifest_error=manifest_error,
        bundle=current.bundle if current is not None else None,
        patterns=patterns,
        unlisted=unlisted,
        debris=debris,
    )
