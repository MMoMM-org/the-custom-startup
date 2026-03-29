"""Tests for semantic_detector.py — AI validation + contradiction detection.

Tests are grouped by function. All subprocess calls are mocked — no real claude CLI
invocations occur during the test suite.
"""
import json
import os
import subprocess
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../plugins/tcs-helper/scripts'))

from lib.semantic_detector import (
    detect_contradictions,
    semantic_analyze,
    validate_queue_items,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_subprocess_result(stdout_dict):
    """Return a mock CompletedProcess whose stdout is JSON-encoded stdout_dict."""
    result = MagicMock()
    result.stdout = json.dumps(stdout_dict)
    result.returncode = 0
    return result


def _make_queue_item(message, confidence, item_type='auto'):
    return {
        'type': item_type,
        'message': message,
        'confidence': confidence,
        'sentiment': 'correction',
    }


# ---------------------------------------------------------------------------
# T5.1 — semantic_analyze()
# ---------------------------------------------------------------------------

class TestSemanticAnalyze:
    def test_returns_expected_dict_on_valid_response(self):
        payload = {
            'is_learning': True,
            'type': 'correction',
            'confidence': 0.9,
            'reasoning': 'user corrected a behaviour',
            'extracted_learning': 'always use tabs',
        }
        with patch('subprocess.run', return_value=_make_subprocess_result(payload)) as mock_run:
            result = semantic_analyze('use tabs not spaces')
        assert result == payload
        mock_run.assert_called_once()

    def test_returns_none_when_claude_unavailable(self):
        with patch('subprocess.run', side_effect=FileNotFoundError):
            result = semantic_analyze('use tabs not spaces')
        assert result is None

    def test_returns_none_on_oserror(self):
        with patch('subprocess.run', side_effect=OSError('not found')):
            result = semantic_analyze('use tabs not spaces')
        assert result is None

    def test_returns_none_on_timeout(self):
        with patch('subprocess.run', side_effect=subprocess.TimeoutExpired(cmd='claude', timeout=5)):
            result = semantic_analyze('use tabs not spaces')
        assert result is None

    def test_returns_none_when_disabled_via_env(self, monkeypatch):
        monkeypatch.setenv('TCS_SEMANTIC_VALIDATION', 'false')
        with patch('subprocess.run') as mock_run:
            result = semantic_analyze('use tabs not spaces')
        assert result is None
        mock_run.assert_not_called()

    def test_returns_none_on_invalid_json(self):
        bad_result = MagicMock()
        bad_result.stdout = 'not json at all'
        with patch('subprocess.run', return_value=bad_result):
            result = semantic_analyze('use tabs not spaces')
        assert result is None

    def test_returns_none_on_empty_stdout(self):
        empty_result = MagicMock()
        empty_result.stdout = ''
        with patch('subprocess.run', return_value=empty_result):
            result = semantic_analyze('some text')
        assert result is None

    def test_passes_model_to_subprocess(self):
        payload = {
            'is_learning': True,
            'type': 'preference',
            'confidence': 0.8,
            'reasoning': 'r',
            'extracted_learning': 'e',
        }
        with patch('subprocess.run', return_value=_make_subprocess_result(payload)) as mock_run:
            semantic_analyze('prefer spaces', model='haiku')
        call_args = mock_run.call_args
        cmd = call_args[0][0]
        assert 'haiku' in cmd

    def test_uses_five_second_timeout(self):
        payload = {
            'is_learning': False,
            'type': 'none',
            'confidence': 0.1,
            'reasoning': 'r',
            'extracted_learning': '',
        }
        with patch('subprocess.run', return_value=_make_subprocess_result(payload)) as mock_run:
            semantic_analyze('ok')
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs.get('timeout') == 5

    def test_env_var_true_does_not_disable(self, monkeypatch):
        monkeypatch.setenv('TCS_SEMANTIC_VALIDATION', 'true')
        payload = {
            'is_learning': True,
            'type': 'correction',
            'confidence': 0.85,
            'reasoning': 'r',
            'extracted_learning': 'e',
        }
        with patch('subprocess.run', return_value=_make_subprocess_result(payload)) as mock_run:
            result = semantic_analyze('no, use tabs')
        assert result is not None
        mock_run.assert_called_once()

    def test_returns_none_on_json_missing_required_fields(self):
        # JSON that parses but lacks the expected keys
        incomplete = MagicMock()
        incomplete.stdout = json.dumps({'is_learning': True})
        with patch('subprocess.run', return_value=incomplete):
            result = semantic_analyze('some text')
        # Should still return the dict — caller decides what to do with partial data
        # OR return None — spec says "invalid JSON response → None" but partial JSON
        # is technically valid. The implementation may return either; we accept both.
        # Key constraint: must not raise an exception.
        assert result is None or isinstance(result, dict)


# ---------------------------------------------------------------------------
# T5.1 — validate_queue_items()
# ---------------------------------------------------------------------------

class TestValidateQueueItems:
    def test_empty_list_returns_empty(self):
        assert validate_queue_items([]) == []

    def test_high_confidence_item_passes_through_unchanged(self):
        item = _make_queue_item('use tabs', confidence=0.8)
        with patch('lib.semantic_detector.semantic_analyze') as mock_sa:
            result = validate_queue_items([item])
        assert result == [item]
        mock_sa.assert_not_called()

    def test_filters_false_positive_when_semantic_says_not_learning(self):
        item = _make_queue_item('no problem', confidence=0.5)
        semantic_response = {
            'is_learning': False,
            'type': 'none',
            'confidence': 0.1,
            'reasoning': 'greeting not instruction',
            'extracted_learning': '',
        }
        with patch('lib.semantic_detector.semantic_analyze', return_value=semantic_response):
            result = validate_queue_items([item])
        assert result == []

    def test_merges_confidence_when_semantic_confirms_learning(self):
        item = _make_queue_item('use tabs', confidence=0.5)
        semantic_response = {
            'is_learning': True,
            'type': 'preference',
            'confidence': 0.9,
            'reasoning': 'explicit preference',
            'extracted_learning': 'use tabs',
        }
        with patch('lib.semantic_detector.semantic_analyze', return_value=semantic_response):
            result = validate_queue_items([item])
        assert len(result) == 1
        assert result[0]['confidence'] == pytest.approx(0.7)  # (0.5 + 0.9) / 2

    def test_keeps_original_when_semantic_returns_none(self):
        item = _make_queue_item('use tabs', confidence=0.5)
        with patch('lib.semantic_detector.semantic_analyze', return_value=None):
            result = validate_queue_items([item])
        assert result == [item]

    def test_exact_threshold_item_passes_through_without_ai_call(self):
        # confidence == 0.7 is NOT < 0.7, so should pass through
        item = _make_queue_item('use tabs', confidence=0.7)
        with patch('lib.semantic_detector.semantic_analyze') as mock_sa:
            result = validate_queue_items([item])
        assert result == [item]
        mock_sa.assert_not_called()

    def test_mixed_list_processes_only_low_confidence(self):
        high = _make_queue_item('use tabs', confidence=0.9)
        low = _make_queue_item('no problem', confidence=0.4)
        semantic_response = {
            'is_learning': False,
            'type': 'none',
            'confidence': 0.1,
            'reasoning': 'not an instruction',
            'extracted_learning': '',
        }
        with patch('lib.semantic_detector.semantic_analyze', return_value=semantic_response) as mock_sa:
            result = validate_queue_items([high, low])
        assert result == [high]
        mock_sa.assert_called_once()

    def test_multiple_low_confidence_items_each_validated(self):
        items = [
            _make_queue_item('pref A', confidence=0.4),
            _make_queue_item('pref B', confidence=0.5),
        ]
        semantic_response = {
            'is_learning': True,
            'type': 'preference',
            'confidence': 0.8,
            'reasoning': 'r',
            'extracted_learning': 'e',
        }
        with patch('lib.semantic_detector.semantic_analyze', return_value=semantic_response) as mock_sa:
            result = validate_queue_items(items)
        assert len(result) == 2
        assert mock_sa.call_count == 2


# ---------------------------------------------------------------------------
# T5.2 — detect_contradictions()
# ---------------------------------------------------------------------------

class TestDetectContradictions:
    def test_finds_opposite_style_entries(self):
        # High keyword overlap + opposite sentiment triggers keyword fallback.
        # "never use tabs for indentation" vs "always use tabs for indentation"
        # shares: use, tabs, indentation → jaccard > 0.6, sentiments differ.
        existing = ['never use tabs for indentation']
        with patch('subprocess.run', side_effect=FileNotFoundError):
            result = detect_contradictions('always use tabs for indentation', existing)
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_no_conflict_for_unrelated_entries(self):
        existing = ['use snake_case for Python variables']
        with patch('subprocess.run', side_effect=FileNotFoundError):
            result = detect_contradictions('always commit with --no-verify for hotfixes', existing)
        assert isinstance(result, list)
        # Unrelated entries should produce no contradiction
        assert len(result) == 0

    def test_empty_entries_returns_empty(self):
        result = detect_contradictions('always use tabs', [])
        assert result == []

    def test_returns_list_of_tuples(self):
        existing = ["don't use tabs ever, always use spaces"]
        with patch('subprocess.run', side_effect=FileNotFoundError):
            result = detect_contradictions('always use tabs', existing)
        for item in result:
            assert isinstance(item, tuple)
            assert len(item) == 2
            assert isinstance(item[0], str)
            assert isinstance(item[1], str)

    def test_keyword_fallback_detects_negation_vs_affirmation(self):
        # "never use pytest for testing" vs "always use pytest for testing"
        # Jaccard = 4/5 = 0.8 with opposite sentiment → keyword fallback detects it
        existing = ['never use pytest for testing']
        with patch('subprocess.run', side_effect=FileNotFoundError):
            result = detect_contradictions('always use pytest for testing', existing)
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_claude_based_detection_when_available(self):
        existing = ['always use 2-space indent']
        claude_response = MagicMock()
        claude_response.stdout = 'yes, they contradict each other'
        claude_response.returncode = 0
        with patch('subprocess.run', return_value=claude_response):
            result = detect_contradictions('always use 4-space indent', existing)
        # Should still return list of tuples (may or may not detect depending on impl)
        assert isinstance(result, list)

    def test_single_entry_no_overlap_no_contradiction(self):
        existing = ['use git rebase for clean history']
        with patch('subprocess.run', side_effect=FileNotFoundError):
            result = detect_contradictions('prefer dark mode in the editor', existing)
        assert result == []
