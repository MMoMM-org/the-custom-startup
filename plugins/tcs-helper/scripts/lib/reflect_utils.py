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
    # Claude Code uses URL-encoding style: replace / with - and other special chars
    encoded = project_path.replace('/', '-').replace(' ', '_').lstrip('-')
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
    """Save the learnings queue for a project."""
    queue_path = get_queue_path(project_path)
    with open(queue_path, 'w', encoding='utf-8') as f:
        json.dump(queue, f, indent=2, ensure_ascii=False)


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


def detect_learning(prompt: str) -> tuple:
    """Detect if a prompt contains a learning. Returns (type, patterns, confidence) or None."""
    if len(prompt) > MAX_CAPTURE_LENGTH and not EXPLICIT_PATTERN.search(prompt):
        return None

    if EXPLICIT_PATTERN.search(prompt):
        return ('explicit', 'explicit', 1.0)

    for pattern in GUARDRAIL_PATTERNS:
        if pattern.search(prompt):
            return ('guardrail', 'guardrail', 0.85)

    for pattern in POSITIVE_PATTERNS:
        if pattern.search(prompt):
            return ('positive', 'positive', 0.70)

    for pattern in CORRECTION_PATTERNS:
        if pattern.search(prompt):
            return ('auto', 'correction', 0.75)

    return None
