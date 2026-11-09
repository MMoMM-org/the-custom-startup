"""The review brief must request what synthesis consumes, fence git, and scope the diff.

Why this exists (#251): step 4 deduplicates findings by location and sorts by
severity then confidence, but step 3 never asked reviewers for those fields. The
brief also lacked the read-only git fence implement carries (#156) and the
commit-range scoping from docs/ai/memory/active.md, so reviewers could flag a
teammate's uncommitted work.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / "plugins" / "tcs-workflow" / "skills" / "review" / "SKILL.md"


def _step(number: int) -> str:
    text = SKILL.read_text()
    m = re.search(rf"^### {number}\..*?(?=^### |\Z)", text, re.S | re.M)
    assert m, f"step {number} not found"
    return m.group(0)


def _interface_fields() -> set[str]:
    m = re.search(r"^Finding \{\n(.*?)^\}", SKILL.read_text(), re.S | re.M)
    assert m
    return set(re.findall(r"^\s+(\w+)\??:", m.group(1), re.M))


def test_brief_requests_every_top_level_finding_field():
    brief = _step(3)
    fields = _interface_fields() - {"consumers", "migration"}
    assert {"severity", "confidence", "location"} <= fields
    missing = {f for f in fields if f"`{f}`" not in brief}
    assert not missing, f"brief does not request {sorted(missing)}"


def test_brief_asks_for_an_explicit_empty_result():
    assert "no findings" in _step(3).lower()


def test_brief_fences_git_read_only():
    brief = _step(3)
    for verb in ("stash", "checkout", "reset", "restore", "clean"):
        assert f"`{verb}`" in brief, verb
    assert "git archive" in brief
    assert "CLAUDE_ALLOW_" in brief


def test_brief_scopes_to_range_and_files():
    brief = _step(3)
    assert "$BASE_SHA..$HEAD_SHA" in brief
    assert "--name-only" in brief
    assert "ignore uncommitted changes" in brief
