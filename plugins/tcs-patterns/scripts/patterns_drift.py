#!/usr/bin/env python3
"""The tcs-patterns drift reporter (spec-020 T4.2).

    patterns_drift.py <repo> [--catalogue <dir>]

Prints zero or more lines to stdout and exits 0 regardless -- the caller
decides what to do, exactly as `drift_check_hook_bundle` does
`[ref: SDD/Interface Specifications/Process contract: drift reporter]`:

    OK                        manifest present, every installed pattern current
    MISSING                   no manifest, or one that cannot be parsed
    DRIFT:<p>:<inst>:<cat>    installed pattern behind the catalogue
    UNKNOWN:<p>:<inst>        catalogue VERSION absent or non-numeric

Drift is computed from each pattern's own manifest `version`, never from the
manifest's top-level `bundle`: `bundle` records the plugin version that last
WROTE the manifest, so refreshing one pattern advances it while another keeps
older content (decision 9). Catalogue patterns the manifest does not list are
never mentioned (PRD/F7 2nd). Any DRIFT or UNKNOWN line suppresses `OK`.

Python 3.11+, standard library only (ADR-2). The lib and the default catalogue
resolve from this file's own location, so any cwd works.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_PLUGIN_ROOT = Path(__file__).resolve().parents[1]
_LIB_DIR = _PLUGIN_ROOT / "skills" / "patterns-setup" / "lib"
DEFAULT_CATALOGUE_DIR = _PLUGIN_ROOT / "templates" / "patterns"

if str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))

import manifest as manifest_lib  # noqa: E402

_NUMERIC = re.compile(r"^[0-9]+$")


def _catalogue_version(catalogue_dir: Path, name: str) -> str | None:
    """The pattern's catalogue VERSION, or None if absent, unreadable or non-numeric."""
    try:
        text = (catalogue_dir / name / "VERSION").read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        return None
    return text if _NUMERIC.match(text) else None


def drift_lines(repo_dir: Path, *, catalogue_dir: Path = DEFAULT_CATALOGUE_DIR) -> list[str]:
    """The reporter's stdout lines, sorted by pattern name."""
    repo_dir = Path(repo_dir)
    catalogue_dir = Path(catalogue_dir)

    # `read()` maps an absent file to an empty manifest; MISSING keys on the
    # file's absence instead, so a present manifest naming no patterns is OK.
    if not manifest_lib._manifest_path(repo_dir).is_file():
        return ["MISSING"]
    try:
        current = manifest_lib.read(repo_dir)
    except manifest_lib.ManifestUnparseableError:
        return ["MISSING"]

    lines: list[str] = []
    for name in sorted(current.patterns):
        entry = current.patterns[name]
        catalogue_version = _catalogue_version(catalogue_dir, name)
        if catalogue_version is None:
            lines.append(f"UNKNOWN:{name}:{entry.version}")
        elif not manifest_lib.is_current(entry, catalogue_version):
            lines.append(f"DRIFT:{name}:{entry.version}:{catalogue_version}")
    return lines or ["OK"]


def main(argv: list[str]) -> int:
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
