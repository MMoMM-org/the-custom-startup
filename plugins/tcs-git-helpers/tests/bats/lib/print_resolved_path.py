"""Print git_status_audit.py's resolved paths, for cache-path-parity.bats.

Kept as a committed file rather than an inline `python3 -c` on purpose: the
repo's shell is zsh, which rewrites `!` even inside quoted heredocs, and nested
quoting through bats -> bash -> python is the exact shape that breaks.

Usage:
    python3 print_resolved_path.py cache   # the cache directory
    python3 print_resolved_path.py data    # its parent, the plugin data directory

Resolution follows the caller's CWD and environment, so run it from inside the
git repository under test.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

import git_status_audit as gsa  # noqa: E402


def main() -> int:
    what = sys.argv[1] if len(sys.argv) > 1 else "cache"
    data_dir = gsa._plugin_data_dir()
    if what == "data":
        print(data_dir)
    elif what == "cache":
        print(gsa._cache_dir(data_dir))
    else:
        print(f"unknown selector: {what}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
