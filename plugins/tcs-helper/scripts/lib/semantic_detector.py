"""Semantic validation and contradiction detection using the claude CLI.

All functions degrade gracefully when the claude CLI is unavailable — callers
receive None or empty lists rather than exceptions.

Python 3.8 compatible: no walrus operator, no match statement.
"""
import json
import os
import re
import subprocess
from typing import List, Optional, Tuple

_REQUIRED_FIELDS = {'is_learning', 'type', 'confidence', 'reasoning', 'extracted_learning'}

_NEGATION_INDICATORS = {'don\'t', 'never', 'avoid', 'not', 'stop', 'dont'}
_AFFIRMATION_INDICATORS = {'always', 'prefer', 'must', 'should'}

_STOPWORDS = frozenset([
    'the', 'a', 'an', 'is', 'are', 'was', 'were', 'to', 'of', 'in', 'for',
    'on', 'with', 'at', 'by', 'it', 'this', 'that', 'i', 'and', 'or',
])


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _is_disabled():
    # type: () -> bool
    """Return True when TCS_SEMANTIC_VALIDATION env var is explicitly 'false'."""
    return os.environ.get('TCS_SEMANTIC_VALIDATION', '').lower() == 'false'


def _tokenize(text):
    # type: (str) -> set
    """Lowercase, strip punctuation, split, remove stopwords."""
    normalized = re.sub(r'[^\w\s]', ' ', text.lower())
    return set(w for w in normalized.split() if w and w not in _STOPWORDS)


def _sentiment(tokens):
    # type: (set) -> str
    """Return 'negative', 'positive', or 'neutral' based on indicator overlap."""
    neg = tokens & _NEGATION_INDICATORS
    pos = tokens & _AFFIRMATION_INDICATORS
    if len(neg) > len(pos):
        return 'negative'
    if len(pos) > len(neg):
        return 'positive'
    return 'neutral'


def _keyword_contradiction(new_text, entry_text):
    # type: (str, str) -> Optional[str]
    """Check for keyword-based contradiction between two entries.

    Returns a reason string if >60% keyword overlap AND opposite sentiment,
    otherwise returns None.
    """
    new_tokens = _tokenize(new_text)
    entry_tokens = _tokenize(entry_text)

    if not new_tokens or not entry_tokens:
        return None

    overlap = new_tokens & entry_tokens
    union = new_tokens | entry_tokens
    jaccard = len(overlap) / len(union)

    if jaccard < 0.6:
        return None

    new_sentiment = _sentiment(new_tokens)
    entry_sentiment = _sentiment(entry_tokens)

    opposites = (
        (new_sentiment == 'positive' and entry_sentiment == 'negative')
        or (new_sentiment == 'negative' and entry_sentiment == 'positive')
    )
    if opposites:
        return 'keyword overlap {:.0%} with opposite sentiment ({} vs {})'.format(
            jaccard, new_sentiment, entry_sentiment
        )
    return None


def _claude_contradiction(new_text, entry_text):
    # type: (str, str) -> Optional[str]
    """Ask the claude CLI whether two entries contradict each other.

    Returns a reason string on contradiction, None otherwise or on any error.
    """
    prompt = (
        'Do these two entries contradict each other? '
        'Answer with just "yes" or "no" and a one-line reason.\n'
        'Entry A: {}\nEntry B: {}'.format(new_text, entry_text)
    )
    try:
        result = subprocess.run(
            ['claude', '-p', prompt],
            capture_output=True,
            text=True,
            timeout=5,
        )
        answer = result.stdout.strip().lower()
        if answer.startswith('yes'):
            return result.stdout.strip()
        return None
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def semantic_analyze(text, model='sonnet'):
    # type: (str, str) -> Optional[dict]
    """Call claude -p to classify whether text is a learning worth remembering.

    Returns a dict with keys: is_learning, type, confidence, reasoning,
    extracted_learning.  Returns None on any error or when disabled.
    """
    if _is_disabled():
        return None

    prompt = (
        'Analyze this text from a coding session. '
        'Is it a user correction, preference, or instruction that should be remembered?\n'
        'Text: "{}"\n'
        'Reply with JSON only, no markdown fences: '
        '{{"is_learning": bool, "type": "correction"|"preference"|"instruction"|"none", '
        '"confidence": 0.0-1.0, "reasoning": "one line", '
        '"extracted_learning": "the key insight"}}'
    ).format(text)

    try:
        result = subprocess.run(
            ['claude', '-p', '--output-format', 'json', '--model', model, prompt],
            capture_output=True,
            text=True,
            timeout=5,
        )
        raw = result.stdout.strip()
        if not raw:
            return None
        parsed = json.loads(raw)
    except (FileNotFoundError, OSError):
        return None
    except subprocess.TimeoutExpired:
        return None
    except (json.JSONDecodeError, ValueError):
        return None

    if not isinstance(parsed, dict):
        return None
    if not _REQUIRED_FIELDS.issubset(parsed.keys()):
        return None
    return parsed


def validate_queue_items(items, model='sonnet'):
    # type: (list, str) -> list
    """Batch validate queue items, filtering false positives and merging confidence.

    Items with confidence >= 0.7 pass through unchanged.
    Items with confidence < 0.7 are checked via semantic_analyze():
      - is_learning=False  → removed from list
      - is_learning=True   → confidence updated to average of regex + semantic
      - analyze returns None → item kept with original confidence
    """
    validated = []
    for item in items:
        if item.get('confidence', 0.0) >= 0.7:
            validated.append(item)
            continue

        analysis = semantic_analyze(item.get('message', ''), model=model)

        if analysis is None:
            validated.append(item)
            continue

        if not analysis.get('is_learning', False):
            continue  # filter out

        regex_confidence = item.get('confidence', 0.0)
        semantic_confidence = analysis.get('confidence', 0.0)
        merged = (regex_confidence + semantic_confidence) / 2.0

        updated = dict(item)
        updated['confidence'] = merged
        validated.append(updated)

    return validated


def detect_contradictions(new_learning, existing_entries):
    # type: (str, list) -> List[Tuple[str, str]]
    """Find entries in existing_entries that contradict new_learning.

    Uses the claude CLI when available, falls back to keyword-based detection.
    Returns a list of (entry_text, contradiction_reason) tuples.
    """
    if not existing_entries:
        return []

    results = []
    for entry in existing_entries:
        reason = _claude_contradiction(new_learning, entry)
        if reason is None:
            reason = _keyword_contradiction(new_learning, entry)
        if reason is not None:
            results.append((entry, reason))

    return results
