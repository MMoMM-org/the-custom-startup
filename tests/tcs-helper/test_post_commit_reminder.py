"""Tests for the PostToolUse(Bash) hook that reminds after git commit."""
import json
import os
import sys
import subprocess
import pytest

SCRIPT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '../../plugins/tcs-helper/scripts/post_commit_reminder.py')
)


def run_hook(stdin_payload, env_overrides=None):
    """Run the hook script with the given payload string, return subprocess result."""
    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)
    return subprocess.run(
        [sys.executable, SCRIPT],
        input=stdin_payload,
        capture_output=True,
        text=True,
        env=env,
    )


def run_hook_with_command(command, env_overrides=None):
    """Build a standard tool_input payload and run the hook."""
    payload = json.dumps({'tool_input': {'command': command}})
    return run_hook(payload, env_overrides=env_overrides)


def run_hook_with_tool_output(tool_output, cwd='/project/path', command='ls', env_overrides=None):
    """Build a payload with tool_output and run the hook."""
    payload = json.dumps({
        'tool_input': {'command': command},
        'tool_output': tool_output,
        'cwd': cwd,
    })
    return run_hook(payload, env_overrides=env_overrides)


def load_queue_from_dir(queue_dir, cwd='/project/path'):
    """Load the learnings queue written by the hook for a given cwd."""
    # The hook uses encode_project_path() which replaces / with -
    encoded = cwd.replace('/', '-').replace(' ', '_')
    queue_path = os.path.join(queue_dir, 'projects', encoded, 'learnings-queue.json')
    if not os.path.exists(queue_path):
        return []
    with open(queue_path) as f:
        return json.load(f)


def test_git_commit_with_message_outputs_reminder():
    result = run_hook_with_command("git commit -m 'add feature'")
    assert result.returncode == 0
    assert result.stdout.strip() != ''
    output = json.loads(result.stdout)
    assert 'hookSpecificOutput' in output
    assert output['hookSpecificOutput']['hookEventName'] == 'PostToolUse'
    assert 'memory-add' in output['hookSpecificOutput']['additionalContext'].lower()


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
    hso = output['hookSpecificOutput']
    assert isinstance(hso, dict)
    assert hso['hookEventName'] == 'PostToolUse'
    assert isinstance(hso['additionalContext'], str)
    assert len(hso['additionalContext']) > 0


def test_git_commit_no_flags_outputs_reminder():
    result = run_hook_with_command('git commit')
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert 'hookSpecificOutput' in output
    assert output['hookSpecificOutput']['hookEventName'] == 'PostToolUse'


# --- Tool error detection tests ---

def test_tool_error_not_captured_on_first_occurrence(tmp_path):
    env = {
        'TCS_QUEUE_OVERRIDE': str(tmp_path),
        'TCS_ERROR_COUNTER_OVERRIDE': str(tmp_path / 'error-counts.json'),
    }
    result = run_hook_with_tool_output(
        "ModuleNotFoundError: No module named 'requests'",
        env_overrides=env,
    )
    assert result.returncode == 0
    queue = load_queue_from_dir(str(tmp_path))
    assert queue == []


def test_tool_error_captured_on_second_occurrence(tmp_path):
    env = {
        'TCS_QUEUE_OVERRIDE': str(tmp_path),
        'TCS_ERROR_COUNTER_OVERRIDE': str(tmp_path / 'error-counts.json'),
    }
    tool_output = "ModuleNotFoundError: No module named 'requests'"
    run_hook_with_tool_output(tool_output, env_overrides=env)
    run_hook_with_tool_output(tool_output, env_overrides=env)
    queue = load_queue_from_dir(str(tmp_path))
    assert len(queue) == 1
    assert queue[0]['item_type'] == 'tool_error'


def test_module_not_found_error_categorized(tmp_path):
    env = {
        'TCS_QUEUE_OVERRIDE': str(tmp_path),
        'TCS_ERROR_COUNTER_OVERRIDE': str(tmp_path / 'error-counts.json'),
    }
    tool_output = "ModuleNotFoundError: No module named 'foo'"
    run_hook_with_tool_output(tool_output, env_overrides=env)
    run_hook_with_tool_output(tool_output, env_overrides=env)
    queue = load_queue_from_dir(str(tmp_path))
    assert len(queue) == 1
    assert queue[0]['error_pattern'] == 'module_not_found'


def test_connection_refused_error_categorized(tmp_path):
    env = {
        'TCS_QUEUE_OVERRIDE': str(tmp_path),
        'TCS_ERROR_COUNTER_OVERRIDE': str(tmp_path / 'error-counts.json'),
    }
    tool_output = 'Connection refused: could not connect to localhost:5432'
    run_hook_with_tool_output(tool_output, env_overrides=env)
    run_hook_with_tool_output(tool_output, env_overrides=env)
    queue = load_queue_from_dir(str(tmp_path))
    assert len(queue) == 1
    assert queue[0]['error_pattern'] == 'connection_refused'


def test_non_error_tool_output_no_queue(tmp_path):
    env = {
        'TCS_QUEUE_OVERRIDE': str(tmp_path),
        'TCS_ERROR_COUNTER_OVERRIDE': str(tmp_path / 'error-counts.json'),
    }
    run_hook_with_tool_output('All tests passed.', env_overrides=env)
    run_hook_with_tool_output('All tests passed.', env_overrides=env)
    queue = load_queue_from_dir(str(tmp_path))
    assert queue == []


def test_git_commit_detection_still_works(tmp_path):
    env = {
        'TCS_QUEUE_OVERRIDE': str(tmp_path),
        'TCS_ERROR_COUNTER_OVERRIDE': str(tmp_path / 'error-counts.json'),
    }
    result = run_hook_with_command("git commit -m 'feat: something'", env_overrides=env)
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert 'hookSpecificOutput' in output
    assert output['hookSpecificOutput']['hookEventName'] == 'PostToolUse'
    assert 'memory-add' in output['hookSpecificOutput']['additionalContext'].lower()


def test_error_counter_persists_across_calls(tmp_path):
    env = {
        'TCS_QUEUE_OVERRIDE': str(tmp_path),
        'TCS_ERROR_COUNTER_OVERRIDE': str(tmp_path / 'error-counts.json'),
    }
    tool_output = 'FileNotFoundError: No such file or directory: /tmp/missing.txt'
    run_hook_with_tool_output(tool_output, env_overrides=env)
    counter_path = tmp_path / 'error-counts.json'
    assert counter_path.exists(), 'Counter file should be written after first occurrence'
    with open(counter_path) as f:
        counts = json.load(f)
    assert any(v == 1 for v in counts.values()), 'Counter should be 1 after first call'
    run_hook_with_tool_output(tool_output, env_overrides=env)
    queue = load_queue_from_dir(str(tmp_path))
    assert len(queue) == 1


def test_transient_error_then_different_error(tmp_path):
    env = {
        'TCS_QUEUE_OVERRIDE': str(tmp_path),
        'TCS_ERROR_COUNTER_OVERRIDE': str(tmp_path / 'error-counts.json'),
    }
    run_hook_with_tool_output(
        "ModuleNotFoundError: No module named 'alpha'",
        env_overrides=env,
    )
    run_hook_with_tool_output(
        "ModuleNotFoundError: No module named 'beta'",
        env_overrides=env,
    )
    queue = load_queue_from_dir(str(tmp_path))
    assert queue == [], 'Two distinct errors seen once each should not be queued'


def test_queue_item_has_required_fields(tmp_path):
    env = {
        'TCS_QUEUE_OVERRIDE': str(tmp_path),
        'TCS_ERROR_COUNTER_OVERRIDE': str(tmp_path / 'error-counts.json'),
    }
    tool_output = "SyntaxError: invalid syntax at line 5"
    cwd = '/project/myapp'
    run_hook_with_tool_output(tool_output, cwd=cwd, env_overrides=env)
    run_hook_with_tool_output(tool_output, cwd=cwd, env_overrides=env)
    queue = load_queue_from_dir(str(tmp_path), cwd=cwd)
    assert len(queue) == 1
    item = queue[0]
    assert item['type'] == 'tool_error'
    assert item['item_type'] == 'tool_error'
    assert item['error_pattern'] == 'syntax_error'
    assert item['sentiment'] == 'error'
    assert item['confidence'] == 1.0
    assert item['decay_days'] == 90
    assert 'message' in item
    assert 'timestamp' in item
    assert 'project' in item
    assert len(item['message']) <= 500


def test_missing_tool_output_field_does_not_crash(tmp_path):
    env = {
        'TCS_QUEUE_OVERRIDE': str(tmp_path),
        'TCS_ERROR_COUNTER_OVERRIDE': str(tmp_path / 'error-counts.json'),
    }
    payload = json.dumps({'tool_input': {'command': 'ls'}, 'cwd': '/project/path'})
    result = run_hook(payload, env_overrides=env)
    assert result.returncode == 0
