#!/usr/bin/env python3
"""UserPromptSubmit hook — detect recurrence signals and suggest /enforce-rule.

Mirrors capture_learning.py structure: stdin JSON, try/except all errors, exit 0 always.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib.trigger_phrases import load, match


def _phrases_path() -> str:
    """Resolve trigger-phrases.md relative to the plugin root.

    At runtime CLAUDE_PLUGIN_ROOT is set by Claude Code.
    For local dev/tests, fall back to __file__-relative path.
    """
    plugin_root = os.environ.get('CLAUDE_PLUGIN_ROOT', '')
    if plugin_root:
        return os.path.join(plugin_root, 'skills', 'rule-enforcer', 'reference', 'trigger-phrases.md')
    # Derive from __file__: scripts/ → skills/rule-enforcer/reference/
    scripts_dir = os.path.dirname(os.path.abspath(__file__))
    plugin_dir = os.path.dirname(scripts_dir)
    return os.path.join(plugin_dir, 'skills', 'rule-enforcer', 'reference', 'trigger-phrases.md')


def _find_matched_phrase(text: str, patterns: list) -> str:
    """Return the matched phrase snippet from the first matching pattern."""
    for pattern in patterns:
        try:
            m = pattern.search(text)
            if m:
                return m.group()
        except Exception:
            continue
    return ''


def _compute_suggestion(stdin_text: str) -> str | None:
    """Parse stdin and return suggestion string, or None if no action needed."""
    data = json.loads(stdin_text)
    prompt = data.get('prompt', '')
    if not prompt:
        return None

    patterns = load(_phrases_path())
    if not match(prompt, patterns):
        return None

    snippet = _find_matched_phrase(prompt, patterns)
    return (
        f"[rule-enforcer] Recurrence signal detected ('{snippet}'). "
        f'Consider /enforce-rule "<rule>" to triage.'
    )


def main():
    suggestion = None
    try:
        suggestion = _compute_suggestion(sys.stdin.read())
    except Exception:
        pass  # never block

    if suggestion:
        print(suggestion)
    sys.exit(0)


if __name__ == '__main__':
    main()
