"""Single-source checks for the prompt-author catalog (spec 023 T1.4, SDD-ADR-2).

The catalog is the one place a prompt-authoring rule is written; every other file
cites it by PA ID. A copied rule drifts from its entry, a dead ID points nowhere, and
an @-import loads the whole catalog into every session, so these scans guard the
git-tracked .md under plugins/ and docs/about/ outside catalog/: no active entry's
fingerprint is copied there, every PA token names an indexed entry that is not
retired, no file @-imports a catalog file, every documented `claude plugin eval` run
under plugins/ keeps its report private, and each consumer skill cites at least one
entry (strict xfails until Phase 3 migrates them).

Each scan is a function returning findings with file and line, run once against
the repo and once against seeded fixtures, so a scan that silently finds nothing
fails. Contested entries are exempt from the copy scan; their intentional copies
are pinned instead (repo ADR-4).
"""
import bisect
import re
import subprocess

import pytest

from catalog_helpers import (
    CATALOG_REL, PA_TOKEN_RE, REPO_ROOT, all_entries, fingerprints, index_statuses,
)

SCAN_ROOTS = ('plugins', 'docs/about')
ALL_FILES = ('.',)
EVAL_LOOP = REPO_ROOT / 'plugins/tcs-helper/skills/prompt-author/reference/eval-loop.md'
# An @-import starts a line or follows whitespace or an opening bracket, as Claude Code resolves it.
CATALOG_IMPORT_RE = re.compile(r'(?:^|[\s(\[])@(\S*catalog/[\w.-]+\.md)')
EVAL_COMMAND = 'claude plugin eval'
EVAL_REQUIRED_FLAGS = ('--no-publish', '--output-dir')
FENCE_RE = re.compile(r'^\s*(`{3,}|~{3,})')
INLINE_CODE_RE = re.compile(r'`[^`]*`')
# A blockquote or list marker opens the line, not the sentence; stripped so a quoted copy wrapped over lines still joins.
LINE_MARKER_RE = re.compile(r'^\s*(?:>\s*)*(?:(?:[-*+]|\d+\.)\s+)?')
TRAILING_PUNCTUATION = '.,;:)'

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
MIGRATED_CONSUMERS = {'skill-author', 'agent-author', 'memory-claude-md-optimize'}


# ---------------------------------------------------------------- loaders

def tracked_markdown(roots=SCAN_ROOTS, include_catalog=False):
    """{repo-relative path: text} for git-tracked .md files under roots, catalog/ excluded unless asked."""
    listed = subprocess.run(
        ['git', '-C', str(REPO_ROOT), 'ls-files', '-z', '--', *roots],
        capture_output=True, text=True, check=True,
    ).stdout.split('\0')
    return {
        rel: (REPO_ROOT / rel).read_text(encoding='utf-8')
        for rel in listed
        if rel.endswith('.md') and (REPO_ROOT / rel).is_file()
        and (include_catalog or not rel.startswith(CATALOG_REL))
    }


def active_fingerprints():
    """[(PA ID, fingerprint)] of active entries; contested and retired entries are exempt."""
    return [
        (e['id'], sentence)
        for e in all_entries()
        if e['fields'].get('Status') == 'active'
        for sentence in fingerprints(e)
    ]


def consumer_rule_files(files, skill_dir):
    """The subset of files that are a skill's rules: SKILL.md and reference/*.md directly under it.

    examples/, evals/ and change logs illustrate or record; a citation there is not
    the skill applying the catalog.
    """
    rule_files = {skill_dir + 'SKILL.md'}
    return {
        rel: text for rel, text in files.items()
        if rel in rule_files or re.fullmatch(re.escape(skill_dir) + r'reference/[^/]+\.md', rel)
    }


# ---------------------------------------------------------------- scans
#
# Accepted gaps, each a trade-off rather than an oversight: AUTHORITY_PHRASE matches
# case-sensitively within one line, so a lowercase or line-wrapped "MUST BE USED"
# escapes the pin check; a fingerprint matches only a verbatim copy after
# normalisation (case, *, _, `, whitespace, blockquote and list markers), so a
# paraphrased copy, or one with a link or HTML inside the sentence, is not detected
# (SDD-ADR-2: Phase 3 removes paraphrases by reading); the dead-ID scan counts tokens
# inside code too, on purpose, since a dead ID in a sample still misleads; and an eval
# run is recognised only from the literal "claude plugin eval" text, continued over
# lines by a trailing backslash outside inline code.

def normalise(text):
    """Lowercase, strip Markdown emphasis (*, _, `), collapse whitespace."""
    return ' '.join(re.sub(r'[*_`]', '', text.lower()).split())


def unfenced_lines(text):
    """[(line, text)] for lines outside ``` and ~~~ fenced code blocks.

    A fence closes only on a run of its own character at least as long as the opener.
    """
    lines, fence = [], None
    for lineno, line in enumerate(text.splitlines(), start=1):
        marker = FENCE_RE.match(line)
        if marker:
            run = marker.group(1)
            if fence is None:
                fence = run
                continue
            if run[0] == fence[0] and len(run) >= len(fence):
                fence = None
                continue
        if fence is None:
            lines.append((lineno, line))
    return lines


def resolving_citations(files, statuses):
    """['file:line PA-NN'] for each prose PA token naming an indexed entry that is not retired.

    Tokens in fenced blocks and inline code spans are samples, not the skill citing a rule.
    """
    return [
        f'{rel}:{lineno} {token}'
        for rel, text in files.items()
        for lineno, line in unfenced_lines(text)
        for token in PA_TOKEN_RE.findall(INLINE_CODE_RE.sub('', line))
        if statuses.get(token) not in (None, 'retired')
    ]


def copy_findings(files, sentences):
    """[(file, line, PA ID, fingerprint)] for each (PA ID, fingerprint) found in a file after normalising.

    Each line loses its blockquote and list markers, is normalised, and is joined to
    the next with a space, which equals normalising the whole file, so a fingerprint
    wrapped across lines is still found.
    """
    findings = []
    for rel, text in files.items():
        starts, parts, line_numbers, offset = [], [], [], 0
        for lineno, line in enumerate(text.splitlines(), start=1):
            part = normalise(LINE_MARKER_RE.sub('', line, count=1))
            if not part:
                continue
            starts.append(offset)
            parts.append(part)
            line_numbers.append(lineno)
            offset += len(part) + 1
        joined = ' '.join(parts)
        for entry_id, sentence in sentences:
            needle = normalise(sentence)
            position = joined.find(needle) if needle else -1
            while position >= 0:
                lineno = line_numbers[bisect.bisect_right(starts, position) - 1]
                findings.append((rel, lineno, entry_id, sentence))
                position = joined.find(needle, position + 1)
    return findings


def dead_id_findings(files, statuses):
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


def catalog_import_findings(files):
    findings = []
    for rel, text in files.items():
        for lineno, line in enumerate(text.splitlines(), start=1):
            for target in CATALOG_IMPORT_RE.findall(line):
                findings.append(f'{rel}:{lineno}: @-imports {target}; cite the entry ID instead')
    return findings


def eval_commands(text):
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


def flag_names(command):
    """{'--flag'} for each token, '=value' and trailing punctuation removed."""
    return {token.rstrip(TRAILING_PUNCTUATION).split('=', 1)[0] for token in command.split()}


def eval_flag_findings(files):
    """[(file, line, missing flag, command)] for documented eval runs lacking a required flag."""
    findings = []
    for rel, text in files.items():
        for lineno, command in eval_commands(text):
            present = flag_names(command)
            for flag in EVAL_REQUIRED_FLAGS:
                if flag not in present:
                    findings.append((rel, lineno, flag, command))
    return findings


def unpinned_authority_lines(files, pinned):
    """['file:line: text'] for unfenced lines carrying AUTHORITY_PHRASE that hold no (file, sentence) pin."""
    return [
        f'{rel}:{lineno}: {line.strip()}'
        for rel, text in sorted(files.items())
        for lineno, line in unfenced_lines(text)
        if AUTHORITY_PHRASE in line
        and not any(rel == pin_rel and sentence in line for pin_rel, sentence in pinned)
    ]


# ---------------------------------------------------------------- seeded fixtures

def _write_seeds(tmp_path, seeds):
    """Write {relative path: text} under tmp_path and read it back as the scans' input."""
    for rel, text in seeds.items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
    return {rel: (tmp_path / rel).read_text(encoding='utf-8') for rel in seeds}


def _seeded_files(tmp_path):
    """{relative path: text} written under tmp_path, each carrying one seeded defect or near miss."""
    fingerprint = active_fingerprints()[0]
    words = fingerprint[1].split()
    assert len(words) >= 4, f'seed fingerprint {fingerprint[1]!r} is too short to decorate'
    # Emphasis and a code span inside the sentence, where only normalisation can remove them.
    decorated = ' '.join([words[0], f'*{words[1]}*', f'`{words[2]}`', *words[3:]])
    near_miss = ' '.join([*words[:2], 'xyzzy', *words[3:]])
    half = len(words) // 2
    quoted = '> - ' + ' '.join(words[:half]) + '\n> ' + ' '.join(words[half:])
    seeds = {
        'plugins/demo/copy.md': f'# Demo\n\nIntro line.\n**{fingerprint[1].upper()}**\n',
        'plugins/demo/wrapped.md': 'Lead.\n' + fingerprint[1].replace(' ', '\n', 1) + '\n',
        'plugins/demo/decorated.md': f'Lead.\n{decorated}\n',
        'plugins/demo/quoted.md': f'Lead.\n\n{quoted}\n',
        'plugins/demo/near-miss.md': f'Lead.\n{near_miss}\n',
        'plugins/demo/dead.md': 'See PA-99 for the rule.\n',
        'plugins/demo/retired.md': 'Line one.\nSee PA-01.\n',
        'docs/about/import.md': 'Rules:\n@../plugins/tcs-helper/skills/prompt-author/reference/catalog/core.md\n',
        'plugins/tcs-helper/evals/README.md': (
            'Run `claude plugin eval plugins/tcs-helper --case x --no-publish`.\n'
            '```\nclaude plugin eval plugins/tcs-helper --runs 3 \\\n  --output-dir /tmp/x\n```\n'
            'A `claude plugin eval` case; scaffold with `claude plugin eval init --bare x`.\n'
            'claude plugin eval plugins/demo --no-publish --output-dir=/tmp/out.\n'
            'claude plugin eval plugins/demo --no-publishing --output-directory /tmp/x\n'
        ),
    }
    return _write_seeds(tmp_path, seeds), fingerprint


# ---------------------------------------------------------------- scan tests

def test_tracked_markdown_scan_covers_plugins_and_docs_about_but_not_the_catalog():
    files = tracked_markdown()
    assert any(rel.startswith('docs/about/') for rel in files), 'docs/about/ not scanned'
    assert any(rel.startswith('plugins/tcs-helper/skills/prompt-author/reference/profiles/') for rel in files)
    assert not any(rel.startswith(CATALOG_REL) for rel in files), 'the catalog must not scan itself'
    assert any(rel.startswith(CATALOG_REL) for rel in tracked_markdown(include_catalog=True))


def test_copy_scan_catches_a_seeded_copy_with_file_and_line(tmp_path):
    files, (entry_id, sentence) = _seeded_files(tmp_path)
    found = {(rel, line, pa) for rel, line, pa, _ in copy_findings(files, [(entry_id, sentence)])}
    assert ('plugins/demo/copy.md', 4, entry_id) in found
    assert ('plugins/demo/wrapped.md', 2, entry_id) in found


def test_copy_scan_normalises_emphasis_code_and_quote_markers_inside_the_sentence(tmp_path):
    files, (entry_id, sentence) = _seeded_files(tmp_path)
    found = {(rel, line, pa) for rel, line, pa, _ in copy_findings(files, [(entry_id, sentence)])}
    assert ('plugins/demo/decorated.md', 2, entry_id) in found
    assert ('plugins/demo/quoted.md', 3, entry_id) in found


def test_copy_scan_ignores_a_one_word_near_miss(tmp_path):
    files, (entry_id, sentence) = _seeded_files(tmp_path)
    found = {rel for rel, _, _, _ in copy_findings(files, [(entry_id, sentence)])}
    assert 'plugins/demo/near-miss.md' not in found
    assert found == {'plugins/demo/copy.md', 'plugins/demo/wrapped.md',
                     'plugins/demo/decorated.md', 'plugins/demo/quoted.md'}


def test_id_scan_catches_a_dead_and_a_retired_id_with_file_and_line(tmp_path):
    files, _ = _seeded_files(tmp_path)
    statuses = dict(index_statuses(), **{'PA-01': 'retired'})
    findings = dead_id_findings(files, statuses)
    assert 'plugins/demo/dead.md:1: PA-99 is not in index.md' in findings
    assert 'plugins/demo/retired.md:2: PA-01 is retired' in findings


def test_import_scan_catches_a_seeded_catalog_import_with_file_and_line(tmp_path):
    files, _ = _seeded_files(tmp_path)
    findings = catalog_import_findings(files)
    assert findings == [
        'docs/about/import.md:2: @-imports ../plugins/tcs-helper/skills/prompt-author/reference/catalog/core.md; '
        'cite the entry ID instead'
    ]


def test_eval_scan_catches_runs_without_the_privacy_flags(tmp_path):
    files, _ = _seeded_files(tmp_path)
    found = {(rel, line, flag) for rel, line, flag, _ in eval_flag_findings(files)}
    assert found == {
        ('plugins/tcs-helper/evals/README.md', 1, '--output-dir'),
        ('plugins/tcs-helper/evals/README.md', 3, '--no-publish'),
        ('plugins/tcs-helper/evals/README.md', 8, '--no-publish'),
        ('plugins/tcs-helper/evals/README.md', 8, '--output-dir'),
    }


def test_unpinned_authority_scan_reports_only_the_unpinned_unfenced_line(tmp_path):
    skill_dir = 'plugins/tcs-helper/skills/demo/'
    pinned_sentence = '- Use `MUST BE USED` in every description.'
    files = _write_seeds(tmp_path, {
        skill_dir + 'SKILL.md': (
            '# Demo\n'
            f'{pinned_sentence}\n'
            '- Agents MUST BE USED sparingly.\n'
            '```yaml\ndescription: MUST BE USED when backticks fence it\n```\n'
            '~~~yaml\ndescription: MUST BE USED when tildes fence it\n```\nstill fenced: MUST BE USED\n~~~\n'
            'Closing prose.\n'
        ),
    })
    pinned = {(skill_dir + 'SKILL.md', pinned_sentence)}
    assert unpinned_authority_lines(files, pinned) == [
        f'{skill_dir}SKILL.md:3: - Agents MUST BE USED sparingly.'
    ]


# ---------------------------------------------------------------- repo tests

def test_no_active_fingerprint_is_copied_outside_the_catalog():
    findings = copy_findings(tracked_markdown(), active_fingerprints())
    unlisted = [
        f'{rel}:{line}: copies {pa} fingerprint "{sentence}"; cite {pa} instead'
        for rel, line, pa, sentence in findings
        if (rel, pa) not in PRE_MIGRATION_COPIES
    ]
    assert not unlisted, '\n'.join(unlisted)


def test_pre_migration_allow_list_is_owned_and_still_needed():
    found = {(rel, pa) for rel, _, pa, _ in copy_findings(tracked_markdown(), active_fingerprints())}
    problems = [
        f'{key}: owner {owner!r} is not a Phase 3 task' for key, owner in PRE_MIGRATION_COPIES.items()
        if not re.fullmatch(r'T3\.[1-7]', owner)
    ] + [f'{key}: no longer copied; remove it from PRE_MIGRATION_COPIES' for key in PRE_MIGRATION_COPIES
         if key not in found]
    assert not problems, '\n'.join(problems)


def test_every_pa_token_outside_the_catalog_names_an_indexed_entry_that_is_not_retired():
    findings = dead_id_findings(tracked_markdown(), index_statuses())
    assert not findings, '\n'.join(findings)


def test_no_file_at_imports_a_catalog_file():
    findings = catalog_import_findings(tracked_markdown(ALL_FILES, include_catalog=True))
    assert not findings, '\n'.join(findings)


def test_documented_plugin_eval_runs_keep_the_report_private():
    files = tracked_markdown(('plugins',), include_catalog=True)
    assert any(eval_commands(text) for text in files.values()), 'no documented `claude plugin eval` run found'
    findings = [
        f'{rel}:{line}: `claude plugin eval` run lacks {flag}: {command}'
        for rel, line, flag, command in eval_flag_findings(files)
    ]
    assert not findings, '\n'.join(findings)


def test_eval_loop_reference_exists():
    assert EVAL_LOOP.is_file(), f'missing {EVAL_LOOP.relative_to(REPO_ROOT)}'


@pytest.mark.parametrize('rel, sentence', PINNED_AUTHORITY_SENTENCES)
def test_contested_authority_sentences_stay_verbatim(rel, sentence):
    text = (REPO_ROOT / AGENT_AUTHOR_REL / rel).read_text(encoding='utf-8')
    assert sentence in text, f'{AGENT_AUTHOR_REL}{rel}: pinned PA-50 sentence changed: {sentence!r}'


def test_every_rule_bearing_authority_sentence_is_pinned():
    files = consumer_rule_files(tracked_markdown(), AGENT_AUTHOR_REL)
    assert AGENT_AUTHOR_REL + 'SKILL.md' in files, 'agent-author SKILL.md not scanned'
    pinned = {(AGENT_AUTHOR_REL + rel, sentence) for rel, sentence in PINNED_AUTHORITY_SENTENCES}
    unpinned = unpinned_authority_lines(files, pinned)
    assert not unpinned, 'pin these PA-50 sentences in PINNED_AUTHORITY_SENTENCES:\n' + '\n'.join(unpinned)


@pytest.mark.parametrize('consumer', [
    pytest.param(name, marks=() if name in MIGRATED_CONSUMERS else
                 pytest.mark.xfail(strict=True, reason=f'{name} cites the catalog from {task}'))
    for name, task in CONSUMERS.items()
])
def test_consumer_cites_a_catalog_entry(consumer):
    skill_dir = f'plugins/tcs-helper/skills/{consumer}/'
    files = consumer_rule_files(tracked_markdown(), skill_dir)
    assert skill_dir + 'SKILL.md' in files, f'no tracked {skill_dir}SKILL.md'
    assert resolving_citations(files, index_statuses()), (
        f'{consumer}: neither SKILL.md nor reference/*.md cites an indexed, non-retired PA entry'
    )


def test_consumer_citation_counts_only_resolving_ids_in_rule_files(tmp_path):
    skill_dir = 'plugins/tcs-helper/skills/demo/'
    files = _write_seeds(tmp_path, {skill_dir + rel: text for rel, text in {
        'SKILL.md': '# Demo\n\nNo citation here, only a sample `PA-06`.\n```\nPA-07\n```\n~~~\nPA-08\n~~~\n',
        'reference/rules.md': 'See PA-99 and PA-01.\n',
        'examples/sample.md': 'Avoid PA-02.\n',
        'evals/README.md': 'Checks PA-03.\n',
        'CHANGELOG.md': 'Cites PA-04 now.\n',
        'reference/nested/deep.md': 'PA-05.\n',
    }.items()})
    statuses = dict(index_statuses(), **{'PA-01': 'retired'})

    rule_files = consumer_rule_files(files, skill_dir)
    assert set(rule_files) == {skill_dir + 'SKILL.md', skill_dir + 'reference/rules.md'}
    assert resolving_citations(rule_files, statuses) == [], (
        'unknown PA-99, retired PA-01 and code-sample PA-06/07/08 must not count'
    )

    files[skill_dir + 'SKILL.md'] += 'Applies PA-02.\n'
    assert resolving_citations(consumer_rule_files(files, skill_dir), statuses) == [
        f'{skill_dir}SKILL.md:10 PA-02'
    ]
