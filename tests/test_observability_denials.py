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
import re
import sys
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
        ("sandbox: network", None, "medium"),
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
