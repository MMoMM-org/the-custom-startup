"""Tests for reflect_utils.py — queue I/O and path utilities."""
import json
import os
import sys
import pytest
from unittest.mock import patch

# Add scripts to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../plugins/tcs-helper/scripts'))
from lib.reflect_utils import (
    get_queue_path, load_queue, save_queue, create_queue_item, encode_project_path
)


def test_encode_project_path_replaces_slashes():
    result = encode_project_path('/home/user/myproject')
    assert '/' not in result
    # Leading - is preserved (root / → -), matching Claude Code's actual directory naming
    assert result == '-home-user-myproject'


def test_get_queue_path_returns_project_specific_path(tmp_path):
    with patch('lib.reflect_utils.CLAUDE_DIR', str(tmp_path)):
        path = get_queue_path('/home/user/myproject')
    assert 'learnings-queue.json' in path
    assert 'projects' in path


def test_load_queue_returns_empty_list_when_file_missing(tmp_path):
    with patch('lib.reflect_utils.CLAUDE_DIR', str(tmp_path)):
        queue = load_queue('/nonexistent/project')
    assert queue == []


def test_save_and_load_queue_roundtrip(tmp_path):
    item = {'type': 'explicit', 'message': 'test', 'timestamp': '2026-01-01T00:00:00+00:00',
            'project': '/test/proj', 'patterns': 'explicit', 'confidence': 1.0,
            'sentiment': 'correction', 'decay_days': 120}
    with patch('lib.reflect_utils.CLAUDE_DIR', str(tmp_path)):
        save_queue('/test/proj', [item])
        result = load_queue('/test/proj')
    assert len(result) == 1
    assert result[0]['message'] == 'test'


def test_create_queue_item_has_required_fields():
    item = create_queue_item(
        message='use fd not find',
        project='/test/proj',
        item_type='explicit'
    )
    required = ['type', 'message', 'timestamp', 'project', 'patterns', 'confidence',
                'sentiment', 'decay_days']
    for field in required:
        assert field in item, f'Missing field: {field}'


def test_create_queue_item_explicit_has_high_confidence():
    item = create_queue_item('remember: always use fd', '/test/proj', 'explicit')
    assert item['confidence'] == 1.0
    assert item['decay_days'] == 120


def test_create_queue_item_with_tcs_extensions():
    item = create_queue_item(
        'use fd not find', '/test/proj', 'explicit',
        tcs_category='tools', tcs_target='docs/ai/memory/tools.md'
    )
    assert item['tcs_category'] == 'tools'
    assert item['tcs_target'] == 'docs/ai/memory/tools.md'
