"""Tests for the observability registration editor (spec-019 T2.3).

The risk this file exists to cover is not "does our block get added" -- it is
what happens to everything else in a file we did not write and the maintainer
cannot recover from version control (ADR-1: the write target is deliberately
untracked). So the assertions compare the file's FULL content, not just our
keys.

The precedent, `modules/satori/scripts/install-hooks.sh`, supplies the merge
and is the anti-model for the write: it opens the real file with 'w' at
:97-99, truncating before rewriting. It also ships a --settings-style override
that nothing tests. Both are deliberately covered here.
"""
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time

import pytest

SCRIPT = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        '../../plugins/tcs-helper/skills/observability-setup/lib/registration.py',
    )
)

# entry_is_ours's tolerant branches (malformed `hooks` shapes) are unreachable
# through the CLI: add_registration validates and raises ValueError on those
# same shapes before entry_is_ours is ever consulted. They are still real
# code paths -- T2.4 (removal) will call entry_is_ours on paths that skip that
# validation loop -- so they are exercised here as a direct unit import,
# following the `lib.<module>` idiom used elsewhere in this suite (see
# test_reflect_utils.py).
sys.path.insert(0, os.path.join(
    os.path.dirname(__file__),
    '../../plugins/tcs-helper/skills/observability-setup/lib',
))
import registration  # noqa: E402
from registration import entry_is_ours, command_for  # noqa: E402
# The lock knobs live in the lock module now. Imported by NAME rather than
# as `import lock`, because several tests below bind a local `lock` to a
# lock-file path and a module binding of the same name would be shadowed.
from lock import LOCK_GRACE, LOCK_TIMEOUT_ENV, LOCK_TTL_ENV  # noqa: E402

OUR_NAMESPACE = '$HOME/.claude/observability/'

EXPECTED_EVENTS = {
    'InstructionsLoaded': ('', 'log_instructions.sh'),
    'PreToolUse': ('Skill', 'log_skill.sh'),
    'SubagentStart': ('', 'log_agent.sh'),
}


def run_registration(settings_path, *extra_args, env_extra=None):
    """Invoke the editor against a settings file, never a real one.

    `env_extra` exists for the T2.5 tests, which need to neutralise the
    operator's global git ignore rules inside the child process too -- see
    GIT_ISOLATION below.
    """
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, SCRIPT, '--settings', str(settings_path), *extra_args],
        capture_output=True,
        text=True,
        env=env,
    )


def write_settings(path, data):
    """Write a settings document, returning the exact text on disk."""
    text = json.dumps(data, indent=2, ensure_ascii=False) + '\n'
    path.write_text(text, encoding='utf-8')
    return text


def our_commands(settings_text):
    """Every hook command in the document that points into our namespace."""
    data = json.loads(settings_text)
    found = []
    for entries in data.get('hooks', {}).values():
        for entry in entries:
            for hook in entry.get('hooks', []):
                command = hook.get('command', '')
                if OUR_NAMESPACE in command:
                    found.append(command)
    return found


# ---------------------------------------------------------------------------
# The registration itself
# ---------------------------------------------------------------------------

def test_absent_settings_file_is_created_with_only_our_entries(tmp_path):
    """SDD-AC-2: an absent file is created holding only what we author."""
    settings = tmp_path / 'settings.local.json'
    assert not settings.exists()

    result = run_registration(settings)

    assert result.returncode == 0, result.stderr
    data = json.loads(settings.read_text(encoding='utf-8'))
    assert set(data) == {'env', 'hooks'}
    assert set(data['hooks']) == set(EXPECTED_EVENTS)
    assert len(our_commands(settings.read_text(encoding='utf-8'))) == 3


def test_the_three_hook_entries_and_the_env_switch_are_all_present(tmp_path):
    """Each event carries its own script under its own matcher."""
    settings = tmp_path / 'settings.local.json'

    assert run_registration(settings).returncode == 0

    data = json.loads(settings.read_text(encoding='utf-8'))
    assert data['env']['CLAUDE_OBSERVABILITY_ENABLED'] == '1'
    for event, (matcher, script) in EXPECTED_EVENTS.items():
        ours = [
            entry for entry in data['hooks'][event]
            if any(OUR_NAMESPACE in h.get('command', '') for h in entry['hooks'])
        ]
        assert len(ours) == 1, f'{event} should carry exactly one entry of ours'
        assert ours[0]['matcher'] == matcher
        assert script in ours[0]['hooks'][0]['command']


# ---------------------------------------------------------------------------
# What must survive -- the actual risk
# ---------------------------------------------------------------------------

def test_unrelated_top_level_keys_survive_unchanged(tmp_path):
    """SDD-AC-3: keys we know nothing about are not ours to touch."""
    settings = tmp_path / 'settings.local.json'
    original = {
        'permissions': {'allow': ['Bash(ls:*)'], 'deny': []},
        'model': 'claude-opus-5',
        'statusLine': {'type': 'command', 'command': 'my-statusline.sh'},
        'env': {'SOMETHING_ELSE': 'keep me'},
    }
    write_settings(settings, original)

    assert run_registration(settings).returncode == 0

    data = json.loads(settings.read_text(encoding='utf-8'))
    assert data['permissions'] == original['permissions']
    assert data['model'] == original['model']
    assert data['statusLine'] == original['statusLine']
    # our switch is added beside the existing env, not instead of it
    assert data['env']['SOMETHING_ELSE'] == 'keep me'
    assert data['env']['CLAUDE_OBSERVABILITY_ENABLED'] == '1'


def test_foreign_hooks_survive_including_under_our_own_event_names(tmp_path):
    """A foreign entry under PreToolUse is somebody's working hook, not a conflict to resolve."""
    settings = tmp_path / 'settings.local.json'
    foreign_pre = {
        'matcher': 'Bash',
        'hooks': [{'type': 'command', 'command': '.claude/hooks/block-bad-git-ops.sh'}],
    }
    foreign_stop = {
        'matcher': '',
        'hooks': [{'type': 'command', 'command': '.claude/hooks/on-stop.sh'}],
    }
    write_settings(settings, {'hooks': {'PreToolUse': [foreign_pre], 'Stop': [foreign_stop]}})

    assert run_registration(settings).returncode == 0

    data = json.loads(settings.read_text(encoding='utf-8'))
    assert foreign_pre in data['hooks']['PreToolUse']
    assert data['hooks']['Stop'] == [foreign_stop]
    # ours was appended beside it, not in place of it
    assert len(data['hooks']['PreToolUse']) == 2


def test_non_ascii_foreign_values_stay_byte_identical(tmp_path):
    """SDD-AC-10, and the default this repository has already been bitten by.

    json.dump defaults to ensure_ascii=True, which silently rewrites a literal
    'ä' as '\\u00e4'. The document still parses to the same object, so an
    assertion on the parsed value passes while the file's bytes have changed
    under a maintainer who never asked for it.
    """
    settings = tmp_path / 'settings.local.json'
    value = 'Прове́рка — Grüße, 日本語'
    write_settings(settings, {
        'hooks': {'Stop': [{
            'matcher': '',
            'hooks': [{'type': 'command', 'command': f'echo "{value}"'}],
        }]},
    })

    assert run_registration(settings).returncode == 0

    text = settings.read_text(encoding='utf-8')
    assert value in text, 'non-ASCII content was re-encoded'
    assert '\\u' not in text, 'file contains escaped non-ASCII where it had literals'


# ---------------------------------------------------------------------------
# Failure and repetition
# ---------------------------------------------------------------------------

def test_unparseable_settings_writes_nothing_and_exits_non_zero(tmp_path):
    """SDD-AC-5: a diagnosis, not a traceback, and the file is left alone."""
    settings = tmp_path / 'settings.local.json'
    broken = '{ "hooks": { "PreToolUse": [ ,,, ] }\n'
    settings.write_text(broken, encoding='utf-8')

    result = run_registration(settings)

    assert result.returncode != 0
    assert settings.read_text(encoding='utf-8') == broken, 'the file was modified'
    assert 'Traceback' not in result.stderr
    combined = result.stdout + result.stderr
    assert 'JSON' in combined or 'parse' in combined.lower()


def test_running_twice_changes_nothing(tmp_path):
    """Idempotence, asserted over the whole file rather than over our keys."""
    settings = tmp_path / 'settings.local.json'
    write_settings(settings, {'model': 'claude-opus-5', 'hooks': {'Stop': []}})

    assert run_registration(settings).returncode == 0
    after_first = settings.read_text(encoding='utf-8')

    assert run_registration(settings).returncode == 0
    after_second = settings.read_text(encoding='utf-8')

    assert after_second == after_first
    assert len(our_commands(after_second)) == 3


# ---------------------------------------------------------------------------
# The override itself
# ---------------------------------------------------------------------------

def test_settings_override_is_the_only_file_touched(tmp_path):
    """satori ships such an override and nothing tests it; do not repeat that.

    If --settings were ignored, the editor would fall back to a real settings
    file somewhere on this machine -- which is precisely what must never happen
    in a test run.
    """
    settings = tmp_path / 'nested' / 'chosen.json'
    settings.parent.mkdir()
    decoy = tmp_path / 'settings.local.json'
    decoy.write_text('{}\n', encoding='utf-8')

    assert run_registration(settings).returncode == 0

    assert settings.exists(), '--settings path was not written'
    assert len(our_commands(settings.read_text(encoding='utf-8'))) == 3
    assert decoy.read_text(encoding='utf-8') == '{}\n', 'a file outside --settings was touched'


# ---------------------------------------------------------------------------
# Zero-byte file handling (SDD-AC-2)
# ---------------------------------------------------------------------------

def test_zero_byte_settings_file_is_treated_as_empty_document(tmp_path):
    """SDD-AC-2: a zero-byte file should be treated like an absent file."""
    settings = tmp_path / 'settings.local.json'
    settings.write_text('', encoding='utf-8')

    result = run_registration(settings)

    assert result.returncode == 0, result.stderr
    data = json.loads(settings.read_text(encoding='utf-8'))
    assert set(data) == {'env', 'hooks'}
    assert set(data['hooks']) == set(EXPECTED_EVENTS)
    assert len(our_commands(settings.read_text(encoding='utf-8'))) == 3


# ---------------------------------------------------------------------------
# Malformed shapes: env and hooks guards (SDD-AC-5)
# ---------------------------------------------------------------------------

import pytest


@pytest.mark.parametrize('bad_env,bad_hooks,bad_event_value,expected_marker', [
    # Item 1a: env is not a dict
    ('string_env', None, None, '"env"'),
    # Item 1b: hooks is not a dict
    (None, 'string_hooks', None, '"hooks"'),
    # Item 1c: hooks[event] is not a list
    (None, None, 'string_event_value', '"hooks.PreToolUse"'),
])
def test_malformed_shapes_exit_with_diagnosis(
        tmp_path, bad_env, bad_hooks, bad_event_value, expected_marker):
    """SDD-AC-5: malformed documents exit 1 with diagnosis naming the bad key, no Traceback.

    A diagnostic that merely exists is not enough -- it must name the key that
    is actually malformed, or a wrong-key diagnosis (or a generic "bad
    settings" message) would pass unnoticed.
    """
    settings = tmp_path / 'settings.local.json'
    data = {}

    if bad_env is not None:
        data['env'] = bad_env
    if bad_hooks is not None:
        data['hooks'] = bad_hooks
    if bad_event_value is not None:
        data['hooks'] = {'PreToolUse': bad_event_value}

    original_text = write_settings(settings, data)

    result = run_registration(settings)

    assert result.returncode != 0, 'should exit non-zero on bad shape'
    assert settings.read_text(encoding='utf-8') == original_text, 'file was modified'
    assert 'Traceback' not in result.stderr, 'stderr should contain diagnosis, not traceback'
    combined = result.stdout + result.stderr
    assert expected_marker in combined, (
        f'diagnostic should name the malformed key {expected_marker!r}; got: {combined!r}')


# ---------------------------------------------------------------------------
# Foreign entries with malformed hooks field (SDD-AC-5, item 3)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('bad_hooks_value', [
    'string_instead_of_list',
    [{'type': 'command', 'command': 'ok'}, 'not_an_object'],
    {'type': 'command', 'command': 'dict_not_list'},
])
def test_foreign_entry_with_malformed_hooks_exits_with_diagnosis(tmp_path, bad_hooks_value):
    """SDD-AC-5: foreign entry with non-list hooks field should be diagnosed, not crash.

    entry_is_ours should not raise AttributeError when examining a malformed entry.
    """
    settings = tmp_path / 'settings.local.json'
    foreign_entry = {
        'matcher': 'SomeOtherTool',
        'hooks': bad_hooks_value,
    }
    write_settings(settings, {'hooks': {'PreToolUse': [foreign_entry]}})

    result = run_registration(settings)

    # Should exit non-zero and leave file untouched
    assert result.returncode != 0, f'should exit non-zero; stderr: {result.stderr}'
    assert 'Traceback' not in result.stderr, 'should have diagnosis, not traceback'
    assert 'PreToolUse' in result.stderr or 'hooks' in result.stderr, \
        'stderr should name the problematic key'


# ---------------------------------------------------------------------------
# entry_is_ours: direct unit coverage of the tolerant branches
#
# These shapes cannot be reached through the CLI -- add_registration raises
# ValueError on a non-list `hooks` field or a non-dict hook before
# entry_is_ours is ever called on the entry. The tolerance is still real
# defence-in-depth (T2.4 will call entry_is_ours on paths that skip that
# validation loop), so it is covered directly here rather than through
# run_registration.
# ---------------------------------------------------------------------------

def test_entry_is_ours_false_when_hooks_field_is_a_string():
    entry = {'matcher': '', 'hooks': 'not_a_list'}
    assert entry_is_ours(entry) is False


def test_entry_is_ours_false_when_hooks_field_is_a_dict():
    entry = {'matcher': '', 'hooks': {'type': 'command', 'command': 'ok'}}
    assert entry_is_ours(entry) is False


def test_entry_is_ours_skips_non_dict_elements_and_still_finds_ours():
    entry = {
        'matcher': '',
        'hooks': ['not_a_dict', {'type': 'command', 'command': command_for('log_agent.sh')}],
    }
    assert entry_is_ours(entry) is True


def test_entry_is_ours_skips_non_dict_elements_with_no_match():
    entry = {
        'matcher': '',
        'hooks': ['not_a_dict', {'type': 'command', 'command': 'some/foreign/script.sh'}],
    }
    assert entry_is_ours(entry) is False


def test_entry_is_ours_true_for_well_formed_entry_of_ours():
    entry = {
        'matcher': '',
        'hooks': [{'type': 'command', 'command': command_for('log_instructions.sh')}],
    }
    assert entry_is_ours(entry) is True


def test_entry_is_ours_false_for_well_formed_foreign_entry():
    entry = {
        'matcher': '',
        'hooks': [{'type': 'command', 'command': '.claude/hooks/on-stop.sh'}],
    }
    assert entry_is_ours(entry) is False


# ---------------------------------------------------------------------------
# Removal (T2.4)
#
# ADR-5 is why removal cannot be exact-string matching: an entry written by
# an older bundle version has a command that still points inside our
# namespace but is not byte-identical to what command_for() produces today.
# Exact-string equality would orphan it forever -- namespace membership is
# the only test that survives a version change.
# ---------------------------------------------------------------------------

def _snapshot(dir_path, exclude):
    """Path -> (size, mtime_ns) for everything under dir_path except exclude.

    Used to prove removal's blast radius is the --settings file alone --
    SDD-AC-14 says existing records must survive, and the only way to trust
    that is to show nothing else on disk moved.
    """
    exclude = os.path.abspath(str(exclude))
    snap = {}
    for root, _dirs, files in os.walk(str(dir_path)):
        for name in files:
            path = os.path.join(root, name)
            if os.path.abspath(path) == exclude:
                continue
            st = os.stat(path)
            snap[path] = (st.st_size, st.st_mtime_ns)
    return snap


def test_removal_deletes_only_our_entries_foreign_entry_survives(tmp_path):
    """SDD-AC-12: only namespace-owned entries go; a foreign entry under the
    same event name is untouched, and the env switch we own is removed
    without disturbing a foreign env key beside it."""
    settings = tmp_path / 'settings.local.json'
    foreign = {
        'matcher': 'Bash',
        'hooks': [{'type': 'command', 'command': '.claude/hooks/block-bad-git-ops.sh'}],
    }
    write_settings(settings, {
        'env': {'CLAUDE_OBSERVABILITY_ENABLED': '1', 'SOMETHING_ELSE': 'keep me'},
        'hooks': {
            'PreToolUse': [
                foreign,
                {'matcher': 'Skill', 'hooks': [{'type': 'command', 'command': command_for('log_skill.sh')}]},
            ],
        },
    })

    result = run_registration(settings, '--remove')

    assert result.returncode == 0, result.stderr
    data = json.loads(settings.read_text(encoding='utf-8'))
    assert data['hooks']['PreToolUse'] == [foreign]
    assert data['env'] == {'SOMETHING_ELSE': 'keep me'}


def test_removal_leaves_a_preexisting_empty_env_untouched(tmp_path):
    """SDD-AC-12: a foreign 'env' that already had nothing in it -- no key
    of ours, ever -- is not ours to delete. An empty dict a foreign owner
    left behind is still a foreign entry, and it must remain, same as any
    other foreign entry.

    This distinguishes "we emptied it" (ours to prune) from "it was already
    empty" (never ours, must survive) -- the exact case `remove_registration`
    document but that no test held before this one.
    """
    settings = tmp_path / 'settings.local.json'
    write_settings(settings, {
        'env': {},
        'hooks': {
            'InstructionsLoaded': [
                {'matcher': '', 'hooks': [{'type': 'command', 'command': command_for('log_instructions.sh')}]},
            ],
        },
    })

    result = run_registration(settings, '--remove')

    assert result.returncode == 0, result.stderr
    data = json.loads(settings.read_text(encoding='utf-8'))
    assert data == {'env': {}}, 'a pre-existing empty foreign env must survive removal'


def test_removal_leaves_a_preexisting_empty_hooks_object_untouched(tmp_path):
    """Same distinction as the empty-env case, for 'hooks': a top-level
    'hooks': {} that held none of our events to begin with is foreign and
    already empty -- removal did not empty it, so removal must not delete
    it either."""
    settings = tmp_path / 'settings.local.json'
    write_settings(settings, {
        'env': {'CLAUDE_OBSERVABILITY_ENABLED': '1'},
        'hooks': {},
    })

    result = run_registration(settings, '--remove')

    assert result.returncode == 0, result.stderr
    data = json.loads(settings.read_text(encoding='utf-8'))
    assert data == {'hooks': {}}, 'a pre-existing empty foreign hooks object must survive removal'


def test_removal_leaves_a_preexisting_empty_foreign_hook_bucket_untouched(tmp_path):
    """SDD-AC-12: a foreign event bucket that was already an empty list
    survives removal even while our own event bucket, sitting beside it in
    the same 'hooks' object, gets emptied and dropped."""
    settings = tmp_path / 'settings.local.json'
    write_settings(settings, {
        'hooks': {
            'SomeForeignEvent': [],
            'InstructionsLoaded': [
                {'matcher': '', 'hooks': [{'type': 'command', 'command': command_for('log_instructions.sh')}]},
            ],
        },
    })

    result = run_registration(settings, '--remove')

    assert result.returncode == 0, result.stderr
    data = json.loads(settings.read_text(encoding='utf-8'))
    assert data == {'hooks': {'SomeForeignEvent': []}}, (
        'a pre-existing empty foreign hook bucket must survive removal '
        'while our own emptied bucket is dropped')


def test_removal_on_never_configured_target_changes_nothing(tmp_path):
    """SDD-AC-13: nothing to remove leaves the file byte-identical, exit 0."""
    settings = tmp_path / 'settings.local.json'
    original = write_settings(settings, {'model': 'claude-opus-5'})

    result = run_registration(settings, '--remove')

    assert result.returncode == 0, result.stderr
    assert settings.read_text(encoding='utf-8') == original


def test_removal_never_deletes_records_or_touches_other_files(tmp_path):
    """SDD-AC-14: removal's blast radius is the settings file, nothing else --
    asserted by counting record files before and after, not just by reading
    the settings diff."""
    settings = tmp_path / 'settings.local.json'
    assert run_registration(settings).returncode == 0

    records_dir = tmp_path / 'records'
    records_dir.mkdir()
    for i in range(3):
        (records_dir / ('events-%d.jsonl' % i)).write_text('{"event": "x"}\n', encoding='utf-8')
    record_files_before = sorted(p.name for p in records_dir.iterdir())
    snapshot_before = _snapshot(tmp_path, exclude=settings)

    result = run_registration(settings, '--remove')

    assert result.returncode == 0, result.stderr
    record_files_after = sorted(p.name for p in records_dir.iterdir())
    assert record_files_after == record_files_before
    snapshot_after = _snapshot(tmp_path, exclude=settings)
    assert snapshot_after == snapshot_before, 'a path outside --settings was written'


def test_removal_recognises_an_older_bundle_versions_command_as_ours(tmp_path):
    """ADR-5: ownership is the namespace, not the exact command string -- an
    entry from an older bundle version must be removed, not orphaned."""
    settings = tmp_path / 'settings.local.json'
    old_command = command_for('log_instructions_v1.sh')
    assert old_command != command_for('log_instructions.sh')
    write_settings(settings, {
        'hooks': {
            'InstructionsLoaded': [
                {'matcher': '', 'hooks': [{'type': 'command', 'command': old_command}]},
            ],
        },
    })

    result = run_registration(settings, '--remove')

    assert result.returncode == 0, result.stderr
    data = json.loads(settings.read_text(encoding='utf-8'))
    assert 'InstructionsLoaded' not in data.get('hooks', {})


def test_rerunning_setup_after_a_version_change_replaces_in_place(tmp_path):
    """SDD-AC-8: the old entry is replaced, never duplicated."""
    settings = tmp_path / 'settings.local.json'
    old_command = command_for('log_instructions_v1.sh')
    foreign = {'matcher': 'Bash', 'hooks': [{'type': 'command', 'command': 'foreign.sh'}]}
    write_settings(settings, {
        'hooks': {
            'InstructionsLoaded': [
                {'matcher': '', 'hooks': [{'type': 'command', 'command': old_command}]},
            ],
            'PreToolUse': [foreign],
        },
    })

    result = run_registration(settings)

    assert result.returncode == 0, result.stderr
    data = json.loads(settings.read_text(encoding='utf-8'))
    instructions_entries = data['hooks']['InstructionsLoaded']
    ours = [
        e for e in instructions_entries
        if command_for('log_instructions.sh') in e['hooks'][0]['command']
    ]
    assert len(ours) == 1
    assert len(instructions_entries) == 1, 'the old entry must be replaced, not left beside the new one'
    assert old_command not in json.dumps(instructions_entries)
    # PreToolUse had no entry of ours yet: the foreign entry is left alone
    # and ours is appended beside it, same as any other first install.
    assert foreign in data['hooks']['PreToolUse']
    assert len(data['hooks']['PreToolUse']) == 2


def test_replace_in_place_preserves_position_among_foreign_entries(tmp_path):
    """The comment above the replace step in add_registration promises the
    refreshed entry lands at the first occurrence's position, not appended
    at the end. A single-entry list can't tell "replaced in place" apart
    from "removed then appended" -- both produce a 1-item list -- so this
    uses a 3-entry list where only "in place" keeps the stale entry's slot.
    """
    settings = tmp_path / 'settings.local.json'
    old_command = command_for('log_instructions_v1.sh')
    foreign_a = {'matcher': 'Bash', 'hooks': [{'type': 'command', 'command': 'foreign-a.sh'}]}
    foreign_b = {'matcher': 'Bash', 'hooks': [{'type': 'command', 'command': 'foreign-b.sh'}]}
    stale_ours = {'matcher': '', 'hooks': [{'type': 'command', 'command': old_command}]}
    write_settings(settings, {
        'hooks': {'InstructionsLoaded': [foreign_a, stale_ours, foreign_b]},
    })

    result = run_registration(settings)

    assert result.returncode == 0, result.stderr
    data = json.loads(settings.read_text(encoding='utf-8'))
    entries = data['hooks']['InstructionsLoaded']
    assert len(entries) == 3, 'replacing must not change the list length'
    assert entries[0] == foreign_a
    assert entries[2] == foreign_b
    refreshed = entries[1]
    assert command_for('log_instructions.sh') in refreshed['hooks'][0]['command'], (
        'the refreshed entry must sit at the stale entry\'s original index, between the two foreign entries')


# ---------------------------------------------------------------------------
# Reporting: the only externally visible difference between three outcomes
# that all leave a correct file behind (T2.4)
# ---------------------------------------------------------------------------

def test_reporting_distinguishes_install_already_configured_and_update(tmp_path):
    settings = tmp_path / 'settings.local.json'

    first = run_registration(settings)
    assert first.returncode == 0, first.stderr
    assert 'registered observability hooks in' in first.stdout
    assert 'already configured' not in first.stdout
    assert 'updated observability registration in' not in first.stdout

    second = run_registration(settings)
    assert second.returncode == 0, second.stderr
    assert 'already configured' in second.stdout
    assert 'registered observability hooks in' not in second.stdout
    assert 'updated observability registration in' not in second.stdout

    # simulate a version change: an older command lands under our namespace
    data = json.loads(settings.read_text(encoding='utf-8'))
    data['hooks']['InstructionsLoaded'][0]['hooks'][0]['command'] = command_for('log_instructions_v1.sh')
    settings.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

    third = run_registration(settings)
    assert third.returncode == 0, third.stderr
    assert 'updated observability registration in' in third.stdout
    assert 'already configured' not in third.stdout
    assert 'registered observability hooks in' not in third.stdout


def test_reporting_an_env_only_correction_still_reports_update(tmp_path):
    """The status stays 'update' when only the env switch was stale --
    something of ours was wrong and got corrected -- but the message must
    not claim a hook was touched when none was.

    (Reviewer ruling: the STATUS is right to stay 'update' here; what was
    wrong was the word "hooks" in a message that fires when no hook entry
    changed.)
    """
    settings = tmp_path / 'settings.local.json'
    assert run_registration(settings).returncode == 0

    # hand-edit only the env switch's value; every hook entry stays current
    data = json.loads(settings.read_text(encoding='utf-8'))
    data['env']['CLAUDE_OBSERVABILITY_ENABLED'] = '0'
    settings.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

    result = run_registration(settings)

    assert result.returncode == 0, result.stderr
    assert 'updated observability registration in' in result.stdout, (
        'an env-only correction must still report as an update, not an install')
    assert 'already configured' not in result.stdout
    assert 'registered observability hooks in' not in result.stdout
    data = json.loads(settings.read_text(encoding='utf-8'))
    assert data['env']['CLAUDE_OBSERVABILITY_ENABLED'] == '1'


# ---------------------------------------------------------------------------
# Round trip: install -> remove must restore the original bytes, with no
# backup or other sibling file left behind (T2.4; T2.5 owns the actual
# backup mechanism -- this only guards today's no-backup behaviour so a
# regression there is caught before T2.5 has to reason about it)
# ---------------------------------------------------------------------------

def test_install_then_remove_round_trips_to_the_original_bytes(tmp_path):
    settings = tmp_path / 'settings.local.json'
    original = write_settings(settings, {'model': 'claude-opus-5', 'permissions': {'allow': []}})

    assert run_registration(settings).returncode == 0
    installed = settings.read_text(encoding='utf-8')
    assert installed != original, 'install should have changed the file'

    result = run_registration(settings, '--remove')

    assert result.returncode == 0, result.stderr
    assert settings.read_text(encoding='utf-8') == original
    siblings = sorted(p.name for p in tmp_path.iterdir())
    assert siblings == [settings.name], 'unexpected sibling files: %r' % siblings


# ---------------------------------------------------------------------------
# T2.5 -- durability: backup, atomic replace, and the lock
#
# The three sidecar paths this feature writes all sit beside the settings
# file and share one infix, so a single ignore rule covers the set:
#
#   <settings>.tcs-observability.bak    the pre-write copy   (SDD-AC-9)
#   <settings>.tcs-observability.lock   the serializing lock (SDD-AC-11)
#   <settings>.tcs-observability.tmp    the staging file replaced onto target
#
# The temp file is deliberately NOT mkstemp-random: a random name cannot be
# handed to `git check-ignore` before it exists, and the Safety requirement
# ("no file this feature writes in a target is reachable by version control")
# binds the temp file exactly as it binds the other two.
# ---------------------------------------------------------------------------

# Taken from the module rather than retyped: a suffix that drifts in
# production has to break these tests, not slip past them. The same reasoning
# is why the Safety test below asserts against registration.written_paths()
# instead of rebuilding the list locally.
BACKUP_SUFFIX = registration.BACKUP_SUFFIX
LOCK_SUFFIX = registration.LOCK_SUFFIX
TEMP_SUFFIX = registration.TEMP_SUFFIX


# The repository's gitignored scratch directory, on the repository's own
# volume. One test deliberately needs a target that is NOT under $TMPDIR --
# see test_the_temp_file_is_created_on_the_same_filesystem_as_the_target.
REPO_SCRATCH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', 'tmp'))

# `git check-ignore` reads the operator's global excludes, and
# GIT_CONFIG_GLOBAL=/dev/null alone is NOT isolation: with core.excludesFile
# unset git falls back to ~/.config/git/ignore, which on the machine this was
# written on carries `**/.claude/settings.local.json`. Without neutralising
# core.excludesFile too, the by-name fixture below would read as ignored and
# the test would silently assert nothing. Same override the bats suites use
# (observability-detect.bats), and it lives only here -- registration.py calls
# plain `git check-ignore`, because a global rule is real for a real user.
GIT_ISOLATION = {
    'GIT_CONFIG_GLOBAL': '/dev/null',
    'GIT_CONFIG_SYSTEM': '/dev/null',
    'GIT_CONFIG_COUNT': '1',
    'GIT_CONFIG_KEY_0': 'core.excludesFile',
    'GIT_CONFIG_VALUE_0': '/dev/null',
}


def _git(*args):
    env = dict(os.environ)
    env.update(GIT_ISOLATION)
    return subprocess.run(['git', *args], capture_output=True, text=True, env=env)


def _make_repo(root, ignore_line):
    """A real repository whose .gitignore carries exactly one rule.

    `git init <dir>` with an explicit directory (never a bare `git init` after
    a chdir) so a failure cannot fall back to this repository's own .git.
    """
    root.mkdir(parents=True, exist_ok=True)
    result = _git('init', '-q', str(root))
    assert result.returncode == 0, result.stderr
    (root / '.gitignore').write_text(ignore_line + '\n', encoding='utf-8')
    return root


def _is_ignored(repo, path):
    return _git('-C', str(repo), 'check-ignore', '-q', '--', str(path)).returncode == 0


def _sidecars(settings):
    return [
        str(settings) + BACKUP_SUFFIX,
        str(settings) + LOCK_SUFFIX,
        str(settings) + TEMP_SUFFIX,
    ]


def _dead_pid():
    """A PID that is certainly not running: start a process, reap it, reuse it."""
    proc = subprocess.Popen([sys.executable, '-c', 'pass'])
    proc.wait()
    return proc.pid


def _hold_lock(settings, pid, age_seconds=0):
    """Plant a lock file in the precedent's `<pid>:<epoch>` format."""
    lock = str(settings) + LOCK_SUFFIX
    with open(lock, 'w', encoding='utf-8') as handle:
        handle.write('%d:%d\n' % (pid, int(time.time()) - age_seconds))
    return lock


# --- the backup ------------------------------------------------------------

def test_the_backup_lands_beside_the_settings_file_and_holds_the_pre_write_bytes(tmp_path):
    """SDD-AC-9: a backup exists after a write and matches the pre-write content."""
    settings = tmp_path / 'settings.local.json'
    original = write_settings(settings, {'model': 'claude-opus-5'})

    assert run_registration(settings).returncode == 0

    backup = tmp_path / ('settings.local.json' + BACKUP_SUFFIX)
    assert backup.exists(), 'no backup at the named path %s' % backup
    assert backup.read_text(encoding='utf-8') == original
    assert settings.read_text(encoding='utf-8') != original, 'the write did not happen'


def test_at_most_one_backup_per_target_overwritten_by_the_next_write(tmp_path):
    """Retention: the backup is overwritten by the next write, never accumulated."""
    settings = tmp_path / 'settings.local.json'
    write_settings(settings, {'model': 'claude-opus-5'})

    assert run_registration(settings).returncode == 0
    after_first = settings.read_text(encoding='utf-8')

    # make the second run write again (an env-only correction is enough)
    data = json.loads(after_first)
    data['env']['CLAUDE_OBSERVABILITY_ENABLED'] = '0'
    after_first = json.dumps(data, indent=2, ensure_ascii=False) + '\n'
    settings.write_text(after_first, encoding='utf-8')

    assert run_registration(settings).returncode == 0

    backups = sorted(p.name for p in tmp_path.iterdir() if p.name.endswith(BACKUP_SUFFIX))
    assert backups == ['settings.local.json' + BACKUP_SUFFIX], (
        'expected exactly one backup, found %r' % backups)
    backup = tmp_path / backups[0]
    assert backup.read_text(encoding='utf-8') == after_first, (
        'the backup holds the state before the LAST write, not an older one')


def test_removal_deletes_the_backup_and_leaves_no_lock_or_temp_file(tmp_path):
    """Retention: removal takes the backup with it, so at most one exists per
    target and none outlives the feature."""
    settings = tmp_path / 'settings.local.json'
    write_settings(settings, {'model': 'claude-opus-5'})
    assert run_registration(settings).returncode == 0
    assert (tmp_path / ('settings.local.json' + BACKUP_SUFFIX)).exists()

    assert run_registration(settings, '--remove').returncode == 0

    siblings = sorted(p.name for p in tmp_path.iterdir())
    assert siblings == ['settings.local.json'], 'left behind: %r' % siblings


# --- every written path is out of version control's reach ------------------

def test_every_path_this_feature_writes_is_ignored_when_the_target_ignores_claude(tmp_path):
    """Quality Requirement "Safety", the ordinary case: a target that ignores
    `.claude/` wholesale covers the settings file and all three sidecars.

    Asserted for the settings path, the backup, the lock AND the temp file --
    each is a real file written into a repository we do not own (ADR-1).
    """
    repo = _make_repo(tmp_path / 'target', '.claude/')
    settings = repo / '.claude' / 'settings.local.json'
    settings.parent.mkdir(parents=True)
    write_settings(settings, {'model': 'claude-opus-5'})

    result = run_registration(settings, env_extra=GIT_ISOLATION)
    assert result.returncode == 0, result.stderr
    assert (tmp_path / 'target' / '.claude' / ('settings.local.json' + BACKUP_SUFFIX)).exists(), (
        'nothing was written, so this asserts nothing')

    # The module's own declared write set, not a list rebuilt here: an
    # assertion over a locally-rebuilt list would keep passing if production
    # moved the temp file to $TMPDIR (outside the repository, and therefore
    # outside `git check-ignore`'s reach entirely).
    declared = registration.written_paths(settings)
    assert set(declared) == set([os.path.abspath(str(settings))] + _sidecars(settings)), (
        'the written-path set drifted from the names this test pins: %r' % declared)
    for path in declared:
        assert _is_ignored(repo, path), 'not ignored: %s' % path


# --- the replace is a rename, not a rewrite --------------------------------

def test_the_temp_file_is_created_on_the_same_filesystem_as_the_target():
    """os.replace() is an atomic rename only WITHIN one filesystem, so the temp
    file has to be created in the target's own directory.

    This has its own test rather than riding on the truncation check below
    because the mistake it guards is the likely one: both precedents this task
    was told to imitate (install.sh:729-731,
    scripts/the-custom-startup-configure-statusline.sh:176-180) `mktemp` into
    $TMPDIR, which on this machine is a different device from the repositories
    being configured. The truncation check would catch a shutil.move() fallback
    too -- its cross-device path opens the destination in write mode -- but it
    would report "the settings file was truncated" and leave the next reader to
    work out that the real cause was a temp file on the wrong filesystem.

    Observed, not inferred: the temp file is identified by ROLE -- it is
    whatever gets renamed onto the target -- and compared by st_dev, never by
    path string. A string check would pass for the wrong reason if $TMPDIR were
    ever pointed inside the repository.

    NOT `tmp_path`, and that is the whole point: pytest's tmp_path lives under
    $TMPDIR, so a temp file mistakenly created by `tempfile.mkstemp()` would
    land on the SAME device as the target and this assertion would be vacuous
    -- it would pass while the bug is present. The fixture therefore sits on
    the repository's own volume, under the gitignored `tmp/` scratch directory,
    which is a different device here (measured: 16777245 vs 16777234).
    """
    os.makedirs(REPO_SCRATCH, exist_ok=True)
    target_dir = tempfile.mkdtemp(prefix='t25-device-', dir=REPO_SCRATCH)
    try:
        _assert_temp_shares_the_targets_filesystem(target_dir)
    finally:
        shutil.rmtree(target_dir, ignore_errors=True)


def _assert_temp_shares_the_targets_filesystem(target_dir):
    settings = pathlib.Path(target_dir) / 'settings.local.json'
    write_settings(settings, {'model': 'claude-opus-5'})
    target = os.path.abspath(str(settings))

    renamed = {}
    real_replace = os.replace

    def recording_replace(src, dst, *args, **kwargs):
        renamed.setdefault('src', os.path.abspath(str(src)))
        return real_replace(src, dst, *args, **kwargs)

    os.replace = recording_replace
    try:
        failure = None
        try:
            assert registration.main(['--settings', str(settings)]) == 0
        except OSError as exc:
            failure = exc   # e.g. EXDEV -- report the cause below, not this
    finally:
        os.replace = real_replace

    assert 'src' in renamed, 'the document never reached the target via os.replace'
    temp_dir = os.stat(os.path.dirname(renamed['src']))
    target_dir_stat = os.stat(os.path.dirname(target))
    assert temp_dir.st_dev == target_dir_stat.st_dev, (
        'the temp file was created on a different filesystem (st_dev %d) from '
        'the target (st_dev %d): %s. os.replace() is only an atomic rename '
        'within one filesystem -- create the temp file in the target'
        "'s own directory." % (temp_dir.st_dev, target_dir_stat.st_dev, renamed['src']))
    # Same device is the requirement; same directory is how this module meets
    # it, and asserting it by inode (not by path string) keeps the test's teeth
    # on a machine where $TMPDIR happens to share the target's filesystem.
    assert temp_dir.st_ino == target_dir_stat.st_ino, (
        'the temp file was created outside the target\'s own directory: %s'
        % renamed['src'])
    assert failure is None, failure

def test_the_settings_file_is_never_opened_for_writing(tmp_path):
    """Quality Requirement "Atomicity", by mechanism: wrap `builtins.open` and
    `os.open` and assert the final path never appears in a truncating -- in
    fact never in any writing -- mode. The document reaches the file only
    through `os.replace`.
    """
    import builtins

    settings = tmp_path / 'settings.local.json'
    write_settings(settings, {'model': 'claude-opus-5'})
    target = os.path.abspath(str(settings))

    opens = []
    real_open = builtins.open
    real_os_open = os.open

    def recording_open(file, mode='r', *args, **kwargs):
        opens.append((os.path.abspath(str(file)), mode))
        return real_open(file, mode, *args, **kwargs)

    def recording_os_open(path, flags, *args, **kwargs):
        opens.append((os.path.abspath(str(path)), flags))
        return real_os_open(path, flags, *args, **kwargs)

    builtins.open = recording_open
    os.open = recording_os_open
    try:
        assert registration.main(['--settings', str(settings)]) == 0
    finally:
        builtins.open = real_open
        os.open = real_os_open

    for path, mode in opens:
        if path != target:
            continue
        if isinstance(mode, str):
            assert 'w' not in mode and 'a' not in mode and '+' not in mode, (
                'the settings file was opened %r -- truncating rewrite' % mode)
        else:
            writing = os.O_WRONLY | os.O_RDWR | os.O_TRUNC | os.O_CREAT
            assert not (mode & writing), (
                'the settings file was opened with flags %d -- truncating rewrite' % mode)


def test_the_settings_files_inode_changes_across_a_write(tmp_path):
    """A rename replaces the inode; an in-place rewrite does not."""
    settings = tmp_path / 'settings.local.json'
    write_settings(settings, {'model': 'claude-opus-5'})
    before = os.stat(str(settings)).st_ino

    assert run_registration(settings).returncode == 0

    assert os.stat(str(settings)).st_ino != before, (
        'the inode survived the write -- the file was rewritten in place, '
        'not replaced by a rename')


def test_an_interrupted_write_leaves_the_original_and_the_backup_intact(tmp_path):
    """SDD-AC-9. The rename is patched to raise once the temp file exists, so
    the failure lands in the one window this whole task exists to close."""
    settings = tmp_path / 'settings.local.json'
    original = write_settings(settings, {'model': 'claude-opus-5'})
    temp = str(settings) + TEMP_SUFFIX

    seen = {}
    real_replace = os.replace

    def exploding_replace(src, dst, *args, **kwargs):
        seen['temp_existed'] = os.path.exists(temp)
        seen['temp_content'] = (
            open(temp, encoding='utf-8').read() if seen['temp_existed'] else None)
        raise OSError(5, 'simulated interruption')

    os.replace = exploding_replace
    try:
        with pytest.raises(OSError):
            registration.main(['--settings', str(settings)])
    finally:
        os.replace = real_replace

    assert seen.get('temp_existed'), 'the rename fired before the temp file was written'
    assert seen['temp_content'], 'the temp file was empty at rename time'
    assert settings.read_text(encoding='utf-8') == original, 'the original was damaged'
    backup = tmp_path / ('settings.local.json' + BACKUP_SUFFIX)
    assert backup.exists(), 'no backup survived the interruption'
    assert backup.read_text(encoding='utf-8') == original
    assert not os.path.exists(temp), 'the temp file was left behind'


# --- the lock --------------------------------------------------------------

def test_two_concurrent_runs_serialize_and_neither_observes_a_partial_file(tmp_path):
    """SDD-AC-11. Both runs are started at once against one target; while they
    run the test polls the file and asserts every state it can observe is a
    complete, parseable document."""
    settings = tmp_path / 'settings.local.json'
    write_settings(settings, {'model': 'claude-opus-5'})

    env = dict(os.environ)
    env[LOCK_TIMEOUT_ENV] = '20'
    procs = [
        subprocess.Popen(
            [sys.executable, SCRIPT, '--settings', str(settings)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
        for _ in range(2)
    ]
    observations = 0
    while any(proc.poll() is None for proc in procs):
        try:
            text = settings.read_text(encoding='utf-8')
        except (OSError, UnicodeDecodeError) as exc:
            raise AssertionError('unreadable mid-run: %s' % exc)
        json.loads(text)  # raises if a partial document was ever observable
        observations += 1
    for proc in procs:
        proc.wait()

    assert observations > 0, 'the runs finished before anything could be observed'
    for proc in procs:
        assert proc.returncode == 0, proc.stderr.read()

    data = json.loads(settings.read_text(encoding='utf-8'))
    assert data['model'] == 'claude-opus-5'
    assert len(our_commands(settings.read_text(encoding='utf-8'))) == 3, (
        'the two runs did not serialize -- entries were doubled')


def test_a_lock_released_inside_the_wait_window_lets_the_second_run_wait_then_succeed(tmp_path):
    """The first of the two outcomes the precedent's poll loop produces
    (lock.sh:78-99): the wait is bounded, and a lock that goes away inside the
    window is followed by a normal, successful run."""
    settings = tmp_path / 'settings.local.json'
    original = write_settings(settings, {'model': 'claude-opus-5'})
    holder = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])
    lock = _hold_lock(settings, holder.pid)

    started = time.time()
    proc = subprocess.Popen(
        [sys.executable, SCRIPT, '--settings', str(settings)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        env=dict(os.environ, **{LOCK_TIMEOUT_ENV: '10'}))
    try:
        time.sleep(0.6)
        assert proc.poll() is None, 'the run did not wait for the lock at all'
        os.unlink(lock)
        stdout, stderr = proc.communicate(timeout=30)
    finally:
        holder.kill()
        holder.wait()

    elapsed = time.time() - started
    assert proc.returncode == 0, stderr
    assert elapsed >= 0.6, 'the run cannot have waited: %.2fs' % elapsed
    assert settings.read_text(encoding='utf-8') != original, 'the run never wrote'


def test_a_lock_held_past_the_timeout_makes_the_second_run_report_and_exit(tmp_path):
    """The other outcome of the same mechanism: on expiry the run reports the
    contention on stderr and exits non-zero, within the bounded time -- it does
    not wait forever and does not write."""
    settings = tmp_path / 'settings.local.json'
    original = write_settings(settings, {'model': 'claude-opus-5'})
    holder = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])
    _hold_lock(settings, holder.pid)

    started = time.time()
    try:
        result = subprocess.run(
            [sys.executable, SCRIPT, '--settings', str(settings)],
            capture_output=True, text=True, timeout=30,
            env=dict(os.environ, **{LOCK_TIMEOUT_ENV: '1'}))
    finally:
        holder.kill()
        holder.wait()
    elapsed = time.time() - started

    assert result.returncode != 0
    assert 'holds' in result.stderr, result.stderr
    assert 'Traceback' not in result.stderr
    # Both bounds are tied to the 1s injected above: the run must not give up
    # early, and must not wait an order of magnitude past its own timeout. The
    # upper bound is not redundant with communicate()'s 30s guard -- a
    # regression stretching the effective wait from 1s to 20s would clear that
    # guard silently, and this is what catches it. Change the injected timeout
    # and both numbers move with it.
    assert elapsed >= 1.0, 'it gave up before the timeout: %.2fs' % elapsed
    assert elapsed < 15.0, 'the wait ran well past its 1s timeout: %.2fs' % elapsed
    assert settings.read_text(encoding='utf-8') == original, 'it wrote despite the lock'


def test_a_live_foreign_lock_is_never_force_removed(tmp_path):
    """The hazard: force-removing a lock whose owner is still running is how
    two runs end up in the same settings file. A contended run therefore
    leaves the lock exactly as it found it -- same file, same bytes."""
    settings = tmp_path / 'settings.local.json'
    write_settings(settings, {'model': 'claude-opus-5'})
    holder = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])
    lock = _hold_lock(settings, holder.pid)
    before = open(lock, encoding='utf-8').read()

    try:
        result = subprocess.run(
            [sys.executable, SCRIPT, '--settings', str(settings)],
            capture_output=True, text=True, timeout=30,
            env=dict(os.environ, **{LOCK_TIMEOUT_ENV: '1'}))
    finally:
        holder.kill()
        holder.wait()

    assert result.returncode != 0
    assert os.path.exists(lock), 'a live foreign lock was force-removed'
    assert open(lock, encoding='utf-8').read() == before, 'a live foreign lock was overwritten'


def test_a_stale_lock_left_by_a_dead_owner_is_reclaimed(tmp_path):
    """ADR-4 / lock.sh:72 -- stale by liveness."""
    settings = tmp_path / 'settings.local.json'
    original = write_settings(settings, {'model': 'claude-opus-5'})
    lock = _hold_lock(settings, _dead_pid())

    result = subprocess.run(
        [sys.executable, SCRIPT, '--settings', str(settings)],
        capture_output=True, text=True, timeout=30,
        env=dict(os.environ, **{LOCK_TIMEOUT_ENV: '2'}))

    assert result.returncode == 0, result.stderr
    assert settings.read_text(encoding='utf-8') != original
    assert not os.path.exists(lock), 'the reclaimed lock was not released'


def test_a_stale_lock_older_than_the_ttl_is_reclaimed_even_with_a_live_owner(tmp_path):
    """The other half of the same rule: stale by TTL. The recorded owner here
    is very much alive -- it is this test -- so only the age can reclaim it."""
    settings = tmp_path / 'settings.local.json'
    original = write_settings(settings, {'model': 'claude-opus-5'})
    lock = _hold_lock(settings, os.getpid(), age_seconds=400)

    result = subprocess.run(
        [sys.executable, SCRIPT, '--settings', str(settings)],
        capture_output=True, text=True, timeout=30,
        env=dict(os.environ, **{LOCK_TIMEOUT_ENV: '2', LOCK_TTL_ENV: '300'}))

    assert result.returncode == 0, result.stderr
    assert settings.read_text(encoding='utf-8') != original
    assert not os.path.exists(lock), 'the reclaimed lock was not released'


def _age_lock(lock, seconds):
    """Backdate the lock file's mtime -- the observable the grace check reads."""
    old = time.time() - seconds
    os.utime(lock, (old, old))


def test_a_freshly_created_empty_lock_is_not_reclaimed(tmp_path):
    """SDD-AC-11's real hazard, and the one an "unreadable means stale" rule
    walks straight into.

    Creating the lock file IS the acquisition, but the owner's `pid:epoch`
    line lands on the NEXT statement -- so for a few microseconds a perfectly
    live lock reads as empty. A contender that calls that stale unlinks the
    lock out from under its owner, race-creates its own, and both runs edit
    the same settings file. An empty lock file with a fresh mtime therefore
    has to be respected, not reclaimed.

    The injected timeout (1s) is deliberately SHORTER than the grace period
    (2s): the run must give up while the empty lock is still inside its
    grace window. If either number moves, this pairing has to move with it.
    """
    settings = tmp_path / 'settings.local.json'
    original = write_settings(settings, {'model': 'claude-opus-5'})
    lock = str(settings) + LOCK_SUFFIX
    open(lock, 'w', encoding='utf-8').close()   # created, not yet written
    assert os.path.getsize(lock) == 0
    assert LOCK_GRACE > 1.0, (
        'this test needs the grace period to outlast the injected timeout')

    result = subprocess.run(
        [sys.executable, SCRIPT, '--settings', str(settings)],
        capture_output=True, text=True, timeout=30,
        env=dict(os.environ, **{LOCK_TIMEOUT_ENV: '1'}))

    assert result.returncode != 0, (
        'a half-written lock was treated as abandoned -- two runs can now '
        'enter the same settings file')
    assert os.path.exists(lock), 'a live lock was unlinked out from under its owner'
    assert settings.read_text(encoding='utf-8') == original, 'it wrote anyway'


def test_an_empty_lock_older_than_the_grace_period_is_reclaimed(tmp_path):
    """The other half: a lock left empty by a crash must not wedge setup
    forever. Once it is older than any create-to-write window could be, it is
    abandoned and gets reclaimed."""
    settings = tmp_path / 'settings.local.json'
    original = write_settings(settings, {'model': 'claude-opus-5'})
    lock = str(settings) + LOCK_SUFFIX
    open(lock, 'w', encoding='utf-8').close()
    _age_lock(lock, LOCK_GRACE + 60)

    result = subprocess.run(
        [sys.executable, SCRIPT, '--settings', str(settings)],
        capture_output=True, text=True, timeout=30,
        env=dict(os.environ, **{LOCK_TIMEOUT_ENV: '2'}))

    assert result.returncode == 0, result.stderr
    assert settings.read_text(encoding='utf-8') != original
    assert not os.path.exists(lock), 'the reclaimed lock was not released'


def test_a_lock_holding_junk_is_reclaimed_once_it_is_older_than_the_grace_period(tmp_path):
    """Content that is neither empty nor `pid:epoch` takes the same path as
    empty content: unusable, but only abandoned once it is old. Until now only
    a dead PID and an over-TTL timestamp were covered, both of which require a
    well-formed line to detect."""
    settings = tmp_path / 'settings.local.json'
    original = write_settings(settings, {'model': 'claude-opus-5'})
    lock = str(settings) + LOCK_SUFFIX

    with open(lock, 'w', encoding='utf-8') as handle:
        handle.write('not-a-pid:not-an-epoch\n')
    _age_lock(lock, LOCK_GRACE + 60)

    result = subprocess.run(
        [sys.executable, SCRIPT, '--settings', str(settings)],
        capture_output=True, text=True, timeout=30,
        env=dict(os.environ, **{LOCK_TIMEOUT_ENV: '2'}))

    assert result.returncode == 0, result.stderr
    assert settings.read_text(encoding='utf-8') != original
    assert not os.path.exists(lock)


def test_junk_in_a_fresh_lock_is_respected_like_an_empty_one(tmp_path):
    """The junk path gets the grace period too -- it is the same branch, and a
    test that only ever backdates the mtime would not notice if it did not."""
    settings = tmp_path / 'settings.local.json'
    original = write_settings(settings, {'model': 'claude-opus-5'})
    lock = str(settings) + LOCK_SUFFIX
    with open(lock, 'w', encoding='utf-8') as handle:
        handle.write('garbage\n')

    result = subprocess.run(
        [sys.executable, SCRIPT, '--settings', str(settings)],
        capture_output=True, text=True, timeout=30,
        env=dict(os.environ, **{LOCK_TIMEOUT_ENV: '1'}))

    assert result.returncode != 0
    assert os.path.exists(lock)
    assert settings.read_text(encoding='utf-8') == original
