"""The observability README must document the denials report's limits (spec-024 F7).

Why this exists: the report prints `not observable ... (see README "Denials")`
and a pointer that resolves to nothing, or a part that omits a category the code
emits, tells a reader less than the report does. The code's own `TABLE` and
`NOT_OBSERVABLE` are the source of truth; this test pins the README to them.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts" / "observability"))

import denials  # noqa: E402  (sys.path must be extended first)

README = REPO_ROOT / "plugins" / "tcs-helper" / "scripts" / "observability" / "README.md"
EXAMPLE = REPO_ROOT / "scripts" / "observability" / "observability-sources.toml.example"


def _denials_part() -> str:
    """The README text under the exact heading `## Denials`, up to the next `## `."""
    text = README.read_text(encoding="utf-8")
    match = re.search(r"^## Denials\n(.*?)(?=^## |\Z)", text, re.MULTILINE | re.DOTALL)
    assert match, 'README has no "## Denials" heading, so the report\'s pointer resolves to nothing'
    return re.sub(r"\s+", " ", match.group(1))  # line wraps must not split a phrase


def test_denials_part_names_every_category_and_unattributed():
    part = _denials_part()
    categories = {row.category for row in denials.TABLE}
    missing = sorted(c for c in categories | {"unattributed"} if c not in part)
    assert not missing, f"README Denials part does not name: {missing}"


def test_denials_part_names_every_hook_owner_in_the_table():
    part = _denials_part()
    owners = {row.hook for row in denials.TABLE if row.hook}
    missing = sorted(o for o in owners if o not in part)
    assert not missing, f"README Denials part does not name hook owners: {missing}"


def test_denials_part_lists_each_not_observable_item():
    part = _denials_part().lower()
    for needle in ("settings deny rules", "ask prompt", "transcripts were removed", "no tool error"):
        assert needle in part, f"README Denials part lacks the not-observable item: {needle}"
    assert "not proof" in part


def test_denials_part_states_how_to_enable_and_that_it_stays_local():
    part = _denials_part()
    assert "denials = true" in part
    assert "never prints" in part and "leaves the machine" in part
    assert "--denials-weeks" in part and "--denials-since" in part


def test_denials_part_states_the_known_limits():
    part = _denials_part()
    for needle in ("2.1.71", "2.1.332", "overrides.jsonl.1", "same folder name", "worktree"):
        assert needle in part, f"README Denials part lacks the known limit: {needle}"


def test_checked_versions_in_readme_match_the_code():
    low, high = denials.CHECKED_VERSIONS
    part = _denials_part()
    assert ".".join(map(str, low)) in part and ".".join(map(str, high)) in part


def test_example_config_carries_a_commented_denials_line():
    lines = EXAMPLE.read_text(encoding="utf-8").splitlines()
    assert any(re.match(r"^#\s*denials\s*=\s*true\b", line) for line in lines)
