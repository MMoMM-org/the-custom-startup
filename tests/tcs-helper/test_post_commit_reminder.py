"""Tests for the PostToolUse(Bash) hook that reminds after git commit."""
import json
import os
import sys
import subprocess

SCRIPT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '../../plugins/tcs-helper/scripts/post_commit_reminder.py')
)


def run_hook(stdin_payload):
    """Run the hook script with the given payload string, return subprocess result."""
    return subprocess.run(
        [sys.executable, SCRIPT],
        input=stdin_payload,
        capture_output=True,
        text=True,
    )


def run_hook_with_command(command):
    """Build a standard tool_input payload and run the hook."""
    payload = json.dumps({'tool_input': {'command': command}})
    return run_hook(payload)


def test_git_commit_with_message_outputs_reminder():
    result = run_hook_with_command("git commit -m 'add feature'")
    assert result.returncode == 0
    assert result.stdout.strip() != ''
    output = json.loads(result.stdout)
    assert 'hookSpecificOutput' in output
    assert 'memory-add' in output['hookSpecificOutput'].lower()


def test_git_commit_amend_produces_no_output():
    result = run_hook_with_command('git commit --amend')
    assert result.returncode == 0
    assert result.stdout.strip() == ''


def test_non_git_command_produces_no_output():
    result = run_hook_with_command('ls -la')
    assert result.returncode == 0
    assert result.stdout.strip() == ''


def test_malformed_json_stdin_does_not_crash():
    result = run_hook('this is not json {{{')
    assert result.returncode == 0
    assert result.stdout.strip() == ''


def test_empty_stdin_does_not_crash():
    result = run_hook('')
    assert result.returncode == 0
    assert result.stdout.strip() == ''


def test_output_is_valid_json_with_hook_specific_output_key():
    result = run_hook_with_command('git commit -m "chore: update docs"')
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert isinstance(output, dict)
    assert 'hookSpecificOutput' in output
    assert isinstance(output['hookSpecificOutput'], str)
    assert len(output['hookSpecificOutput']) > 0


def test_git_commit_no_flags_outputs_reminder():
    result = run_hook_with_command('git commit')
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert 'hookSpecificOutput' in output
