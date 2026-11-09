"""Port-profile checks for prompt-author (spec 023 T1.2, SDD-ADR-6).

Guards reference/profiles/: every topic has guidance, a source, a date and one
evidence grade; only the T5 small-local findings are graded measured; an unverified
topic says so in its first word; profiles cite catalog IDs instead of restating
entries. A port report repeats a profile's grade and wording to the user, so an
ungraded or uncited topic would pass an unsourced claim off as guidance.
"""
import re

import pytest

from catalog_helpers import (
    EVIDENCE_GRADES, PA_TOKEN_RE, PROFILE_TARGETS, all_entries, fingerprints, grade, grade_rule_violations,
    load_profile, profile_path,
)

PROFILE_TOPICS = ('Placement', 'Delimiters', 'Examples', 'Negatives', 'Emphasis', 'Literalness', 'Turn shape')
PROFILE_FIELDS = ('Source', 'Date', 'Evidence')
# SDD-ADR-6: only the T5 findings are measured for small-local; no vendor guidance exists for it.
SMALL_LOCAL_MEASURED = ('Turn shape', 'Gate exits')
# A topic whose guidance has no source says so in its first word, so a port report can repeat the label.
UNVERIFIED_LEAD_IN = 'Unverified'
DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')


@pytest.mark.parametrize('target', PROFILE_TARGETS)
def test_profile_exists(target):
    assert profile_path(target).is_file(), f'missing port profile {target}.md'


@pytest.mark.parametrize('target', PROFILE_TARGETS)
def test_profile_has_every_topic_with_guidance_source_date_and_evidence(target):
    _, topics = load_profile(target)
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
    assert not problems, '\n'.join(problems)


@pytest.mark.parametrize('target', PROFILE_TARGETS)
def test_profile_grades_follow_the_catalog_rule(target):
    # Same enum and rule as catalog entries: vendor is a model vendor's own guidance, a study is research.
    _, topics = load_profile(target)
    problems = []
    for topic, section in topics.items():
        where = f'{target} / {topic}'
        found = grade(section['fields'].get('Evidence', ''))
        source = section['fields'].get('Source', '')
        if found not in EVIDENCE_GRADES:
            problems.append(f'{where}: {found!r} is not one of {sorted(EVIDENCE_GRADES)}')
        problems.extend(f'{where}: {problem}' for problem in grade_rule_violations(found, source))
    assert not problems, '\n'.join(problems)


def test_small_local_grades_only_the_t5_findings_as_measured():
    _, topics = load_profile('small-local')
    problems = []
    for topic in SMALL_LOCAL_MEASURED:
        if topic not in topics:
            problems.append(f'small-local: no "## {topic}" section')
    for topic, section in topics.items():
        found = grade(section['fields'].get('Evidence', ''))
        expected = 'measured' if topic in SMALL_LOCAL_MEASURED else 'unverified'
        if found != expected:
            problems.append(f'small-local / {topic}: evidence {found!r}, expected {expected!r}')
    assert not problems, '\n'.join(problems)


@pytest.mark.parametrize('target', [t for t in PROFILE_TARGETS if t != 'small-local'])
def test_vendor_profiles_grade_no_topic_as_measured(target):
    # SDD-ADR-6: the only measurements are the T5 runs on a small local model.
    _, topics = load_profile(target)
    measured = [
        topic for topic, section in topics.items()
        if grade(section['fields'].get('Evidence', '')) == 'measured'
    ]
    assert not measured, f'{target}: topics graded measured without a measurement: {measured}'


@pytest.mark.parametrize('target', PROFILE_TARGETS)
def test_unverified_lead_in_matches_the_grade(target):
    _, topics = load_profile(target)
    problems = []
    for topic, section in topics.items():
        unverified = grade(section['fields'].get('Evidence', '')) == 'unverified'
        leads_in = bool(section['guidance']) and section['guidance'][0].startswith(UNVERIFIED_LEAD_IN)
        if unverified and not leads_in:
            problems.append(f'{target} / {topic}: graded unverified, guidance must start with "{UNVERIFIED_LEAD_IN}"')
        if leads_in and not unverified:
            problems.append(f'{target} / {topic}: guidance starts with "{UNVERIFIED_LEAD_IN}" but is graded otherwise')
    assert not problems, '\n'.join(problems)


@pytest.mark.parametrize('target', PROFILE_TARGETS)
def test_profile_cites_only_catalogued_entries(target):
    text, _ = load_profile(target)
    cited = set(PA_TOKEN_RE.findall(text))
    known = {e['id'] for e in all_entries()}
    assert cited, f'{target}.md cites no catalog entry; profiles cite PA IDs for the underlying rule'
    assert not cited - known, f'{target}.md cites unknown entries {sorted(cited - known)}'


@pytest.mark.parametrize('target', PROFILE_TARGETS)
def test_profile_does_not_restate_a_catalog_fingerprint(target):
    text, _ = load_profile(target)
    copied = [
        f"{e['id']}: {sentence}"
        for e in all_entries()
        for sentence in fingerprints(e)
        if sentence in text
    ]
    assert not copied, f'{target}.md restates catalog entries instead of citing them: {copied}'
