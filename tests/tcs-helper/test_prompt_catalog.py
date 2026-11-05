"""Entry, index and evidence-grade checks for the prompt-author failure catalog (spec 023, C5).

Guards the catalog's own shape: the ID set and file placement match solution.md's
INITIAL ENTRIES, every entry carries all fields in the allowed vocabularies and stays
within its size budget, the index agrees row by row with the sections, and Evidence
is one grade wherever it appears. The catalog is loaded into the authoring context
and cited by ID from other skills, so a malformed entry or a drifting index row
misleads every consumer at once.

Evidence is one grade wherever it appears (entry, index row, profile topic):
solution.md (ENTITY: CatalogEntry) defines no compound such as "vendor + measured".
"""
import re

import pytest

from catalog_helpers import (
    CATALOG_DIR, ENTRY_FILES, EVIDENCE_GRADES, EXPECTED, INDEX_LINK_RE, KINDS, LINT_CHECKS,
    PROFILE_TARGETS, REQUIRED_FIELDS, STATUSES, TARGETS,
    all_entries, applies_to, cites_a_vendor, fingerprints, github_slug, grade, grade_rule_violations,
    index_rows, index_statuses, profile_path, profile_topics, source_hosts,
)

MAX_ENTRY_LINES = 12
# Entries are loaded into the authoring context; the largest (PA-03) is ~1,570 chars, so 1,900 leaves ~20% headroom.
MAX_ENTRY_CHARS = 1900
MAX_FINGERPRINTS = 3
# The copy scan searches every tracked .md for each fingerprint; a short one matches incidental prose.
MIN_FINGERPRINT_CHARS = 20


def test_initial_entries_block_parses():
    assert len(EXPECTED) >= 30, 'INITIAL ENTRIES block in solution.md did not parse'
    assert all(spec['file'] in ENTRY_FILES for spec in EXPECTED.values())


@pytest.mark.parametrize('file_name', ('index.md',) + ENTRY_FILES)
def test_catalog_file_exists(file_name):
    assert (CATALOG_DIR / file_name).is_file(), f'missing catalog file {file_name}'


def test_entry_ids_are_unique():
    ids = [e['id'] for e in all_entries()]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    assert not duplicates, f'duplicate entry IDs: {duplicates}'


def test_entry_id_set_matches_initial_entries():
    found = {e['id'] for e in all_entries()}
    missing = sorted(set(EXPECTED) - found)
    extra = sorted(found - set(EXPECTED))
    assert not missing and not extra, f'missing: {missing}; not in solution.md: {extra}'


def test_each_entry_lives_in_its_specified_file():
    misplaced = [
        f"{e['id']} in {e['file']}, expected {EXPECTED[e['id']]['file']}"
        for e in all_entries()
        if e['id'] in EXPECTED and EXPECTED[e['id']]['file'] != e['file']
    ]
    assert not misplaced, misplaced


def test_every_entry_has_all_fields():
    entries = all_entries()
    assert entries, 'no catalog entries found'
    problems = []
    for e in entries:
        for field in REQUIRED_FIELDS:
            if not e['fields'].get(field):
                problems.append(f"{e['file']}:{e['lineno']} {e['id']} lacks {field}")
    assert not problems, '\n'.join(problems)


def test_field_values_use_the_allowed_vocabularies():
    problems = []
    for e in all_entries():
        f = e['fields']
        where = f"{e['file']}:{e['lineno']} {e['id']}"
        if 'Applies to' in f:
            kinds, targets = applies_to(f['Applies to'])
            if not kinds or kinds - KINDS:
                problems.append(f'{where} kinds {sorted(kinds - KINDS) or "empty"}')
            if not targets or targets - TARGETS:
                problems.append(f'{where} targets {sorted(targets - TARGETS) or "empty"}')
        if 'Status' in f and f['Status'] not in STATUSES:
            problems.append(f"{where} status {f['Status']!r}")
        if 'Fingerprint' in f:
            sentences = fingerprints(e)
            if not 1 <= len(sentences) <= MAX_FINGERPRINTS:
                problems.append(f'{where} has {len(sentences)} fingerprint sentences, expected 1-{MAX_FINGERPRINTS}')
            problems += [
                f'{where} fingerprint {s!r} is shorter than {MIN_FINGERPRINT_CHARS} characters'
                for s in sentences if len(s) < MIN_FINGERPRINT_CHARS
            ]
    assert not problems, '\n'.join(problems)


def test_lint_backed_entries_name_their_check():
    problems = []
    for e in all_entries():
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
    for e in all_entries():
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
        for e in all_entries()
        if len(e['body']) > MAX_ENTRY_LINES
    ]
    assert not too_long, too_long


def test_entries_stay_within_the_character_budget():
    too_long = []
    for e in all_entries():
        size = len('\n'.join(e['body']))
        if size > MAX_ENTRY_CHARS:
            too_long.append(f"{e['file']}:{e['lineno']} {e['id']} has {size} chars")
    assert not too_long, too_long


def test_fingerprints_are_unique_across_entries():
    owners = {}
    for e in all_entries():
        for sentence in fingerprints(e):
            owners.setdefault(sentence, []).append(e['id'])
    shared = {s: ids for s, ids in owners.items() if len(ids) > 1}
    assert not shared, f'fingerprints shared by several entries: {shared}'


def test_index_rows_and_sections_agree():
    entries = {e['id']: e for e in all_entries()}
    rows = index_rows()
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
        entry_kinds, entry_targets = applies_to(f.get('Applies to', ' · '))
        checks = {
            'name': (name, entry['name']),
            'file': (file_name, entry['file']),
            'link file': (link_file, entry['file']),
            'anchor': (anchor, github_slug(f"{entry_id} {entry['name']}")),
            'status': (status, f.get('Status')),
            'kinds': ({k.strip() for k in kinds.split(',')}, entry_kinds),
            'targets': ({t.strip() for t in targets.split(',')}, entry_targets),
            'evidence': (evidence, grade(f.get('Evidence', ''))),
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


def test_index_statuses_reads_every_catalog_entry_with_its_real_status():
    # Section-to-row status agreement is test_index_rows_and_sections_agree's job.
    statuses = index_statuses()
    assert set(statuses) == set(EXPECTED), (
        f'index IDs differ from solution.md: missing {sorted(set(EXPECTED) - set(statuses))}, '
        f'extra {sorted(set(statuses) - set(EXPECTED))}'
    )
    expected = {pa: 'contested' if spec['contested'] else 'active' for pa, spec in EXPECTED.items()}
    assert statuses == expected
    assert statuses['PA-50'] == 'contested'


# ---------------------------------------------------------------- evidence grades

def _evidence_values():
    """{source: [(location, Evidence value)]} for catalog entries, index rows and profile topics."""
    topics = [
        (f'{target}.md / {topic}', section['fields'].get('Evidence', ''))
        for target in PROFILE_TARGETS if profile_path(target).is_file()
        for topic, section in profile_topics(profile_path(target)).items()
    ]
    return {
        'catalog entries': [
            (f"{e['file']}:{e['lineno']} {e['id']}", e['fields'].get('Evidence', '')) for e in all_entries()
        ],
        'index rows': [(f'index.md {cells[0]}', cells[4]) for cells in index_rows() if len(cells) == 7],
        'profile topics': topics,
    }


def test_evidence_is_a_single_allowed_grade():
    sources = _evidence_values()
    empty = [name for name, values in sources.items() if not values]
    assert not empty, f'no Evidence values found in: {empty}'
    # A missing or empty value is reported by the field-presence and index-agreement tests.
    problems = [
        f'{where}: {grade(value)!r} is not exactly one of {sorted(EVIDENCE_GRADES)}'
        for values in sources.values()
        for where, value in values
        if value and grade(value) not in EVIDENCE_GRADES
    ]
    assert not problems, '\n'.join(problems)


def test_evidence_grades_are_the_five_from_solution_md():
    # solution.md ENTITY: CatalogEntry, revised 2026-11-05: research split from vendor.
    assert EVIDENCE_GRADES == {'vendor', 'research', 'measured', 'practitioner', 'unverified'}


def test_each_entry_carries_the_grade_solution_md_gives_it():
    entries = {e['id']: e for e in all_entries()}
    problems = []
    for entry_id, spec in sorted(EXPECTED.items()):
        entry = entries.get(entry_id)
        if not entry:
            continue  # reported by test_entry_id_set_matches_initial_entries
        found = grade(entry['fields'].get('Evidence', ''))
        if spec['contested']:
            # "contested" is a status, not a grade: the entry keeps its own grade and says so.
            # solution.md gives a contested row no grade to compare against, so only
            # Status contested plus some valid grade can be checked here.
            if entry['fields'].get('Status') != 'contested' or found not in EVIDENCE_GRADES:
                problems.append(f'{entry_id}: contested row needs Status contested and one grade, has {found!r}')
            continue
        if found != spec['grade']:
            problems.append(f"{entry['file']}:{entry['lineno']} {entry_id}: evidence {found!r}, solution.md {spec['grade']!r}")
    assert not problems, '\n'.join(problems)


def test_entry_grades_follow_the_vendor_and_research_source_rules():
    # A study or OWASP is research, however well it is cited; vendor is a model vendor's own guidance.
    problems = [
        f"{e['file']}:{e['lineno']} {e['id']}: {problem}"
        for e in all_entries()
        for problem in grade_rule_violations(grade(e['fields'].get('Evidence', '')), e['fields'].get('Sources', ''))
    ]
    assert not problems, '\n'.join(problems)


@pytest.mark.parametrize('value, hosts', [
    ('https://platform.claude.com/docs/en/prompting', ['platform.claude.com']),
    ('http://docs.anthropic.com', ['docs.anthropic.com']),
    ('(https://developers.openai.com/api/docs)', ['developers.openai.com']),
    ('https://aistudio.google.com:443/prompts', ['aistudio.google.com']),
    ('see https://openai.com, then https://arxiv.org.', ['openai.com', 'arxiv.org']),
    ('https://genai.owasp.org/llmrisk/', ['genai.owasp.org']),
    ('', []),
    ('anthropic.com, no scheme', []),
])
def test_source_hosts_parses_the_host_of_every_url(value, hosts):
    assert source_hosts(value) == hosts


@pytest.mark.parametrize('value, expected', [
    ('https://platform.claude.com/docs/en/prompting', True),
    ('https://docs.anthropic.com/en/docs', True),
    ('https://aistudio.google.com/prompts', True),
    ('https://developers.openai.com/api/docs', True),
    ('http://docs.anthropic.com', True),
    ('https://openai.com:443/guide', True),
    ('https://arxiv.org/abs/1, then https://anthropic.com.', True),
    ('https://evilanthropic.com/docs', False),
    ('https://anthropic.com.evil.example/docs', False),
    ('https://arxiv.org/abs/2507.11538', False),
    ('https://genai.owasp.org/llmrisk/ and https://owasp.org/www-project', False),
    ('', False),
    ('docs.anthropic.com without a scheme', False),
])
def test_cites_a_vendor_accepts_only_model_vendor_hosts(value, expected):
    assert cites_a_vendor(value) is expected


@pytest.mark.parametrize('found, sources, expected', [
    ('vendor', 'https://docs.anthropic.com/en/docs', []),
    ('vendor', 'https://genai.owasp.org/llmrisk/', ["graded vendor, sources cite no model vendor (['genai.owasp.org'])"]),
    ('vendor', 'Anthropic docs, not linked', ['vendor-graded without a source URL']),
    ('research', 'https://arxiv.org/abs/2507.11538', []),
    ('research', 'IFScale, not linked', ['research-graded without a source URL']),
    ('measured', '', []),
    ('practitioner', '', []),
])
def test_grade_rule_violations(found, sources, expected):
    assert grade_rule_violations(found, sources) == expected
