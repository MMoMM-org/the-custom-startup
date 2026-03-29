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
    detect_learning, strip_code_blocks, is_false_positive, calculate_confidence,
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


# ---------------------------------------------------------------------------
# T3.1 — strip_code_blocks() and is_false_positive()
# ---------------------------------------------------------------------------

class TestStripCodeBlocks:
    """Tests for code block removal before pattern matching."""

    def test_no_blocks_text_unchanged(self):
        text = "no, that's wrong. Use fd instead."
        assert strip_code_blocks(text) == text

    def test_single_block_removed(self):
        text = "don't use this:\n```\nold_code()\n```\nuse the new API"
        result = strip_code_blocks(text)
        assert "old_code()" not in result
        assert "don't use this:" in result
        assert "use the new API" in result

    def test_multiple_blocks_removed(self):
        text = "wrong:\n```\nbad()\n```\ncorrect:\n```\ngood()\n```\ndo this"
        result = strip_code_blocks(text)
        assert "bad()" not in result
        assert "good()" not in result
        assert "do this" in result

    def test_inline_backticks_preserved(self):
        text = "use `fd` not `find` for file searches"
        assert strip_code_blocks(text) == text

    def test_language_annotated_block_removed(self):
        text = "stop using:\n```python\nimport os\n```\nuse pathlib"
        result = strip_code_blocks(text)
        assert "import os" not in result
        assert "use pathlib" in result

    def test_empty_string(self):
        assert strip_code_blocks("") == ""

    def test_unclosed_block_preserved(self):
        # Unclosed blocks should not eat the rest of the text
        text = "remember: use venv\n```\nsome code"
        result = strip_code_blocks(text)
        # With no closing ```, different implementations may handle this differently
        # but the key text before the block should survive
        assert "remember:" in result


class TestIsFalsePositive:
    """Tests for false positive phrase detection."""

    def test_no_problem(self):
        assert is_false_positive("no problem, thanks", []) is True

    def test_no_worries(self):
        assert is_false_positive("no worries about that", []) is True

    def test_dont_worry(self):
        assert is_false_positive("don't worry about it", []) is True

    def test_never_mind(self):
        assert is_false_positive("never mind, I figured it out", []) is True

    def test_dont_bother(self):
        assert is_false_positive("don't bother with that", []) is True

    def test_real_correction_not_false_positive(self):
        assert is_false_positive("no, that's wrong", []) is False

    def test_stop_command_not_false_positive(self):
        assert is_false_positive("stop refactoring unrelated code", []) is False

    def test_dont_instruction_not_false_positive(self):
        assert is_false_positive("don't use find, use fd", []) is False

    def test_no_need(self):
        assert is_false_positive("no need for that", []) is True

    def test_case_insensitive(self):
        assert is_false_positive("No Problem at all", []) is True


# ---------------------------------------------------------------------------
# T3.2 — CJK correction patterns
# ---------------------------------------------------------------------------

class TestCJKPatterns:
    """Tests for CJK (Chinese, Japanese, Korean) correction detection."""

    @pytest.mark.parametrize('prompt,description', [
        ("違う、そのアプローチではなく", "Japanese chigau - wrong"),
        ("そうじゃない、別の方法で", "Japanese souja-nai - not like that"),
        ("間違ってるよ、直して", "Japanese machigatte - it's wrong"),
        ("いや、そっちじゃない", "Japanese iya - no"),
        ("やめて！", "Japanese yamete - stop"),
    ])
    def test_japanese_correction_detected(self, prompt, description):
        result = detect_learning(prompt)
        assert result is not None, "Expected CJK match for: {}".format(description)
        assert result[2] >= 0.60

    @pytest.mark.parametrize('prompt,description', [
        ("不是，应该用另一种方法", "Chinese bushi - no"),
        ("错了，重新来", "Chinese cuole - wrong"),
        ("不要用find要用fd", "Chinese buyao-yao - don't X use Y"),
    ])
    def test_chinese_correction_detected(self, prompt, description):
        result = detect_learning(prompt)
        assert result is not None, "Expected CJK match for: {}".format(description)
        assert result[2] >= 0.60

    @pytest.mark.parametrize('prompt,description', [
        ("아니, 그게 아니라", "Korean ani - no"),
        ("틀렸어, 다시 해봐", "Korean teullyeoss - wrong"),
    ])
    def test_korean_correction_detected(self, prompt, description):
        result = detect_learning(prompt)
        assert result is not None, "Expected CJK match for: {}".format(description)
        assert result[2] >= 0.60

    def test_mixed_language_detected(self):
        result = detect_learning("no, 違う、use the other approach")
        assert result is not None

    def test_cjk_inside_code_block_no_match(self):
        text = "looks good\n```\n違う\n```\ncarry on"
        result = detect_learning(text)
        assert result is None


# ---------------------------------------------------------------------------
# T3.3 — calculate_confidence()
# ---------------------------------------------------------------------------

class TestCalculateConfidence:
    """Tests for confidence scoring adjustments."""

    def test_short_text_boost(self):
        # < 20 chars → +0.05 boost
        result = calculate_confidence(0.75, "no, use fd", 1)
        assert result == pytest.approx(0.80, abs=0.001)

    def test_long_text_penalty(self):
        # > 500 chars → -0.10 penalty
        long_text = "actually " + "x" * 500
        result = calculate_confidence(0.75, long_text, 1)
        assert result == pytest.approx(0.65, abs=0.001)

    def test_normal_length_no_adjustment(self):
        # 20-500 chars → no length adjustment
        text = "no, that's wrong. Use the other approach instead."
        result = calculate_confidence(0.75, text, 1)
        assert result == pytest.approx(0.75, abs=0.001)

    def test_multi_pattern_boost_two(self):
        # 2 patterns → +0.05
        result = calculate_confidence(0.75, "medium length text here", 2)
        assert result == pytest.approx(0.80, abs=0.001)

    def test_multi_pattern_boost_three(self):
        # 3 patterns → +0.10
        result = calculate_confidence(0.75, "medium length text here", 3)
        assert result == pytest.approx(0.85, abs=0.001)

    def test_cap_at_095(self):
        # Even with all boosts, never exceed 0.95
        result = calculate_confidence(0.90, "short", 5)
        assert result <= 0.95

    def test_single_pattern_no_multi_boost(self):
        # 1 pattern → no multi-pattern boost
        result = calculate_confidence(0.75, "medium length text here", 1)
        assert result == pytest.approx(0.75, abs=0.001)

    def test_combined_short_and_multi(self):
        # Short text + 2 patterns → +0.05 + 0.05 = +0.10
        result = calculate_confidence(0.70, "no, use fd", 2)
        assert result == pytest.approx(0.80, abs=0.001)


# ---------------------------------------------------------------------------
# T3.3 continued — minimum length gate
# ---------------------------------------------------------------------------

def test_detect_learning_minimum_length_gate():
    """Text shorter than 5 chars should return None regardless of content."""
    assert detect_learning("no") is None
    assert detect_learning("ok") is None
    assert detect_learning("   ") is None


def test_detect_learning_empty_string_still_none():
    """Empty string returns None (existing behavior, verify not broken)."""
    assert detect_learning("") is None


# ---------------------------------------------------------------------------
# T3.4 — Integration tests (full pipeline)
# ---------------------------------------------------------------------------

class TestDetectLearningPipeline:
    """Integration tests exercising the full 8-step pipeline."""

    def test_explicit_with_code_block_strips_block(self):
        """Code block stripped, but 'remember:' in real text still matches explicit."""
        text = "remember: use venv\n```\nsome code\n```"
        result = detect_learning(text)
        assert result is not None
        assert result[0] == 'explicit'

    def test_false_positive_no_problem_returns_none(self):
        """'no problem' triggers false positive filter → None."""
        result = detect_learning("no problem, that works great")
        assert result is None

    def test_false_positive_dont_worry_returns_none(self):
        """'don't worry about it' triggers false positive filter → None."""
        result = detect_learning("don't worry about it")
        assert result is None

    def test_cjk_correction_has_correct_confidence_range(self):
        """CJK correction yields confidence in expected range."""
        result = detect_learning("違う、そのアプローチではなく")
        assert result is not None
        assert 0.60 <= result[2] <= 0.95

    def test_multi_pattern_text_boosted_confidence(self):
        """Text matching multiple correction patterns gets boosted confidence."""
        # "no," matches ^no,?\s+ AND "actually" matches \bactually\b
        text = "no, actually that's wrong, use the other one"
        result = detect_learning(text)
        assert result is not None
        # Should be higher than base due to multi-pattern boost
        assert result[2] >= 0.75

    def test_correction_inside_code_block_only_returns_none(self):
        """If the only correction text is inside a code block, no match."""
        text = "here's an example:\n```\nno, don't use this\n```"
        result = detect_learning(text)
        assert result is None

    def test_guardrail_false_positive_not_filtered(self):
        """Guardrail patterns should NOT be filtered by false positive check."""
        text = "don't change unless I explicitly ask"
        result = detect_learning(text)
        assert result is not None
        assert result[0] == 'guardrail'

    def test_explicit_false_positive_not_filtered(self):
        """Explicit patterns should NOT be filtered by false positive check."""
        text = "remember: no problem with the current approach"
        result = detect_learning(text)
        assert result is not None
        assert result[0] == 'explicit'
