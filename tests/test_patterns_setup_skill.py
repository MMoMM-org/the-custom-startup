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
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = REPO_ROOT / "plugins" / "tcs-patterns" / "skills" / "patterns-setup"
SKILL_MD = SKILL_DIR / "SKILL.md"
LIB_DIR = SKILL_DIR / "lib"
CLI = LIB_DIR / "cli.py"

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


def _section_between(start: str, end: str) -> str:
    body = _body()
    return body[body.index(start) + len(start) : body.index(end)]


def _constraint_list(label: str) -> str:
    body = _body()
    m = re.search(rf"^\*\*{label}:\*\*\n((?:- .*\n?|  .*\n?)+)", body, re.M)
    assert m, f"no **{label}:** list"
    return m.group(1)


def _companions_item() -> str:
    m = re.search(r"\*\*Companions\*\*.*?(?=\n\d\. \*\*)", _verb_section("install"), re.S)
    assert m, "no Companions item"
    return m.group(0)


def _bash_blocks(text: str) -> list[str]:
    return re.findall(r"```bash\n(.*?)```", text, re.S)


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
    assert "tcs-patterns:pattern" in description, "must name the catalogue reader it is not"
    assert len(description) <= 400, f"description is {len(description)} chars; the listing is budgeted"


def test_persona_announces_the_active_skill() -> None:
    assert "**Active skill: tcs-patterns:patterns-setup**" in _body()


def test_the_only_commands_run_are_the_cli_the_step_1_lookup_and_the_3g_git_commands() -> None:
    """The Persona's claim about which commands run must be literally true:
    it names step 1 and 3g, and every command in a bash block is the CLI, the
    step-1 `find`, or a `git` command in 3g."""
    persona = _section_between("## Persona", "## Interface")
    assert "step 1" in persona and "3g" in persona
    allowed_first = {"python3", "find", "git"}
    body = _body()
    for block in _bash_blocks(body):
        for line in block.splitlines():
            if line.strip():
                assert line.split()[0] in allowed_first, f"unexpected command: {line!r}"
    for block in _bash_blocks(body):
        if "git " in block:
            assert block in _verb_section("install").split("#### 3g.")[1], "a git command outside 3g"
    assert "git rev-parse --show-toplevel" in _section("Locate the CLI")


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


def test_remove_asks_before_discarding_edits_on_a_divergence() -> None:
    section = _verb_section("remove")
    _require_in_order(section, 'remove "<repo>"', "diverged", "ask", 'remove "<repo>" "<p1>" "<p2>" --discard-edits')


def test_remove_shows_the_refusals_diff_before_asking() -> None:
    """Consent is to a loss the user can see (SDD/ADR-4, 2026-10-06): the
    refusal's own `diff` is shown, read as installed -> catalogue, before the
    question. `git diff` shows nothing for an install never committed, so the
    skill must not send the user there instead."""
    section = _verb_section("remove")
    _require_in_order(section, "`refused`", "`diff`", "`diff` block", "`-` lines", "ask")
    assert "git diff" not in section and 'git -C "<repo>" diff' not in section


def test_the_old_override_flag_and_its_hook_workaround_are_gone() -> None:
    """The flag was renamed so the path runs from Claude; a leftover mention
    would send the model back to the name a safety hook blocks."""
    text = _text()
    assert "--" + "force" not in text
    assert "hook blocks" not in _verb_section("remove")


def test_the_commit_offer_commits_only_the_paths_the_verb_changed() -> None:
    """SDD/ADR-8, 2026-10-06: stage and commit only the changed paths, never
    the user's other staged work, and never retry a hook refusal."""
    section = _verb_section("install")
    assert "status --porcelain" in section
    assert 'commit -m "chore: <verb> tcs patterns <names>" -- "<path>"' in section
    assert "<verb>` is the verb that ran" in section
    assert "--no-verify" in section and "never retry" in section


def test_status_relays_unknown_and_debris_resolutions() -> None:
    section = _verb_section("status")
    assert 'status "<repo>"' in section
    assert "UNKNOWN" in section
    assert "debris" in section and "resolution" in section
    assert "verbatim" in section.lower()


def test_path_defaults_to_the_working_directory_and_the_toplevel_is_reused() -> None:
    body = _body()
    assert "$ARGUMENTS[1]" in body, "the path argument"
    assert "`repo` field the CLI returned" in _section("Locate the CLI"), (
        "later calls use the toplevel the CLI reported"
    )


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
    never = _constraint_list("Never").lower()
    assert "ask a question whose gate is closed" in never
    assert "more than the three gated questions" in never
    section = _verb_section("install").lower()
    assert "never ask a closed one" in section
    assert '"q2_architecture": []' in section, "a gate answered with none is passed as []"
    assert "including none" in section


def test_proposal_shows_per_entry_listing_cost_and_baseline_separately() -> None:
    section = _verb_section("install")
    assert "`listing_cost`" in section
    assert "characters" in section
    assert "unknown" in section, "a null cost renders as unknown, never 0"
    assert "`baseline`" in section and "not as a recommendation" in section


def test_unrecognised_stack_is_said_plainly() -> None:
    section = _verb_section("install")
    m = re.search(r"- If `unrecognised_stack` is true[^\n]*(?:\n  [^\n]*)*", section)
    assert m, "no unrecognised_stack bullet"
    bullet = m.group(0).lower()
    assert "recommend nothing" in bullet
    assert "do not offer a default selection" in bullet
    assert "`not_reached`" in bullet and "confirmation" in bullet, (
        "every gate is shut here; the not-reached report must still be shown"
    )
    assert "skip this screen" in section, "no open gate, no question screen"
    assert "'{}'" in section, "no open gate: the re-scan passes an empty object"


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


def test_companions_are_priced_from_the_scan() -> None:
    item = _companions_item()
    assert "`listing_cost`" in item and "unknown" in item


def test_remove_discards_several_approved_patterns_in_one_call() -> None:
    section = _verb_section("remove")
    call = next(b for b in _bash_blocks(section) if "--discard-edits" in b)
    tokens = shlex.split(call.strip().splitlines()[0])
    assert tokens[:3] == ["python3", "<cli>", "remove"] and tokens[3] == "<repo>"
    rest = tokens[4:]
    first_flag = rest.index("--discard-edits")
    positional = rest[:first_flag]
    discarded = [rest[i + 1] for i, tok in enumerate(rest) if tok == "--discard-edits"]
    assert len(positional) >= 2 and len(discarded) >= 2, "several patterns in one call"
    assert set(discarded) == set(positional), "the CLI exits 2 on a discard name that is not positional"
    assert "exits 2" in section.lower()


def test_commit_message_verb_follows_the_verb_that_ran() -> None:
    assert "chore: install tcs patterns" not in _text()
    for verb in ("update", "remove"):
        section = _verb_section(verb)
        assert "3g" in section and f"`<verb>` is `{verb}`" in section


def test_declined_question_pattern_proposed_as_companion_is_named_as_such() -> None:
    section = _verb_section("install")
    item = _companions_item()
    assert "`declined_by_question`" in item and "you declined" in item


def test_declined_intermediate_companion_is_handled_honestly() -> None:
    """The closure informs rather than guarantees: declining an intermediate
    companion still ships a dangling citation, and the skill must not promise
    otherwise."""
    body = _body()
    assert "dangling" in _companions_item()
    never = _constraint_list("Never")
    for m in re.finditer(r"[^\n]*\bwill resolve\b[^\n]*", body):
        assert m.group(0).lstrip("- ") in never, f"promise outside the Never list: {m.group(0)!r}"


def test_commit_is_offered_and_never_performed_unasked() -> None:
    section = _verb_section("install")
    assert "not committed" in section.lower()
    never = _constraint_list("Never").lower()
    assert "commit" in never and "yes" in never


def test_install_refusals_report_both_locations() -> None:
    section = _verb_section("install")
    paragraph = next(p for p in section.split("\n\n") if "`refused`" in p)
    assert "`intended_path`" in paragraph and "`path`" in paragraph and "`namespace`" in paragraph


# --- review round: remove's names, quoting, the commit paths, the selection ---------


def test_remove_names_are_checked_before_they_reach_a_shell() -> None:
    """`remove` is the only verb whose names come from the user. Step 5 states
    where a name may come from, the regex it must match, and what to do with
    anything else."""
    section = _verb_section("remove")
    assert "^[a-z0-9-]+$" in section
    assert "`patterns`" in section and "`status`" in section
    assert "never pass" in section.lower()
    # the rule is stated before the first call that carries the names
    assert section.index("^[a-z0-9-]+$") < section.index('remove "<repo>"')


def test_every_placeholder_in_a_cli_or_git_call_is_quoted() -> None:
    """A name, path or repo in an unquoted shell position is an injection point."""
    placeholder = re.compile(r"<(?:repo|cli|pattern|p\d|path)>")
    calls = 0
    for block in _bash_blocks(_body()):
        for line in block.splitlines():
            if not line.startswith(("python3 ", "git ")):
                continue
            calls += 1
            for m in placeholder.finditer(line):
                assert line[m.start() - 1] == '"' and line[m.end()] == '"', f"unquoted {m.group(0)} in {line!r}"
    assert calls >= 8
    # the inline status call of 3g too
    inline = re.search(r"`(git -C [^`]*status --porcelain[^`]*)`", _verb_section("install"))
    assert inline, "no inline status call"
    for m in placeholder.finditer(inline.group(1)):
        assert inline.group(1)[m.start() - 1] == '"' and inline.group(1)[m.end()] == '"'


def test_the_commit_offer_runs_one_status_call_over_all_paths_and_skips_an_empty_result() -> None:
    section = _verb_section("install").split("#### 3g.")[1]
    assert re.search(r'status --porcelain -- "<path>" "<path>" \.\.\.', section), "one call, many paths"
    assert "once" in section
    assert "nothing to commit" in section


def test_the_commit_offer_comes_once_after_the_last_install_rerun() -> None:
    section = _verb_section("install")
    assert "3g is offered once, after the last 3f" in section


def test_the_selection_is_the_will_install_names_the_companions_and_the_hand_added() -> None:
    section = _verb_section("install")
    m = re.search(r"The selection passed to `install` is[^.]*\.", section, re.S)
    assert m, "no statement of what the selection is"
    sentence = m.group(0)
    assert "Will install" in sentence and "companions" in sentence and "by hand" in sentence
    assert "`listing_cost`" in section[section.index(sentence) :]


def test_screens_are_counted_before_anything_is_written() -> None:
    assert "Three screens before anything is written" in _verb_section("install")


# --- the field names the skill relies on exist in the real CLI's output ------------

# Typed by hand from SKILL.md. `<n>` stands for a dynamic key (a pattern name).
SKILL_FIELD_PATHS = {
    "repo",
    "report.unrecognised_stack",
    "report.auto",
    "report.auto.pattern",
    "report.auto.evidence",
    "report.baseline",
    "report.unreadable",
    "report.nested_repos",
    "report.gates",
    "report.gate_evidence",
    "listing_cost.<n>",
    "outcomes.installed",
    "outcomes.declined_by_question",
    "outcomes.excluded_by_stack_fact",
    "outcomes.not_reached",
    "companions.proposed.<n>.from",
    "companions.proposed.<n>.target",
    "companions.proposed.<n>.source_file",
    "companions.proposed.<n>.line",
    "companions.ambiguous",
    "installed.<n>.installed_as",
    "unchanged",
    "failed",
    "skipped",
    "refused.<n>.path",
    "refused.<n>.namespace",
    "refused.<n>.intended_path",
    "refused.<n>.reason",
    "refused.<n>.diff",
    "refreshed.<n>.version_before",
    "refreshed.<n>.version_after",
    "refreshed.<n>.installed_as",
    "current",
    "declined.<n>.diff",
    "removed.<n>.installed_as",
    "removed.<n>.directory_existed",
    "manifest.state",
    "manifest.error",
    "patterns.<n>.catalogue_version",
    "patterns.<n>.state",
    "patterns.<n>.diverged",
    "patterns.<n>.directory_present",
    "unlisted",
    "debris.name",
    "debris.kind",
    "debris.resolution",
    "skills_error",
}

_DYNAMIC_MAPS = {
    "listing_cost",
    "companions.proposed",
    "installed",
    "unchanged",
    "failed",
    "refused",
    "refreshed",
    "current",
    "declined",
    "removed",
    "patterns",
}


def _collect(node: object, prefix: str, out: set[str]) -> None:
    if prefix:
        out.add(prefix)
    if isinstance(node, dict):
        for key, value in node.items():
            seg = "<n>" if prefix in _DYNAMIC_MAPS else key
            _collect(value, f"{prefix}.{seg}" if prefix else seg, out)
    elif isinstance(node, list):
        for item in node:
            _collect(item, prefix, out)


def _real_cli_field_paths(tmp: Path) -> set[str]:
    """Run the real CLI through every verb against a fixture and collect every
    key path any document carries."""
    home = tmp / "home"
    home.mkdir()
    cat = tmp / "catalogue"
    bodies = {
        "python-project": "See `reference/hex-guide.md`.\n",
        "hexagonal": "See `reference/fn-guide.md`.\n",
        "functional": "Pure.\n",
        "ddd": "Domain.\n",
        "api-design": "Resources.\n",
    }
    for name, body in bodies.items():
        d = cat / name
        (d / "reference").mkdir(parents=True)
        (d / "VERSION").write_text("1\n", encoding="utf-8")
        (d / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: Fixture {name}\nuser-invocable: true\n---\n\n{body}",
            encoding="utf-8",
        )
    (cat / "hexagonal/reference/hex-guide.md").write_text("h\n", encoding="utf-8")
    (cat / "functional/reference/fn-guide.md").write_text("f\n", encoding="utf-8")
    repo = tmp / "repo"
    repo.mkdir()
    elsewhere = tmp / "elsewhere"
    elsewhere.mkdir()
    env = {**os.environ, "HOME": str(home), "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"}
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True, capture_output=True, env=env)
    (repo / "pyproject.toml").write_text('[project]\nname = "x"\ndependencies = ["fastapi"]\n', encoding="utf-8")
    (repo / "app.py").write_text("print(1)\n", encoding="utf-8")

    found: set[str] = set()

    def run(*args: str) -> dict:
        r = subprocess.run(
            [sys.executable, str(CLI), "--catalogue", str(cat), *args],
            capture_output=True, cwd=elsewhere, env=env,
        )
        assert r.returncode == 0, r.stderr.decode("utf-8", "replace")
        doc = json.loads(r.stdout.decode("utf-8"))
        _collect(doc, "", found)
        return doc

    def skill_md(name: str) -> Path:
        return repo / ".claude" / "skills" / f"tcs-{name}" / "SKILL.md"

    run("scan", str(repo))
    run("scan", str(repo), "--answers", '{"q1_backend": ["api-design"], "q2_architecture": []}')
    # a user-namespace collision for ddd, and a skill the guard cannot read
    taken = home / ".claude" / "skills" / "tcs-ddd"
    taken.mkdir(parents=True)
    (taken / "SKILL.md").write_text("---\nname: tcs-ddd\ndescription: mine\n---\n", encoding="utf-8")
    broken = home / ".claude" / "skills" / "broken"
    broken.mkdir()
    (broken / "SKILL.md").write_text("no frontmatter\n", encoding="utf-8")
    run("install", str(repo), "ddd", "hexagonal")
    shutil.rmtree(taken)
    shutil.rmtree(broken)
    run("install", str(repo), "ddd", "hexagonal")
    run("install", str(repo), "ddd", "hexagonal")  # now unchanged
    (repo / ".claude" / "skills" / "tcs-mine").mkdir()
    (repo / ".claude" / "skills" / ".tcs-ddd.tmp").mkdir()
    run("status", str(repo))
    # the catalogue moves on; ddd is edited locally, hexagonal is not
    for name in ("ddd", "hexagonal"):
        (cat / name / "VERSION").write_text("2\n", encoding="utf-8")
    (cat / "ddd" / "SKILL.md").write_text(
        (cat / "ddd" / "SKILL.md").read_text(encoding="utf-8") + "Upstream.\n", encoding="utf-8"
    )
    skill_md("ddd").write_text(skill_md("ddd").read_text(encoding="utf-8") + "Mine.\n", encoding="utf-8")
    run("update", str(repo))
    run("update", str(repo), "--accept", "ddd")
    skill_md("hexagonal").write_text(skill_md("hexagonal").read_text(encoding="utf-8") + "Edit.\n", encoding="utf-8")
    run("remove", str(repo), "hexagonal")
    run("remove", str(repo), "hexagonal", "--discard-edits", "hexagonal")
    return found


def test_every_field_the_skill_names_appears_in_the_real_cli_output(tmp_path: Path) -> None:
    """The skill reads these fields by name; a rename in the CLI, or a typo in
    the skill, must fail here rather than in a user's session."""
    found = _real_cli_field_paths(tmp_path)
    missing = sorted(SKILL_FIELD_PATHS - found)
    assert not missing, f"fields the skill relies on that the CLI never emitted: {missing}"


def test_the_field_list_is_what_the_skill_text_names() -> None:
    """The hand-typed list must not drift from SKILL.md: every distinctive leaf
    field name in it appears in the skill's text."""
    body = _body()
    leaves = {path.split(".")[-1] for path in SKILL_FIELD_PATHS} - {"<n>", "repo", "line", "from", "target"}
    absent = sorted(leaf for leaf in leaves if not re.search(rf"\b{leaf}\b", body))
    assert not absent, f"field names in the test but not in SKILL.md: {absent}"
