"""Tests for the PostToolUse(Write|Edit|MultiEdit) authoring reminder (ADR-4 layer 1)."""
import json
import os
import subprocess
import sys

import pytest

SCRIPT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '../../plugins/tcs-helper/scripts/authoring_reminder.py')
)
HOOKS_JSON = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '../../plugins/tcs-helper/hooks/hooks.json')
)


def run_hook(payload):
    return subprocess.run(
        [sys.executable, SCRIPT],
        input=payload if isinstance(payload, str) else json.dumps(payload),
        capture_output=True,
        text=True,
    )


def context_for(path, tool='Write'):
    result = run_hook({'tool_name': tool, 'tool_input': {'file_path': path}})
    assert result.returncode == 0, result.stderr
    if not result.stdout.strip():
        return None
    out = json.loads(result.stdout)
    assert out['hookSpecificOutput']['hookEventName'] == 'PostToolUse'
    return out['hookSpecificOutput']['additionalContext']


@pytest.mark.parametrize('path', [
    '/repo/plugins/tcs-helper/skills/memory-add/SKILL.md',
    '/repo/plugins/tcs-patterns/templates/patterns/testing/SKILL.md',
    '/home/u/.claude/skills/mine/SKILL.md',
])
def test_a_skill_file_points_at_skill_author(path):
    assert '/tcs-helper:skill-author' in context_for(path)


@pytest.mark.parametrize('path', [
    '/repo/plugins/tcs-workflow/agents/tdd-guardian.md',
    '/repo/plugins/tcs-team/agents/the-architect/design-system.md',
    '/home/u/.claude/agents/reviewer.md',
])
def test_an_agent_file_points_at_agent_author(path):
    assert '/tcs-helper:agent-author' in context_for(path, tool='Edit')


@pytest.mark.parametrize('path', [
    '/repo/plugins/tcs-helper/skills/memory-add/reference/category-formats.md',
    '/repo/plugins/tcs-team/agents/README.md',
    '/repo/.claude/agent-memory/reviewer/MEMORY.md',
    '/repo/docs/SKILL.md.bak',
    '/repo/README.md',
    '',
])
def test_other_files_get_nothing(path):
    assert context_for(path) is None


def test_malformed_payload_fails_open():
    result = run_hook('{ not json')
    assert result.returncode == 0
    assert result.stdout == ''


def test_registered_for_every_file_writing_tool():
    with open(HOOKS_JSON, encoding='utf-8') as handle:
        hooks = json.load(handle)['hooks']['PostToolUse']
    entry = next(h for h in hooks if 'authoring_reminder.py' in json.dumps(h))
    assert set(entry['matcher'].split('|')) == {'Write', 'Edit', 'MultiEdit'}
