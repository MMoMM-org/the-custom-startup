"""No bats assertion may sit where its failure is ignored.

Written for #159 (and its duplicate #173). Two statement forms are evaluated
and then discarded when they are not the last statement of a test or helper
body, so the test passes whatever they assert:

  - a bare `[[ ... ]]` — under bash 3.2 (macOS `/bin/bash`, the macos-latest
    CI leg and every local run here) it does not trip errexit. Bash 4.1 and
    later do apply errexit to it, so the ubuntu leg alone still enforced these
    and hid the problem.
  - `! cmd` — exempt from errexit on every bash version.

Use `_has` / `_lacks` (plugins/*/tests/bats/lib/) or `[ ]` instead. A line
that carries its own failure path (`[[ ... ]] || { ...; return 1; }`,
including across a `\\` continuation) is fine and is not flagged.

Body boundaries are taken from layout, not from counting braces: a body runs
from a column-0 `@test ... {` or `name() {` line to the next column-0 `}`.
Counting `{` and `}` was tried first and is wrong on 14 bodies in this repo —
`${var}`, jq filters and JSON literals unbalance it, merging neighbouring
tests or cutting one short, which both invents and hides findings.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

OPENER = re.compile(
    r"^(?:@test\s.*|(?:function\s+)?[A-Za-z_][A-Za-z0-9_]*\s*\(\)\s*)\{\s*$"
)
CLOSER = re.compile(r"^\}\s*$")
GUARDED_BRACKET = re.compile(r"\]\]\s*(?:\|\||&&)")


def _logical_lines(body):
    """Join `\\` continuations; yield (first line number, joined text)."""
    pending_no, pending = None, []
    for no, text in body:
        if pending_no is None:
            pending_no = no
        if text.rstrip().endswith("\\"):
            pending.append(text.rstrip()[:-1])
            continue
        pending.append(text)
        yield pending_no, " ".join(part.strip() for part in pending)
        pending_no, pending = None, []
    if pending:
        yield pending_no, " ".join(part.strip() for part in pending)


def _bodies(lines):
    i = 0
    while i < len(lines):
        if not OPENER.match(lines[i]):
            i += 1
            continue
        j, body = i + 1, []
        while j < len(lines) and not CLOSER.match(lines[j]):
            body.append((j + 1, lines[j]))
            j += 1
        yield body
        i = j + 1


def find_blind(text):
    """Return [(line number, statement)] for every blind assertion in text."""
    found = []
    for body in _bodies(text.splitlines()):
        code = [
            (no, stmt)
            for no, stmt in _logical_lines(body)
            if stmt and not stmt.startswith("#")
        ]
        for no, stmt in code[:-1]:
            if stmt.startswith("[[ ") and not GUARDED_BRACKET.search(stmt):
                found.append((no, stmt))
            elif stmt.startswith("! "):
                found.append((no, stmt))
    return found


def _bats_sources():
    for pattern in ("plugins/*/tests/bats/**/*.bats", "plugins/*/tests/bats/**/*.bash"):
        yield from REPO_ROOT.glob(pattern)


def test_no_blind_assertions_in_bats_suites():
    sources = sorted(set(_bats_sources()))
    assert sources, "glob matched no bats sources — the scan would pass vacuously"
    findings = [
        "%s:%d  %s" % (path.relative_to(REPO_ROOT), no, stmt)
        for path in sources
        for no, stmt in find_blind(path.read_text(encoding="utf-8", errors="replace"))
    ]
    assert not findings, (
        "non-final bare [[ ]] / `! cmd` cannot fail a bats test "
        "(use _has/_lacks or [ ]):\n" + "\n".join(findings)
    )


# --- the detector itself ------------------------------------------------------


def _lines(found):
    return [no for no, _ in found]


def test_flags_a_non_final_bracket():
    src = '@test "t" {\n  [[ "$o" == *x* ]]\n  true\n}\n'
    assert _lines(find_blind(src)) == [2]


def test_flags_a_non_final_negation():
    src = '@test "t" {\n  ! grep -q x f\n  true\n}\n'
    assert _lines(find_blind(src)) == [2]


def test_flags_inside_a_helper_function():
    src = '_helper() {\n  [[ "$o" == *x* ]]\n  return 0\n}\n'
    assert _lines(find_blind(src)) == [2]


def test_exempts_the_final_statement():
    src = '@test "t" {\n  true\n  [[ "$o" == *x* ]]\n  # trailing comment\n\n}\n'
    assert find_blind(src) == []


def test_exempts_a_guarded_bracket_on_one_line():
    src = '@test "t" {\n  [[ "$o" == *x* ]] || { echo no >&2; return 1; }\n  true\n}\n'
    assert find_blind(src) == []


def test_exempts_a_guarded_bracket_across_a_continuation():
    src = '@test "t" {\n  [[ "$o" == *x* ]] \\\n    || return 1\n  true\n}\n'
    assert find_blind(src) == []


def test_does_not_treat_an_unguarded_bracket_with_inner_or_as_guarded():
    src = '@test "t" {\n  [[ "$o" == *a* || "$o" == *b* ]]\n  true\n}\n'
    assert _lines(find_blind(src)) == [2]


def test_body_ends_at_column_zero_brace_not_at_brace_balance():
    # `${x}` and a jq filter would unbalance a brace counter and run this body
    # into the next test, making line 3 look non-final.
    src = (
        '@test "a" {\n'
        "  jq -n '{a: {b: 1}' >/dev/null\n"
        '  ! grep -q "${x}" f\n'
        "}\n"
        '@test "b" {\n'
        "  true\n"
        "}\n"
    )
    assert find_blind(src) == []
