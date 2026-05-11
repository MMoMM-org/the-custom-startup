"""Tests for the SessionStart context-bridge restore hook."""
import json
import os
import sys
import subprocess
import tempfile

SCRIPT = os.path.join(
    os.path.dirname(__file__),
    '../../plugins/tcs-helper/scripts/session_start_context_bridge.py',
)


def _run(stdin_payload, project_path):
    return subprocess.run(
        [sys.executable, SCRIPT],
        input=stdin_payload,
        capture_output=True,
        text=True,
    )


def _write_checkpoint(project_path, body):
    claude_dir = os.path.join(project_path, '.claude')
    os.makedirs(claude_dir, exist_ok=True)
    path = os.path.join(claude_dir, '.session-checkpoint.md')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(body)
    return path


def test_no_op_when_source_is_startup():
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_checkpoint(tmp, '# untouched\n')
        payload = json.dumps({'source': 'startup', 'cwd': tmp})
        result = _run(payload, tmp)
        assert result.returncode == 0
        assert result.stdout == ''
        assert os.path.exists(path), 'checkpoint must be preserved on non-clear/compact'


def test_no_op_when_source_is_resume():
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_checkpoint(tmp, '# untouched\n')
        payload = json.dumps({'source': 'resume', 'cwd': tmp})
        result = _run(payload, tmp)
        assert result.returncode == 0
        assert result.stdout == ''
        assert os.path.exists(path)


def test_silent_when_no_checkpoint_exists():
    with tempfile.TemporaryDirectory() as tmp:
        payload = json.dumps({'source': 'clear', 'cwd': tmp})
        result = _run(payload, tmp)
        assert result.returncode == 0
        assert result.stdout == ''


def test_restores_checkpoint_after_clear():
    with tempfile.TemporaryDirectory() as tmp:
        body = '---\nbranch: foo\n---\n# Where I left off\nediting frobnicator\n'
        path = _write_checkpoint(tmp, body)
        payload = json.dumps({'source': 'clear', 'cwd': tmp})
        result = _run(payload, tmp)
        assert result.returncode == 0
        assert 'Restored from context-bridge checkpoint' in result.stdout
        assert 'before /clear' in result.stdout
        assert '# Where I left off' in result.stdout
        assert 'editing frobnicator' in result.stdout
        # Checkpoint must be consumed (renamed) so it is not re-injected
        assert not os.path.exists(path)
        remaining = os.listdir(os.path.join(tmp, '.claude'))
        assert any(f.startswith('.session-checkpoint.consumed-') for f in remaining)


def test_restores_checkpoint_after_compact():
    with tempfile.TemporaryDirectory() as tmp:
        _write_checkpoint(tmp, '# body\n')
        payload = json.dumps({'source': 'compact', 'cwd': tmp})
        result = _run(payload, tmp)
        assert result.returncode == 0
        assert 'before /compact' in result.stdout
        assert '# body' in result.stdout


def test_malformed_stdin_does_not_crash():
    result = subprocess.run(
        [sys.executable, SCRIPT],
        input='not-json-at-all',
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert result.stdout == ''


def test_preserves_utf8_content():
    with tempfile.TemporaryDirectory() as tmp:
        body = '# 状態スナップショット — café ☕\n'
        _write_checkpoint(tmp, body)
        payload = json.dumps({'source': 'clear', 'cwd': tmp})
        result = _run(payload, tmp)
        assert result.returncode == 0
        assert '状態スナップショット' in result.stdout
        assert 'café ☕' in result.stdout
