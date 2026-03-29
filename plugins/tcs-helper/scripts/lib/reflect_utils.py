"""Core utilities for tcs-helper memory scripts.
Based on claude-reflect's reflect_utils.py, extended with TCS category routing."""
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

CLAUDE_DIR = os.path.expanduser('~/.claude')


def encode_project_path(project_path: str) -> str:
    """Encode a project path to a safe directory name (matches claude-reflect encoding)."""
    # Claude Code replaces / with - and preserves the leading - (root / → -)
    encoded = project_path.replace('/', '-').replace(' ', '_')
    return encoded


def get_queue_path(project_path: str) -> str:
    """Get the learnings queue file path for a given project."""
    encoded = encode_project_path(project_path)
    projects_dir = os.path.join(CLAUDE_DIR, 'projects', encoded)
    os.makedirs(projects_dir, exist_ok=True)
    return os.path.join(projects_dir, 'learnings-queue.json')


def load_queue(project_path: str) -> list:
    """Load the learnings queue for a project. Returns [] if not found."""
    try:
        queue_path = get_queue_path(project_path)
        if not os.path.exists(queue_path):
            return []
        with open(queue_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_queue(project_path: str, queue: list) -> None:
    """Save the learnings queue for a project. Silently no-ops on I/O errors."""
    try:
        queue_path = get_queue_path(project_path)
        with open(queue_path, 'w', encoding='utf-8') as f:
            json.dump(queue, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def create_queue_item(
    message: str,
    project: str,
    item_type: str = 'auto',
    patterns: str = '',
    confidence: float = 0.75,
    sentiment: str = 'correction',
    tcs_category: str = None,
    tcs_target: str = None,
) -> dict:
    """Create a new queue item in the claude-reflect compatible format."""
    decay_days = 120 if item_type in ('explicit', 'guardrail') else 90
    if item_type in ('explicit', 'guardrail'):
        confidence = max(confidence, 0.90)
    # explicit items always have confidence 1.0
    if item_type == 'explicit':
        confidence = 1.0

    item = {
        'type': item_type,
        'message': message,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'project': project,
        'patterns': patterns or item_type,
        'confidence': confidence,
        'sentiment': sentiment,
        'decay_days': decay_days,
    }
    if tcs_category:
        item['tcs_category'] = tcs_category
    if tcs_target:
        item['tcs_target'] = tcs_target
    return item


# Pattern detection (regex-based, same priority as claude-reflect)
EXPLICIT_PATTERN = re.compile(r'\bremember\s*:', re.IGNORECASE)
GUARDRAIL_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"don'?t\s+\w+\s+unless", r"only\s+change\s+what\s+I\s+asked",
        r"stop\s+(refactoring|changing|modifying)\s+unrelated",
        r"leave\s+\w+\s+alone", r"minimal\s+changes",
    ]
]
POSITIVE_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"perfect!?", r"exactly\s+right", r"great\s+approach", r"nailed\s+it",
        r"that'?s\s+(exactly|correct|right)",
    ]
]
CORRECTION_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"^no,?\s+", r"\bdon'?t\b", r"\bstop\b", r"that'?s\s+wrong",
        r"\bactually\b", r"use\s+\w+\s+not\s+\w+",
        r"\bi\s+meant\b", r"\bi\s+told\s+you\b",
    ]
]
MAX_CAPTURE_LENGTH = 2000  # skip very long prompts unless they contain "remember:"

# CJK correction patterns — ported from claude-reflect v3.1.0
# Each tuple: (regex, name, is_correction)
CJK_CORRECTION_PATTERNS = [
    # Japanese
    (re.compile(r"^いや[、,.\s]|^いや違", re.UNICODE), "iya", 0.75),
    (re.compile(r"^違う[、，,.\s！!。]|^ちがう[、,.\s]", re.UNICODE), "chigau", 0.75),
    (re.compile(r"そうじゃなく[てけ]|そっちじゃなく[てけ]", re.UNICODE), "souja-nakute", 0.75),
    (re.compile(r"間違[いえっ]て", re.UNICODE), "machigatte", 0.75),
    (re.compile(r"じゃなくて.{0,30}にして", re.UNICODE), "janakute-nishite", 0.75),
    (re.compile(r"^やめて[。！!]?\s*$", re.UNICODE), "yamete", 0.75),
    (re.compile(r"^そうじゃない", re.UNICODE), "souja-nai", 0.75),
    (re.compile(r"って言った[のよでじゃ]", re.UNICODE), "tte-itta", 0.75),
    # Chinese
    (re.compile(r"^不是[，,. ]", re.UNICODE), "bushi", 0.75),
    (re.compile(r"^错了|^錯了", re.UNICODE), "cuole", 0.75),
    (re.compile(r"不要.{0,20}要", re.UNICODE), "buyao-yao", 0.75),
    # Korean
    (re.compile(r"^아니[,. ]", re.UNICODE), "ani", 0.75),
    (re.compile(r"틀렸", re.UNICODE), "teullyeoss", 0.75),
]

# Non-correction phrases that superficially match correction patterns
NON_CORRECTION_PHRASES = [
    re.compile(p, re.IGNORECASE) for p in [
        r"^no\s+problem",
        r"^no\s+worries",
        r"^no\s+need\b",
        r"^no\s+way\b",
        r"^don't\s+worry",
        r"^don't\s+mind",
        r"^don't\s+bother",
        r"^never\s+mind",
        r"^stop\s+worrying",
    ]
]

# False positive patterns — text that looks like corrections but isn't
FALSE_POSITIVE_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"[?\uff1f]$",
        r"^(please|can you|could you|would you|help me)\b",
        r"^I (need|want|would like)\b",
        r"^(ok|okay|alright)[,.]?\s+(so|now|let)",
    ]
]


def _effective_length(text):
    """Return effective length, counting CJK characters as 2 (they carry more meaning)."""
    count = 0
    for ch in text:
        cp = ord(ch)
        # CJK Unified Ideographs, Hiragana, Katakana, Hangul Syllables
        if (0x4E00 <= cp <= 0x9FFF or 0x3040 <= cp <= 0x309F
                or 0x30A0 <= cp <= 0x30FF or 0xAC00 <= cp <= 0xD7AF
                or 0xFF01 <= cp <= 0xFF60):
            count += 2
        else:
            count += 1
    return count


def strip_code_blocks(text):
    """Remove triple-backtick delimited code blocks from text before pattern matching.

    Preserves inline backtick-enclosed text (single backticks).
    Unclosed blocks are removed from the opening fence onward.
    """
    # Match ``` with optional language tag through closing ```
    result = re.sub(r'```[^\n]*\n.*?```', '', text, flags=re.DOTALL)
    # Handle unclosed code blocks — remove from opening fence to end
    result = re.sub(r'```[^\n]*\n.*$', '', result, flags=re.DOTALL)
    return result


def is_false_positive(text, matched_patterns):
    """Check if text is a non-correction phrase that superficially matches patterns.

    Returns True if the text is a false positive (should NOT be treated as a learning).
    """
    stripped = text.strip()
    for pattern in NON_CORRECTION_PHRASES:
        if pattern.search(stripped):
            return True
    for pattern in FALSE_POSITIVE_PATTERNS:
        if pattern.search(stripped):
            return True
    return False


def calculate_confidence(base, text, pattern_count):
    """Adjust confidence based on text length, pattern count, and context.

    Rules:
    - Short text (< 20 chars): +0.05 boost (corrections are often terse)
    - Long text (> 500 chars): -0.10 penalty (likely not a focused correction)
    - Multiple patterns: +0.05 per extra match (cap 0.95)
    """
    confidence = base

    text_len = len(text.strip())
    if text_len < 20:
        confidence += 0.05
    elif text_len > 500:
        confidence -= 0.10

    if pattern_count > 1:
        confidence += 0.05 * (pattern_count - 1)

    return min(confidence, 0.95)


def _count_matches(text, patterns):
    """Count how many patterns match the given text."""
    count = 0
    for pattern in patterns:
        if pattern.search(text):
            count += 1
    return count


def _count_cjk_matches(text):
    """Count how many CJK patterns match the given text."""
    count = 0
    for pattern, _name, _conf in CJK_CORRECTION_PATTERNS:
        if pattern.search(text):
            count += 1
    return count


def detect_learning(prompt):
    """Detect if a prompt contains a learning. Returns (type, patterns, confidence) or None.

    8-step pipeline:
    1. Minimum length gate (< 5 chars → None)
    2. Strip code blocks
    3. Check explicit patterns (highest priority)
    4. Check guardrail patterns
    5. Check correction patterns (English + CJK)
    6. Check positive patterns
    7. False positive filter (correction/positive only)
    8. Confidence adjustment
    """
    # Step 1: Minimum length gate (CJK chars count as 2)
    if _effective_length(prompt.strip()) < 5:
        return None

    # Length gate for very long prompts (preserve existing behavior)
    if len(prompt) > MAX_CAPTURE_LENGTH and not EXPLICIT_PATTERN.search(prompt):
        return None

    # Step 2: Strip code blocks
    clean_text = strip_code_blocks(prompt)

    # Step 3: Explicit patterns — highest priority, no false-positive filtering
    if EXPLICIT_PATTERN.search(clean_text):
        return ('explicit', 'explicit', 1.0)

    # Step 4: Guardrail patterns — high priority, no false-positive filtering
    for pattern in GUARDRAIL_PATTERNS:
        if pattern.search(clean_text):
            return ('guardrail', 'guardrail', 0.85)

    # Step 5: Correction patterns (English)
    english_correction = False
    for pattern in CORRECTION_PATTERNS:
        if pattern.search(clean_text):
            english_correction = True
            break

    # Step 5b: CJK correction patterns
    cjk_correction = False
    for pattern, _name, _conf in CJK_CORRECTION_PATTERNS:
        if pattern.search(clean_text):
            cjk_correction = True
            break

    # Step 6: Positive patterns
    positive_match = False
    for pattern in POSITIVE_PATTERNS:
        if pattern.search(clean_text):
            positive_match = True
            break

    # Determine best match by priority: positive > correction (preserves existing order)
    if positive_match:
        # Step 7: False positive filter
        if is_false_positive(clean_text, []):
            return None
        pattern_count = _count_matches(clean_text, POSITIVE_PATTERNS)
        # Step 8: Confidence adjustment
        confidence = calculate_confidence(0.70, clean_text, pattern_count)
        return ('positive', 'positive', confidence)

    if english_correction or cjk_correction:
        # Step 7: False positive filter
        if is_false_positive(clean_text, []):
            return None
        # Count total correction matches for confidence boost
        pattern_count = (
            _count_matches(clean_text, CORRECTION_PATTERNS)
            + _count_cjk_matches(clean_text)
        )
        base = 0.75
        # Step 8: Confidence adjustment
        confidence = calculate_confidence(base, clean_text, pattern_count)
        return ('auto', 'correction', confidence)

    return None
