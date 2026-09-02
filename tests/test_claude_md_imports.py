"""Every @-import in a tracked CLAUDE.md must resolve to a file that exists.

Why this exists: root CLAUDE.md imported `@AGENTS.md` for months after that
file had been renamed to FOR-AGENTS.md. Claude Code does not report a broken
import — it loads nothing and carries on — so 11 KB of repository guidance
silently stopped reaching every session and every subagent dispatch. Nobody
noticed until someone read the file (issue #106).

`memory-sync`'s Check 2 already audits this, but it only runs when a human
thinks to run it. This is the same check on every pull request.
"""

import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

# Claude Code's import syntax, in the line-anchored form this repo uses.
IMPORT_RE = re.compile(r"^@(?P<target>\S+)\s*$")


def _tracked_claude_md_files():
    """Git-tracked CLAUDE.md files.

    Deliberately git-tracked rather than a filesystem walk: claude-docker-home/
    is a gitignored local mirror of the plugin cache, and its copies would be
    checked twice and could fail for reasons that have nothing to do with the
    sources.
    """
    out = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files", "*CLAUDE.md", "CLAUDE.md"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return sorted({REPO_ROOT / line for line in out.splitlines() if line})


def _imports(path):
    for lineno, line in enumerate(path.read_text().splitlines(), start=1):
        m = IMPORT_RE.match(line)
        if m:
            yield lineno, m.group("target")


CLAUDE_MD_FILES = _tracked_claude_md_files()


def test_repo_has_claude_md_files():
    """Guard the guard: an extraction bug would otherwise make this suite vacuous."""
    assert CLAUDE_MD_FILES, "found no tracked CLAUDE.md files — the git ls-files query is wrong"


@pytest.mark.parametrize("claude_md", CLAUDE_MD_FILES, ids=lambda p: str(p.relative_to(REPO_ROOT)))
def test_claude_md_imports_resolve(claude_md):
    broken = []
    for lineno, target in _imports(claude_md):
        # ~-prefixed imports point outside the repo at the user's global config
        # (e.g. @~/Kouzou/standards/general.md). Whether those resolve depends
        # on the machine, so they are out of scope here.
        if target.startswith("~"):
            continue
        resolved = (claude_md.parent / target).resolve()
        if not resolved.exists():
            broken.append(f"{claude_md.relative_to(REPO_ROOT)}:{lineno} @{target}")

    assert not broken, "broken @-imports:\n  " + "\n  ".join(broken)
