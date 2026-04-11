#!/usr/bin/env python3
"""PostToolUse(Bash) hook — remind user to run /memory-add after git commit,
and capture recurring tool errors to the learnings queue."""
import hashlib
import json
import os
import sys

# Add lib/ to path so reflect_utils is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib'))
from reflect_utils import create_queue_item, load_queue, save_queue  # noqa: E402


# Error patterns: (name, list-of-indicator-strings)
ERROR_PATTERNS = [
    ('module_not_found', ['ModuleNotFoundError', 'No module named']),
    ('connection_refused', ['Connection refused', 'ECONNREFUSED']),
    ('permission_denied', ['Permission denied', 'EACCES']),
    ('file_not_found', ['FileNotFoundError', 'No such file or directory']),
    ('syntax_error', ['SyntaxError', 'IndentationError']),
    ('type_error', ['TypeError', 'AttributeError']),
]

_ERROR_COUNTER_DEFAULT = os.path.expanduser('~/.claude/tcs-error-counts.json')


def _counter_path():
    override = os.environ.get('TCS_ERROR_COUNTER_OVERRIDE')
    return override if override else _ERROR_COUNTER_DEFAULT


def _queue_base():
    override = os.environ.get('TCS_QUEUE_OVERRIDE')
    return override if override else os.path.expanduser('~/.claude')


def _detect_error_pattern(tool_output):
    """Return the first matching error pattern name, or None."""
    for name, indicators in ERROR_PATTERNS:
        if any(indicator in tool_output for indicator in indicators):
            return name
    return None


def _error_key(pattern_name, tool_output):
    """Stable key for a (pattern, output-hash) pair."""
    text_hash = hashlib.sha256(tool_output.encode('utf-8')).hexdigest()[:16]
    return '{}:{}'.format(pattern_name, text_hash)


def _load_counters():
    path = _counter_path()
    try:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        pass
    return {}


def _save_counters(counters):
    path = _counter_path()
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(counters, f)
    except Exception:
        pass


def _increment_and_check(error_key):
    """Increment the counter for error_key. Return True when count reaches 2."""
    counters = _load_counters()
    counters[error_key] = counters.get(error_key, 0) + 1
    _save_counters(counters)
    return counters[error_key] >= 2


def _handle_git_commit(command):
    """Print hookSpecificOutput if command is a non-amend git commit."""
    if 'git commit' in command and '--amend' not in command:
        output = {
            'hookSpecificOutput': {
                'hookEventName': 'PostToolUse',
                'additionalContext': (
                    '💡 Committed! Any corrections or learnings from this session? '
                    'Run /memory-add to capture them.'
                ),
            }
        }
        print(json.dumps(output))


def _handle_tool_error(tool_output, project_path):
    """Queue a tool_error item if this error has been seen 2+ times."""
    pattern_name = _detect_error_pattern(tool_output)
    if not pattern_name:
        return

    key = _error_key(pattern_name, tool_output)
    if not _increment_and_check(key):
        return

    # Override queue base when TCS_QUEUE_OVERRIDE is set
    orig_claude_dir = None
    queue_base = os.environ.get('TCS_QUEUE_OVERRIDE')
    if queue_base:
        import reflect_utils
        orig_claude_dir = reflect_utils.CLAUDE_DIR
        reflect_utils.CLAUDE_DIR = queue_base

    try:
        queue = load_queue(project_path)
        item = create_queue_item(
            message=tool_output[:500],
            project=project_path,
            item_type='tool_error',
            patterns='tool_error',
            confidence=1.0,
            sentiment='error',
        )
        item['item_type'] = 'tool_error'
        item['error_pattern'] = pattern_name
        item['decay_days'] = 90
        queue.append(item)
        save_queue(project_path, queue)
    finally:
        if orig_claude_dir is not None:
            import reflect_utils
            reflect_utils.CLAUDE_DIR = orig_claude_dir


def main():
    try:
        data = json.loads(sys.stdin.read())
        command = data.get('tool_input', {}).get('command', '')
        tool_output = data.get('tool_output', '')
        project_path = data.get('cwd', os.getcwd())

        _handle_git_commit(command)

        if tool_output:
            _handle_tool_error(tool_output, project_path)

    except Exception:
        pass
    sys.exit(0)


if __name__ == '__main__':
    main()
