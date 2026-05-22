"""Trigger-phrase loader and matcher for the rule-enforcer intercept hook.

Public API:
    load(path: str) -> list[re.Pattern]
    match(text: str, patterns: list[re.Pattern]) -> bool

The markdown format (ADR-5):
    ## <Language>
    ```
    pattern1
    pattern2
    ```

Patterns inside each code fence are compiled with re.IGNORECASE.
load() returns [] (never raises) on missing or malformed files — CON-4.
"""
import re
from pathlib import Path


def load(path: str) -> list:
    """Load compiled regex patterns from a trigger-phrases markdown file.

    Extracts all code-fenced blocks that follow a ## heading.
    Returns a flat list of compiled patterns across all language sections.
    Returns [] if the file is missing, unreadable, or contains no fenced blocks.
    """
    try:
        text = Path(path).read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError):
        return []

    return _parse_patterns(text)


def match(text: str, patterns: list) -> bool:
    """Return True if any pattern matches text (case-insensitive).

    Returns False when patterns is empty or text is empty.
    Never raises.
    """
    if not text or not patterns:
        return False
    for pattern in patterns:
        try:
            if pattern.search(text):
                return True
        except Exception:
            continue
    return False


def _parse_patterns(text: str) -> list:
    """Extract compiled regex patterns from markdown code fences under ## headings.

    Only code fences that appear after a ## heading are collected.
    Lines inside a fence that are empty or whitespace-only are skipped.
    Invalid regex lines are silently skipped.
    """
    patterns = []
    in_fence = False
    after_heading = False

    for line in text.splitlines():
        stripped = line.strip()

        if stripped.startswith('## '):
            after_heading = True
            in_fence = False
            continue

        if stripped.startswith('```'):
            if after_heading and not in_fence:
                in_fence = True
                after_heading = False
            elif in_fence:
                in_fence = False
            continue

        if in_fence and stripped:
            try:
                patterns.append(re.compile(stripped, re.IGNORECASE))
            except re.error:
                pass

    return patterns
