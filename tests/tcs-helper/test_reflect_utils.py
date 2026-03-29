"""Tests for reflect_utils.py — queue I/O and path utilities."""
import json
import os
import sys
import pytest
from unittest.mock import patch

# Add scripts to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../plugins/tcs-helper/scripts'))
from lib.reflect_utils import (
    get_queue_path, load_queue, save_queue, create_queue_item, encode_project_path,
    detect_learning,
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


# ---------------------------------------------------------------------------
# detect_learning() — parametrized unit tests
# ---------------------------------------------------------------------------

# Explicit pattern: "remember:" keyword → ('explicit', 'explicit', 1.0)
@pytest.mark.parametrize('prompt', [
    'remember: always use venv for Python deps',
    'remember:this is important',
    'Remember: use fd not find',
    'REMEMBER: never skip hooks',
    # embedded in a longer sentence
    'Just a note — remember: commit after every task',
])
def test_detect_learning_explicit_patterns(prompt):
    result = detect_learning(prompt)
    assert result is not None
    learning_type, pattern_name, confidence = result
    assert learning_type == 'explicit'
    assert pattern_name == 'explicit'
    assert confidence == 1.0


# Guardrail patterns — returns ('guardrail', 'guardrail', 0.85)
@pytest.mark.parametrize('prompt', [
    # r"don'?t\s+\w+\s+unless" — straight apostrophe required by the regex
    "don't run unless asked",
    "only change what I asked",
    "stop refactoring unrelated code",
    # r"leave\s+\w+\s+alone" — exactly one word between leave and alone
    "leave config alone",
    "minimal changes please",
])
def test_detect_learning_guardrail_patterns(prompt):
    result = detect_learning(prompt)
    assert result is not None
    learning_type, pattern_name, confidence = result
    assert learning_type == 'guardrail'
    assert pattern_name == 'guardrail'
    assert confidence >= 0.80


# Positive patterns — returns ('positive', 'positive', 0.70)
@pytest.mark.parametrize('prompt', [
    'perfect!',
    'exactly right',
    'great approach here',
    'nailed it',
    "that's exactly what I wanted",
])
def test_detect_learning_positive_patterns(prompt):
    result = detect_learning(prompt)
    assert result is not None
    learning_type, pattern_name, confidence = result
    assert learning_type == 'positive'
    assert pattern_name == 'positive'
    assert confidence >= 0.70


# Correction patterns — note: type is 'auto', pattern name is 'correction'
@pytest.mark.parametrize('prompt', [
    "no, that's wrong",
    "don't do that",
    "stop it",
    "that's wrong",
    "actually, use the other approach",
    "use fd not find",
    "i meant the other file",
    "i told you not to do that",
])
def test_detect_learning_correction_patterns(prompt):
    result = detect_learning(prompt)
    assert result is not None
    learning_type, pattern_name, confidence = result
    # The implementation returns type='auto' (not 'correction') for correction matches
    assert learning_type == 'auto'
    assert pattern_name == 'correction'
    assert confidence >= 0.55


# Non-matching prompts — should return None
@pytest.mark.parametrize('prompt', [
    'hello world',
    'how do I use this?',
    '',
    'please help me understand the codebase',
    'what does this function do?',
])
def test_detect_learning_no_match_returns_none(prompt):
    assert detect_learning(prompt) is None


# Long prompt (> 2000 chars) without "remember:" is skipped entirely
def test_detect_learning_long_prompt_without_remember_returns_none():
    # Build a prompt that would match a correction pattern if not too long
    long_prompt = "actually, " + "x" * 2100
    assert detect_learning(long_prompt) is None


# Long prompt (> 2000 chars) WITH "remember:" is still processed
def test_detect_learning_long_prompt_with_remember_returns_explicit():
    long_prompt = "remember: always use venv. " + "x" * 2100
    result = detect_learning(long_prompt)
    assert result is not None
    assert result[0] == 'explicit'
    assert result[2] == 1.0


# Return format validation — tuple of (str, str, float)
def test_detect_learning_return_format_is_typed_tuple():
    result = detect_learning('remember: validate return type')
    assert isinstance(result, tuple)
    assert len(result) == 3
    learning_type, pattern_name, confidence = result
    assert isinstance(learning_type, str)
    assert isinstance(pattern_name, str)
    assert isinstance(confidence, float)


# Explicit takes priority over guardrail patterns
def test_detect_learning_explicit_takes_priority_over_guardrail():
    # "only change what I asked" would match guardrail,
    # but "remember:" prefix wins first
    prompt = "remember: only change what I asked"
    result = detect_learning(prompt)
    assert result[0] == 'explicit'


# Guardrail takes priority over positive patterns
def test_detect_learning_guardrail_takes_priority_over_positive():
    # "minimal changes" matches guardrail; "perfect" matches positive
    # guardrail check runs before positive check
    prompt = "minimal changes — perfect!"
    result = detect_learning(prompt)
    assert result[0] == 'guardrail'


# Positive takes priority over correction patterns
def test_detect_learning_positive_takes_priority_over_correction():
    # "exactly right" matches positive; "actually" would match correction
    prompt = "actually that's exactly right"
    result = detect_learning(prompt)
    assert result[0] == 'positive'
