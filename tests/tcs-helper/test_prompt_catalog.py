"""Consistency checks for the prompt-author failure catalog (spec 023, component C5).

This file holds the format, ID-set, index-agreement and size checks. The expected
ID set, the file each entry lives in, the lint check it names and its contested
status are read from the INITIAL ENTRIES block of the spec's solution.md, so the
tests are red on a missing or partial catalog instead of passing vacuously.

The port-profile checks (spec 023 T1.2, SDD-ADR-6) cover reference/profiles/:
every topic sourced, dated and graded, and profiles cite catalog IDs instead of
restating entries.

Evidence is one grade wherever it appears (entry, index row, profile topic):
solution.md (ENTITY: CatalogEntry) defines no compound such as "vendor + measured".
"""
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOG_DIR = REPO_ROOT / 'plugins/tcs-helper/skills/prompt-author/reference/catalog'
INDEX_FILE = CATALOG_DIR / 'index.md'
SOLUTION_MD = REPO_ROOT / 'docs/XDD/specs/023-prompt-author/solution.md'

ENTRY_FILES = ('core.md', 'agentic.md', 'instruction-files.md', 'porting.md', 'harness.md')

KINDS = {'api-system', 'brief', 'chat-template', 'code', 'instruction-file', 'skill', 'agent', 'any'}
TARGETS = {'claude', 'openai', 'google', 'small-local', 'any'}
EVIDENCE_GRADES = {'vendor', 'measured', 'practitioner', 'unverified'}
STATUSES = {'active', 'contested', 'retired'}
LINT_CHECKS = {'E1', 'E2', 'E3', 'E4', 'W1', 'W2', 'W3'}

REQUIRED_FIELDS = ('Tell', 'Fails because', 'Fix', 'Applies to', 'Evidence', 'Fingerprint', 'Status')
MAX_ENTRY_LINES = 12
# Entries are loaded into the authoring context; the largest (PA-03) is ~1,570 chars, so 1,900 leaves ~20% headroom.
MAX_ENTRY_CHARS = 1900

HEADING_RE = re.compile(r'^## (PA-\d{2}) (.+?)\s*$')
FIELD_RE = re.compile(r'^- \*\*([^*]+):\*\* ?(.*)$')
QUOTED_RE = re.compile(r'"([^"]+)"')
CONTESTED_RE = re.compile(r'— contested|contested —')
INDEX_LINK_RE = re.compile(r'^\[(PA-\d{2})\]\(([^)#]+)#([^)]+)\)$')


# ---------------------------------------------------------------- expected set

def _initial_entries():
    """Parse solution.md INITIAL ENTRIES into {id: {file, lint, contested}}."""
    text = SOLUTION_MD.read_text(encoding='utf-8')
    try:
        start = text.index('INITIAL ENTRIES')
        end = text.index('ENTITY: CatalogIndex', start)
    except ValueError:
        raise AssertionError(
            f'{SOLUTION_MD}: no "INITIAL ENTRIES" block ending at "ENTITY: CatalogIndex"; '
            'the format of solution.md changed'
        ) from None
    expected = {}
    current_file = None
    block_start = text.count('\n', 0, start) + 1
    for offset, line in enumerate(text[start:end].splitlines()):
        file_match = re.match(r'^\s+([a-z-]+\.md)\s*$', line)
        if file_match:
            current_file = file_match.group(1)
            continue
        entry_match = re.match(r'^\s+(PA-\d{2})\s', line)
        if entry_match:
            if current_file is None:
                raise AssertionError(
                    f'{SOLUTION_MD}:{block_start + offset}: entry before any file heading: {line.strip()!r}'
                )
            lint = re.search(r'Lint: (E\d|W\d)', line)
            expected[entry_match.group(1)] = {
                'file': current_file,
                'lint': lint.group(1) if lint else None,
                'contested': bool(CONTESTED_RE.search(line)),
            }
    return expected


EXPECTED = _initial_entries()


# ---------------------------------------------------------------- catalog parse

def _sections(path):
    """Return [(id, name, lineno, body_lines)] for every '## PA-NN' section in path.

    body_lines run from the heading to the last non-blank line before the next
    '## ' heading or end of file.
    """
    lines = path.read_text(encoding='utf-8').splitlines()
    sections = []
    current = None
    for lineno, line in enumerate(lines, start=1):
        if line.startswith('## ') or line.startswith('# '):
            if current:
                sections.append(current)
                current = None
            heading = HEADING_RE.match(line)
            if heading:
                current = (heading.group(1), heading.group(2), lineno, [line])
            continue
        if current:
            current[3].append(line)
    if current:
        sections.append(current)
    trimmed = []
    for entry_id, name, lineno, body in sections:
        while body and not body[-1].strip():
            body.pop()
        trimmed.append((entry_id, name, lineno, body))
    return trimmed


def _fields(body):
    fields = {}
    for line in body[1:]:
        match = FIELD_RE.match(line)
        if match:
            fields[match.group(1)] = match.group(2).strip()
    return fields


def _strip_parentheticals(value):
    return re.sub(r'\([^)]*\)', '', value)


def _applies_to(value):
    """'brief, agent · any (note)' -> ({'brief', 'agent'}, {'any'})."""
    kinds_part, sep, targets_part = value.partition(' · ')
    assert sep, f'Applies to needs "<kinds> · <targets>": {value!r}'
    kinds = {k.strip() for k in _strip_parentheticals(kinds_part).split(',') if k.strip()}
    targets = {t.strip() for t in _strip_parentheticals(targets_part).split(',') if t.strip()}
    return kinds, targets


def _grade(value):
    """'measured (corpus: 3 of 16)' -> 'measured'; a compound such as 'vendor + measured' stays whole."""
    return ' '.join(_strip_parentheticals(value).split())


def _all_entries():
    entries = []
    for file_name in ENTRY_FILES:
        path = CATALOG_DIR / file_name
        if not path.exists():
            continue
        for entry_id, name, lineno, body in _sections(path):
            entries.append({
                'id': entry_id, 'name': name, 'file': file_name, 'lineno': lineno,
                'body': body, 'fields': _fields(body),
            })
    return entries


def _index_rows():
    rows = []
    for line in INDEX_FILE.read_text(encoding='utf-8').splitlines():
        if not line.startswith('|'):
            continue
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if cells[0] == 'ID' or set(cells[0]) <= set('-: '):
            continue
        rows.append(cells)
    return rows


def _github_slug(heading_text):
    slug = heading_text.strip().lower().replace('`', '')
    slug = re.sub(r'[^\w\- ]', '', slug)
    return slug.replace(' ', '-')


# ---------------------------------------------------------------- tests

def test_initial_entries_block_parses():
    assert len(EXPECTED) >= 30, 'INITIAL ENTRIES block in solution.md did not parse'
    assert all(spec['file'] in ENTRY_FILES for spec in EXPECTED.values())


@pytest.mark.parametrize('file_name', ('index.md',) + ENTRY_FILES)
def test_catalog_file_exists(file_name):
    assert (CATALOG_DIR / file_name).is_file(), f'missing catalog file {file_name}'


def test_entry_ids_are_unique():
    ids = [e['id'] for e in _all_entries()]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    assert not duplicates, f'duplicate entry IDs: {duplicates}'


def test_entry_id_set_matches_initial_entries():
    found = {e['id'] for e in _all_entries()}
    missing = sorted(set(EXPECTED) - found)
    extra = sorted(found - set(EXPECTED))
    assert not missing and not extra, f'missing: {missing}; not in solution.md: {extra}'


def test_each_entry_lives_in_its_specified_file():
    misplaced = [
        f"{e['id']} in {e['file']}, expected {EXPECTED[e['id']]['file']}"
        for e in _all_entries()
        if e['id'] in EXPECTED and EXPECTED[e['id']]['file'] != e['file']
    ]
    assert not misplaced, misplaced


def test_every_entry_has_all_fields():
    entries = _all_entries()
    assert entries, 'no catalog entries found'
    problems = []
    for e in entries:
        for field in REQUIRED_FIELDS:
            if not e['fields'].get(field):
                problems.append(f"{e['file']}:{e['lineno']} {e['id']} lacks {field}")
    assert not problems, '\n'.join(problems)


def test_field_values_use_the_allowed_vocabularies():
    problems = []
    for e in _all_entries():
        f = e['fields']
        where = f"{e['file']}:{e['lineno']} {e['id']}"
        if 'Applies to' in f:
            kinds, targets = _applies_to(f['Applies to'])
            if not kinds or kinds - KINDS:
                problems.append(f'{where} kinds {sorted(kinds - KINDS) or "empty"}')
            if not targets or targets - TARGETS:
                problems.append(f'{where} targets {sorted(targets - TARGETS) or "empty"}')
        if 'Status' in f and f['Status'] not in STATUSES:
            problems.append(f"{where} status {f['Status']!r}")
        if 'Fingerprint' in f:
            count = len(QUOTED_RE.findall(f['Fingerprint']))
            if not 1 <= count <= 3:
                problems.append(f'{where} has {count} fingerprint sentences, expected 1-3')
    assert not problems, '\n'.join(problems)


def test_vendor_graded_entries_cite_sources():
    uncited = [
        f"{e['file']}:{e['lineno']} {e['id']}"
        for e in _all_entries()
        if _grade(e['fields'].get('Evidence', '')) == 'vendor'
        and 'http' not in e['fields'].get('Sources', '')
    ]
    assert not uncited, f'vendor-graded entries without a Sources URL: {uncited}'


def test_lint_backed_entries_name_their_check():
    problems = []
    for e in _all_entries():
        expected_lint = EXPECTED.get(e['id'], {}).get('lint')
        named = e['fields'].get('Lint', '')
        named_checks = set(re.findall(r'\b[EW]\d\b', named))
        if named_checks - LINT_CHECKS:
            problems.append(f"{e['id']} names unknown check {sorted(named_checks - LINT_CHECKS)}")
        if expected_lint and expected_lint not in named_checks:
            problems.append(f"{e['id']} must name Lint: {expected_lint}")
        if not expected_lint and named_checks:
            problems.append(f"{e['id']} names {sorted(named_checks)}, solution.md lists none")
    assert not problems, problems


def test_contested_status_matches_initial_entries_and_states_the_decision():
    problems = []
    for e in _all_entries():
        status = e['fields'].get('Status')
        expected_contested = EXPECTED.get(e['id'], {}).get('contested', False)
        if expected_contested and status != 'contested':
            problems.append(f"{e['id']} must be contested")
        if not expected_contested and status == 'contested':
            problems.append(f"{e['id']} is contested, solution.md lists it as active")
        if status == 'contested' and not e['fields'].get('Decision'):
            problems.append(f"{e['id']} is contested but states no Decision")
    assert not problems, problems


def test_entries_stay_within_the_line_budget():
    too_long = [
        f"{e['file']}:{e['lineno']} {e['id']} has {len(e['body'])} lines"
        for e in _all_entries()
        if len(e['body']) > MAX_ENTRY_LINES
    ]
    assert not too_long, too_long


def test_entries_stay_within_the_character_budget():
    too_long = []
    for e in _all_entries():
        size = len('\n'.join(e['body']))
        if size > MAX_ENTRY_CHARS:
            too_long.append(f"{e['file']}:{e['lineno']} {e['id']} has {size} chars")
    assert not too_long, too_long


def _fingerprints(entry):
    return QUOTED_RE.findall(entry['fields'].get('Fingerprint', ''))


def test_fingerprints_are_unique_across_entries():
    owners = {}
    for e in _all_entries():
        for sentence in _fingerprints(e):
            owners.setdefault(sentence, []).append(e['id'])
    shared = {s: ids for s, ids in owners.items() if len(ids) > 1}
    assert not shared, f'fingerprints shared by several entries: {shared}'


def test_index_rows_and_sections_agree():
    entries = {e['id']: e for e in _all_entries()}
    rows = _index_rows()
    row_ids = []
    problems = []
    for cells in rows:
        if len(cells) != 7:
            problems.append(f'index row needs 7 cells (id|name|kinds|targets|evidence|status|file): {cells}')
            continue
        id_cell, name, kinds, targets, evidence, status, file_name = cells
        link = INDEX_LINK_RE.match(id_cell)
        if not link:
            problems.append(f'index ID cell must be [PA-NN](file#anchor): {id_cell}')
            continue
        entry_id, link_file, anchor = link.groups()
        row_ids.append(entry_id)
        entry = entries.get(entry_id)
        if not entry:
            problems.append(f'index row {entry_id} has no section')
            continue
        f = entry['fields']
        entry_kinds, entry_targets = _applies_to(f.get('Applies to', ' · '))
        checks = {
            'name': (name, entry['name']),
            'file': (file_name, entry['file']),
            'link file': (link_file, entry['file']),
            'anchor': (anchor, _github_slug(f"{entry_id} {entry['name']}")),
            'status': (status, f.get('Status')),
            'kinds': ({k.strip() for k in kinds.split(',')}, entry_kinds),
            'targets': ({t.strip() for t in targets.split(',')}, entry_targets),
            'evidence': (evidence, _grade(f.get('Evidence', ''))),
        }
        for label, (in_index, in_section) in checks.items():
            if in_index != in_section:
                problems.append(f'{entry_id} {label}: index {in_index!r} vs section {in_section!r}')
    duplicates = sorted({i for i in row_ids if row_ids.count(i) > 1})
    if duplicates:
        problems.append(f'duplicate index rows: {duplicates}')
    missing_rows = sorted(set(entries) - set(row_ids))
    if missing_rows:
        problems.append(f'sections without an index row: {missing_rows}')
    assert rows, 'index has no rows'
    assert not problems, '\n'.join(problems)


# ---------------------------------------------------------------- port profiles

PROFILES_DIR = CATALOG_DIR.parent / 'profiles'
PROFILE_TARGETS = ('anthropic', 'openai', 'google', 'small-local')
PROFILE_TOPICS = ('Placement', 'Delimiters', 'Examples', 'Negatives', 'Emphasis', 'Literalness', 'Turn shape')
PROFILE_FIELDS = ('Source', 'Date', 'Evidence')
# SDD-ADR-6: only the T5 findings are measured for small-local; no vendor guidance exists for it.
SMALL_LOCAL_MEASURED = ('Turn shape', 'Gate exits')
DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
PA_REF_RE = re.compile(r'\bPA-\d{2}\b')


def _profile_topics(path):
    """Return {topic: {'guidance': [lines], 'fields': {name: value}}} for each '## ' section."""
    topics = {}
    current = None
    for line in path.read_text(encoding='utf-8').splitlines():
        if line.startswith('## '):
            current = {'guidance': [], 'fields': {}}
            topics[line[3:].strip()] = current
            continue
        if current is None or not line.strip():
            continue
        field = FIELD_RE.match(line)
        if field:
            current['fields'][field.group(1)] = field.group(2).strip()
        else:
            current['guidance'].append(line)
    return topics


def _profile_path(target):
    return PROFILES_DIR / f'{target}.md'


@pytest.mark.parametrize('target', PROFILE_TARGETS)
def test_profile_exists(target):
    assert _profile_path(target).is_file(), f'missing port profile {target}.md'


@pytest.mark.parametrize('target', PROFILE_TARGETS)
def test_profile_has_every_topic_with_guidance_source_date_and_evidence(target):
    path = _profile_path(target)
    assert path.is_file(), f'missing port profile {target}.md'
    topics = _profile_topics(path)
    problems = []
    for topic in PROFILE_TOPICS:
        if topic not in topics:
            problems.append(f'{target}: no "## {topic}" section')
    for topic, section in topics.items():
        where = f'{target} / {topic}'
        if not section['guidance']:
            problems.append(f'{where}: no guidance text')
        fields = section['fields']
        for name in PROFILE_FIELDS:
            if not fields.get(name):
                problems.append(f'{where}: lacks {name}')
        if fields.get('Date') and not DATE_RE.match(fields['Date']):
            problems.append(f"{where}: Date {fields['Date']!r} is not YYYY-MM-DD")
        if _grade(fields.get('Evidence', '')) == 'vendor' and 'http' not in fields.get('Source', ''):
            problems.append(f'{where}: vendor-graded without a source URL')
    assert not problems, '\n'.join(problems)


def test_small_local_grades_only_the_t5_findings_as_measured():
    path = _profile_path('small-local')
    assert path.is_file(), 'missing port profile small-local.md'
    topics = _profile_topics(path)
    problems = []
    for topic in SMALL_LOCAL_MEASURED:
        if topic not in topics:
            problems.append(f'small-local: no "## {topic}" section')
    for topic, section in topics.items():
        grade = _grade(section['fields'].get('Evidence', ''))
        expected = 'measured' if topic in SMALL_LOCAL_MEASURED else 'unverified'
        if grade != expected:
            problems.append(f'small-local / {topic}: evidence {grade!r}, expected {expected!r}')
    assert not problems, '\n'.join(problems)


@pytest.mark.parametrize('target', PROFILE_TARGETS)
def test_profile_cites_only_catalogued_entries(target):
    path = _profile_path(target)
    assert path.is_file(), f'missing port profile {target}.md'
    cited = set(PA_REF_RE.findall(path.read_text(encoding='utf-8')))
    known = {e['id'] for e in _all_entries()}
    assert cited, f'{target}.md cites no catalog entry; profiles cite PA IDs for the underlying rule'
    assert not cited - known, f'{target}.md cites unknown entries {sorted(cited - known)}'


@pytest.mark.parametrize('target', PROFILE_TARGETS)
def test_profile_does_not_restate_a_catalog_fingerprint(target):
    path = _profile_path(target)
    assert path.is_file(), f'missing port profile {target}.md'
    text = path.read_text(encoding='utf-8')
    copied = [
        f"{e['id']}: {sentence}"
        for e in _all_entries()
        for sentence in _fingerprints(e)
        if sentence in text
    ]
    assert not copied, f'{target}.md restates catalog entries instead of citing them: {copied}'


# ---------------------------------------------------------------- evidence grades

def _evidence_values():
    """{source: [(location, Evidence value)]} for catalog entries, index rows and profile topics."""
    profile_topics = [
        (f'{target}.md / {topic}', section['fields'].get('Evidence', ''))
        for target in PROFILE_TARGETS if _profile_path(target).is_file()
        for topic, section in _profile_topics(_profile_path(target)).items()
    ]
    return {
        'catalog entries': [
            (f"{e['file']}:{e['lineno']} {e['id']}", e['fields'].get('Evidence', '')) for e in _all_entries()
        ],
        'index rows': [(f'index.md {cells[0]}', cells[4]) for cells in _index_rows() if len(cells) == 7],
        'profile topics': profile_topics,
    }


def test_evidence_is_a_single_allowed_grade():
    sources = _evidence_values()
    empty = [name for name, values in sources.items() if not values]
    assert not empty, f'no Evidence values found in: {empty}'
    # A missing or empty value is reported by the field-presence and index-agreement tests.
    problems = [
        f'{where}: {_grade(value)!r} is not exactly one of {sorted(EVIDENCE_GRADES)}'
        for values in sources.values()
        for where, value in values
        if value and _grade(value) not in EVIDENCE_GRADES
    ]
    assert not problems, '\n'.join(problems)
