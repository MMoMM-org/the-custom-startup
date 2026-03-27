"""Tests for the UserPromptSubmit hook."""
import json
import os
import sys
import subprocess
import tempfile
import pytest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../plugins/tcs-helper/scripts'))


def run_hook(prompt_text, project_path, queue_path_override=None):
    """Run capture_learning.py with given stdin."""
    env = os.environ.copy()
    if queue_path_override:
        env['TCS_QUEUE_OVERRIDE'] = queue_path_override
    stdin_data = json.dumps({'prompt': prompt_text})
    script = os.path.join(os.path.dirname(__file__),
                          '../../plugins/tcs-helper/scripts/capture_learning.py')
    result = subprocess.run(
        [sys.executable, script, project_path],
        input=stdin_data.encode(),
        capture_output=True,
        env=env
    )
    return result


def test_correction_prompt_is_queued(tmp_path):
    queue_file = tmp_path / 'queue.json'
    result = run_hook('no, use fd not find', '/test/proj',
                      queue_path_override=str(queue_file))
    assert result.returncode == 0
    queue = json.loads(queue_file.read_text())
    assert len(queue) == 1
    assert queue[0]['message'] == 'no, use fd not find'
    assert queue[0]['type'] == 'auto'


def test_explicit_remember_is_queued(tmp_path):
    queue_file = tmp_path / 'queue.json'
    result = run_hook('remember: always use fd not find', '/test/proj',
                      queue_path_override=str(queue_file))
    assert result.returncode == 0
    queue = json.loads(queue_file.read_text())
    assert len(queue) == 1
    assert queue[0]['type'] == 'explicit'
    assert queue[0]['confidence'] == 1.0


def test_neutral_prompt_is_not_queued(tmp_path):
    queue_file = tmp_path / 'queue.json'
    result = run_hook('can you help me write a function?', '/test/proj',
                      queue_path_override=str(queue_file))
    assert result.returncode == 0
    assert not queue_file.exists() or json.loads(queue_file.read_text()) == []


def test_hook_always_exits_zero_on_error():
    result = run_hook('anything', '/nonexistent/path/that/causes/errors')
    assert result.returncode == 0
