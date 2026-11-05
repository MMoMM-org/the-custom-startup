"""Shared parsing helpers and constants for the prompt-author catalog tests (spec 023).

The catalog, index and profile tests and the single-source scans all read the same
Markdown, so they parse it here once: a format change breaks one parser, not three
copies that could drift apart and disagree about what the catalog contains.

The expected ID set, the file each entry lives in, the lint check it names, its
evidence grade and its contested status are read from the INITIAL ENTRIES block of the spec's solution.md,
so the tests are red on a missing or partial catalog instead of passing vacuously.
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOG_DIR = REPO_ROOT / 'plugins/tcs-helper/skills/prompt-author/reference/catalog'
CATALOG_REL = CATALOG_DIR.relative_to(REPO_ROOT).as_posix() + '/'
INDEX_FILE = CATALOG_DIR / 'index.md'
SOLUTION_MD = REPO_ROOT / 'docs/XDD/specs/023-prompt-author/solution.md'

ENTRY_FILES = ('core.md', 'agentic.md', 'instruction-files.md', 'porting.md', 'harness.md')

KINDS = {'api-system', 'brief', 'chat-template', 'code', 'instruction-file', 'skill', 'agent', 'any'}
TARGETS = {'claude', 'openai', 'google', 'small-local', 'any'}
# solution.md ENTITY: CatalogEntry; vendor = a model vendor's own guidance, research = published research or a standards body.
EVIDENCE_GRADES = {'vendor', 'research', 'measured', 'practitioner', 'unverified'}
# Hosts of model vendors' own guidance; a vendor grade needs a source on one of them.
VENDOR_HOSTS = ('anthropic.com', 'claude.com', 'openai.com', 'google.com', 'google.dev')
URL_HOST_RE = re.compile(r'https?://([^/\s)]+)')
STATUSES = {'active', 'contested', 'retired'}
LINT_CHECKS = {'E1', 'E2', 'E3', 'E4', 'W1', 'W2', 'W3'}

REQUIRED_FIELDS = ('Tell', 'Fails because', 'Fix', 'Applies to', 'Evidence', 'Fingerprint', 'Status')

# A PA token anywhere in prose: a citation, a profile reference, a dead or retired ID.
PA_TOKEN_RE = re.compile(r'\bPA-\d+\b')
HEADING_RE = re.compile(r'^## (PA-\d{2}) (.+?)\s*$')
FIELD_RE = re.compile(r'^- \*\*([^*]+):\*\* ?(.*)$')
QUOTED_RE = re.compile(r'"([^"]+)"')
CONTESTED_RE = re.compile(r'— contested|contested —')
INDEX_LINK_RE = re.compile(r'^\[(PA-\d{2})\]\(([^)#]+)#([^)]+)\)$')

PROFILES_DIR = CATALOG_DIR.parent / 'profiles'
PROFILE_TARGETS = ('anthropic', 'openai', 'google', 'small-local')


# ---------------------------------------------------------------- expected set

def initial_entries():
    """Parse solution.md INITIAL ENTRIES into {id: {file, lint, grade, contested}}.

    The grade is the first word of the row's last column (before any "Lint:"); a
    contested row carries no expected grade, since "contested" is a status.
    """
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
            contested = bool(CONTESTED_RE.search(line))
            grade_column = re.split(r'\s{2,}', line.split('Lint:')[0].strip())[-1]
            expected[entry_match.group(1)] = {
                'file': current_file,
                'lint': lint.group(1) if lint else None,
                'grade': None if contested else grade_column.split()[0],
                'contested': contested,
            }
    return expected


EXPECTED = initial_entries()


# ---------------------------------------------------------------- catalog parse

def sections(path):
    """Return [(id, name, lineno, body_lines)] for every '## PA-NN' section in path.

    body_lines run from the heading to the last non-blank line before the next
    '## ' heading or end of file.
    """
    lines = path.read_text(encoding='utf-8').splitlines()
    found = []
    current = None
    for lineno, line in enumerate(lines, start=1):
        if line.startswith('## ') or line.startswith('# '):
            if current:
                found.append(current)
                current = None
            heading = HEADING_RE.match(line)
            if heading:
                current = (heading.group(1), heading.group(2), lineno, [line])
            continue
        if current:
            current[3].append(line)
    if current:
        found.append(current)
    trimmed = []
    for entry_id, name, lineno, body in found:
        while body and not body[-1].strip():
            body.pop()
        trimmed.append((entry_id, name, lineno, body))
    return trimmed


def entry_fields(body):
    fields = {}
    for line in body[1:]:
        match = FIELD_RE.match(line)
        if match:
            fields[match.group(1)] = match.group(2).strip()
    return fields


def strip_parentheticals(value):
    return re.sub(r'\([^)]*\)', '', value)


def applies_to(value):
    """'brief, agent · any (note)' -> ({'brief', 'agent'}, {'any'})."""
    kinds_part, sep, targets_part = value.partition(' · ')
    assert sep, f'Applies to needs "<kinds> · <targets>": {value!r}'
    kinds = {k.strip() for k in strip_parentheticals(kinds_part).split(',') if k.strip()}
    targets = {t.strip() for t in strip_parentheticals(targets_part).split(',') if t.strip()}
    return kinds, targets


def grade(value):
    """'measured (corpus: 3 of 16)' -> 'measured'; a compound such as 'vendor + measured' stays whole."""
    return ' '.join(strip_parentheticals(value).split())


def source_hosts(value):
    """Hosts of every URL in a Sources or Source value."""
    return URL_HOST_RE.findall(value)


def cites_a_vendor(value):
    return any(host == v or host.endswith('.' + v) for host in source_hosts(value) for v in VENDOR_HOSTS)


def all_entries():
    entries = []
    for file_name in ENTRY_FILES:
        path = CATALOG_DIR / file_name
        if not path.exists():
            continue
        for entry_id, name, lineno, body in sections(path):
            entries.append({
                'id': entry_id, 'name': name, 'file': file_name, 'lineno': lineno,
                'body': body, 'fields': entry_fields(body),
            })
    return entries


def index_rows():
    rows = []
    for line in INDEX_FILE.read_text(encoding='utf-8').splitlines():
        if not line.startswith('|'):
            continue
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if cells[0] == 'ID' or set(cells[0]) <= set('-: '):
            continue
        rows.append(cells)
    return rows


def index_statuses():
    """{PA ID: status} from the index rows."""
    statuses = {}
    for cells in index_rows():
        link = INDEX_LINK_RE.match(cells[0])
        if link and len(cells) == 7:
            statuses[link.group(1)] = cells[5]
    return statuses


def github_slug(heading_text):
    slug = heading_text.strip().lower().replace('`', '')
    slug = re.sub(r'[^\w\- ]', '', slug)
    return slug.replace(' ', '-')


def fingerprints(entry):
    return QUOTED_RE.findall(entry['fields'].get('Fingerprint', ''))


# ---------------------------------------------------------------- profile parse

def profile_path(target):
    return PROFILES_DIR / f'{target}.md'


def profile_topics(path):
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


def load_profile(target):
    """Return (text, topics) of a port profile; a missing profile fails the calling test."""
    path = profile_path(target)
    assert path.is_file(), f'missing port profile {target}.md'
    return path.read_text(encoding='utf-8'), profile_topics(path)
