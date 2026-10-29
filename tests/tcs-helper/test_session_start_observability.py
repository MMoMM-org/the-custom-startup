"""Tests for the SessionStart observability bundle check (#246).

Observability hooks are registered in the repository's `.claude/settings.local.json`,
which a host and a dev container share through the mount, but the bundle they call
lives under each environment's own `$HOME`. A repository registered from one
environment records nothing in the other, silently. This hook says so at session start.
"""
import json
import os
import subprocess
import sys

SCRIPT = os.path.join(os.path.dirname(__file__),
                      '../../plugins/tcs-helper/scripts/session_start_observability.py')

BUNDLE_SCRIPTS = ('log_instructions.sh', 'log_tool.sh', 'log_agent.sh', 'log_expansion.sh')


def _settings(enabled=True):
    events = {
        'InstructionsLoaded': 'log_instructions.sh',
        'PreToolUse': 'log_tool.sh',
        'SubagentStart': 'log_agent.sh',
        'UserPromptExpansion': 'log_expansion.sh',
    }
    doc = {'hooks': {
        event: [{'hooks': [{'type': 'command', 'command': f'"$HOME/.claude/observability/{name}"'}]}]
        for event, name in events.items()
    }}
    if enabled:
        doc['env'] = {'CLAUDE_OBSERVABILITY_ENABLED': '1'}
    return doc


def _repo(tmp_path, settings):
    repo = tmp_path / 'repo'
    (repo / '.claude').mkdir(parents=True)
    if settings is not None:
        text = settings if isinstance(settings, str) else json.dumps(settings)
        (repo / '.claude' / 'settings.local.json').write_text(text, encoding='utf-8')
    return repo


def _home(tmp_path, bundle):
    home = tmp_path / 'home'
    home.mkdir()
    if bundle:
        target = home / '.claude' / 'observability'
        target.mkdir(parents=True)
        for name in BUNDLE_SCRIPTS:
            (target / name).write_text('#!/bin/sh\nexit 0\n', encoding='utf-8')
    return home


def _run(repo, home, extra_env=None):
    env = {k: v for k, v in os.environ.items() if k != 'CLAUDE_OBSERVABILITY_ENABLED'}
    env['HOME'] = str(home)
    env.update(extra_env or {})
    return subprocess.run([sys.executable, SCRIPT], input=json.dumps({'cwd': str(repo)}),
                          capture_output=True, text=True, env=env)


def test_warns_when_registered_and_enabled_but_bundle_missing(tmp_path):
    repo = _repo(tmp_path, _settings())
    home = _home(tmp_path, bundle=False)

    result = _run(repo, home)

    assert result.returncode == 0
    assert f'{home}/.claude/observability' in result.stdout
    assert 'nothing is recorded' in result.stdout
    assert '/tcs-helper:observability-setup install' in result.stdout


def test_warns_when_enabled_only_through_the_process_environment(tmp_path):
    repo = _repo(tmp_path, _settings(enabled=False))
    home = _home(tmp_path, bundle=False)

    result = _run(repo, home, {'CLAUDE_OBSERVABILITY_ENABLED': '1'})

    assert 'nothing is recorded' in result.stdout


def test_silent_when_bundle_is_installed(tmp_path):
    repo = _repo(tmp_path, _settings())
    home = _home(tmp_path, bundle=True)

    result = _run(repo, home)

    assert result.returncode == 0
    assert result.stdout == ''


def test_warns_when_one_registered_script_is_missing(tmp_path):
    repo = _repo(tmp_path, _settings())
    home = _home(tmp_path, bundle=True)
    (home / '.claude' / 'observability' / 'log_tool.sh').unlink()

    result = _run(repo, home)

    assert 'nothing is recorded' in result.stdout


def test_silent_when_recording_is_switched_off(tmp_path):
    repo = _repo(tmp_path, _settings(enabled=False))
    home = _home(tmp_path, bundle=False)

    result = _run(repo, home)

    assert result.stdout == ''


def test_silent_when_no_observability_hook_is_registered(tmp_path):
    settings = {'env': {'CLAUDE_OBSERVABILITY_ENABLED': '1'},
                'hooks': {'Stop': [{'hooks': [{'type': 'command', 'command': '"$HOME/bin/other.sh"'}]}]}}
    repo = _repo(tmp_path, settings)
    home = _home(tmp_path, bundle=False)

    result = _run(repo, home)

    assert result.stdout == ''


def test_silent_without_a_settings_file(tmp_path):
    repo = _repo(tmp_path, None)
    home = _home(tmp_path, bundle=False)

    result = _run(repo, home)

    assert result.returncode == 0
    assert result.stdout == ''


def test_fails_open_on_malformed_settings(tmp_path):
    repo = _repo(tmp_path, '{not json')
    home = _home(tmp_path, bundle=False)

    result = _run(repo, home)

    assert result.returncode == 0
    assert result.stdout == ''
    assert result.stderr == ''
