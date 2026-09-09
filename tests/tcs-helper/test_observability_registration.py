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
import subprocess
import sys

SCRIPT = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        '../../plugins/tcs-helper/skills/observability-setup/lib/registration.py',
    )
)

OUR_NAMESPACE = '$HOME/.claude/observability/'

EXPECTED_EVENTS = {
    'InstructionsLoaded': ('', 'log_instructions.sh'),
    'PreToolUse': ('Skill', 'log_skill.sh'),
    'SubagentStart': ('', 'log_agent.sh'),
}


def run_registration(settings_path, *extra_args):
    """Invoke the editor against a settings file, never a real one."""
    return subprocess.run(
        [sys.executable, SCRIPT, '--settings', str(settings_path), *extra_args],
        capture_output=True,
        text=True,
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
