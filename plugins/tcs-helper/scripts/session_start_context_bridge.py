#!/usr/bin/env python3
"""SessionStart hook — restore context-bridge checkpoint after /clear or /compact.

Reads `.claude/.session-checkpoint.md` from the project root when SessionStart
fires with source=clear or source=compact, prints the contents to stdout (which
Claude Code injects as additional context for the new session), and renames the
file to `.session-checkpoint.consumed-<timestamp>.md` so it is not re-injected
on subsequent session starts.

Companion skill: tcs-helper:context-bridge (writes the checkpoint).
"""
import json
import os
import sys
from datetime import datetime


def main():
    try:
        try:
            data = json.loads(sys.stdin.read())
        except (json.JSONDecodeError, ValueError):
            data = {}

        source = data.get('source', '')
        if source not in ('clear', 'compact'):
            sys.exit(0)

        project_path = data.get('cwd', os.getcwd())
        checkpoint_path = os.path.join(
            project_path, '.claude', '.session-checkpoint.md'
        )
        if not os.path.exists(checkpoint_path):
            sys.exit(0)

        try:
            with open(checkpoint_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except OSError:
            sys.exit(0)

        print(
            f'**Restored from context-bridge checkpoint** '
            f'(written before /{source}). Use this to pick up where the '
            f'previous session left off when the user sends their next prompt; '
            f'do not act on it unprompted.\n\n'
            f'{content}'
        )

        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        consumed_path = os.path.join(
            project_path, '.claude',
            f'.session-checkpoint.consumed-{timestamp}.md',
        )
        try:
            os.rename(checkpoint_path, consumed_path)
        except OSError:
            pass

    except Exception:
        pass
    sys.exit(0)


if __name__ == '__main__':
    main()
