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


def test_name_validated_before_any_path_is_built():
    body = _body()
    assert "^[a-z0-9-]+$" in body
    assert body.index("^[a-z0-9-]+$") < body.index("<name>/SKILL.md")


def test_known_name_shows_full_body_and_lists_companion_files():
    body = _body()
    assert "<name>/SKILL.md" in body
    assert re.search(r"\bfull\b|\bentire\b|\bcomplete\b", body)
    assert "reference/" in body and "examples/" in body
    assert re.search(r"names? of|list", body)


def test_unknown_or_invalid_name_lists_available_never_empty():
    body = _body()
    assert re.search(r"unknown", body, re.I)
    assert re.search(r"invalid|rejected", body, re.I)
    assert re.search(r"available (pattern )?names", body, re.I)
    assert re.search(r"never (an )?empty|not empty|never .*empty", body, re.I)


def test_never_rule_writes_nothing():
    body = _body()
    never = body[body.index("**Never:**") :]
    assert re.search(r"write|create|install", never, re.I)
    assert "nothing" in body.lower()


def test_catalogue_has_exactly_21_directories():
    dirs = sorted(p for p in CATALOGUE.iterdir() if p.is_dir())
    assert len(dirs) == 21
    for d in dirs:
        assert (d / "SKILL.md").is_file(), d
        assert re.fullmatch(r"[a-z0-9-]+", d.name)
