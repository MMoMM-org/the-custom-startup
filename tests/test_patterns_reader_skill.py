"""T5.2 (spec-020): the catalogue reader skill's SKILL.md.

Markdown, so the text is what is under test: frontmatter, the read-only tool
grant, how the catalogue is located, the name check that precedes any path,
and the three outcomes (known, unknown, invalid)
`[ref: plan/phase-5.md, T5.2; PRD/F10; SDD/Process contract: the skills]`.
The walkthrough, not these tests, shows the instructions are followable.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN = REPO_ROOT / "plugins" / "tcs-patterns"
SKILL_MD = PLUGIN / "skills" / "pattern" / "SKILL.md"
CATALOGUE = PLUGIN / "templates" / "patterns"

WRITE_TOOLS = ("Write", "Edit", "NotebookEdit", "Bash")


def _text() -> str:
    assert SKILL_MD.is_file(), f"{SKILL_MD} does not exist"
    return SKILL_MD.read_text(encoding="utf-8")


def _frontmatter() -> dict:
    text = _text()
    assert text.startswith("---\n"), "no opening frontmatter delimiter"
    end = text.index("\n---", 4)
    parsed = yaml.safe_load(text[4:end])
    assert isinstance(parsed, dict)
    return parsed


def _body() -> str:
    text = _text()
    return text[text.index("\n---", 4) + 4 :]


def test_frontmatter_parses_with_name_and_invocation():
    fm = _frontmatter()
    assert fm["name"] == "pattern"
    assert fm["user-invocable"] is True
    assert fm["argument-hint"] == "<pattern-name>"


def test_allowed_tools_grant_nothing_write_capable():
    granted = str(_frontmatter()["allowed-tools"])
    for tool in WRITE_TOOLS:
        assert not re.search(rf"\b{tool}\b", granted), f"{tool} granted"
    assert "Read" in granted and "Glob" in granted


def test_description_routes_and_names_its_neighbour():
    desc = _frontmatter()["description"]
    assert re.search(r"without installing", desc)
    assert "tcs-patterns:patterns-setup" in desc
    assert len(desc) <= 400


def test_catalogue_located_from_base_directory_with_fallbacks():
    body = _body()
    assert "Base directory for this skill" in body
    assert "../../templates/patterns/" in body
    assert "sort -V" in body or "numerically" in body
    assert ".claude/plugins/cache" in body
    assert "plugins/tcs-patterns/templates/patterns" in body
    assert "not installed" in body


def _section(heading: str) -> str:
    """The workflow step whose `### N. <heading>` title matches, up to the next heading."""
    body = _body()
    workflow = body[body.index("## Workflow") :]
    match = re.search(rf"^### \d+\. {re.escape(heading)}\n", workflow, re.M)
    assert match, f"no workflow step titled {heading!r}"
    rest = workflow[match.end() :]
    nxt = re.search(r"^##+ ", rest, re.M)
    return rest[: nxt.start()] if nxt else rest


def _never_block() -> str:
    body = _body()
    start = body.index("**Never:**")
    end = body.index("\n## ", start)
    return body[start:end]


def test_name_validated_before_any_path_is_built():
    validate = _section("Validate the name")
    read = _section("Show a known name")
    assert "^[a-z0-9-]+$" in validate
    assert "No path has been built" in validate
    assert "<catalogue>/<name>/SKILL.md" not in validate
    assert "<catalogue>/<name>/SKILL.md" in read
    body = _body()
    assert body.index("### 3. Validate the name") < body.index("### 4. Show a known name")


def test_known_name_shows_full_body_and_lists_companion_files():
    known = _section("Show a known name")
    assert "show the whole file" in known
    assert "list the names of the" in known
    assert "`reference/`" in known and "`examples/`" in known
    assert "Show the pattern's body verbatim and in full." in _body()


def test_unknown_or_invalid_name_lists_available_never_empty():
    body = _body()
    assert "unknown   // name is well formed but not in the catalogue: available names listed" in body
    assert "invalid   // name fails the check: available names listed" in body
    listing = _section("List the available names")
    assert "every available name" in listing
    assert (
        "- Answer an unknown or invalid name with an empty result or silence (never empty)."
        in _never_block()
    )
    assert "- Answer an unknown or invalid name with the available names, whatever their count." in body


def test_never_rule_writes_nothing():
    never = _never_block()
    assert "- Write, create, edit, install or delete anything." in never
    assert "- Build a path from a name that has not passed the check." in never
    assert "- Summarise or trim a pattern body." in never


def test_catalogue_has_exactly_21_directories():
    dirs = sorted(p for p in CATALOGUE.iterdir() if p.is_dir())
    assert len(dirs) == 21
    for d in dirs:
        assert (d / "SKILL.md").is_file(), d
        assert re.fullmatch(r"[a-z0-9-]+", d.name)
