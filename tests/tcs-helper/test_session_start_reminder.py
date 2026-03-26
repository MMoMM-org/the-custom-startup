"""Tests for the SessionStart hook."""
import json
import os
import sys
import subprocess
import tempfile
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../plugins/tcs-helper/scripts'))


def run_reminder(queue_items=None, yolo_review_exists=False, project_path='/test/proj'):
    script = os.path.join(os.path.dirname(__file__),
                          '../../plugins/tcs-helper/scripts/session_start_reminder.py')
    with tempfile.TemporaryDirectory() as tmp:
        queue_file = os.path.join(tmp, 'queue.json')
        with open(queue_file, 'w') as f:
            json.dump(queue_items or [], f)
        env = os.environ.copy()
        env['TCS_QUEUE_OVERRIDE'] = queue_file
        if yolo_review_exists:
            env['TCS_YOLO_REVIEW_PATH'] = os.path.join(tmp, 'yolo-review.md')
            with open(env['TCS_YOLO_REVIEW_PATH'], 'w') as f:
                f.write('- [ ] **Target:** `docs/ai/memory/tools.md`\n  Test entry\n')
        result = subprocess.run(
            [sys.executable, script, project_path],
            capture_output=True, text=True, env=env
        )
    return result


def test_no_output_when_queue_empty():
    result = run_reminder(queue_items=[])
    assert result.returncode == 0
    assert result.stdout.strip() == ''


def test_shows_count_when_queue_has_items():
    items = [{'type': 'auto', 'message': 'use fd', 'timestamp': '2026-01-01T00:00:00+00:00',
               'project': '/test', 'patterns': 'auto', 'confidence': 0.75,
               'sentiment': 'correction', 'decay_days': 90}]
    result = run_reminder(queue_items=items)
    assert '1' in result.stdout
    assert 'memory-add' in result.stdout.lower() or 'reflect' in result.stdout.lower()


def test_shows_yolo_warning_when_review_file_exists():
    result = run_reminder(yolo_review_exists=True)
    assert 'yolo' in result.stdout.lower() or 'review' in result.stdout.lower()
    assert 'memory-add' in result.stdout.lower()
