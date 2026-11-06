"""agent-author's canonical example meets its own agentic contract (spec 023 T3.8, F-B1).

examples/canonical-agent.md is the reference target agent-author points authors at,
so an example that skips the contract teaches authors to skip it. Each test checks
one element: the Mission's done criterion (PA-22) and the four rows of the
conventions.md § Agentic Contract table (PA-20, PA-21, PA-23, PA-24).

The markers are read from that table, not restated here, so a reworded table row
fails these tests until the example follows it.
"""
import re

from catalog_helpers import REPO_ROOT

AGENT_AUTHOR = REPO_ROOT / 'plugins/tcs-helper/skills/agent-author'
CANONICAL = AGENT_AUTHOR / 'examples/canonical-agent.md'
CONVENTIONS = AGENT_AUTHOR / 'reference/conventions.md'

BODY_START = '## File: '
BODY_END = '## Why this is canonical'
BACKTICK_RE = re.compile(r'`([^`]+)`')


# ---------------------------------------------------------------- loaders

def contract_row(pa_id):
    """The § Agentic Contract table row that cites pa_id."""
    text = CONVENTIONS.read_text(encoding='utf-8')
    section = text.split('## Agentic Contract', 1)[1].split('\n## ', 1)[0]
    anchor = f'#{pa_id.lower()}-'
    rows = [line for line in section.splitlines() if line.startswith('|') and anchor in line]
    assert len(rows) == 1, f'expected one Agentic Contract row citing {pa_id}, found {len(rows)}'
    return rows[0]


def table_marker(pa_id, phrase):
    """phrase, after asserting the table row still words the rule with it."""
    assert phrase in contract_row(pa_id), (
        f'conventions.md § Agentic Contract row {pa_id} no longer contains {phrase!r}; '
        'update the marker here and the canonical example together'
    )
    return phrase


def agent_body():
    """The annotated agent file: from '## File:' to '## Why this is canonical'."""
    text = CANONICAL.read_text(encoding='utf-8')
    start = text.index(BODY_START)
    return text[start:text.index(BODY_END, start)]


def section(heading_prefix):
    """The body of the first '## <heading_prefix>...' section of the agent file."""
    parts = re.split(r'^## ', agent_body(), flags=re.MULTILINE)
    matches = [p for p in parts if p.startswith(heading_prefix)]
    assert matches, f'canonical agent has no "## {heading_prefix}" section'
    return matches[0].split('\n', 1)[1]


def constraint_block(kind):
    """The items of the Constraints `require {}` or `never {}` block."""
    constraints = section('Constraints')
    match = re.search(kind + r'\s*\{\n(.*?)\n\s*\}', constraints, flags=re.DOTALL)
    assert match, f'Constraints has no {kind} {{}} block'
    return [line.strip() for line in match.group(1).splitlines() if line.strip()]


def table_rows(text):
    """Data rows of every Markdown table in text, header and divider rows excluded."""
    lines = [line for line in text.splitlines() if line.startswith('|')]
    return [
        line for i, line in enumerate(lines)
        if not re.fullmatch(r'\|[\s|:-]+\|', line)
        and not (i + 1 < len(lines) and re.fullmatch(r'\|[\s|:-]+\|', lines[i + 1]))
    ]


def output_status_values():
    """The backticked values of the Output table's `status` field."""
    rows = [r for r in table_rows(section('Output')) if r.split('|')[1].strip() == 'status']
    assert len(rows) == 1, 'Output table has no single `status` field'
    return BACKTICK_RE.findall(rows[0])


# ---------------------------------------------------------------- tests

def test_mission_states_a_done_criterion():
    assert 'done criterion' in CONVENTIONS.read_text(encoding='utf-8')
    mission = section('Mission')
    assert re.search(r'\bis done when\b', mission), (
        'Mission names no done criterion ("... is done when ..."); conventions.md § 4 / PA-22'
    )


def test_unclear_input_returns_a_named_status():
    statuses = [s for s in BACKTICK_RE.findall(contract_row('PA-20')) if s.isupper()]
    assert statuses, 'PA-20 row names no status value'
    status = statuses[0]
    decision_rows = [r for r in table_rows(section('Decision')) if status in r]
    assert decision_rows, f'no ## Decision row returns `{status}` for an unclear input'
    assert status in output_status_values(), f'Output `status` does not list `{status}`'


def test_a_non_success_stop_condition_names_its_report():
    trigger = table_marker('PA-21', 'the same error twice')
    stop_lines = [
        line for line in constraint_block('require') + table_rows(section('Decision'))
        if trigger in line and re.search(r'\bstop\b', line, flags=re.IGNORECASE)
    ]
    assert stop_lines, f'no Constraints or Decision line stops on "{trigger}"'
    statuses = set(BACKTICK_RE.findall(stop_lines[0])) & set(output_status_values())
    assert statuses, 'the stop condition names no Output `status` value'
    status = statuses.pop()
    report_fields = [
        r for r in table_rows(section('Output'))
        if r.split('|')[1].strip() != 'status' and status in r
    ]
    assert report_fields, f'no Output field says what a `{status}` report contains'


def test_every_never_item_names_an_alternative():
    marker = table_marker('PA-23', 'instead')
    never_items = constraint_block('never')
    assert never_items, 'never {} block is empty'
    missing = [item for item in never_items if marker not in item]
    assert not missing, f'never {{}} items with no "{marker}" alternative: {missing}'


def test_scope_fence_names_scope_and_allowed_git_and_writes():
    ignore_marker = table_marker('PA-24', 'everything else')
    table_marker('PA-24', 'git and write operations')
    require = constraint_block('require')
    assert any(ignore_marker in item for item in require), (
        f'require {{}} does not tell the agent to ignore "{ignore_marker}"'
    )
    git_items = [
        item for item in require
        if re.search(r'`git [a-z]', item) and 'read-only' in item and 'write' in item
    ]
    assert git_items, (
        'require {} names no read-only git commands (backticked `git ...`) and write rule'
    )
