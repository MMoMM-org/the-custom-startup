#!/usr/bin/env python3
"""PostToolUse(Bash) hook — remind user to run /memory-add after git commit."""
import json
import sys


def main():
    try:
        data = json.loads(sys.stdin.read())
        command = data.get('tool_input', {}).get('command', '')

        if 'git commit' in command and '--amend' not in command:
            output = {
                'hookSpecificOutput': (
                    '💡 Committed! Any corrections or learnings from this session? '
                    'Run /memory-add to capture them.'
                )
            }
            print(json.dumps(output))
    except Exception:
        pass
    sys.exit(0)


if __name__ == '__main__':
    main()
