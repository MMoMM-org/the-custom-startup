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
import re
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


# The catalogue VERSION shape, and the same bound `manifest.py` puts on a
# recorded `version` (ADR-3): a VERSION outside it is one the manifest cannot
# record, and past 4300 digits `int()` raises (PR #176 M1).
_CATALOGUE_VERSION_RE = re.compile(r"^[0-9]{1,9}$")


class CatalogueVersionError(ValueError):
    """A catalogue pattern's `VERSION` is absent, unreadable, or not 1-9
    ASCII digits."""


def read_catalogue_version(catalogue_dir: Path, name: str) -> str:
    """`<catalogue_dir>/<name>/VERSION`, stripped -- the ONE reader the
    installer (`install`, `update`) and `status` share, so the version a
    writer acts on and the one `status` compares can never be read by two
    rules (PR #176 M1). Raises `CatalogueVersionError` for an absent,
    unreadable or undecodable file, or a value outside `^[0-9]{1,9}$`; the
    writers turn that into a per-pattern failure BEFORE anything is
    written, `status` into `None` (its `UNKNOWN`)."""
    path = Path(catalogue_dir) / name / "VERSION"
    try:
        text = path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError) as e:
        raise CatalogueVersionError(f"could not read VERSION for catalogue pattern {name!r}: {e}") from e
    if not _CATALOGUE_VERSION_RE.fullmatch(text):
        shown = text if len(text) <= 40 else text[:40] + "..."
        raise CatalogueVersionError(
            f"catalogue pattern {name!r} has VERSION {shown!r}, which is not 1-9 digits; "
            "nothing was written for it"
        )
    return text
