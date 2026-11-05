"""Tests for prompt_lint.py, the prompt-author lint (spec 023, T1.3, SDD-ADR-5).

Each check E1-E4 and W1-W3 has a positive and a negative fixture under
fixtures/prompt_lint/. Secrets are assembled at runtime from parts, so no
token-shaped string is committed (push protection would reject it, and the
committed fixture uses only AWS's documented example key).
"""
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "plugins/tcs-helper/skills/prompt-author/scripts/prompt_lint.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "prompt_lint"
SEMANTIC_DETECTOR = REPO_ROOT / "plugins/tcs-helper/scripts/lib/semantic_detector.py"


def _load_module():
    if not SCRIPT.is_file():
        pytest.fail("prompt_lint.py does not exist yet: {}".format(SCRIPT))
    spec = importlib.util.spec_from_file_location("prompt_lint_under_test", str(SCRIPT))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def pl():
    return _load_module()


def _run(*args, cwd=None, env=None):
    return subprocess.run(
        [sys.executable, "-I", str(SCRIPT)] + [str(a) for a in args],
        capture_output=True, text=True, cwd=cwd, env=env, timeout=60,
    )


def _findings(pl, name, check=None, kind=None, include_suppressed=False):
    found = pl.lint([str(FIXTURES / name)], kind=kind)
    return [
        f for f in found
        if (check is None or f.check == check) and (include_suppressed or not f.suppressed)
    ]


def _lines(findings):
    return sorted(f.line for f in findings)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

def test_registry_contains_exactly_the_seven_checks(pl):
    assert set(pl.CHECKS) == {"E1", "E2", "E3", "E4", "W1", "W2", "W3"}


def test_errors_and_warnings_have_their_levels_and_catalog_entries(pl):
    expected = {
        "E1": ("error", "PA-19"), "E2": ("error", "PA-18"), "E3": ("error", "PA-30"),
        "E4": ("error", "PA-15"), "W1": ("warning", "PA-03"), "W2": ("warning", "PA-10"),
        "W3": ("warning", "PA-04"),
    }
    assert {cid: (c.level, c.entry) for cid, c in pl.CHECKS.items()} == expected


# ---------------------------------------------------------------------------
# E1 secret
# ---------------------------------------------------------------------------

def _secret_values():
    # Assembled from parts so the source holds no token-shaped literal.
    return {
        "anthropic": "sk-" + "ant-" + "a1B2" * 6,
        "openai": "sk-" + "proj-" + "Z9y8" * 6,
        "google": "AI" + "za" + "A1b2C3d4E5" * 3 + "f6G7h",
        "github-token": "gh" + "p_" + "aB3dE" * 7 + "f",
        "github-pat": "github_" + "pat_" + "Q1w2E3r4T5" * 4 + "y",
        "aws": "AK" + "IA" + "ABCDEFGH" + "23456789",
        "private-key": "-----BEGIN RSA " + "PRIVATE KEY-----",
    }


def test_e1_flags_a_secret_inside_a_fence(pl):
    assert _lines(_findings(pl, "e1_positive.md", "E1")) == [6]


def test_e1_negative_fixture_is_clean(pl):
    assert _findings(pl, "e1_negative.md", "E1") == []


def test_e1_matches_every_pattern_and_never_prints_the_value(tmp_path):
    values = _secret_values()
    target = tmp_path / "brief.md"
    target.write_text("# Brief\n\n" + "\n".join("value: " + v for v in values.values()) + "\n")
    text = _run(target)
    as_json = _run("--json", target)
    assert text.returncode == 1
    data = json.loads(as_json.stdout)
    assert sorted(f["line"] for f in data["findings"] if f["check"] == "E1") == list(range(3, 10))
    for value in values.values():
        assert value not in text.stdout + text.stderr
        assert value not in as_json.stdout + as_json.stderr


def test_e1_scans_code_files(tmp_path):
    target = tmp_path / "client.py"
    target.write_text('API_KEY = "{}"\n'.format(_secret_values()["aws"]))
    result = _run("--json", target)
    assert [f["check"] for f in json.loads(result.stdout)["findings"]] == ["E1"]


# ---------------------------------------------------------------------------
# E2 unbalanced XML-style tag
# ---------------------------------------------------------------------------

def test_e2_flags_an_unclosed_and_a_stray_closing_tag(pl):
    assert _lines(_findings(pl, "e2_positive.md", "E2")) == [3, 7]


def test_e2_ignores_void_self_closing_inline_code_and_fenced_tags(pl):
    assert _findings(pl, "e2_negative.md", "E2") == []


def test_e2_treats_an_unclosed_name_inside_a_sentence_as_a_placeholder(pl, tmp_path):
    target = tmp_path / "skill.md"
    target.write_text("# Skill\n\nRun /xdd <path> to begin, then label it \"not run on <target>\".\n"
                      "Wrap it in <b>bold</b>, and <i>this one never closes.\n\n</i2>\n")
    found = [(f.line, f.message) for f in pl.lint([str(target)]) if f.check == "E2"]
    assert found == [(6, "closing </i2> has no opening tag")]


# ---------------------------------------------------------------------------
# E3 dead reference
# ---------------------------------------------------------------------------

def test_e3_flags_missing_files_anchors_and_imports(pl):
    found = _findings(pl, "e3_positive.md", "E3", kind="instruction-file")
    assert _lines(found) == [3, 4, 5, 6, 8]


def test_e3_skips_urls_home_absolute_templates_and_backticks_and_slugs_like_github(pl):
    found = _findings(pl, "e3_negative.md", "E3", kind="instruction-file")
    assert found == [], [(f.line, f.message) for f in found]


def test_e3_checks_at_imports_only_in_instruction_files(pl):
    # Claude Code expands @-imports in memory files only; in a skill "@x.md" is a mention.
    assert _lines(_findings(pl, "e3_positive.md", "E3", kind="skill")) == [3, 4, 5, 6]


def test_github_slug_rule(pl):
    assert pl.github_slugs(["Step 1 - prepare", "Paths a/b and c", "The `--repo` flag",
                            "Notes", "Notes", "Notes"]) == [
        "step-1---prepare", "paths-ab-and-c", "the---repo-flag", "notes", "notes-1", "notes-2",
    ]


# ---------------------------------------------------------------------------
# E4 undelimited interpolation (code only)
# ---------------------------------------------------------------------------

def test_e4_flags_each_prompt_form_and_treats_quotes_as_no_delimiter(pl):
    # 6 f-string in quotes, 12 system=, 13 role/content dict, 18 claude argv, 22 .format via name
    assert _lines(_findings(pl, "e4_positive.py", "E4")) == [6, 12, 13, 18, 22]


def test_e4_accepts_tag_pairs_and_fences_and_ignores_non_prompts(pl):
    assert _findings(pl, "e4_negative.py", "E4") == []


def test_e4_flags_semantic_detector_prompt():
    # #253 is the acceptance case; both sites are reported at the literal's first line.
    e4 = [f.line for f in _load_module().lint([str(SEMANTIC_DETECTOR)]) if f.check == "E4"]
    assert any(128 <= line <= 136 for line in e4), e4
    assert any(94 <= line <= 98 for line in e4), e4


def test_e4_runs_only_on_code(pl, tmp_path):
    target = tmp_path / "brief.md"
    target.write_text("# Brief\n\nprompt = f\"Summarise {text}\"\n")
    assert [f for f in pl.lint([str(target)]) if f.check == "E4"] == []


def test_code_files_get_only_e1_and_e4(pl, tmp_path):
    target = tmp_path / "tool.py"
    target.write_text('"""<context> [dead](missing.md) MUST NEVER ALWAYS DO NOT."""\n')
    assert pl.lint([str(target)]) == []


# ---------------------------------------------------------------------------
# W1 emphasis density
# ---------------------------------------------------------------------------

def test_w1_fires_at_three_hits_above_five_per_thousand(pl):
    found = _findings(pl, "w1_positive.md", "W1")
    assert [f.level for f in found] == ["warning"]
    assert found[0].message.startswith("5 emphasis tokens in 20 words")


def test_w1_ignores_critical_inline_code_enums_quotes_frontmatter_and_fences(pl):
    assert _findings(pl, "w1_negative.md", "W1") == []


def test_w1_needs_density_as_well_as_three_hits(pl, tmp_path):
    target = tmp_path / "long.md"
    target.write_text("# Long\n\nYou MUST run it. NEVER skip. ALWAYS read.\n\n" + "word " * 1000 + "\n")
    assert [f for f in pl.lint([str(target)]) if f.check == "W1"] == []


def test_frontmatter_must_be_used_not_flagged(pl):
    # repo ADR-4: agent-author mandates MUST BE USED in descriptions
    assert _findings(pl, "agent_frontmatter.md", kind="agent") == []


# ---------------------------------------------------------------------------
# W2 instruction count, W3 prohibition-only paragraph
# ---------------------------------------------------------------------------

def test_w2_fires_above_150_list_items(pl):
    assert len(_findings(pl, "w2_positive.md", "W2")) == 1


def test_w2_counts_150_items_as_fine_and_skips_fences(pl):
    assert _findings(pl, "w2_negative.md", "W2") == []


def test_w3_flags_a_paragraph_of_only_prohibitions(pl):
    assert _lines(_findings(pl, "w3_positive.md", "W3")) == [3]


def test_w3_ignores_mixed_single_sentence_list_and_fenced_paragraphs(pl):
    assert _findings(pl, "w3_negative.md", "W3") == []


# ---------------------------------------------------------------------------
# Fences, suppression
# ---------------------------------------------------------------------------

def test_fenced_blocks_are_skipped_except_for_e1(pl):
    assert [(f.check, f.line) for f in _findings(pl, "fences.md")] == [("E1", 8)]


def test_suppression_on_same_line_and_line_above_with_reason(pl):
    found = _findings(pl, "suppression.md", include_suppressed=True)
    suppressed = sorted((f.line, f.check, f.reason) for f in found if f.suppressed)
    assert suppressed == [
        (3, "E3", "the file is generated at install time"),
        (6, "E3", "created by the setup script"),
    ]


def test_suppression_without_reason_does_not_count_and_is_an_error(pl):
    found = _findings(pl, "suppression.md")
    assert ("W3", 9) in [(f.check, f.line) for f in found]
    assert ("E3", 11) in [(f.check, f.line) for f in found]
    reasonless = [f for f in found if f.check == "E0"]
    assert sorted(f.line for f in reasonless) == [8, 11]
    assert all(f.level == "error" for f in reasonless)


# ---------------------------------------------------------------------------
# CLI: output, exit codes, no execution
# ---------------------------------------------------------------------------

def test_exit_0_with_warnings_only():
    result = _run(FIXTURES / "w1_positive.md")
    assert result.returncode == 0
    assert "W1" in result.stdout


def test_exit_1_on_an_unsuppressed_error():
    assert _run(FIXTURES / "e3_positive.md").returncode == 1


def test_exit_0_when_every_error_is_suppressed(tmp_path):
    target = tmp_path / "doc.md"
    target.write_text("# Doc\n\n[x](gone.md) <!-- lint-ok: E3 removed upstream -->\n")
    assert _run(target).returncode == 0


def test_lint_exit_2_on_internal_failure(pl, monkeypatch, capsys):
    def boom(*_args, **_kwargs):
        raise RuntimeError("forced")

    monkeypatch.setattr(pl.CHECKS["E2"], "run", boom)
    assert pl.main([str(FIXTURES / "e2_negative.md")]) == 2
    assert "internal error" in capsys.readouterr().err


def test_exit_2_on_a_missing_path(tmp_path):
    result = _run(tmp_path / "absent.md")
    assert result.returncode == 2
    assert "absent.md" in result.stderr


def test_text_output_shape():
    result = _run(FIXTURES / "e3_positive.md")
    first = result.stdout.splitlines()[0]
    assert first.startswith(str(FIXTURES / "e3_positive.md") + ":3: E3 dead-reference: ")
    assert first.endswith("[PA-30]")


def test_json_output_shape():
    result = _run("--json", FIXTURES / "suppression.md")
    data = json.loads(result.stdout)
    assert data["version"] == 1
    assert data["files"] == 1
    keys = {"path", "line", "level", "check", "entry", "message", "suppressed", "reason"}
    assert all(set(f) == keys for f in data["findings"])
    assert any(f["suppressed"] and f["reason"] for f in data["findings"])
    assert result.returncode == 1


def test_kind_override_turns_markdown_checks_off_for_code(tmp_path):
    target = tmp_path / "notes.md"
    target.write_text("# Notes\n\n[x](gone.md)\n")
    assert _run("--kind", "code", target).returncode == 0
    assert _run("--kind", "brief", target).returncode == 1


def test_linting_python_never_executes_it(tmp_path):
    workdir = tmp_path / "work"
    workdir.mkdir()
    source = (FIXTURES / "no_exec" / "creates_file.py").read_text()
    target = workdir / "creates_file.py"
    target.write_text(source)
    marker = tmp_path / "marker.txt"
    env = dict(os.environ, PROMPT_LINT_MARKER=str(marker))
    result = _run("--json", target, cwd=str(workdir), env=env)
    assert result.returncode == 1  # its prompt is undelimited
    assert not marker.exists()
    assert not (workdir / "prompt-lint-marker").exists()
    assert sorted(p.name for p in workdir.iterdir()) == ["creates_file.py"]


def test_kind_inference_from_repo_paths(pl):
    cases = {
        "plugins/tcs-helper/skills/x/SKILL.md": "skill",
        "plugins/tcs-helper/skills/x/reference/catalog/core.md": "skill",
        "plugins/tcs-team/agents/the-architect/review-security.md": "agent",
        ".claude/agents/helper.md": "agent",
        "CLAUDE.md": "instruction-file",
        "docs/sub/CLAUDE.md": "instruction-file",
        "AGENTS.md": "instruction-file",
        "docs/templates/review-prompt.md": "chat-template",
        "docs/templates/setup-repo.md": "chat-template",
        "evals/system.prompt.md": "api-system",
        "x/prompts/judge.md": "api-system",
        "plugins/tcs-helper/scripts/lib/semantic_detector.py": "code",
        "scripts/release.py": "code",
        "docs/about/principles.md": None,
        "docs/XDD/specs/022-x/experiment/prompts/a.md": None,
        "tests/tcs-helper/fixtures/prompt_lint/SKILL.md": None,
    }
    assert {path: pl.repo_kind(path) for path in cases} == cases
