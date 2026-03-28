#!/usr/bin/env python3
"""
extract_session_learnings.py — reads .jsonl session files and extracts user messages.

Usage (from SKILL.md bash blocks):
  python3 extract_session_learnings.py <project_path> [--days N]

Outputs one user message per line to stdout.
Always exits 0.
"""
import json
import os
import sys
import time


def extract_user_messages(jsonl_path: str) -> list:
    """Extract user-role message content from a single .jsonl file."""
    messages = []
    try:
        with open(jsonl_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if obj.get('type') == 'message' and obj.get('role') == 'user':
                        content = obj.get('content', '')
                        if isinstance(content, str) and content.strip():
                            messages.append(content.strip())
                        elif isinstance(content, list):
                            # Handle multi-part content blocks
                            for block in content:
                                if isinstance(block, dict) and block.get('type') == 'text':
                                    text = block.get('text', '').strip()
                                    if text:
                                        messages.append(text)
                except (json.JSONDecodeError, KeyError):
                    continue
    except (IOError, OSError):
        pass
    return messages


def extract_from_project(sessions_dir: str, days: int = 14) -> list:
    """Extract user messages from all .jsonl files in sessions_dir modified within `days`."""
    cutoff = time.time() - (days * 86400)
    messages = []
    try:
        for fname in os.listdir(sessions_dir):
            if not fname.endswith('.jsonl'):
                continue
            fpath = os.path.join(sessions_dir, fname)
            try:
                if os.path.getmtime(fpath) < cutoff:
                    continue
            except OSError:
                continue
            messages.extend(extract_user_messages(fpath))
    except (IOError, OSError):
        pass
    return messages


def main():
    if len(sys.argv) < 2:
        sys.exit(0)

    project_path = sys.argv[1]
    days = 14
    if '--days' in sys.argv:
        try:
            days = int(sys.argv[sys.argv.index('--days') + 1])
        except (ValueError, IndexError):
            pass

    # Resolve sessions dir: ~/.claude/projects/<encoded>/
    sys.path.insert(0, os.path.dirname(__file__))
    from lib.reflect_utils import get_queue_path
    queue_path = get_queue_path(project_path)
    sessions_dir = os.path.dirname(queue_path)

    messages = extract_from_project(sessions_dir, days=days)
    for msg in messages:
        # Output each message on its own line, truncated to 200 chars for readability
        print(msg[:200])

    sys.exit(0)


if __name__ == '__main__':
    main()
