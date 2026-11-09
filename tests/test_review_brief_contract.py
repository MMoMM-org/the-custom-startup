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


def test_brief_scopes_to_the_step_1_boundary_and_files():
    brief = _step(3)
    assert "step 1 boundary" in brief
    assert "changed-file list from step 1" in brief
    assert "ignore every change outside the boundary" in brief


# #258: the boundary was always merge-base(main, HEAD)..HEAD, wrong for a staged
# review and for a PR or branch that is not checked out.

def _target_arms() -> dict:
    block = re.search(r"match \(target\) \{\n(.*?)^\}", _step(1), re.S | re.M)
    assert block
    arms = {}
    for line in block.group(1).splitlines():
        key, _, rule = line.strip().partition("=>")
        arms[key.strip()] = rule
    return arms


def test_step_1_never_derives_the_boundary_from_head():
    step = _step(1)
    assert "merge-base origin/main HEAD" not in step
    assert "git rev-parse HEAD" not in step


def test_step_1_resolves_a_boundary_per_target():
    arms = _target_arms()
    assert set(arms) == {"/^\\d+$/", '"staged"', "containsSlash", "default"}
    assert "headRefOid" in arms["/^\\d+$/"] and "pull/$target/head" in arms["/^\\d+$/"]
    assert "`--cached`" in arms['"staged"'] and "no SHA range" in arms['"staged"']
    assert "git rev-parse $target" in arms["default"]
    assert "merge-base origin/main $target" in arms["default"]


def test_step_1_derives_diff_and_files_from_the_boundary():
    step = _step(1)
    assert "git diff <boundary>" in step
    assert "git diff --name-only <boundary>" in step
