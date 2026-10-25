#!/usr/bin/env python3
"""PostToolUse(Write|Edit|MultiEdit) hook — ADR-4 layer 1: when a skill or
agent definition is written, point at the authoring skill that audits it.

Shipped in the plugin rather than in ~/.claude: a hook in a home directory
reaches only that home, so a per-repo container never saw it."""
import json
import re
import sys

SKILL_FILE = re.compile(r'(^|/)SKILL\.md$')
AGENT_FILE = re.compile(r'(^|/)agents/(.+/)?[^/]+\.md$')

SKILL_REMINDER = (
    'This wrote a skill definition. Before committing, audit it with '
    '/tcs-helper:skill-author.'
)
AGENT_REMINDER = (
    'This wrote an agent definition. Before committing, audit it with '
    '/tcs-helper:agent-author.'
)


def reminder_for(path):
    if SKILL_FILE.search(path):
        return SKILL_REMINDER
    if AGENT_FILE.search(path) and not path.endswith('/README.md'):
        return AGENT_REMINDER
    return None


def main():
    try:
        data = json.loads(sys.stdin.read())
        path = (data.get('tool_input') or {}).get('file_path') or ''
        text = reminder_for(path)
        if text:
            output = {
                'hookSpecificOutput': {
                    'hookEventName': 'PostToolUse',
                    'additionalContext': text,
                }
            }
            print(json.dumps(output))  # json-ascii: machine-read
    except Exception:
        pass
    sys.exit(0)


if __name__ == '__main__':
    main()
