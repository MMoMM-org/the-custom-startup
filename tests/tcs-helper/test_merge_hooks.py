"""Tests for merge_hooks.py — additive settings.json hook installer with path resolution."""
import json
import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../plugins/tcs-helper/scripts'))
from merge_hooks import (
    merge_hooks, read_settings, write_settings,
    resolve_command, resolve_hook_entry, resolve_plugin_root, resolve_settings_path,
)

FAKE_PLUGIN_ROOT = '/Users/test/.claude/plugins/cache/tcs/tcs-helper/1.0.0'


def test_merge_into_empty_settings(tmp_path):
    settings_file = tmp_path / 'settings.json'
    settings_file.write_text('{}')
    hooks_to_add = {
        'UserPromptSubmit': [{'matcher': '', 'hooks': [{'type': 'command', 'command': 'python3 test.py'}]}]
    }
    merge_hooks(str(settings_file), hooks_to_add, plugin_root=FAKE_PLUGIN_ROOT)
    result = json.loads(settings_file.read_text())
    assert 'hooks' in result
    assert 'UserPromptSubmit' in result['hooks']


def test_merge_does_not_duplicate_existing_hook(tmp_path):
    settings_file = tmp_path / 'settings.json'
    existing = {'hooks': {'UserPromptSubmit': [
        {'matcher': '', 'hooks': [{'type': 'command', 'command': 'python3 test.py'}]}
    ]}}
    settings_file.write_text(json.dumps(existing))
    merge_hooks(str(settings_file), {'UserPromptSubmit': [
        {'matcher': '', 'hooks': [{'type': 'command', 'command': 'python3 test.py'}]}
    ]}, plugin_root=FAKE_PLUGIN_ROOT)
    result = json.loads(settings_file.read_text())
    assert len(result['hooks']['UserPromptSubmit']) == 1


def test_merge_preserves_existing_unrelated_hooks(tmp_path):
    settings_file = tmp_path / 'settings.json'
    existing = {'hooks': {'PostToolUse': [
        {'matcher': 'Bash', 'hooks': [{'type': 'command', 'command': 'python3 other.py'}]}
    ]}}
    settings_file.write_text(json.dumps(existing))
    merge_hooks(str(settings_file), {'UserPromptSubmit': [
        {'matcher': '', 'hooks': [{'type': 'command', 'command': 'python3 new.py'}]}
    ]}, plugin_root=FAKE_PLUGIN_ROOT)
    result = json.loads(settings_file.read_text())
    assert 'PostToolUse' in result['hooks']
    assert 'UserPromptSubmit' in result['hooks']


def test_sets_cleanup_period(tmp_path):
    settings_file = tmp_path / 'settings.json'
    settings_file.write_text('{}')
    merge_hooks(str(settings_file), {}, plugin_root=FAKE_PLUGIN_ROOT, set_cleanup_period=True)
    result = json.loads(settings_file.read_text())
    assert result.get('cleanupPeriodDays') == 99999


def test_cleanup_period_not_overridden_if_higher(tmp_path):
    settings_file = tmp_path / 'settings.json'
    settings_file.write_text('{"cleanupPeriodDays": 999999}')
    merge_hooks(str(settings_file), {}, plugin_root=FAKE_PLUGIN_ROOT, set_cleanup_period=True)
    result = json.loads(settings_file.read_text())
    assert result['cleanupPeriodDays'] == 999999


# --- Path resolution tests ---

def test_resolve_command_replaces_plugin_root():
    cmd = 'python3 "${CLAUDE_PLUGIN_ROOT}/scripts/foo.py" "${PWD}"'
    resolved = resolve_command(cmd, '/opt/plugins/tcs')
    assert resolved == 'python3 "/opt/plugins/tcs/scripts/foo.py" "${PWD}"'


def test_resolve_command_no_vars():
    cmd = '~/.claude/hooks/backup.sh'
    assert resolve_command(cmd, '/opt/plugins/tcs') == cmd


def test_resolve_hook_entry_deep_copies():
    entry = {'matcher': '', 'hooks': [
        {'type': 'command', 'command': 'python3 "${CLAUDE_PLUGIN_ROOT}/scripts/foo.py"'}
    ]}
    resolved = resolve_hook_entry(entry, '/opt/plugins/tcs')
    # Original unchanged
    assert '${CLAUDE_PLUGIN_ROOT}' in entry['hooks'][0]['command']
    # Resolved has absolute path
    assert resolved['hooks'][0]['command'] == 'python3 "/opt/plugins/tcs/scripts/foo.py"'


def test_resolve_plugin_root_from_hooks_json():
    hooks_path = '/Users/test/.claude/plugins/cache/tcs/tcs-helper/1.0.0/hooks/hooks.json'
    root = resolve_plugin_root(hooks_path)
    assert root == '/Users/test/.claude/plugins/cache/tcs/tcs-helper/1.0.0'


def test_resolve_settings_path_global():
    path = resolve_settings_path('g')
    assert path.endswith('.claude/settings.json')
    assert os.path.expanduser('~') in path


def test_resolve_settings_path_repo():
    path = resolve_settings_path('r')
    assert path.endswith('.claude/settings.json')
    assert os.getcwd() in path


# --- Integration: template vars resolved before merge ---

def test_merge_resolves_plugin_root_vars(tmp_path):
    settings_file = tmp_path / 'settings.json'
    settings_file.write_text('{}')
    hooks_to_add = {
        'SessionStart': [{'matcher': '', 'hooks': [
            {'type': 'command', 'command': 'python3 "${CLAUDE_PLUGIN_ROOT}/scripts/reminder.py"'}
        ]}]
    }
    merge_hooks(str(settings_file), hooks_to_add, plugin_root='/opt/tcs')
    result = json.loads(settings_file.read_text())
    cmd = result['hooks']['SessionStart'][0]['hooks'][0]['command']
    assert '${CLAUDE_PLUGIN_ROOT}' not in cmd
    assert '/opt/tcs/scripts/reminder.py' in cmd


def test_merge_deduplicates_after_resolution(tmp_path):
    """If the resolved command already exists, it should be skipped."""
    settings_file = tmp_path / 'settings.json'
    existing = {'hooks': {'SessionStart': [
        {'matcher': '', 'hooks': [
            {'type': 'command', 'command': 'python3 "/opt/tcs/scripts/reminder.py"'}
        ]}
    ]}}
    settings_file.write_text(json.dumps(existing))
    hooks_to_add = {
        'SessionStart': [{'matcher': '', 'hooks': [
            {'type': 'command', 'command': 'python3 "${CLAUDE_PLUGIN_ROOT}/scripts/reminder.py"'}
        ]}]
    }
    report = merge_hooks(str(settings_file), hooks_to_add, plugin_root='/opt/tcs')
    result = json.loads(settings_file.read_text())
    assert len(result['hooks']['SessionStart']) == 1
    assert len(report['skipped']) == 1
    assert len(report['added']) == 0
