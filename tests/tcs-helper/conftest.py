"""Shared pytest fixtures for tcs-helper tests."""
import json
import os
import sys
import pytest

# Ensure scripts directory is on sys.path for all tests in this suite
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../plugins/tcs-helper/scripts'))

SCRIPTS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '../../plugins/tcs-helper/scripts')
)


@pytest.fixture
def tmp_queue_path(tmp_path):
    """Temporary queue file path. File does not yet exist — tests create it as needed."""
    return tmp_path / 'queue.json'


@pytest.fixture
def mock_stdin(monkeypatch):
    """Return a helper that sets TCS_QUEUE_OVERRIDE and provides a subprocess env builder.

    Usage inside a test:
        env = mock_stdin({'prompt': 'no, use fd not find'}, queue_file=tmp_queue_path)
        subprocess.run([sys.executable, script], input=json.dumps(payload).encode(), env=env)
    """
    def _build_env(queue_path=None, extra_env=None):
        env = os.environ.copy()
        if queue_path is not None:
            env['TCS_QUEUE_OVERRIDE'] = str(queue_path)
        if extra_env:
            env.update(extra_env)
        return env
    return _build_env


@pytest.fixture
def sample_queue_items():
    """A list of sample queue items matching the full queue item schema."""
    return [
        {
            'type': 'auto',
            'message': 'use fd not find',
            'timestamp': '2026-01-01T00:00:00+00:00',
            'project': '/test/proj',
            'patterns': 'correction',
            'confidence': 0.75,
            'sentiment': 'correction',
            'decay_days': 90,
        },
        {
            'type': 'explicit',
            'message': 'remember: always use pytest',
            'timestamp': '2026-01-02T00:00:00+00:00',
            'project': '/test/proj',
            'patterns': 'explicit',
            'confidence': 1.0,
            'sentiment': 'correction',
            'decay_days': 120,
        },
        {
            'type': 'guardrail',
            'message': "don't change unrelated files",
            'timestamp': '2026-01-03T00:00:00+00:00',
            'project': '/test/proj',
            'patterns': 'guardrail',
            'confidence': 0.90,
            'sentiment': 'correction',
            'decay_days': 120,
        },
    ]


@pytest.fixture
def project_path(tmp_path):
    """A temporary directory that stands in for a real project root."""
    project_dir = tmp_path / 'project'
    project_dir.mkdir()
    return project_dir


@pytest.fixture
def scripts_dir():
    """Absolute path to the tcs-helper scripts directory."""
    return SCRIPTS_DIR


@pytest.fixture
def populated_queue_file(tmp_queue_path, sample_queue_items):
    """A queue file pre-populated with sample_queue_items, ready for scripts to read."""
    tmp_queue_path.write_text(json.dumps(sample_queue_items))
    return tmp_queue_path
