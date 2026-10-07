#!/usr/bin/env python3
"""The tcs-patterns drift reporter (spec-020 T4.2).

    patterns_drift.py <repo> [--catalogue <dir>]

Prints zero or more lines to stdout and exits 0 regardless -- the caller
decides what to do, exactly as `drift_check_hook_bundle` does
`[ref: SDD/Interface Specifications/Process contract: drift reporter]`:

    OK                        manifest present, every installed pattern current
    MISSING                   no manifest, or one that cannot be parsed
    DRIFT:<p>:<inst>:<cat>    installed pattern BEHIND the catalogue
    UNKNOWN:<p>:<inst>        the catalogue cannot account for what is installed:
                              its VERSION is absent or non-numeric, its pattern
                              directory is gone (deleted upstream), or the
                              installed version is AHEAD of it (a rollback)
    UNSUPPORTED:python        Python older than 3.11; nothing else is checked

A pattern name longer than MAX_NAME_LEN is skipped, never printed: the line
reaches the session-start brief verbatim (review M2). A skipped name also
suppresses `OK`, which would claim it current.

Versions compare as integers, so `01` against `1` is current. The rule is
`status.drift_verdict`, and the catalogue read `status.catalogue_version`, both
in `lib/status.py` so that the `status` verb reuses them rather than restating
them (T5.1a); neither is `manifest.is_current`, which `update()` also calls.

Drift is computed from each pattern's own manifest `version`, never from the
manifest's top-level `bundle`: `bundle` records the plugin version that last
WROTE the manifest, so refreshing one pattern advances it while another keeps
older content (decision 9). Catalogue patterns the manifest does not list are
never mentioned (PRD/F7 2nd). Any DRIFT or UNKNOWN line suppresses `OK`.

Python 3.11+, standard library only (ADR-2). The lib and the default catalogue
resolve from this file's own location, so any cwd works.
"""

from __future__ import annotations

import sys
from pathlib import Path

_PLUGIN_ROOT = Path(__file__).resolve().parents[1]
_LIB_DIR = _PLUGIN_ROOT / "skills" / "patterns-setup" / "lib"
DEFAULT_CATALOGUE_DIR = _PLUGIN_ROOT / "templates" / "patterns"
MAX_NAME_LEN = 64
MIN_PYTHON = (3, 11)  # lib/manifest.py imports tomllib

if str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))


def python_supported(version_info: tuple[int, ...] = tuple(sys.version_info)) -> bool:
    """True when `version_info` can run the lib. Checked before any lib import,
    so an old interpreter yields `UNSUPPORTED:python` instead of an ImportError."""
    return tuple(version_info[:2]) >= MIN_PYTHON


def drift_lines(repo_dir: Path, *, catalogue_dir: Path = DEFAULT_CATALOGUE_DIR) -> list[str]:
    """The reporter's stdout lines, sorted by pattern name."""
    # Imported here, not at module level: a missing or broken lib must fail
    # inside main()'s guard (exit 0, empty stdout), never as an import traceback.
    import manifest as manifest_lib

    repo_dir = Path(repo_dir)
    catalogue_dir = Path(catalogue_dir)

    # `read()` maps an absent file to an empty manifest; MISSING keys on the
    # file's absence instead, so a present manifest naming no patterns is OK.
    if not manifest_lib.manifest_path(repo_dir).is_file():
        return ["MISSING"]
    try:
        current = manifest_lib.read(repo_dir)
    except manifest_lib.ManifestUnparseableError:
        return ["MISSING"]

    # Lazy for the same reason as `manifest` above: a lib that has
    # `manifest.py` but not `status.py` must still exit 0 with empty stdout.
    from status import catalogue_version, drift_verdict

    lines: list[str] = []
    skipped = False
    for name in sorted(current.patterns):
        if len(name) > MAX_NAME_LEN:
            skipped = True
            continue
        entry = current.patterns[name]
        catalogue = catalogue_version(catalogue_dir, name)
        verdict = drift_verdict(entry.version, catalogue)
        if verdict == "UNKNOWN":
            lines.append(f"UNKNOWN:{name}:{entry.version}")
        elif verdict == "DRIFT":
            lines.append(f"DRIFT:{name}:{entry.version}:{catalogue}")
    if lines or skipped:
        return lines
    return ["OK"]


def main(argv: list[str]) -> int:
    if not python_supported():
        print("UNSUPPORTED:python")
        return 0
    args = argv[1:]
    catalogue_dir = DEFAULT_CATALOGUE_DIR
    if "--catalogue" in args:
        i = args.index("--catalogue")
        if i + 1 >= len(args):
            print("usage: patterns_drift.py <repo> [--catalogue <dir>]", file=sys.stderr)
            return 0
        catalogue_dir = Path(args[i + 1])
        del args[i : i + 2]
    if len(args) != 1:
        print("usage: patterns_drift.py <repo> [--catalogue <dir>]", file=sys.stderr)
        return 0  # exit 0 regardless; the caller decides
    try:
        for line in drift_lines(Path(args[0]), catalogue_dir=catalogue_dir):
            print(line)
    except Exception as e:  # the contract is exit 0 in every case
        print(f"patterns_drift: {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
