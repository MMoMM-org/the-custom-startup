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

The single-source checks (spec 023 T1.4, SDD-ADR-2) scan every git-tracked .md
under plugins/ and docs/about/ outside catalog/: no active entry's fingerprint is
copied there, every PA-NN token names an indexed entry that is not retired, no
file @-imports a catalog file, every documented `claude plugin eval` run keeps
its report private, and each consumer skill cites at least one entry. Each scan
is a function returning "file:line ..." findings, run once against the repo and
once against seeded fixtures, so a scan that silently finds nothing fails.
Contested entries are exempt from the copy scan; their intentional copies are
pinned instead (repo ADR-4).
"""
import bisect
import re
import subprocess
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

PROFILES_DIR = CATALOG_DIR.parent / 'profiles'
PROFILE_TARGETS = ('anthropic', 'openai', 'google', 'small-local')
PROFILE_TOPICS = ('Placement', 'Delimiters', 'Examples', 'Negatives', 'Emphasis', 'Literalness', 'Turn shape')
PROFILE_FIELDS = ('Source', 'Date', 'Evidence')
# SDD-ADR-6: only the T5 findings are measured for small-local; no vendor guidance exists for it.
SMALL_LOCAL_MEASURED = ('Turn shape', 'Gate exits')
# A topic whose guidance has no source says so in its first word, so a port report can repeat the label.
UNVERIFIED_LEAD_IN = 'Unverified'
DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
PA_REF_RE = re.compile(r'\bPA-\d{2}\b')


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


def _fingerprints(entry):
    return QUOTED_RE.findall(entry['fields'].get('Fingerprint', ''))


# ---------------------------------------------------------------- profile parse

def _profile_path(target):
    return PROFILES_DIR / f'{target}.md'


def _profile_topics(path):
    """Return {topic: {'guidance': [lines], 'fields': {name: value}}} for each '## ' section."""
    topics = {}
    current = None
    for lineno, line in enumerate(path.read_text(encoding='utf-8').splitlines(), start=1):
        if line.startswith('## '):
            topic = line[3:].strip()
            assert topic not in topics, f'{path.name}:{lineno}: duplicate "## {topic}" heading'
            current = {'guidance': [], 'fields': {}}
            topics[topic] = current
            continue
        if current is None or not line.strip():
            continue
        field = FIELD_RE.match(line)
        if field:
            current['fields'][field.group(1)] = field.group(2).strip()
        else:
            current['guidance'].append(line)
    return topics


def _load_profile(target):
    """Return (text, topics) of a port profile; a missing profile fails the calling test."""
    path = _profile_path(target)
    assert path.is_file(), f'missing port profile {target}.md'
    return path.read_text(encoding='utf-8'), _profile_topics(path)


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

@pytest.mark.parametrize('target', PROFILE_TARGETS)
def test_profile_exists(target):
    assert _profile_path(target).is_file(), f'missing port profile {target}.md'


@pytest.mark.parametrize('target', PROFILE_TARGETS)
def test_profile_has_every_topic_with_guidance_source_date_and_evidence(target):
    _, topics = _load_profile(target)
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
    _, topics = _load_profile('small-local')
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


@pytest.mark.parametrize('target', [t for t in PROFILE_TARGETS if t != 'small-local'])
def test_vendor_profiles_grade_no_topic_as_measured(target):
    # SDD-ADR-6: the only measurements are the T5 runs on a small local model.
    _, topics = _load_profile(target)
    measured = [
        topic for topic, section in topics.items()
        if _grade(section['fields'].get('Evidence', '')) == 'measured'
    ]
    assert not measured, f'{target}: topics graded measured without a measurement: {measured}'


@pytest.mark.parametrize('target', PROFILE_TARGETS)
def test_unverified_lead_in_matches_the_grade(target):
    _, topics = _load_profile(target)
    problems = []
    for topic, section in topics.items():
        unverified = _grade(section['fields'].get('Evidence', '')) == 'unverified'
        leads_in = bool(section['guidance']) and section['guidance'][0].startswith(UNVERIFIED_LEAD_IN)
        if unverified and not leads_in:
            problems.append(f'{target} / {topic}: graded unverified, guidance must start with "{UNVERIFIED_LEAD_IN}"')
        if leads_in and not unverified:
            problems.append(f'{target} / {topic}: guidance starts with "{UNVERIFIED_LEAD_IN}" but is graded otherwise')
    assert not problems, '\n'.join(problems)


@pytest.mark.parametrize('target', PROFILE_TARGETS)
def test_profile_cites_only_catalogued_entries(target):
    text, _ = _load_profile(target)
    cited = set(PA_REF_RE.findall(text))
    known = {e['id'] for e in _all_entries()}
    assert cited, f'{target}.md cites no catalog entry; profiles cite PA IDs for the underlying rule'
    assert not cited - known, f'{target}.md cites unknown entries {sorted(cited - known)}'


@pytest.mark.parametrize('target', PROFILE_TARGETS)
def test_profile_does_not_restate_a_catalog_fingerprint(target):
    text, _ = _load_profile(target)
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


# ---------------------------------------------------------------- single source (T1.4)

SCAN_ROOTS = ('plugins', 'docs/about')
CATALOG_REL = CATALOG_DIR.relative_to(REPO_ROOT).as_posix() + '/'
TCS_HELPER_REL = 'plugins/tcs-helper/'
EVAL_LOOP = REPO_ROOT / 'plugins/tcs-helper/skills/prompt-author/reference/eval-loop.md'
PA_TOKEN_RE = re.compile(r'\bPA-\d+\b')
# An @-import starts a line or follows whitespace or an opening bracket, as Claude Code resolves it.
CATALOG_IMPORT_RE = re.compile(r'(?:^|[\s(\[])@(\S*catalog/[\w.-]+\.md)')
EVAL_COMMAND = 'claude plugin eval'
EVAL_REQUIRED_FLAGS = ('--no-publish', '--output-dir')

# Pre-migration fingerprint copies: {(file, PA ID): owning Phase 3 task}. A copy
# listed here is reported nowhere else; the owning task removes the entry, sees the
# test fail, and replaces the copy with a citation. T3.8 requires this to be empty.
# Found at T1.4 (2026-11-05): none. The known copies are paraphrases, which a
# fingerprint does not detect (SDD-ADR-2 trade-off); Phase 3 removes them by reading.
PRE_MIGRATION_COPIES = {}

AGENT_AUTHOR_REL = 'plugins/tcs-helper/skills/agent-author/'
AUTHORITY_PHRASE = 'MUST BE USED'

# Contested PA-50 (repo ADR-4): the description authority-language rule stays copied
# verbatim in agent-author. Every rule-bearing sentence carrying it (SKILL.md and
# reference/, outside fenced sample descriptions) is pinned by content, so a rewording
# revisits the decision. Line numbers may move; the text may not.
PINNED_AUTHORITY_SENTENCES = (
    ('SKILL.md',
     '- Make every `description` action-oriented with `Use PROACTIVELY` or `MUST BE USED` '
     '+ 2–5 concrete trigger phrases + 2–3 `<example>` blocks for high-value agents.'),
    ('SKILL.md',
     '   - `description`: `Use PROACTIVELY`/`MUST BE USED` + triggers + 2–3 `<example>` blocks; '
     'trigger in first ~50 chars'),
    ('SKILL.md',
     '2. **Description quality** — first ~50 chars contain trigger; has `Use PROACTIVELY` or '
     '`MUST BE USED`; has ≥2 trigger phrases; high-value agents have `<example>` blocks.'),
    ('reference/conventions.md',
     '- **Expect under-triggering.** Anthropic explicitly notes Claude tends to skip '
     'skills/agents when it should invoke them. Use *"slightly pushy"* phrasing: '
     '`Use PROACTIVELY when…` and `MUST BE USED when…`.'),
    ('reference/description-patterns.md',
     '### 3. Use imperative phrasing — `Use PROACTIVELY when…` and `MUST BE USED when…`'),
    ('reference/description-patterns.md',
     '1. **Action segment** with `Use PROACTIVELY` or `MUST BE USED`'),
    ('reference/description-patterns.md',
     '- [ ] Contains `Use PROACTIVELY` OR `MUST BE USED`'),
    ('reference/output-formats.md',
     '| | Contains `Use PROACTIVELY` or `MUST BE USED` | Yes |'),
    ('reference/anti-patterns.md',
     '- [ ] Description has no `Use PROACTIVELY` / `MUST BE USED`'),
)

CONSUMERS = {
    'skill-author': 'T3.1',
    'agent-author': 'T3.1',
    'memory-claude-md-optimize': 'T3.5',
}


def _normalise(text):
    """Lowercase, strip Markdown emphasis (*, _, `), collapse whitespace."""
    return ' '.join(re.sub(r'[*_`]', '', text.lower()).split())


def _consumer_rule_files(files, skill_dir):
    """The subset of files that are a skill's rules: SKILL.md and reference/*.md directly under it.

    examples/, evals/ and change logs illustrate or record; a citation there is not
    the skill applying the catalog.
    """
    rule_files = {skill_dir + 'SKILL.md'}
    return {
        rel: text for rel, text in files.items()
        if rel in rule_files or re.fullmatch(re.escape(skill_dir) + r'reference/[^/]+\.md', rel)
    }


def _resolving_citations(files, statuses):
    """['file:line PA-NN'] for each PA token that names an indexed entry that is not retired."""
    return [
        f'{rel}:{lineno} {token}'
        for rel, text in files.items()
        for lineno, line in enumerate(text.splitlines(), start=1)
        for token in PA_TOKEN_RE.findall(line)
        if statuses.get(token) not in (None, 'retired')
    ]


def _unfenced_lines(text):
    """[(line, text)] for lines outside fenced code blocks."""
    lines, fenced = [], False
    for lineno, line in enumerate(text.splitlines(), start=1):
        if line.lstrip().startswith('```'):
            fenced = not fenced
            continue
        if not fenced:
            lines.append((lineno, line))
    return lines


def _tracked_markdown():
    """{repo-relative path: text} for git-tracked .md files under SCAN_ROOTS outside catalog/."""
    listed = subprocess.run(
        ['git', '-C', str(REPO_ROOT), 'ls-files', '-z', '--', *SCAN_ROOTS],
        capture_output=True, text=True, check=True,
    ).stdout.split('\0')
    return {
        rel: (REPO_ROOT / rel).read_text(encoding='utf-8')
        for rel in listed
        if rel.endswith('.md') and not rel.startswith(CATALOG_REL) and (REPO_ROOT / rel).is_file()
    }


def _index_statuses():
    """{PA ID: status} from the index rows."""
    statuses = {}
    for cells in _index_rows():
        link = INDEX_LINK_RE.match(cells[0])
        if link and len(cells) == 7:
            statuses[link.group(1)] = cells[5]
    return statuses


def _active_fingerprints():
    """[(PA ID, fingerprint)] of active entries; contested and retired entries are exempt."""
    return [
        (e['id'], sentence)
        for e in _all_entries()
        if e['fields'].get('Status') == 'active'
        for sentence in _fingerprints(e)
    ]


def _copy_findings(files, fingerprints):
    """[(file, line, PA ID, fingerprint)] for each fingerprint found in a file after normalising.

    Lines are normalised one by one and joined with a space, which equals normalising
    the whole file, so a fingerprint wrapped across lines is still found.
    """
    findings = []
    for rel, text in files.items():
        starts, parts, line_numbers, offset = [], [], [], 0
        for lineno, line in enumerate(text.splitlines(), start=1):
            part = _normalise(line)
            if not part:
                continue
            starts.append(offset)
            parts.append(part)
            line_numbers.append(lineno)
            offset += len(part) + 1
        joined = ' '.join(parts)
        for entry_id, sentence in fingerprints:
            needle = _normalise(sentence)
            position = joined.find(needle) if needle else -1
            while position >= 0:
                lineno = line_numbers[bisect.bisect_right(starts, position) - 1]
                findings.append((rel, lineno, entry_id, sentence))
                position = joined.find(needle, position + 1)
    return findings


def _dead_id_findings(files, statuses):
    """['file:line PA-NN reason'] for each PA token not in the index or retired."""
    findings = []
    for rel, text in files.items():
        for lineno, line in enumerate(text.splitlines(), start=1):
            for token in PA_TOKEN_RE.findall(line):
                if token not in statuses:
                    findings.append(f'{rel}:{lineno}: {token} is not in index.md')
                elif statuses[token] == 'retired':
                    findings.append(f'{rel}:{lineno}: {token} is retired')
    return findings


def _catalog_import_findings(files):
    findings = []
    for rel, text in files.items():
        for lineno, line in enumerate(text.splitlines(), start=1):
            for target in CATALOG_IMPORT_RE.findall(line):
                findings.append(f'{rel}:{lineno}: @-imports {target}; cite the entry ID instead')
    return findings


def _eval_commands(text):
    """[(line, command)] for each documented `claude plugin eval` run.

    An inline-code command ends at its closing backtick; a fenced one continues over
    lines ending in a backslash. A bare mention (`claude plugin eval` with no
    arguments) and the `init` subcommand run nothing and are skipped.
    """
    lines = text.splitlines()
    commands = []
    for index, line in enumerate(lines):
        position = line.find(EVAL_COMMAND)
        while position >= 0:
            inline = position > 0 and line[position - 1] == '`'
            command, follow = line[position:], index
            if inline:
                while '`' not in command and follow + 1 < len(lines):
                    follow += 1
                    command += ' ' + lines[follow]
                command = command.split('`', 1)[0]
            else:
                while command.rstrip().endswith('\\') and follow + 1 < len(lines):
                    follow += 1
                    command = command.rstrip()[:-1] + ' ' + lines[follow]
            arguments = command[len(EVAL_COMMAND):].split()
            if arguments and arguments[0] != 'init':
                commands.append((index + 1, ' '.join(command.split())))
            position = line.find(EVAL_COMMAND, position + len(EVAL_COMMAND))
    return commands


def _eval_flag_findings(files):
    """[(file, line, missing flag, command)] for documented eval runs lacking a required flag."""
    findings = []
    for rel, text in files.items():
        for lineno, command in _eval_commands(text):
            for flag in EVAL_REQUIRED_FLAGS:
                if flag not in command.split():
                    findings.append((rel, lineno, flag, command))
    return findings


def _tcs_helper(files):
    return {rel: text for rel, text in files.items() if rel.startswith(TCS_HELPER_REL)}


# Fixtures: one of each defect the scans must catch, in files the repo scan never sees.

def _seeded_files(tmp_path):
    """{relative path: text} written under tmp_path, each carrying one seeded defect."""
    fingerprint = _active_fingerprints()[0]
    seeds = {
        'plugins/demo/copy.md': f'# Demo\n\nIntro line.\n**{fingerprint[1].upper()}**\n',
        'plugins/demo/wrapped.md': 'Lead.\n' + fingerprint[1].replace(' ', '\n', 1) + '\n',
        'plugins/demo/dead.md': 'See PA-99 for the rule.\n',
        'plugins/demo/retired.md': 'Line one.\nSee PA-01.\n',
        'docs/about/import.md': 'Rules:\n@../plugins/tcs-helper/skills/prompt-author/reference/catalog/core.md\n',
        'plugins/tcs-helper/evals/README.md': (
            'Run `claude plugin eval plugins/tcs-helper --case x --no-publish`.\n'
            '```\nclaude plugin eval plugins/tcs-helper --runs 3 \\\n  --output-dir /tmp/x\n```\n'
            'A `claude plugin eval` case; scaffold with `claude plugin eval init --bare x`.\n'
        ),
    }
    for rel, text in seeds.items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
    return {rel: (tmp_path / rel).read_text(encoding='utf-8') for rel in seeds}, fingerprint


def test_tracked_markdown_scan_covers_plugins_and_docs_about_but_not_the_catalog():
    files = _tracked_markdown()
    assert any(rel.startswith('docs/about/') for rel in files), 'docs/about/ not scanned'
    assert any(rel.startswith('plugins/tcs-helper/skills/prompt-author/reference/profiles/') for rel in files)
    assert not any(rel.startswith(CATALOG_REL) for rel in files), 'the catalog must not scan itself'


def test_copy_scan_catches_a_seeded_copy_with_file_and_line(tmp_path):
    files, (entry_id, sentence) = _seeded_files(tmp_path)
    found = {(rel, line, pa) for rel, line, pa, _ in _copy_findings(files, [(entry_id, sentence)])}
    assert ('plugins/demo/copy.md', 4, entry_id) in found
    assert ('plugins/demo/wrapped.md', 2, entry_id) in found


def test_index_statuses_reads_every_catalog_entry_with_its_real_status():
    statuses = _index_statuses()
    assert set(statuses) == set(EXPECTED), (
        f'index IDs differ from solution.md: missing {sorted(set(EXPECTED) - set(statuses))}, '
        f'extra {sorted(set(statuses) - set(EXPECTED))}'
    )
    expected = {pa: 'contested' if spec['contested'] else 'active' for pa, spec in EXPECTED.items()}
    assert statuses == expected
    assert statuses['PA-50'] == 'contested'
    assert {pa: e['fields'].get('Status') for pa, e in ((e['id'], e) for e in _all_entries())} == statuses


def test_id_scan_catches_a_dead_and_a_retired_id_with_file_and_line(tmp_path):
    files, _ = _seeded_files(tmp_path)
    statuses = dict(_index_statuses(), **{'PA-01': 'retired'})
    findings = _dead_id_findings(files, statuses)
    assert 'plugins/demo/dead.md:1: PA-99 is not in index.md' in findings
    assert 'plugins/demo/retired.md:2: PA-01 is retired' in findings


def test_import_scan_catches_a_seeded_catalog_import_with_file_and_line(tmp_path):
    files, _ = _seeded_files(tmp_path)
    findings = _catalog_import_findings(files)
    assert findings == [
        'docs/about/import.md:2: @-imports ../plugins/tcs-helper/skills/prompt-author/reference/catalog/core.md; '
        'cite the entry ID instead'
    ]


def test_eval_scan_catches_runs_without_the_privacy_flags(tmp_path):
    files, _ = _seeded_files(tmp_path)
    found = {(rel, line, flag) for rel, line, flag, _ in _eval_flag_findings(files)}
    assert found == {
        ('plugins/tcs-helper/evals/README.md', 1, '--output-dir'),
        ('plugins/tcs-helper/evals/README.md', 3, '--no-publish'),
    }


def test_no_active_fingerprint_is_copied_outside_the_catalog():
    findings = _copy_findings(_tracked_markdown(), _active_fingerprints())
    unlisted = [
        f'{rel}:{line}: copies {pa} fingerprint "{sentence}"; cite {pa} instead'
        for rel, line, pa, sentence in findings
        if (rel, pa) not in PRE_MIGRATION_COPIES
    ]
    assert not unlisted, '\n'.join(unlisted)


def test_pre_migration_allow_list_is_owned_and_still_needed():
    found = {(rel, pa) for rel, _, pa, _ in _copy_findings(_tracked_markdown(), _active_fingerprints())}
    problems = [
        f'{key}: owner {owner!r} is not a Phase 3 task' for key, owner in PRE_MIGRATION_COPIES.items()
        if not re.fullmatch(r'T3\.[1-7]', owner)
    ] + [f'{key}: no longer copied; remove it from PRE_MIGRATION_COPIES' for key in PRE_MIGRATION_COPIES
         if key not in found]
    assert not problems, '\n'.join(problems)


def test_every_pa_token_outside_the_catalog_names_an_indexed_entry_that_is_not_retired():
    findings = _dead_id_findings(_tracked_markdown(), _index_statuses())
    assert not findings, '\n'.join(findings)


def test_no_file_at_imports_a_catalog_file():
    listed = subprocess.run(
        ['git', '-C', str(REPO_ROOT), 'ls-files', '-z', '--', '*.md'],
        capture_output=True, text=True, check=True,
    ).stdout.split('\0')
    files = {rel: (REPO_ROOT / rel).read_text(encoding='utf-8')
             for rel in listed if rel.endswith('.md') and (REPO_ROOT / rel).is_file()}
    findings = _catalog_import_findings(files)
    assert not findings, '\n'.join(findings)


def test_documented_plugin_eval_runs_keep_the_report_private():
    files = _tcs_helper(_tracked_markdown())
    assert any(_eval_commands(text) for text in files.values()), 'no documented `claude plugin eval` run found'
    findings = [
        f'{rel}:{line}: `claude plugin eval` run lacks {flag}: {command}'
        for rel, line, flag, command in _eval_flag_findings(files)
    ]
    assert not findings, '\n'.join(findings)


@pytest.mark.xfail(strict=True, reason='eval-loop.md is written in T2.4; remove this marker there')
def test_eval_loop_reference_exists():
    assert EVAL_LOOP.is_file(), f'missing {EVAL_LOOP.relative_to(REPO_ROOT)}'


@pytest.mark.parametrize('rel, sentence', PINNED_AUTHORITY_SENTENCES)
def test_contested_authority_sentences_stay_verbatim(rel, sentence):
    text = (REPO_ROOT / AGENT_AUTHOR_REL / rel).read_text(encoding='utf-8')
    assert sentence in text, f'{AGENT_AUTHOR_REL}{rel}: pinned PA-50 sentence changed: {sentence!r}'


def test_every_rule_bearing_authority_sentence_is_pinned():
    files = _consumer_rule_files(_tracked_markdown(), AGENT_AUTHOR_REL)
    assert AGENT_AUTHOR_REL + 'SKILL.md' in files, 'agent-author SKILL.md not scanned'
    pinned = {(AGENT_AUTHOR_REL + rel, sentence) for rel, sentence in PINNED_AUTHORITY_SENTENCES}
    unpinned = [
        f'{rel}:{lineno}: {line.strip()}'
        for rel, text in sorted(files.items())
        for lineno, line in _unfenced_lines(text)
        if AUTHORITY_PHRASE in line
        and not any(rel == pin_rel and sentence in line for pin_rel, sentence in pinned)
    ]
    assert not unpinned, 'pin these PA-50 sentences in PINNED_AUTHORITY_SENTENCES:\n' + '\n'.join(unpinned)


@pytest.mark.parametrize('consumer', [
    pytest.param(name, marks=pytest.mark.xfail(strict=True, reason=f'{name} cites the catalog from {task}'))
    for name, task in CONSUMERS.items()
])
def test_consumer_cites_a_catalog_entry(consumer):
    skill_dir = f'plugins/tcs-helper/skills/{consumer}/'
    files = _consumer_rule_files(_tracked_markdown(), skill_dir)
    assert skill_dir + 'SKILL.md' in files, f'no tracked {skill_dir}SKILL.md'
    assert _resolving_citations(files, _index_statuses()), (
        f'{consumer}: neither SKILL.md nor reference/*.md cites an indexed, non-retired PA entry'
    )


def test_consumer_citation_counts_only_resolving_ids_in_rule_files(tmp_path):
    skill_dir = 'plugins/tcs-helper/skills/demo/'
    seeds = {
        'SKILL.md': '# Demo\n\nNo citation here.\n',
        'reference/rules.md': 'See PA-99 and PA-01.\n',
        'examples/sample.md': 'Avoid PA-02.\n',
        'evals/README.md': 'Checks PA-03.\n',
        'CHANGELOG.md': 'Cites PA-04 now.\n',
        'reference/nested/deep.md': 'PA-05.\n',
    }
    for rel, text in seeds.items():
        path = tmp_path / skill_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
    files = {skill_dir + rel: (tmp_path / skill_dir / rel).read_text(encoding='utf-8') for rel in seeds}
    statuses = dict(_index_statuses(), **{'PA-01': 'retired'})

    rule_files = _consumer_rule_files(files, skill_dir)
    assert set(rule_files) == {skill_dir + 'SKILL.md', skill_dir + 'reference/rules.md'}
    assert _resolving_citations(rule_files, statuses) == [], 'unknown PA-99 and retired PA-01 must not count'

    files[skill_dir + 'SKILL.md'] += 'Applies PA-02.\n'
    assert _resolving_citations(_consumer_rule_files(files, skill_dir), statuses) == [
        f'{skill_dir}SKILL.md:4 PA-02'
    ]
