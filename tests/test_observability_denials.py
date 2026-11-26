"""`scripts/observability/denials.py` must turn transcript error results into denials.

Why this exists: spec-024 (observability denials report). Claude Code records
no event for a hook deny, a settings deny rule or a rejected prompt, so the
only place a denial survives is the session transcript, as an error tool
result whose text is the deny message. This file tests the pieces of
`denials.py` that read that text.

T1.2 -- `classify(text, tool)`: an ordered table of known message openings,
first match wins (SDD ADR-4), hook owners per SDD ADR-8. Two fallbacks after
the table: a text carrying Claude Code's `PreToolUse:<Tool> hook error: `
prefix is still a hook deny, only unattributed; anything else is an ordinary
tool error and not a denial at all.

CON-2: the returned `Denial` carries only fixed labels and identifiers
(category, hook, rule names, classifier reason category, confidence) -- never
the rule's explanation, the command, a path or any other message text.
"""

from __future__ import annotations

import ast
import dataclasses
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "observability"))

import denials  # noqa: E402  (sys.path must be extended first)

DENIALS_PY = REPO_ROOT / "scripts" / "observability" / "denials.py"

PREFIX = "PreToolUse:Bash hook error: "


def _bad_git_ops(*rules: str) -> str:
    """A block-bad-git-ops deny body, shaped like `_emit_permission_decision_deny`."""
    lines = [f"tcs-git-helpers DENIED: {len(rules)} rule(s) matched"]
    lines += [
        f"  - [{rule}] SECRET-RULE-TEXT for {rule} (override: prefix the command with CLAUDE_ALLOW_{rule}=1)"
        for rule in rules
    ]
    lines.append("Master override: CLAUDE_ALLOW_GIT_BAD_OPS=1 (loud warn; granular preferred)")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# One case per table row (SDD/Implementation Examples, ADR-4, ADR-8).
# ---------------------------------------------------------------------------

ROW_CASES = [
    pytest.param(
        "Refusing to Edit 'src/app.py' on 'main'. Create a feature branch first.",
        "Edit",
        ("hook deny", "tcs-git-helpers/pre-edit-branch-check", "high"),
        id="pre-edit-branch-check",
    ),
    pytest.param(
        "Refusing to Write '.git/config': edits to git-internal paths (matched .git/) are blocked",
        "Write",
        ("hook deny", "tcs-git-helpers/protect-git-internals", "high"),
        id="protect-git-internals",
    ),
    pytest.param(
        "Cannot exit worktree:\n  - 2 modified files",
        "ExitWorktree",
        ("hook deny", "tcs-git-helpers/worktree-exit-guard", "high"),
        id="worktree-exit-guard",
    ),
    pytest.param(
        "Refusing to Edit 'main.ts': inline eslint-disable comment detected (// eslint-disable-line).",
        "Edit",
        ("hook deny", "tcs-patterns/block-eslint-disable", "high"),
        id="tcs-patterns-eslint",
    ),
    pytest.param(
        "This reads a GitHub issue without its comments. Comments record what was already done.",
        "Bash",
        ("hook deny", "tcs-issues/require-issue-comments", "high"),
        id="tcs-issues-comments",
    ),
    pytest.param(
        "Dangerous flag detected: --no-verify",
        "Bash",
        ("hook deny", "external: dangerous flag", "medium"),
        id="external-dangerous-flag",
    ),
    pytest.param(
        "rm -rf on critical directory blocked: /",
        "Bash",
        ("hook deny", "external: critical rm", "medium"),
        id="external-critical-rm",
    ),
    pytest.param(
        "Recursive force rm on a critical path blocked",
        "Bash",
        ("hook deny", "external: critical rm", "medium"),
        id="external-critical-rm-alt-wording",
    ),
    pytest.param(
        "Permission for this command was denied by a built-in Claude Code safety check.",
        "Bash",
        ("safety check", None, "high"),
        id="safety-check",
    ),
    pytest.param(
        "Permission to use WebFetch has been denied because Claude Code is running in don't ask mode.",
        "WebFetch",
        ("permission denied", None, "medium"),
        id="permission-denied",
    ),
    pytest.param(
        "This agent is isolated in the worktree /repo/.claude/worktrees/a and cannot edit /repo/x.",
        "Edit",
        ("worktree isolation", None, "high"),
        id="worktree-isolation-agent",
    ),
    pytest.param(
        "This session is isolated in the worktree /repo/.claude/worktrees/b.",
        "Write",
        ("worktree isolation", None, "high"),
        id="worktree-isolation-session",
    ),
    pytest.param(
        "The user doesn't want to proceed with this tool use. The tool use was rejected.",
        "Bash",
        ("prompt rejected", None, "high"),
        id="prompt-rejected-bash",
    ),
    pytest.param(
        "touch: cannot touch '/etc/x': Operation not permitted",
        "Bash",
        ("sandbox: filesystem", None, "low"),
        id="sandbox-filesystem-eperm",
    ),
    pytest.param(
        "sed: couldn't open temporary file: Read-only file system",
        "Bash",
        ("sandbox: filesystem", None, "low"),
        id="sandbox-filesystem-readonly",
    ),
    pytest.param(
        "error: could not lock config file .git/config: Operation failed",
        "Bash",
        ("sandbox: filesystem", None, "low"),
        id="sandbox-filesystem-git-lock",
    ),
    pytest.param(
        "curl: (56) CONNECT tunnel failed, response 403",
        "Bash",
        ("sandbox: network", None, "low"),
        id="sandbox-network",
    ),
]


@pytest.mark.parametrize("text, tool, expected", ROW_CASES)
def test_classify_each_table_row(text, tool, expected):
    result = denials.classify(text, tool)

    assert result is not None
    assert (result.category, result.hook, result.confidence) == expected
    assert result.rules == ()
    assert result.reason_category is None


@pytest.mark.parametrize("text, tool, expected", ROW_CASES)
def test_classify_each_table_row_behind_hook_error_prefix(text, tool, expected):
    """The prefix (2.1.286+) is stripped before matching, so both forms agree."""
    result = denials.classify(f"PreToolUse:{tool} hook error: {text}", tool)

    assert result is not None
    assert (result.category, result.hook, result.confidence) == expected


# ---------------------------------------------------------------------------
# block-bad-git-ops: hook plus each listed rule (PRD F2 AC1).
# ---------------------------------------------------------------------------


def test_classify_bad_git_ops_single_rule():
    result = denials.classify(_bad_git_ops("DESTRUCTIVE_CHECKOUT"), "Bash")

    assert result == denials.Denial(
        category="hook deny",
        hook="tcs-git-helpers/block-bad-git-ops",
        rules=("DESTRUCTIVE_CHECKOUT",),
        reason_category=None,
        confidence="high",
    )


def test_classify_bad_git_ops_three_rules_in_listed_order():
    text = _bad_git_ops("BRANCH_FROM_UNFINISHED", "FORCE_BRANCH_DELETE", "REMOTE_BRANCH_DELETE")

    result = denials.classify(PREFIX + text, "Bash")

    assert result.hook == "tcs-git-helpers/block-bad-git-ops"
    assert result.rules == ("BRANCH_FROM_UNFINISHED", "FORCE_BRANCH_DELETE", "REMOTE_BRANCH_DELETE")


def test_classify_bad_git_ops_ignores_brackets_outside_rule_bullets():
    """Only `  - [RULE]` bullet lines name rules; a bracket elsewhere does not."""
    text = _bad_git_ops("DESTRUCTIVE_CHECKOUT") + "\nSee [NOT_A_RULE] in the docs"

    result = denials.classify(text, "Bash")

    assert result.rules == ("DESTRUCTIVE_CHECKOUT",)


# ---------------------------------------------------------------------------
# Classifier, both wordings, with reason category (PRD F2 AC5).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        pytest.param(
            "Permission for this action was denied by the Claude Code auto mode classifier. "
            "Reason: [Data Exfiltration] SECRET-REASON-TEXT about the command",
            id="current-wording",
        ),
        pytest.param(
            "Permission for this action has been denied. Reason: [Data Exfiltration] SECRET-REASON-TEXT",
            id="earlier-wording",
        ),
    ],
)
def test_classify_classifier_block_with_reason_category(text):
    result = denials.classify(text, "Bash")

    assert result == denials.Denial(
        category="classifier block",
        hook=None,
        rules=(),
        reason_category="Data Exfiltration",
        confidence="high",
    )


def test_classify_earlier_classifier_wording_without_bracket_has_no_reason_category():
    result = denials.classify("Permission for this action has been denied. Reason: risky", "Bash")

    assert result.category == "classifier block"
    assert result.reason_category is None


# ---------------------------------------------------------------------------
# Fallbacks and exclusions (ADR-4; PRD F2 AC2, AC3).
# ---------------------------------------------------------------------------


def test_classify_prefixed_unknown_message_is_unattributed_hook_deny():
    result = denials.classify("PreToolUse:Bash hook error: some-other-hook says no", "Bash")

    assert result is not None
    assert result.category == "hook deny"
    assert result.hook is None
    assert result.rules == ()


_HYPHENATED_MCP_TOOL = "mcp__my-server__tool"


def test_classify_strips_prefix_for_hyphenated_mcp_tool_name():
    text = f"PreToolUse:{_HYPHENATED_MCP_TOOL} hook error: Dangerous flag detected: x"

    result = denials.classify(text, _HYPHENATED_MCP_TOOL)

    assert result is not None
    assert (result.category, result.hook) == ("hook deny", "external: dangerous flag")


def test_classify_prefixed_unknown_message_on_hyphenated_mcp_tool_is_unattributed():
    text = f"PreToolUse:{_HYPHENATED_MCP_TOOL} hook error: some-other-hook says no"

    result = denials.classify(text, _HYPHENATED_MCP_TOOL)

    assert result is not None
    assert (result.category, result.hook) == ("hook deny", None)


def test_classify_unprefixed_unknown_message_is_not_a_denial():
    assert denials.classify("fatal: not a git repository", "Bash") is None


@pytest.mark.parametrize("tool", ["AskUserQuestion", "ExitPlanMode"])
def test_classify_prompt_rejected_on_question_tools_is_not_a_denial(tool):
    text = "The user doesn't want to proceed with this tool use. The tool use was rejected."

    assert denials.classify(text, tool) is None


def test_classify_prompt_rejected_without_tool_name_still_counts():
    text = "The user doesn't want to proceed with this tool use."

    assert denials.classify(text, None).category == "prompt rejected"


def test_classify_prompt_rejected_wins_over_sandbox_text():
    """Order: a rejected call's text can carry EPERM-looking output after it."""
    text = "The user doesn't want to proceed with this tool use.\nOperation not permitted"

    assert denials.classify(text, "Bash").category == "prompt rejected"


@pytest.mark.parametrize("text", ["", "   ", None, 42])
def test_classify_empty_or_non_text_is_not_a_denial(text):
    assert denials.classify(text, "Bash") is None


def test_classify_prefix_only_counts_at_the_start():
    text = "fatal: oops\nPreToolUse:Bash hook error: quoted from a log"

    assert denials.classify(text, "Bash") is None


# ---------------------------------------------------------------------------
# CON-2: no message text in the returned Denial.
# ---------------------------------------------------------------------------


def test_classify_returns_no_message_text():
    texts = [
        _bad_git_ops("DESTRUCTIVE_CHECKOUT", "FORCE_BRANCH_DELETE"),
        "Permission for this action was denied by the Claude Code auto mode classifier. "
        "Reason: [Destructive Action] SECRET-REASON-TEXT",
        "PreToolUse:Bash hook error: SECRET-UNKNOWN-HOOK-TEXT",
    ]

    for text in texts:
        result = denials.classify(text, "Bash")
        values = [v for v in dataclasses.astuple(result) if v is not None]
        flat = repr(values)
        assert "SECRET" not in flat
        assert "override" not in flat


def test_classify_denial_is_immutable():
    result = denials.classify(_bad_git_ops("DESTRUCTIVE_CHECKOUT"), "Bash")

    with pytest.raises(dataclasses.FrozenInstanceError):
        result.hook = "other"


def test_classify_table_rows_use_only_known_confidence_levels():
    assert {row.confidence for row in denials.TABLE} <= {"high", "medium", "low"}


# ---------------------------------------------------------------------------
# Cross-check: each TCS hook's real message still matches its table row
# (SDD Technical Debt; SDD Code Context names the files).
# ---------------------------------------------------------------------------

_SHELL_VAR = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(\[[^\]]*\])?\}")


def _message_template(path: Path, assignment: str, marker: str) -> str:
    """The quoted value of the `<assignment>=` line in `path` that contains `marker`."""
    pattern = re.compile(rf"^\s*{assignment}=([\"'])(.*)\1\s*$")
    for line in path.read_text(encoding="utf-8").splitlines():
        match = pattern.match(line)
        if match and marker in match.group(2):
            return match.group(2)
    raise AssertionError(f"{path}: no {assignment}= line containing {marker!r}")


def _render(template: str, values: dict[str, str]) -> str:
    return _SHELL_VAR.sub(lambda m: values.get(m.group(1), "sample"), template)


def _source_fragment(source: str, pattern: str) -> str:
    match = re.search(pattern, source)
    assert match, f"block-bad-git-ops.sh: deny body fragment {pattern!r} not found"
    return match.group(1)


def _bad_git_ops_from_source() -> str:
    """Rebuild the deny body from its header, per-rule reason and bullet templates."""
    source = (REPO_ROOT / "plugins/tcs-git-helpers/scripts/block-bad-git-ops.sh").read_text(encoding="utf-8")
    header = _source_fragment(source, r'body="(tcs-git-helpers DENIED: [^"]*)"')
    reason = _source_fragment(source, r'DENY_REASONS\+=\("(\[\$\{rule\}\][^"]*)"\)')
    bullet = _source_fragment(source, r'body="\$\{body\}"\$\'\\n\'"(\s+- \$\{DENY_REASONS\[\$i\]\})"')
    bullets = [_render(bullet, {"DENY_REASONS": _render(reason, {"rule": r})}) for r in ("RULE_A", "RULE_B")]
    return "\n".join([_render(header, {"n": "2"})] + bullets)


HOOK_SOURCES = [
    ("plugins/tcs-git-helpers/scripts/pre-edit-branch-check.sh", "Refusing to", {"TOOL": "Edit"},
     "tcs-git-helpers/pre-edit-branch-check"),
    ("plugins/tcs-git-helpers/scripts/protect-git-internals.sh", "Refusing to", {"TOOL": "Write"},
     "tcs-git-helpers/protect-git-internals"),
    ("plugins/tcs-git-helpers/scripts/worktree-exit-guard.sh", "Cannot exit", {},
     "tcs-git-helpers/worktree-exit-guard"),
    ("plugins/tcs-patterns/scripts/block-eslint-disable.sh", "Refusing to",
     {"TOOL": "Edit", "VIOLATION": "inline eslint-disable comment"}, "tcs-patterns/block-eslint-disable"),
    ("plugins/tcs-issues/scripts/require-issue-comments.sh", "without its comments", {},
     "tcs-issues/require-issue-comments"),
]


@pytest.mark.parametrize("rel_path, marker, values, hook", HOOK_SOURCES, ids=[h[3] for h in HOOK_SOURCES])
def test_classify_matches_tcs_hook_source_message(rel_path, marker, values, hook):
    message = _render(_message_template(REPO_ROOT / rel_path, "REASON", marker), values)

    result = denials.classify(message, values.get("TOOL", "Bash"))

    assert result is not None, f"{rel_path}: message no longer classifies: {message[:80]!r}"
    assert (result.category, result.hook) == ("hook deny", hook)


def test_classify_matches_block_bad_git_ops_source_message():
    result = denials.classify(_bad_git_ops_from_source(), "Bash")

    assert result.hook == "tcs-git-helpers/block-bad-git-ops"
    assert result.rules == ("RULE_A", "RULE_B")


# ---------------------------------------------------------------------------
# Module contract: stdlib only (ADR-1), no wall clock or real $HOME (CON-5).
# ---------------------------------------------------------------------------


def _imported_names() -> list[str]:
    tree = ast.parse(DENIALS_PY.read_text(encoding="utf-8"), filename=str(DENIALS_PY))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, "denials.py must not use relative imports"
            names.append(node.module or "")
    return names


def test_classify_module_imports_only_stdlib():
    names = _imported_names()

    assert names, "sanity: denials.py must import something (re, at least)"
    for name in names:
        top = name.split(".")[0]
        assert top in sys.stdlib_module_names, f"denials.py imports {name!r}, not stdlib"


def test_classify_module_has_no_wall_clock_or_real_home():
    source = DENIALS_PY.read_text(encoding="utf-8")

    for forbidden in ("datetime.now", "Path.home", "expanduser", "time.time"):
        assert forbidden not in source, f"denials.py uses {forbidden} (CON-5)"


# ===========================================================================
# T1.3 -- locating transcripts (ADR-3) and scanning one file (ADR-5).
#
# Every fixture builds its own home under tmp_path; nothing reads the real
# $HOME. Lines are written the way Claude Code writes them: compact JSON, one
# object per line.
# ===========================================================================

UTC = timezone.utc
PERIOD = denials.Period(
    start=datetime(2026, 10, 29, tzinfo=UTC),
    end=datetime(2026, 11, 26, tzinfo=UTC),
)
IN_PERIOD = "2026-11-20T10:02:11.123Z"


def _projects(home: Path) -> Path:
    return home / ".claude" / "projects"


def _project_dir(home: Path, repo: Path, suffix: str = "") -> Path:
    path = _projects(home) / (denials._encode(repo) + suffix)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_lines(path: Path, entries) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = [e if isinstance(e, str) else json.dumps(e, separators=(",", ":")) for e in entries]
    path.write_text("".join(line + "\n" for line in rendered), encoding="utf-8")
    return path


def _assistant_tool_use(tool_use_id: str, name: str) -> dict:
    return {
        "type": "assistant",
        "timestamp": IN_PERIOD,
        "sessionId": "s1",
        "message": {"content": [{"type": "tool_use", "id": tool_use_id, "name": name, "input": {}}]},
    }


def _tool_result(tool_use_id: str, content, *, is_error=True, line_type="user", ts=IN_PERIOD, **fields) -> dict:
    result = {"type": "tool_result", "tool_use_id": tool_use_id, "content": content}
    if is_error is not None:
        result["is_error"] = is_error
    line = {
        "type": line_type,
        "timestamp": ts,
        "sessionId": "s1",
        "cwd": "/r/app/.claude/worktrees/w1",
        "version": "2.1.320",
        "isSidechain": False,
        "message": {"content": [result]},
    }
    line.update(fields)
    return line


def _scan(tmp_path: Path, entries, name: str = "s1.jsonl"):
    return denials.scan_file(_write_lines(tmp_path / name, entries), PERIOD)


DENY = PREFIX + "tcs-git-helpers DENIED: 1 rule(s) matched\n  - [RESET_HARD] x"


# --- _encode ---------------------------------------------------------------


def test_encode_replaces_every_non_alphanumeric_character():
    assert denials._encode(Path("/Users/Laura/my.repo_v2")) == "-Users-Laura-my-repo-v2"


# --- locate_transcripts ----------------------------------------------------


def test_locate_finds_main_and_subagent_files(tmp_path):
    home, repo = tmp_path / "home", tmp_path / "r" / "app"
    project = _project_dir(home, repo)
    main = _write_lines(project / "s1.jsonl", [])
    sub = _write_lines(project / "s1" / "subagents" / "agent-a.jsonl", [])
    _write_lines(project / "s1" / "notes.txt", [])
    _write_lines(project / "s1" / "deeper" / "x.jsonl", [])

    result = denials.locate_transcripts(repo, [home])

    assert set(result.files) == {main, sub}
    assert result.searched == (_projects(home),)
    assert result.missing == ()


def test_locate_matches_dir_prefix_case_insensitively(tmp_path):
    home, repo = tmp_path / "home", tmp_path / "r" / "App"
    upper = _projects(home) / denials._encode(repo).upper()
    sibling = _projects(home) / (denials._encode(repo).lower() + "-old")
    other = _projects(home) / "-somewhere-else"
    files = [_write_lines(d / "s.jsonl", []) for d in (upper, sibling, other)]

    result = denials.locate_transcripts(repo, [home])

    # The sibling ("app-old") also matches the prefix; the per-line cwd filter drops it later (ADR-3).
    assert set(result.files) == {files[0], files[1]}


def test_locate_searches_every_home(tmp_path):
    repo = tmp_path / "r" / "app"
    home_a, home_b = tmp_path / "a", tmp_path / "b"
    file_a = _write_lines(_project_dir(home_a, repo) / "s1.jsonl", [])
    file_b = _write_lines(_project_dir(home_b, repo) / "s2.jsonl", [])

    result = denials.locate_transcripts(repo, [home_a, home_b])

    assert set(result.files) == {file_a, file_b}
    assert result.searched == (_projects(home_a), _projects(home_b))


def test_locate_lists_a_repeated_home_once(tmp_path):
    home, repo = tmp_path / "home", tmp_path / "r" / "app"
    main = _write_lines(_project_dir(home, repo) / "s1.jsonl", [])

    result = denials.locate_transcripts(repo, [home, home])

    assert result.files == (main,)
    assert result.searched == (_projects(home),)


def test_locate_reports_searched_dirs_when_none_exist(tmp_path):
    repo = tmp_path / "r" / "app"
    home_a, home_b = tmp_path / "a", tmp_path / "b"
    _projects(home_b).mkdir(parents=True)

    result = denials.locate_transcripts(repo, [home_a, home_b])

    assert result.files == ()
    assert result.searched == (_projects(home_a), _projects(home_b))
    assert result.missing == (_projects(home_a),)


# --- scan_file: what counts (ADR-5; PRD F2 AC7-AC8) ------------------------


def test_scan_keeps_user_error_result_with_its_fields(tmp_path):
    scan = _scan(tmp_path, [_assistant_tool_use("t9", "Bash"), _tool_result("t9", DENY)])

    (result,) = scan.results
    assert result == denials.ErrorResult(
        file=tmp_path / "s1.jsonl",
        tool_use_id="t9",
        tool="Bash",
        text=DENY,
        ts=datetime(2026, 11, 20, 10, 2, 11, 123000, tzinfo=UTC),
        cwd="/r/app/.claude/worktrees/w1",
        session_id="s1",
        version="2.1.320",
        sidechain=False,
    )
    assert scan.skipped_lines == 0 and scan.unreadable is False
    assert scan.versions == frozenset({"2.1.320"})


def test_scan_drops_api_request_blob_copy(tmp_path):
    scan = _scan(tmp_path, [_tool_result("t1", DENY, line_type="api-request-blob")])

    assert scan.results == ()


def test_scan_counts_a_duplicated_tool_result_once(tmp_path):
    scan = _scan(tmp_path, [
        _tool_result("t1", DENY),
        _tool_result("t1", DENY, line_type="api-request-blob"),
        _tool_result("t1", DENY),
    ])

    assert [r.tool_use_id for r in scan.results] == ["t1"]


@pytest.mark.parametrize("is_error", [False, None, "true", 1], ids=["false", "absent", "string", "int"])
def test_scan_never_counts_a_non_error_result_whatever_its_text(tmp_path, is_error):
    text = DENY + " Operation not permitted"
    scan = _scan(tmp_path, [_tool_result("t1", text, is_error=is_error)])

    assert scan.results == ()
    assert scan.skipped_lines == 0


def test_scan_keeps_only_the_error_results_of_a_multi_result_line(tmp_path):
    line = _tool_result("t1", DENY)
    line["message"]["content"].append(
        {"type": "tool_result", "tool_use_id": "t2", "content": DENY, "is_error": False})
    line["message"]["content"].append(
        {"type": "tool_result", "tool_use_id": "t3", "content": "boom", "is_error": True})

    scan = _scan(tmp_path, [line])

    assert [r.tool_use_id for r in scan.results] == ["t1", "t3"]


def test_scan_prefilter_accepts_json_with_spaces(tmp_path):
    spaced = json.dumps(_tool_result("t1", DENY))  # default separators: '"is_error": true'
    assert '"is_error":true' not in spaced

    scan = _scan(tmp_path, [spaced])

    assert [r.tool_use_id for r in scan.results] == ["t1"]


# --- scan_file: content and tool name --------------------------------------


def test_scan_joins_list_form_content(tmp_path):
    parts = [{"type": "text", "text": PREFIX + "tcs-git-helpers DENIED: 1 rule(s) matched"},
             {"type": "image", "source": {}},
             {"type": "text", "text": "  - [RESET_HARD] x"}]

    (result,) = _scan(tmp_path, [_tool_result("t1", parts)]).results

    assert result.text == DENY


def test_scan_maps_tool_name_from_tool_use_later_in_the_file(tmp_path):
    scan = _scan(tmp_path, [
        _tool_result("t1", DENY),
        {"type": "system", "subtype": "compact_boundary"},
        _assistant_tool_use("t1", "Edit"),
    ])

    assert scan.results[0].tool == "Edit"


def test_scan_tool_is_none_without_a_matching_tool_use(tmp_path):
    scan = _scan(tmp_path, [_assistant_tool_use("other", "Bash"), _tool_result("t1", DENY)])

    assert scan.results[0].tool is None


def test_scan_takes_tool_name_only_from_the_same_file(tmp_path):
    _write_lines(tmp_path / "other.jsonl", [_assistant_tool_use("t1", "Bash")])

    scan = _scan(tmp_path, [_tool_result("t1", DENY)])

    assert scan.results[0].tool is None


# --- scan_file: main session vs subagent -----------------------------------


def test_scan_marks_sidechain_from_the_line_flag(tmp_path):
    scan = _scan(tmp_path, [_tool_result("t1", DENY, isSidechain=True)])

    assert scan.results[0].sidechain is True


def test_scan_marks_sidechain_from_the_subagents_location(tmp_path):
    scan = _scan(tmp_path, [_tool_result("t1", DENY)], name="s1/subagents/agent-a.jsonl")

    assert scan.results[0].sidechain is True


# --- scan_file: period -----------------------------------------------------


def test_scan_keeps_only_results_inside_the_period(tmp_path):
    scan = _scan(tmp_path, [
        _tool_result("before", DENY, ts="2026-10-28T23:59:59Z"),
        _tool_result("start", DENY, ts="2026-10-29T00:00:00Z"),
        _tool_result("inside", DENY, ts="2026-11-20T10:00:00+00:00"),
        _tool_result("after", DENY, ts="2026-11-26T00:00:01Z"),
    ])

    assert [r.tool_use_id for r in scan.results] == ["start", "inside"]


def test_scan_reads_a_naive_timestamp_as_utc(tmp_path):
    scan = _scan(tmp_path, [_tool_result("naive", DENY, ts="2026-11-20T10:00:00")])

    assert [r.tool_use_id for r in scan.results] == ["naive"]
    assert scan.results[0].ts == datetime(2026, 11, 20, 10, 0, tzinfo=UTC)
    assert scan.results[0].ts.tzinfo is UTC


def test_scan_drops_a_naive_timestamp_just_outside_the_period(tmp_path):
    scan = _scan(tmp_path, [
        _tool_result("before", DENY, ts="2026-10-28T23:59:59"),
        _tool_result("after", DENY, ts="2026-11-26T00:00:01"),
    ])

    assert scan.results == ()
    assert scan.skipped_lines == 0


def test_scan_compares_an_offset_timestamp_by_its_utc_instant(tmp_path):
    half_hour = denials.Period(
        start=datetime(2026, 11, 20, 9, 0, tzinfo=UTC),
        end=datetime(2026, 11, 20, 9, 30, tzinfo=UTC),
    )
    path = _write_lines(tmp_path / "s1.jsonl", [
        _tool_result("early", DENY, ts="2026-11-20T10:59:59+02:00"),  # 08:59:59Z
        _tool_result("start", DENY, ts="2026-11-20T11:00:00+02:00"),  # 09:00Z
        _tool_result("end", DENY, ts="2026-11-20T11:30:00+02:00"),  # 09:30Z
        _tool_result("late", DENY, ts="2026-11-20T11:30:01+02:00"),  # 09:30:01Z
    ])

    scan = denials.scan_file(path, half_hour)

    assert [r.tool_use_id for r in scan.results] == ["start", "end"]
    assert scan.results[0].ts == half_hour.start


# --- scan_file: partial and unreadable input (PRD F5 AC2) ------------------


def test_scan_counts_a_pathologically_nested_line_as_skipped(tmp_path):
    depth = 100_000
    nested = '{"type":"user","is_error":true,"x":' + "[" * depth + "]" * depth + "}"

    scan = _scan(tmp_path, [nested, _tool_result("t1", DENY)])

    assert [r.tool_use_id for r in scan.results] == ["t1"]
    assert scan.skipped_lines == 1


def test_scan_counts_malformed_and_partial_lines_as_skipped(tmp_path):
    good = json.dumps(_tool_result("t1", DENY), separators=(",", ":"))
    partial_error = good[: good.index('"is_error":true') + 17]  # cut inside the closing brackets
    assert '"is_error":true' in partial_error
    path = tmp_path / "s1.jsonl"
    path.write_text("\n".join([
        good,
        "not json at all",
        '{"type":"user","is_error":true,',
        "",
        partial_error,  # last line, no trailing newline: a write still in progress
    ]), encoding="utf-8")

    scan = denials.scan_file(path, PERIOD)

    assert [r.tool_use_id for r in scan.results] == ["t1"]
    assert scan.skipped_lines == 3


@pytest.mark.parametrize("breakage", [
    pytest.param(lambda line: line.pop("timestamp"), id="no-timestamp"),
    pytest.param(lambda line: line.update(timestamp="yesterday"), id="bad-timestamp"),
    pytest.param(lambda line: line["message"].update(content=line["message"]["content"][0]),
                 id="content-not-a-list"),
    pytest.param(lambda line: line["message"]["content"][0].pop("tool_use_id"), id="no-tool-use-id"),
    pytest.param(lambda line: line["message"]["content"][0].update(content=7), id="result-content-not-text"),
    pytest.param(lambda line: line.update(message=line["message"]["content"]), id="message-not-an-object"),
])
def test_scan_counts_a_wrongly_shaped_error_line_as_skipped(tmp_path, breakage):
    line = _tool_result("t1", DENY)
    breakage(line)

    scan = _scan(tmp_path, [line, _tool_result("t2", DENY)])

    assert [r.tool_use_id for r in scan.results] == ["t2"]
    assert scan.skipped_lines == 1


def test_scan_tolerates_missing_optional_fields(tmp_path):
    line = _tool_result("t1", DENY)
    for key in ("cwd", "sessionId", "version", "isSidechain"):
        line.pop(key)

    (result,) = _scan(tmp_path, [line]).results

    assert (result.cwd, result.session_id, result.version, result.sidechain) == ("", "", "", False)


def test_scan_survives_a_path_it_cannot_read(tmp_path):
    path = tmp_path / "s1.jsonl"
    path.mkdir()  # reading a directory raises, whoever runs the test

    scan = denials.scan_file(path, PERIOD)

    assert (scan.results, scan.unreadable, scan.skipped_lines) == ((), True, 0)


def test_scan_survives_a_file_without_read_permission(tmp_path):
    path = _write_lines(tmp_path / "s1.jsonl", [_tool_result("t1", DENY)])
    path.chmod(0)
    try:
        if os.access(path, os.R_OK):
            pytest.skip("running as a user who can read a mode-000 file (e.g. root)")
        scan = denials.scan_file(path, PERIOD)
    finally:
        path.chmod(0o600)

    assert (scan.results, scan.unreadable) == ((), True)


def test_scan_survives_a_vanished_file(tmp_path):
    scan = denials.scan_file(tmp_path / "gone.jsonl", PERIOD)

    assert (scan.results, scan.unreadable) == ((), True)


def test_scan_survives_invalid_utf8(tmp_path):
    path = _write_lines(tmp_path / "s1.jsonl", [_tool_result("t1", DENY)])
    with path.open("ab") as handle:
        handle.write(b'{"type":"user","is_error":true,"x":"\xff\xfe"}\n')

    scan = denials.scan_file(path, PERIOD)

    assert [r.tool_use_id for r in scan.results] == ["t1"]
    assert scan.unreadable is False


# --- scan_file: oldest transcript timestamp (report "oldest <date>") -------


def _plain_line(ts, line_type="system") -> dict:
    return {"type": line_type, "timestamp": ts, "sessionId": "s1", "content": "note"}


def test_scan_oldest_ts_comes_from_a_non_error_line_older_than_any_error(tmp_path):
    entries = [_tool_result("t1", DENY), _plain_line("2026-11-02T08:00:00Z"), _assistant_tool_use("t1", "Bash")]

    scan = _scan(tmp_path, entries)

    assert scan.oldest_ts == datetime(2026, 11, 2, 8, tzinfo=UTC)


def test_scan_oldest_ts_counts_a_line_outside_the_period(tmp_path):
    entries = [_plain_line("2026-10-02T09:30:00Z", line_type="user"), _tool_result("t1", DENY)]

    scan = _scan(tmp_path, entries)

    assert scan.oldest_ts == datetime(2026, 10, 2, 9, 30, tzinfo=UTC)
    assert [r.tool_use_id for r in scan.results] == ["t1"]


def test_scan_oldest_ts_reads_a_naive_timestamp_as_utc(tmp_path):
    scan = _scan(tmp_path, [_plain_line("2026-11-03T07:00:00"), _tool_result("t1", DENY)])

    assert scan.oldest_ts == datetime(2026, 11, 3, 7, tzinfo=UTC)


def test_scan_oldest_ts_is_none_without_any_timestamp(tmp_path):
    scan = _scan(tmp_path, [{"type": "summary", "summary": "x"}, "not json"])

    assert scan.oldest_ts is None


def test_scan_oldest_ts_is_none_for_an_unreadable_file(tmp_path):
    scan = denials.scan_file(tmp_path / "gone.jsonl", PERIOD)

    assert (scan.unreadable, scan.oldest_ts) == (True, None)


def test_scan_oldest_ts_ignores_a_malformed_timestamp_without_skipping_the_line(tmp_path):
    entries = [_plain_line("yesterday"), _plain_line("2026-13-45T99:00:00Z"), _tool_result("t1", DENY)]

    scan = _scan(tmp_path, entries)

    assert scan.oldest_ts == datetime(2026, 11, 20, 10, 2, 11, 123000, tzinfo=UTC)
    assert scan.skipped_lines == 0


def test_scan_oldest_ts_ignores_a_timestamp_inside_message_text(tmp_path):
    line = _tool_result("t1", 'log: {"timestamp":"2020-01-01T00:00:00Z"}', is_error=False)
    line["timestamp"] = line.pop("timestamp")  # after `message`, as on real user lines

    scan = _scan(tmp_path, [line])

    assert scan.oldest_ts == datetime(2026, 11, 20, 10, 2, 11, 123000, tzinfo=UTC)


# ===========================================================================
# T2.2 -- the period (ADR-7) and aggregation of one repository's denials
# (SDD walkthrough steps 4-6, Complex Logic / week rows).
#
# Everything is built in memory: `ErrorResult` and `ScanResult` values stand
# in for scanned files, so these tests exercise counting, not reading.
# ===========================================================================

from datetime import timedelta  # noqa: E402

NOW = datetime(2026, 11, 26, 15, 30, tzinfo=UTC)  # a Thursday


# --- period_from_args (ADR-7; PRD F3 AC1, F8) -------------------------------


def test_period_default_is_28_days_ending_now():
    period = denials.period_from_args(None, None, NOW)

    assert period == denials.Period(start=NOW - timedelta(days=28), end=NOW)


def test_period_weeks_starts_on_the_monday_n_minus_1_weeks_back():
    period = denials.period_from_args(2, None, NOW)

    assert period == denials.Period(start=datetime(2026, 11, 16, tzinfo=UTC), end=NOW)


def test_period_one_week_is_the_current_week_so_far():
    period = denials.period_from_args(1, None, NOW)

    assert period.start == datetime(2026, 11, 23, tzinfo=UTC)
    assert period.start.weekday() == 0


def test_period_since_starts_at_utc_midnight_of_the_date():
    period = denials.period_from_args(None, "2026-11-01", NOW)

    assert period == denials.Period(start=datetime(2026, 11, 1, tzinfo=UTC), end=NOW)


def test_period_converts_an_offset_now_to_utc():
    offset_now = datetime(2026, 11, 26, 1, 0, tzinfo=timezone(timedelta(hours=5)))

    period = denials.period_from_args(1, None, offset_now)

    assert period.end.utcoffset() == timedelta(0)
    assert period.start == datetime(2026, 11, 23, tzinfo=UTC)  # 2026-11-25 20:00 UTC is a Wednesday


@pytest.mark.parametrize("weeks", [0, -1, True, 1.5, "2"])
def test_period_rejects_weeks_that_are_not_a_positive_int(weeks):
    with pytest.raises(ValueError, match="weeks"):
        denials.period_from_args(weeks, None, NOW)


@pytest.mark.parametrize("since", ["2026-13-01", "20261101", "2026-11-1", "yesterday", "", "2026-11-01T00:00"])
def test_period_rejects_a_since_that_is_not_yyyy_mm_dd(since):
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        denials.period_from_args(None, since, NOW)


def test_period_rejects_a_since_after_now():
    with pytest.raises(ValueError, match="2026-11-27"):
        denials.period_from_args(None, "2026-11-27", NOW)


def test_period_rejects_weeks_and_since_together():
    with pytest.raises(ValueError, match="not both"):
        denials.period_from_args(2, "2026-11-01", NOW)


def test_period_rejects_a_naive_now():
    with pytest.raises(ValueError, match="timezone"):
        denials.period_from_args(None, None, datetime(2026, 11, 26))


# --- aggregate --------------------------------------------------------------

AGG_PERIOD = denials.Period(  # Wednesday .. Thursday: partial first and last weeks
    start=datetime(2026, 10, 29, 15, 30, tzinfo=UTC),
    end=NOW,
)
REPO = Path("/r/app")
AT = datetime(2026, 11, 20, 10, 2, 11, tzinfo=UTC)


def _err(text, *, tool="Bash", ts=AT, cwd="/r/app", session="s1", version="2.1.320",
         sidechain=False) -> denials.ErrorResult:
    return denials.ErrorResult(
        file=Path("/h/.claude/projects/x/s1.jsonl"), tool_use_id="t1",
        tool=tool, text=text, ts=ts, cwd=cwd, session_id=session, version=version, sidechain=sidechain,
    )


def _scan_of(*results, skipped=0, oldest=None, unreadable=False, name="s1.jsonl") -> denials.ScanResult:
    return denials.ScanResult(path=Path("/h") / name, results=tuple(results), skipped_lines=skipped,
                              unreadable=unreadable, oldest_ts=oldest)


def _agg(*results, period=AGG_PERIOD, repo=REPO):
    return denials.aggregate([_scan_of(*results)], repo, period)


REJECTED = "The user doesn't want to proceed with this tool use. The tool use was rejected."
UNKNOWN_HOOK = PREFIX + "some-other-hook said no"
SANDBOX_FS = "touch: /etc/x: Operation not permitted"
CLASSIFIER = "Permission for this action has been denied. Reason: [Production Deploy] free text"


def _deny(*rules: str) -> str:
    return PREFIX + _bad_git_ops(*rules)


@pytest.mark.parametrize("cwd", [
    "/r/app",
    "/r/app/src/lib",
    "/R/App",
    "/r/app/.claude/worktrees/w1",
    "/r/app/.claude/worktrees/w1/src",
    "/r/app/",
])
def test_aggregate_keeps_a_cwd_in_the_repo_or_its_worktrees(cwd):
    summary = _agg(_err(_deny("RESET_HARD"), cwd=cwd))

    assert summary.hook_denies == 1


@pytest.mark.parametrize("repo", [REPO, REPO / ".claude/worktrees/w1"])
def test_aggregate_strips_a_differently_cased_worktree_suffix_like_a_lowercase_one(repo):
    lower = _agg(_err(_deny("RESET_HARD"), cwd="/r/app/.claude/worktrees/w1"), repo=repo)
    mixed = _agg(_err(_deny("RESET_HARD"), cwd="/r/app/.Claude/Worktrees/W1"), repo=repo)

    assert mixed.hook_denies == lower.hook_denies


@pytest.mark.parametrize("cwd", ["/r/app-old", "/r/app-old/.claude/worktrees/w1", "/r/apps/x", "/r", "", "/other"])
def test_aggregate_drops_a_cwd_outside_the_repo(cwd):
    summary = _agg(_err(_deny("RESET_HARD"), cwd=cwd))

    assert summary.hook_denies == 0
    assert summary.by_category == {}
    assert summary.top == []


def test_aggregate_drops_an_error_that_is_not_a_denial():
    summary = _agg(_err("ls: x: No such file or directory"), _err(REJECTED, tool="AskUserQuestion"))

    assert summary.by_category == {}
    assert sum(sum(week.values()) for week in summary.by_week.values()) == 0


def test_aggregate_drops_a_result_outside_the_period():
    summary = _agg(_err(_deny("RESET_HARD"), ts=AGG_PERIOD.start - timedelta(seconds=1)))

    assert summary.hook_denies == 0


def test_aggregate_counts_per_category_split_main_and_subagent():
    summary = _agg(
        _err(REJECTED), _err(REJECTED, sidechain=True), _err(REJECTED, sidechain=True),
        _err(SANDBOX_FS),
    )

    assert summary.by_category == {
        ("prompt rejected", "main"): 1,
        ("prompt rejected", "subagent"): 2,
        ("sandbox: filesystem", "main"): 1,
    }


def test_aggregate_multi_rule_deny_counts_once_in_category_and_once_per_rule():
    summary = _agg(_err(_deny("RESET_HARD", "CLEAN_FORCE")), _err(_deny("RESET_HARD"), sidechain=True))

    hook = "tcs-git-helpers/block-bad-git-ops"
    assert summary.by_category == {("hook deny", "main"): 1, ("hook deny", "subagent"): 1}
    assert summary.by_rule == {
        (hook, "RESET_HARD", "main"): 1,
        (hook, "CLEAN_FORCE", "main"): 1,
        (hook, "RESET_HARD", "subagent"): 1,
    }
    assert summary.hook_denies == 2


def test_aggregate_counts_a_ruleless_hook_under_rule_none():
    text = "Refusing to Edit 'src/app.py' on 'main'. Create a feature branch first."

    summary = _agg(_err(text, tool="Edit"))

    assert summary.by_rule == {("tcs-git-helpers/pre-edit-branch-check", None, "main"): 1}


def test_aggregate_totals_unattributed_and_hook_denies():
    summary = _agg(_err(UNKNOWN_HOOK), _err(UNKNOWN_HOOK, sidechain=True), _err(_deny("RESET_HARD")),
                   _err(REJECTED))

    assert summary.unattributed == 2
    assert summary.hook_denies == 3
    assert summary.by_rule[(None, None, "main")] == 1
    assert summary.by_rule[(None, None, "subagent")] == 1


def test_aggregate_counts_classifier_reason_categories_only():
    summary = _agg(_err(CLASSIFIER), _err(CLASSIFIER), _err("Permission for this action has been denied. Reason: x"))

    assert summary.by_reason == {("classifier block", "Production Deploy"): 2}


def test_aggregate_marks_low_confidence_categories():
    summary = _agg(_err(SANDBOX_FS), _err(REJECTED), _err("curl: CONNECT tunnel failed, response 403"))

    assert summary.low_confidence == frozenset({"sandbox: filesystem", "sandbox: network"})


# --- week rows (SDD Complex Logic) ------------------------------------------


def test_aggregate_has_one_row_per_monday_week_including_empty_ones():
    summary = _agg(_err(REJECTED, ts=datetime(2026, 11, 4, tzinfo=UTC)))

    mondays = [datetime(2026, 10, 26, tzinfo=UTC) + timedelta(weeks=n) for n in range(5)]
    assert list(summary.by_week) == mondays
    assert summary.by_week[mondays[1]] == {"prompt rejected": 1}
    assert [sum(summary.by_week[m].values()) for m in mondays] == [0, 1, 0, 0, 0]


def test_aggregate_week_counts_a_multi_rule_deny_once():
    summary = _agg(_err(_deny("RESET_HARD", "CLEAN_FORCE")))

    # 2026-11-20 is a Friday; its week starts Monday 2026-11-16 (the SDD walkthrough's "11-17" is a Tuesday).
    assert summary.by_week[datetime(2026, 11, 16, tzinfo=UTC)] == {"hook deny": 1}


def test_aggregate_week_boundary_is_monday_midnight_utc():
    sunday_late = datetime(2026, 11, 22, 23, 59, 59, tzinfo=UTC)
    monday = datetime(2026, 11, 23, tzinfo=UTC)

    summary = _agg(_err(REJECTED, ts=sunday_late), _err(SANDBOX_FS, ts=monday))

    assert summary.by_week[datetime(2026, 11, 16, tzinfo=UTC)] == {"prompt rejected": 1}
    assert summary.by_week[monday] == {"sandbox: filesystem": 1}


def test_aggregate_flags_cut_first_and_last_weeks_as_partial():
    summary = _agg()

    assert summary.partial_weeks == frozenset({datetime(2026, 10, 26, tzinfo=UTC), datetime(2026, 11, 23, tzinfo=UTC)})


def test_aggregate_whole_weeks_are_not_partial():
    period = denials.Period(start=datetime(2026, 11, 9, tzinfo=UTC),
                            end=datetime(2026, 11, 22, 23, 59, 59, 999999, tzinfo=UTC))

    summary = _agg(period=period)

    assert list(summary.by_week) == [datetime(2026, 11, 9, tzinfo=UTC), datetime(2026, 11, 16, tzinfo=UTC)]
    assert summary.partial_weeks == frozenset()


def test_aggregate_weeks_period_has_a_full_first_week():
    period = denials.period_from_args(3, None, NOW)

    summary = _agg(period=period)

    assert len(summary.by_week) == 3
    assert summary.partial_weeks == frozenset({datetime(2026, 11, 23, tzinfo=UTC)})


# --- top list (PRD F4 AC1, AC3) ---------------------------------------------


def test_aggregate_top_row_carries_kind_tool_count_and_last_occurrence():
    later = AT + timedelta(hours=3)
    summary = _agg(
        _err(_deny("RESET_HARD"), session="s-old"),
        _err(_deny("RESET_HARD"), session="s-new", ts=later),
        _err(_deny("RESET_HARD"), session="s-mid", ts=AT + timedelta(hours=1)),
    )

    assert summary.top == [denials.TopRow(
        category="hook deny", hook="tcs-git-helpers/block-bad-git-ops", rule="RESET_HARD", tool="Bash",
        count=3, overrides=None, last_session_id="s-new", last_ts=later,
    )]


def test_aggregate_top_rows_split_by_tool():
    summary = _agg(_err(REJECTED, tool="Bash"), _err(REJECTED, tool="Write"), _err(REJECTED, tool="Bash"))

    assert [(row.tool, row.count) for row in summary.top] == [("Bash", 2), ("Write", 1)]


def test_aggregate_top_has_one_row_per_rule_of_a_multi_rule_deny():
    summary = _agg(_err(_deny("RESET_HARD", "CLEAN_FORCE")))

    assert sorted(row.rule for row in summary.top) == ["CLEAN_FORCE", "RESET_HARD"]


def test_aggregate_top_orders_by_count_then_most_recent():
    summary = _agg(
        _err(REJECTED, tool="Write", ts=AT),
        _err(REJECTED, tool="Edit", ts=AT + timedelta(hours=1)),
        _err(SANDBOX_FS), _err(SANDBOX_FS),
    )

    assert [(row.category, row.tool) for row in summary.top] == [
        ("sandbox: filesystem", "Bash"), ("prompt rejected", "Edit"), ("prompt rejected", "Write"),
    ]


def test_aggregate_top_breaks_a_count_and_time_tie_by_kind_whatever_the_scan_order():
    kinds = [_err(SANDBOX_FS, tool="Bash"), _err(REJECTED, tool="Write"), _err(REJECTED, tool="Edit")]

    forward = _agg(*kinds).top
    backward = denials.aggregate([_scan_of(kind, name=f"{n}.jsonl") for n, kind in enumerate(reversed(kinds))],
                                 REPO, AGG_PERIOD).top

    expected = [("prompt rejected", "Edit"), ("prompt rejected", "Write"), ("sandbox: filesystem", "Bash")]
    assert [(row.category, row.tool) for row in forward] == expected
    assert [(row.category, row.tool) for row in backward] == expected


@pytest.mark.parametrize("sessions", [("s-a", "s-b"), ("s-b", "s-a")])
def test_aggregate_top_last_session_on_a_time_tie_is_the_greater_session_id(sessions):
    summary = _agg(*(_err(_deny("RESET_HARD"), session=session) for session in sessions))

    assert [(row.count, row.last_session_id, row.last_ts) for row in summary.top] == [(2, "s-b", AT)]


def test_aggregate_top_keeps_at_most_ten_rows():
    rules = [f"RULE_{letter}" for letter in "ABCDEFGHIJKL"]  # rule ids are [A-Z_]+
    results = [_err(_deny(rule), ts=AT + timedelta(minutes=n)) for n, rule in enumerate(rules)]
    results += [_err(_deny("RULE_A"))]

    summary = _agg(*results)

    assert len(summary.top) == 10
    assert summary.top[0].rule == "RULE_A" and summary.top[0].count == 2
    assert [row.rule for row in summary.top[1:]] == [f"RULE_{letter}" for letter in "LKJIHGFED"]


def test_aggregate_top_is_empty_without_denials():
    assert _agg().top == []


# --- files, lines, timestamps and versions ----------------------------------


def test_aggregate_sums_files_skipped_lines_and_unreadable_files():
    scans = [_scan_of(skipped=2, name="a.jsonl"), _scan_of(skipped=3, name="b.jsonl"),
             _scan_of(unreadable=True, name="c.jsonl")]

    summary = denials.aggregate(scans, REPO, AGG_PERIOD)

    assert summary.files_read == 2
    assert summary.unreadable == 1
    assert summary.skipped_lines == 5
    assert summary.period == AGG_PERIOD


def test_aggregate_oldest_ts_is_the_minimum_of_known_values():
    older = datetime(2026, 10, 2, tzinfo=UTC)
    scans = [_scan_of(oldest=AT, name="a.jsonl"), _scan_of(oldest=None, name="b.jsonl"),
             _scan_of(oldest=older, name="c.jsonl")]

    assert denials.aggregate(scans, REPO, AGG_PERIOD).oldest_ts == older


def test_aggregate_oldest_ts_is_none_without_any_value():
    assert denials.aggregate([_scan_of(), _scan_of(unreadable=True)], REPO, AGG_PERIOD).oldest_ts is None


def test_aggregate_collects_versions_and_those_outside_the_checked_range():
    versions = ["2.1.71", "2.1.332", "2.1.70", "2.1.333", "2.2.0", "1.9.999", "2.1.x", "nightly"]
    results = [_err("ls: plain error", version=v, ts=AT + timedelta(minutes=n)) for n, v in enumerate(versions)]
    results += [_err("ls: plain error", version="")]

    summary = _agg(*results)

    assert summary.versions_seen == set(versions)
    assert summary.unknown_versions == {"2.1.70", "2.1.333", "2.2.0", "1.9.999", "2.1.x", "nightly"}


def test_aggregate_ignores_versions_of_other_repos():
    summary = _agg(_err("ls: plain error", version="2.0.1", cwd="/r/app-old"))

    assert summary.versions_seen == set()
    assert summary.unknown_versions == set()


def test_aggregate_summary_holds_no_transcript_text():
    secret = "SENTINEL-SECRET-9f3a"
    text = PREFIX + f"tcs-git-helpers DENIED: 1 rule(s) matched\n  - [RESET_HARD] {secret}"
    classifier = f"Permission for this action has been denied. Reason: [Data Exfiltration] {secret}"

    summary = _agg(_err(text), _err(classifier), _err(UNKNOWN_HOOK + secret), _err(f"{secret} Operation not permitted"))

    assert secret not in repr(summary)


# ---------------------------------------------------------------------------
# T2.1 -- `read_overrides(repo_root, homes, period)`: override consumptions per
# rule from tcs-git-helpers' audit log (SDD ADR-6). The log lives at
# `<home>/.claude/plugins/data/tcs-git-helpers-<repo basename>/audit/overrides.jsonl`
# (plugin_data.sh); its rows are written by lib/override.sh (consumptions),
# ask-guard.sh (asks, `hook=ask-guard`) and protect-git-internals.sh (denies,
# `env_var=TCS_GIT_HELPERS_SETUP_ACTIVE`). Only `ts`, `env_var` and `hook` are
# read; `command` never reaches the result (CON-2).
# ---------------------------------------------------------------------------

OVR_REPO = Path("/r/app")
OVR_PERIOD = denials.Period(datetime(2026, 11, 1, tzinfo=UTC), datetime(2026, 11, 26, 23, 59, tzinfo=UTC))
OVR_TS = "2026-11-20T10:02:11Z"


def _override_row(env_var, *, ts=OVR_TS, hook="", master=False, command="git reset --hard"):
    return json.dumps({"ts": ts, "repo": "/r/app", "branch": "feat/x", "hook": hook,
                       "env_var": env_var, "master": master, "command": command,
                       "pattern": "", "tool_input_truncated": False})


def _override_log(home, *lines, repo=OVR_REPO):
    audit = home / ".claude" / "plugins" / "data" / f"tcs-git-helpers-{repo.name}" / "audit"
    audit.mkdir(parents=True, exist_ok=True)
    (audit / "overrides.jsonl").write_text("".join(line + "\n" for line in lines))
    return home


def test_overrides_counts_rows_per_rule(tmp_path):
    home = _override_log(tmp_path / "h", _override_row("CLAUDE_ALLOW_RESET_HARD"),
                         _override_row("CLAUDE_ALLOW_RESET_HARD"), _override_row("CLAUDE_ALLOW_NO_VERIFY"))

    counts = denials.read_overrides(OVR_REPO, [home], OVR_PERIOD)

    assert counts.by_rule == {"RESET_HARD": 2, "NO_VERIFY": 1}
    assert counts.master == 0
    assert counts.log_found is True


def test_overrides_master_switch_is_counted_apart_from_rules(tmp_path):
    home = _override_log(tmp_path / "h", _override_row("CLAUDE_ALLOW_GIT_BAD_OPS", master=True),
                         _override_row("CLAUDE_ALLOW_GIT_BAD_OPS", master=True))

    counts = denials.read_overrides(OVR_REPO, [home], OVR_PERIOD)

    assert counts.master == 2
    assert "GIT_BAD_OPS" not in counts.by_rule


def test_overrides_consumed_ask_override_counts_under_its_ask_rule(tmp_path):
    home = _override_log(tmp_path / "h", _override_row("CLAUDE_ALLOW_ASK_FORCE_PUSH"))

    assert denials.read_overrides(OVR_REPO, [home], OVR_PERIOD).by_rule == {"ASK_FORCE_PUSH": 1}


def test_overrides_ignores_ask_guard_rows(tmp_path):
    home = _override_log(tmp_path / "h", _override_row("CLAUDE_ALLOW_ASK_FORCE_PUSH", hook="ask-guard"))

    assert denials.read_overrides(OVR_REPO, [home], OVR_PERIOD).by_rule == {}


def test_overrides_ignores_rows_whose_env_var_is_not_an_allow_switch(tmp_path):
    home = _override_log(tmp_path / "h",
                         _override_row("TCS_GIT_HELPERS_SETUP_ACTIVE", hook="protect-git-internals"),
                         _override_row("CLAUDE_ALLOW_"), _override_row("XCLAUDE_ALLOW_RESET_HARD"))

    counts = denials.read_overrides(OVR_REPO, [home], OVR_PERIOD)

    assert counts.by_rule == {}
    assert counts.master == 0


@pytest.mark.parametrize("ts", ["2026-10-31T23:59:59Z", "2026-11-27T00:00:00Z"])
def test_overrides_ignores_rows_outside_the_period(tmp_path, ts):
    home = _override_log(tmp_path / "h", _override_row("CLAUDE_ALLOW_RESET_HARD", ts=ts),
                         _override_row("CLAUDE_ALLOW_GIT_BAD_OPS", ts=ts))

    counts = denials.read_overrides(OVR_REPO, [home], OVR_PERIOD)

    assert counts.by_rule == {}
    assert counts.master == 0


def test_overrides_period_ends_are_inclusive(tmp_path):
    home = _override_log(tmp_path / "h", _override_row("CLAUDE_ALLOW_RESET_HARD", ts="2026-11-01T00:00:00Z"),
                         _override_row("CLAUDE_ALLOW_RESET_HARD", ts="2026-11-26T23:59:00+00:00"))

    assert denials.read_overrides(OVR_REPO, [home], OVR_PERIOD).by_rule == {"RESET_HARD": 2}


@pytest.mark.parametrize("line", [
    '{"ts": "2026-11-20T10:02:11Z", "env_var": "CLAUDE_ALLOW_RESET_HARD"',  # partial write
    "not json CLAUDE_ALLOW_RESET_HARD",
    '["CLAUDE_ALLOW_RESET_HARD"]',
    '{"env_var": "CLAUDE_ALLOW_RESET_HARD"}',
    '{"ts": 17, "env_var": "CLAUDE_ALLOW_RESET_HARD"}',
    '{"ts": "yesterday", "env_var": "CLAUDE_ALLOW_RESET_HARD"}',
    '{"ts": "2026-11-20T10:02:11Z", "env_var": ["CLAUDE_ALLOW_RESET_HARD"]}',
    "",
])
def test_overrides_skips_malformed_rows(tmp_path, line):
    home = _override_log(tmp_path / "h", line, _override_row("CLAUDE_ALLOW_NO_VERIFY"))

    assert denials.read_overrides(OVR_REPO, [home], OVR_PERIOD).by_rule == {"NO_VERIFY": 1}


def test_overrides_naive_timestamp_is_read_as_utc(tmp_path):
    home = _override_log(tmp_path / "h", _override_row("CLAUDE_ALLOW_RESET_HARD", ts="2026-11-20T10:02:11"))

    assert denials.read_overrides(OVR_REPO, [home], OVR_PERIOD).by_rule == {"RESET_HARD": 1}


def test_overrides_missing_log_reports_no_override_log(tmp_path):
    counts = denials.read_overrides(OVR_REPO, [tmp_path / "h"], OVR_PERIOD)

    assert counts.log_found is False
    assert counts.by_rule == {}
    assert counts.master == 0


def test_overrides_without_homes_reports_no_override_log():
    assert denials.read_overrides(OVR_REPO, [], OVR_PERIOD).log_found is False


def test_overrides_reads_the_log_of_this_repo_basename_only(tmp_path):
    home = _override_log(tmp_path / "h", _override_row("CLAUDE_ALLOW_RESET_HARD"), repo=Path("/r/other"))

    assert denials.read_overrides(OVR_REPO, [home], OVR_PERIOD).log_found is False


def test_overrides_sums_distinct_homes_and_finds_a_log_in_any(tmp_path):
    first = _override_log(tmp_path / "a", _override_row("CLAUDE_ALLOW_RESET_HARD"))
    second = _override_log(tmp_path / "b", _override_row("CLAUDE_ALLOW_RESET_HARD"),
                           _override_row("CLAUDE_ALLOW_GIT_BAD_OPS"))

    counts = denials.read_overrides(OVR_REPO, [tmp_path / "none", first, second], OVR_PERIOD)

    assert counts.by_rule == {"RESET_HARD": 2}
    assert counts.master == 1
    assert counts.log_found is True


def test_overrides_two_homes_that_are_one_directory_are_read_once(tmp_path):
    home = _override_log(tmp_path / "h", _override_row("CLAUDE_ALLOW_RESET_HARD"))
    alias = tmp_path / "alias"
    alias.symlink_to(home)

    assert denials.read_overrides(OVR_REPO, [home, alias], OVR_PERIOD).by_rule == {"RESET_HARD": 1}


def test_overrides_unreadable_log_counts_as_no_override_log(tmp_path):
    home = tmp_path / "h"
    (home / ".claude" / "plugins" / "data" / "tcs-git-helpers-app" / "audit" / "overrides.jsonl").mkdir(parents=True)

    assert denials.read_overrides(OVR_REPO, [home], OVR_PERIOD).log_found is False


def test_overrides_result_holds_no_command_text(tmp_path):
    secret = "SENTINEL-OVERRIDE-CMD-77c1"
    home = _override_log(tmp_path / "h", _override_row("CLAUDE_ALLOW_RESET_HARD", command=secret),
                         _override_row("CLAUDE_ALLOW_GIT_BAD_OPS", command=secret),
                         _override_row("CLAUDE_ALLOW_ASK_X", hook="ask-guard", command=secret))

    counts = denials.read_overrides(OVR_REPO, [home], OVR_PERIOD)

    assert secret not in repr(counts)
    assert {f.name for f in dataclasses.fields(counts)} == {"by_rule", "master", "log_found"}
