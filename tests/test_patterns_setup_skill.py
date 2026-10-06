"""T5.1 (spec-020): the patterns-setup skill's SKILL.md.

The skill is Markdown, so what is under test is its text: the frontmatter a
YAML parser must accept, the four verbs as sequences of `lib/cli.py` calls,
the handling it prescribes for each CLI exit code, the three gated questions'
option lists, and the honesty clauses of the proposal and the outcome report
`[ref: plan/phase-5.md, T5.1; SDD/Process contract: the skills; SDD/Process
contract: the CLI the skill drives]`.

These tests pin that the instructions are *present*. They cannot show the
instructions are *followable*; T5.1's walkthrough is what does that.

`outcomes.GATE_SETTLED_PATTERNS` supplies the expected option lists: the text
of SKILL.md is what is under test, and a hand-copied list in the skill that
drifts from the library's gate table is exactly the defect to catch.
"""

from __future__ import annotations

import importlib
import re
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = REPO_ROOT / "plugins" / "tcs-patterns" / "skills" / "patterns-setup"
SKILL_MD = SKILL_DIR / "SKILL.md"
LIB_DIR = SKILL_DIR / "lib"

VERBS = ("install", "update", "remove", "status")


def _text() -> str:
    assert SKILL_MD.is_file(), f"{SKILL_MD} does not exist"
    return SKILL_MD.read_text(encoding="utf-8")


def _frontmatter() -> dict:
    text = _text()
    assert text.startswith("---\n"), "SKILL.md has no opening frontmatter delimiter"
    end = text.index("\n---", 4)
    parsed = yaml.safe_load(text[4:end])
    assert isinstance(parsed, dict), "frontmatter did not parse to a mapping"
    return parsed


def _body() -> str:
    text = _text()
    return text[text.index("\n---", 4) + 4 :]


def _section(heading_pattern: str) -> str:
    """The text under the first `###` heading matching `heading_pattern`, up to
    the next `##`/`###` heading. `####` sub-headings stay inside the section."""
    body = _body()
    m = re.search(rf"^### [^\n]*{heading_pattern}[^\n]*$", body, re.M)
    assert m, f"no ### heading matching {heading_pattern!r}"
    rest = body[m.end() :]
    nxt = re.search(r"^#{2,3} ", rest, re.M)
    return rest[: nxt.start()] if nxt else rest


def _verb_section(verb: str) -> str:
    return _section(rf"\b{verb}\b")


def _constraint_list(label: str) -> str:
    body = _body()
    m = re.search(rf"^\*\*{label}:\*\*\n((?:- .*\n?|  .*\n?)+)", body, re.M)
    assert m, f"no **{label}:** list"
    return m.group(1)


def _require_in_order(text: str, *needles: str) -> None:
    pos = 0
    for needle in needles:
        found = text.find(needle, pos)
        assert found >= 0, f"{needle!r} missing, or not after the previous step"
        pos = found + len(needle)


def _gate_patterns() -> dict[str, frozenset[str]]:
    if str(LIB_DIR) not in sys.path:
        sys.path.insert(0, str(LIB_DIR))
    return importlib.import_module("outcomes").GATE_SETTLED_PATTERNS


# --- frontmatter --------------------------------------------------------------


def test_frontmatter_parses_with_a_yaml_parser() -> None:
    """A clause ending in `: ` inside an unquoted value makes YAML read it as a
    key; `claude plugin validate` passed ten descriptions broken that way."""
    fm = _frontmatter()
    assert fm["name"] == "patterns-setup"
    assert fm["user-invocable"] is True
    assert fm["argument-hint"] == "<install|update|remove|status> [path]"
    assert isinstance(fm["description"], str) and fm["description"].strip()


def test_description_is_a_routing_contract() -> None:
    """Names the situation it is for, and the neighbouring skill it is not:
    the catalogue reader serves a pattern without installing it."""
    description = _frontmatter()["description"]
    lowered = description.lower()
    assert lowered.startswith("use when")
    assert "repository" in lowered or "repo" in lowered
    assert "install" in lowered and "pattern" in lowered
    assert "tcs-patterns:pattern" in description, "must name the catalogue reader it is not"
    assert len(description) <= 400, f"description is {len(description)} chars; the listing is budgeted"


def test_persona_announces_the_active_skill() -> None:
    assert "**Active skill: tcs-patterns:patterns-setup**" in _body()


# --- the CLI, and only the CLI --------------------------------------------------


def test_locates_the_cli_from_the_skill_base_directory_with_a_numeric_fallback() -> None:
    body = _body()
    assert "Base directory for this skill" in body
    assert "lib/cli.py" in body
    assert "sort -V" in body, "the cache fallback must compare versions numerically (2.10 > 2.9)"


def test_never_imports_inlines_or_rederives_library_code() -> None:
    body = _body()
    assert not re.search(r"\bimport\s+(detect|install|guard|manifest|outcomes|companions|status|paths)\b", body)
    assert not re.search(r"\bfrom\s+(detect|install|guard|manifest|outcomes|companions|status|paths)\s+import\b", body)
    assert "python3 -c" not in body
    assert "CLAUDE_PLUGIN_ROOT}" not in body, "the variable is empty in a Bash-tool subprocess"


def test_every_cli_exit_code_has_a_stated_handling() -> None:
    """Consistent with the SDD's exit-code table: 0 renders the JSON; 1 is a
    defect in the CLI; 2 a defect in the skill; 3 a refusal whose stderr names
    the resolution. 1-3 show stderr and stop."""
    rows = {m.group(1): m.group(0) for m in re.finditer(r"^\| *`?([0-3])`? *\|.*$", _body(), re.M)}
    assert set(rows) == {"0", "1", "2", "3"}, f"exit-code rows found: {sorted(rows)}"
    assert "render" in rows["0"].lower()
    assert "defect in the cli" in rows["1"].lower()
    assert "defect in the skill" in rows["2"].lower()
    for code in "123":
        assert "stderr" in rows[code].lower(), f"exit {code} must show stderr"
        assert "stop" in rows[code].lower(), f"exit {code} must stop"


# --- the four verbs as CLI call sequences -----------------------------------------


@pytest.mark.parametrize("verb", VERBS)
def test_every_verb_is_documented(verb: str) -> None:
    assert f'{verb} "<repo>"' in _verb_section(verb)


def test_install_is_scan_ask_rescan_confirm_install() -> None:
    section = _verb_section("install")
    _require_in_order(
        section,
        'scan "<repo>"\n',
        'scan "<repo>" --answers',
        'install "<repo>"',
    )
    assert "confirm" in section.lower()


def test_update_runs_update_then_accepts_each_approved_diff() -> None:
    section = _verb_section("update")
    _require_in_order(section, 'update "<repo>"', "declined", "diff", 'update "<repo>" --accept')


def test_remove_asks_before_force_on_a_divergence() -> None:
    section = _verb_section("remove")
    _require_in_order(section, 'remove "<repo>"', "diverged", "ask", "--force")


def test_status_relays_unknown_and_debris_resolutions() -> None:
    section = _verb_section("status")
    assert 'status "<repo>"' in section
    assert "UNKNOWN" in section
    assert "debris" in section and "resolution" in section
    assert "verbatim" in section.lower()


def test_path_defaults_to_the_working_directory_and_the_toplevel_is_reused() -> None:
    body = _body()
    assert "working directory" in body
    assert "`repo`" in body, "later calls use the toplevel the CLI reported"


# --- install: aborts, the questions, the proposal --------------------------------


def test_outside_a_git_repository_install_aborts_before_anything() -> None:
    """The first CLI call is `scan`; its exit 3 stops the skill before any
    question is asked or anything is proposed."""
    section = _verb_section("install")
    assert "not inside a git repository" in _body()
    m = re.search(r"exit(?: code)? 3[^\n]*", section, re.I)
    assert m and "stop" in m.group(0).lower() and "before" in m.group(0).lower()


def test_unreadable_paths_are_shown() -> None:
    section = _verb_section("install")
    assert "`unreadable`" in section
    assert "could not read" in section


def test_question_option_lists_equal_the_gate_table() -> None:
    expected = _gate_patterns()
    body = _body()
    for gate, patterns in expected.items():
        row = re.search(rf"^\| *`{gate}` *\|.*$", body, re.M)
        assert row, f"no question row for {gate}"
        named = set(re.findall(r"`([a-z0-9-]+)`", row.group(0))) - {gate}
        assert named == set(patterns), f"{gate}: {sorted(named ^ set(patterns))} differ"


def test_at_most_three_questions_closed_gates_skipped_multiple_answers() -> None:
    section = _verb_section("install").lower()
    assert "three" in section
    assert "closed" in section and "never ask" in section
    assert "any number" in section or "multiple" in section


def test_proposal_shows_per_entry_listing_cost_and_baseline_separately() -> None:
    section = _verb_section("install")
    assert "`listing_cost`" in section
    assert "characters" in section
    assert "unknown" in section, "a null cost renders as unknown, never 0"
    assert "`baseline`" in section and "not as a recommendation" in section


def test_unrecognised_stack_is_said_plainly() -> None:
    assert "`unrecognised_stack`" in _verb_section("install")


def test_outcome_report_distinguishes_not_reached_from_excluded_by_stack_fact() -> None:
    section = _verb_section("install")
    assert "`not_reached`" in section and "`excluded_by_stack_fact`" in section
    assert "does not apply" in section, "excluded: a statement about the repository"
    assert "were not asked" in section, "not reached: a statement about the detection"


def test_companions_offered_individually_with_their_citation() -> None:
    section = _verb_section("install")
    assert "`companions.proposed`" in section
    assert "`source_file`" in section and "`line`" in section
    assert "individually" in section.lower()


def test_declined_question_pattern_proposed_as_companion_is_named_as_such() -> None:
    section = _verb_section("install")
    assert "you declined" in section and "cites it" in section


def test_declined_intermediate_companion_is_handled_honestly() -> None:
    """The closure informs rather than guarantees: declining an intermediate
    companion still ships a dangling citation, and the skill must not promise
    otherwise."""
    body = _body()
    assert "dangl" in _verb_section("install")
    never = _constraint_list("Never")
    for m in re.finditer(r"[^\n]*\bwill resolve\b[^\n]*", body):
        assert m.group(0).lstrip("- ") in never, f"promise outside the Never list: {m.group(0)!r}"
    assert "resolve" in never


def test_commit_is_offered_and_never_performed_unasked() -> None:
    section = _verb_section("install")
    assert "offer" in section.lower() and "commit" in section.lower()
    assert "not committed" in section.lower() or "did not commit" in section.lower()
    never = _constraint_list("Never").lower()
    assert "commit" in never


def test_install_refusals_report_both_locations() -> None:
    section = _verb_section("install")
    assert "`refused`" in section and "`intended_path`" in section and "`path`" in section
