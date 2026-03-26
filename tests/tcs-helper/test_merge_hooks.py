"""Tests for merge_hooks.py — additive settings.json hook installer."""
import json
import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../plugins/tcs-helper/scripts'))
from merge_hooks import merge_hooks, read_settings, write_settings


def test_merge_into_empty_settings(tmp_path):
    settings_file = tmp_path / 'settings.json'
    settings_file.write_text('{}')
    hooks_to_add = {
        'UserPromptSubmit': [{'matcher': '', 'hooks': [{'type': 'command', 'command': 'python3 test.py'}]}]
    }
    merge_hooks(str(settings_file), hooks_to_add)
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
    ]})
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
    ]})
    result = json.loads(settings_file.read_text())
    assert 'PostToolUse' in result['hooks']
    assert 'UserPromptSubmit' in result['hooks']


def test_sets_cleanup_period(tmp_path):
    settings_file = tmp_path / 'settings.json'
    settings_file.write_text('{}')
    merge_hooks(str(settings_file), {}, set_cleanup_period=True)
    result = json.loads(settings_file.read_text())
    assert result.get('cleanupPeriodDays') == 99999


def test_cleanup_period_not_overridden_if_higher(tmp_path):
    settings_file = tmp_path / 'settings.json'
    settings_file.write_text('{"cleanupPeriodDays": 999999}')
    merge_hooks(str(settings_file), {}, set_cleanup_period=True)
    result = json.loads(settings_file.read_text())
    assert result['cleanupPeriodDays'] == 999999
