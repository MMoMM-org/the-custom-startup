"""Where this plugin lives, and the names its writers leave behind (spec-020 T5.1a).

A leaf module: it imports nothing from its siblings, and both the writer
(`install.py`, `manifest.py`) and the read-only `status.py` import it, so the
reader classifies debris by the writer's own constants rather than a second
copy of them `[ref: SDD/Interface Specifications/Process contract: the CLI the
skill drives, status, "A leaf module, lib/paths.py"]`.

**No I/O at import.** Every value below is a path expression or a string
literal. Loaded from a copy whose `parents[3]` resolves to nowhere real, the
paths are wrong but nothing raises -- the property `manifest.py`, `guard.py`,
`detect.py` and `install.py` already keep, so a mutation harness can load any
of them with `importlib.util.spec_from_file_location`. `PLUGIN_JSON` is a path;
reading it is `install._bundle_version()`'s job, lazily, when a value is
needed.

`scripts/patterns_drift.py` deliberately keeps its own `parents[1]`
derivation: it must find `lib/` before it can import anything from it.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[3]
PLUGIN_JSON = PLUGIN_ROOT / ".claude-plugin" / "plugin.json"
DEFAULT_CATALOGUE_DIR = PLUGIN_ROOT / "templates" / "patterns"

# The debris suffixes, each appended to `.<installed_as>` inside
# `.claude/skills/` (and TMP_SUFFIX also ends the manifest's own temp file):
# `.tmp` is a fresh install's staging directory, `.replaced` the stash a
# refresh keeps of the user's directory, `.removing` a pattern `remove` has
# moved aside but not yet deleted.
TMP_SUFFIX = ".tmp"
REPLACED_SUFFIX = ".replaced"
REMOVING_SUFFIX = ".removing"


def sha256_or_none(path: Path) -> str | None:
    """The hex sha256 of `path`'s bytes, or `None` when it cannot be read
    (absent, a directory, permissions) -- callers treat `None` as "differs"
    or "unknown", never as a match."""
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return None
