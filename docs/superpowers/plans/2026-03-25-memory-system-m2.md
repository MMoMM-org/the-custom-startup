# Memory System (M2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the tcs-helper memory system — Python hook infrastructure, `/memory-add` skill, four maintenance skills, and a setup onboarding command.

**Architecture:** Python hook scripts (based on claude-reflect) passively capture learnings during sessions and queue them at `~/.claude/projects/<encoded>/learnings-queue.json`. The `/memory-add` skill processes the queue and routes each learning to the correct scope (global/project/repo) and category file under `docs/ai/memory/`. Three maintenance skills (memory-sync, memory-cleanup, memory-promote) keep the bank lean. The setup skill provisions the full structure in one command and installs all hooks.

**Tech Stack:** Python 3.x (scripts/hooks), Markdown (SKILL.md, templates), JSON (queue + hooks.json), pytest (Python tests)

**Spec:** `docs/XDD/specs/001-memory-claude/` — read solution.md §3–4 before any phase.

---

## File Map

### Created (new):
```
plugins/tcs-helper/
├── hooks/
│   └── hooks.json
├── scripts/
│   ├── lib/
│   │   ├── __init__.py
│   │   └── reflect_utils.py        ← queue I/O, path utils, pattern detection
│   ├── capture_learning.py          ← UserPromptSubmit hook
│   ├── session_start_reminder.py    ← SessionStart hook
│   ├── check_learnings.py           ← PreCompact hook
│   ├── post_commit_reminder.py      ← PostToolUse(Bash) hook
│   ├── merge_hooks.py               ← standalone hook installer utility
│   └── extract_session_learnings.py ← reads .jsonl session files for memory-promote
├── templates/
│   ├── claude-root.md
│   ├── claude-src.md
│   ├── claude-test.md
│   ├── claude-docs.md
│   ├── claude-ai.md
│   ├── memory-index.md
│   ├── memory-general.md
│   ├── memory-tools.md
│   ├── memory-domain.md
│   ├── memory-decisions.md
│   ├── memory-context.md
│   ├── memory-troubleshooting.md
│   ├── routing-reference.md
│   └── stacks/
│       ├── typescript.md
│       ├── go.md
│       ├── python.md
│       ├── cloudflare.md
│       ├── convex.md
│       └── generic.md
└── skills/
    ├── memory-add/
    │   ├── SKILL.md
    │   ├── reference/routing-rules.md
    │   ├── reference/category-formats.md
    │   └── examples/output-example.md
    ├── memory-sync/
    │   ├── SKILL.md
    │   └── examples/output-example.md
    ├── memory-cleanup/
    │   └── SKILL.md
    ├── memory-promote/
    │   └── SKILL.md
    └── setup/
        └── SKILL.md

tests/tcs-helper/
├── test_reflect_utils.py
├── test_capture_learning.py
├── test_session_start_reminder.py
├── test_merge_hooks.py
└── test_extract_session_learnings.py
```

### Modified:
```
plugins/tcs-helper/.claude-plugin/plugin.json   ← add hooks + skills registry
```

---

## Task 1: Core Library — `reflect_utils.py`

**Files:**
- Create: `plugins/tcs-helper/scripts/lib/__init__.py`
- Create: `plugins/tcs-helper/scripts/lib/reflect_utils.py`
- Test: `tests/tcs-helper/test_reflect_utils.py`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p plugins/tcs-helper/scripts/lib
mkdir -p tests/tcs-helper
touch plugins/tcs-helper/scripts/__init__.py
touch plugins/tcs-helper/scripts/lib/__init__.py
touch tests/tcs-helper/__init__.py
```

- [ ] **Step 2: Write failing tests**

Create `tests/tcs-helper/test_reflect_utils.py`:

```python
"""Tests for reflect_utils.py — queue I/O and path utilities."""
import json
import os
import sys
import tempfile
import pytest
from unittest.mock import patch

# Add scripts to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../plugins/tcs-helper/scripts'))
from lib.reflect_utils import (
    get_queue_path, load_queue, save_queue, create_queue_item, encode_project_path
)


def test_encode_project_path_replaces_slashes():
    result = encode_project_path('/home/user/myproject')
    assert '/' not in result
    assert '-' in result or '_' in result


def test_get_queue_path_returns_project_specific_path(tmp_path):
    with patch('lib.reflect_utils.CLAUDE_DIR', str(tmp_path)):
        path = get_queue_path('/home/user/myproject')
    assert 'learnings-queue.json' in path
    assert 'projects' in path


def test_load_queue_returns_empty_list_when_file_missing(tmp_path):
    with patch('lib.reflect_utils.CLAUDE_DIR', str(tmp_path)):
        queue = load_queue('/nonexistent/project')
    assert queue == []


def test_save_and_load_queue_roundtrip(tmp_path):
    item = {'type': 'explicit', 'message': 'test', 'timestamp': '2026-01-01T00:00:00+00:00',
            'project': '/test/proj', 'patterns': 'explicit', 'confidence': 1.0,
            'sentiment': 'correction', 'decay_days': 120}
    with patch('lib.reflect_utils.CLAUDE_DIR', str(tmp_path)):
        save_queue('/test/proj', [item])
        result = load_queue('/test/proj')
    assert len(result) == 1
    assert result[0]['message'] == 'test'


def test_create_queue_item_has_required_fields():
    item = create_queue_item(
        message='use fd not find',
        project='/test/proj',
        item_type='explicit'
    )
    required = ['type', 'message', 'timestamp', 'project', 'patterns', 'confidence',
                'sentiment', 'decay_days']
    for field in required:
        assert field in item, f'Missing field: {field}'


def test_create_queue_item_explicit_has_high_confidence():
    item = create_queue_item('remember: always use fd', '/test/proj', 'explicit')
    assert item['confidence'] == 1.0
    assert item['decay_days'] == 120


def test_create_queue_item_with_tcs_extensions():
    item = create_queue_item(
        'use fd not find', '/test/proj', 'explicit',
        tcs_category='tools', tcs_target='docs/ai/memory/tools.md'
    )
    assert item['tcs_category'] == 'tools'
    assert item['tcs_target'] == 'docs/ai/memory/tools.md'
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
cd /Volumes/Moon/Coding/the-custom-startup
python -m pytest tests/tcs-helper/test_reflect_utils.py -v 2>&1 | head -30
```

Expected: `ModuleNotFoundError: No module named 'lib.reflect_utils'`

- [ ] **Step 4: Implement `reflect_utils.py`**

Create `plugins/tcs-helper/scripts/lib/reflect_utils.py`:

```python
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
```

- [ ] **Step 5: Run tests — expect pass**

```bash
python -m pytest tests/tcs-helper/test_reflect_utils.py -v
```

Expected: All 7 tests PASS

- [ ] **Step 6: Commit**

```bash
git add plugins/tcs-helper/scripts/ tests/tcs-helper/
git commit -m "feat(memory): add reflect_utils.py — queue I/O and pattern detection"
```

---

## Task 2: Hook Scripts

**Files:**
- Create: `plugins/tcs-helper/scripts/capture_learning.py`
- Create: `plugins/tcs-helper/scripts/session_start_reminder.py`
- Create: `plugins/tcs-helper/scripts/check_learnings.py`
- Create: `plugins/tcs-helper/scripts/post_commit_reminder.py`
- Test: `tests/tcs-helper/test_capture_learning.py`
- Test: `tests/tcs-helper/test_session_start_reminder.py`

- [ ] **Step 1: Write failing tests for `capture_learning.py`**

Create `tests/tcs-helper/test_capture_learning.py`:

```python
"""Tests for the UserPromptSubmit hook."""
import json
import os
import sys
import subprocess
import tempfile
import pytest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../plugins/tcs-helper/scripts'))


def run_hook(prompt_text, project_path, queue_path_override=None):
    """Run capture_learning.py with given stdin."""
    env = os.environ.copy()
    if queue_path_override:
        env['TCS_QUEUE_OVERRIDE'] = queue_path_override
    stdin_data = json.dumps({'prompt': prompt_text})
    script = os.path.join(os.path.dirname(__file__),
                          '../../plugins/tcs-helper/scripts/capture_learning.py')
    result = subprocess.run(
        [sys.executable, script, project_path],
        input=stdin_data.encode(),
        capture_output=True,
        env=env
    )
    return result


def test_correction_prompt_is_queued(tmp_path):
    queue_file = tmp_path / 'queue.json'
    result = run_hook('no, use fd not find', '/test/proj',
                      queue_path_override=str(queue_file))
    assert result.returncode == 0
    queue = json.loads(queue_file.read_text())
    assert len(queue) == 1
    assert queue[0]['message'] == 'no, use fd not find'
    assert queue[0]['type'] == 'auto'


def test_explicit_remember_is_queued(tmp_path):
    queue_file = tmp_path / 'queue.json'
    result = run_hook('remember: always use fd not find', '/test/proj',
                      queue_path_override=str(queue_file))
    assert result.returncode == 0
    queue = json.loads(queue_file.read_text())
    assert len(queue) == 1
    assert queue[0]['type'] == 'explicit'
    assert queue[0]['confidence'] == 1.0


def test_neutral_prompt_is_not_queued(tmp_path):
    queue_file = tmp_path / 'queue.json'
    result = run_hook('can you help me write a function?', '/test/proj',
                      queue_path_override=str(queue_file))
    assert result.returncode == 0
    assert not queue_file.exists() or json.loads(queue_file.read_text()) == []


def test_hook_always_exits_zero_on_error():
    result = run_hook('anything', '/nonexistent/path/that/causes/errors')
    assert result.returncode == 0
```

- [ ] **Step 2: Write failing tests for `session_start_reminder.py`**

Create `tests/tcs-helper/test_session_start_reminder.py`:

```python
"""Tests for the SessionStart hook."""
import json
import os
import sys
import subprocess
import tempfile
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../plugins/tcs-helper/scripts'))


def run_reminder(queue_items=None, yolo_review_exists=False, project_path='/test/proj'):
    script = os.path.join(os.path.dirname(__file__),
                          '../../plugins/tcs-helper/scripts/session_start_reminder.py')
    with tempfile.TemporaryDirectory() as tmp:
        queue_file = os.path.join(tmp, 'queue.json')
        with open(queue_file, 'w') as f:
            json.dump(queue_items or [], f)
        env = os.environ.copy()
        env['TCS_QUEUE_OVERRIDE'] = queue_file
        if yolo_review_exists:
            env['TCS_YOLO_REVIEW_PATH'] = os.path.join(tmp, 'yolo-review.md')
            with open(env['TCS_YOLO_REVIEW_PATH'], 'w') as f:
                f.write('- [ ] **Target:** `docs/ai/memory/tools.md`\n  Test entry\n')
        result = subprocess.run(
            [sys.executable, script, project_path],
            capture_output=True, text=True, env=env
        )
    return result


def test_no_output_when_queue_empty():
    result = run_reminder(queue_items=[])
    assert result.returncode == 0
    assert result.stdout.strip() == ''


def test_shows_count_when_queue_has_items():
    items = [{'type': 'auto', 'message': 'use fd', 'timestamp': '2026-01-01T00:00:00+00:00',
               'project': '/test', 'patterns': 'auto', 'confidence': 0.75,
               'sentiment': 'correction', 'decay_days': 90}]
    result = run_reminder(queue_items=items)
    assert '1' in result.stdout
    assert 'memory-add' in result.stdout.lower() or 'reflect' in result.stdout.lower()


def test_shows_yolo_warning_when_review_file_exists():
    result = run_reminder(yolo_review_exists=True)
    assert 'yolo' in result.stdout.lower() or 'review' in result.stdout.lower()
    assert 'memory-add' in result.stdout.lower()
```

- [ ] **Step 3: Run tests — expect fail**

```bash
python -m pytest tests/tcs-helper/test_capture_learning.py tests/tcs-helper/test_session_start_reminder.py -v 2>&1 | head -20
```

Expected: `FileNotFoundError` or `ModuleNotFoundError`

- [ ] **Step 4: Implement `capture_learning.py`**

Create `plugins/tcs-helper/scripts/capture_learning.py`:

```python
#!/usr/bin/env python3
"""UserPromptSubmit hook — detect learnings and append to queue.
Based on claude-reflect's capture_learning.py."""
import json
import os
import sys

# Support queue path override for tests
sys.path.insert(0, os.path.dirname(__file__))
from lib.reflect_utils import detect_learning, load_queue, save_queue, create_queue_item, get_queue_path


def main():
    try:
        project_path = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
        data = json.loads(sys.stdin.read())
        prompt = data.get('prompt', '')

        detection = detect_learning(prompt)
        if not detection:
            sys.exit(0)

        item_type, patterns, confidence = detection

        # Load queue (use override for tests)
        queue_override = os.environ.get('TCS_QUEUE_OVERRIDE')
        if queue_override:
            try:
                with open(queue_override, 'r') as f:
                    queue = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                queue = []
        else:
            queue = load_queue(project_path)

        item = create_queue_item(
            message=prompt[:500],  # truncate very long prompts
            project=project_path,
            item_type=item_type,
            patterns=patterns,
            confidence=confidence,
        )
        queue.append(item)

        if queue_override:
            with open(queue_override, 'w') as f:
                json.dump(queue, f, indent=2)
        else:
            save_queue(project_path, queue)

    except Exception:
        pass  # never block
    sys.exit(0)


if __name__ == '__main__':
    main()
```

- [ ] **Step 5: Implement `session_start_reminder.py`**

Create `plugins/tcs-helper/scripts/session_start_reminder.py`:

```python
#!/usr/bin/env python3
"""SessionStart hook — show pending learnings count and YOLO review reminder."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from lib.reflect_utils import load_queue, get_queue_path


def main():
    try:
        if os.environ.get('CLAUDE_REFLECT_REMINDER', '').lower() == 'false':
            sys.exit(0)

        project_path = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
        messages = []

        # Check queue
        queue_override = os.environ.get('TCS_QUEUE_OVERRIDE')
        if queue_override:
            try:
                with open(queue_override, 'r') as f:
                    queue = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                queue = []
        else:
            queue = load_queue(project_path)

        if queue:
            messages.append(
                f'📋 {len(queue)} pending learning(s) in queue — run /memory-add to process'
            )

        # Check for YOLO review file
        yolo_path_override = os.environ.get('TCS_YOLO_REVIEW_PATH')
        if yolo_path_override:
            yolo_path = yolo_path_override
        else:
            yolo_path = os.path.join(project_path, 'docs', 'ai', 'memory', 'yolo-review.md')

        if os.path.exists(yolo_path):
            messages.append(
                '⚠ Unreviewed YOLO memory entries in docs/ai/memory/yolo-review.md '
                '— run /memory-add --review-yolo'
            )

        if messages:
            print('\n'.join(messages))

    except Exception:
        pass
    sys.exit(0)


if __name__ == '__main__':
    main()
```

- [ ] **Step 6: Implement `check_learnings.py`**

Create `plugins/tcs-helper/scripts/check_learnings.py`:

```python
#!/usr/bin/env python3
"""PreCompact hook — back up learnings queue before context compaction."""
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from lib.reflect_utils import load_queue, CLAUDE_DIR


def main():
    try:
        project_path = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
        queue = load_queue(project_path)
        if not queue:
            sys.exit(0)

        backup_dir = os.path.join(CLAUDE_DIR, 'learnings-backups')
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        backup_path = os.path.join(backup_dir, f'pre-compact-{timestamp}.json')
        with open(backup_path, 'w') as f:
            json.dump(queue, f, indent=2)
    except Exception:
        pass
    sys.exit(0)


if __name__ == '__main__':
    main()
```

- [ ] **Step 7: Implement `post_commit_reminder.py`**

Create `plugins/tcs-helper/scripts/post_commit_reminder.py`:

```python
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
```

- [ ] **Step 8: Run all hook tests — expect pass**

```bash
python -m pytest tests/tcs-helper/test_capture_learning.py tests/tcs-helper/test_session_start_reminder.py -v
```

Expected: All tests PASS

- [ ] **Step 9: Commit**

```bash
git add plugins/tcs-helper/scripts/ tests/tcs-helper/
git commit -m "feat(memory): add hook scripts — capture, reminder, backup, post-commit"
```

---

## Task 3: Hook Installer — `merge_hooks.py`

**Files:**
- Create: `plugins/tcs-helper/scripts/merge_hooks.py`
- Create: `plugins/tcs-helper/hooks/hooks.json`
- Test: `tests/tcs-helper/test_merge_hooks.py`

- [ ] **Step 1: Write failing tests**

Create `tests/tcs-helper/test_merge_hooks.py`:

```python
"""Tests for merge_hooks.py — additive settings.json hook installer."""
import json
import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../plugins/tcs-helper/scripts'))
from merge_hooks import merge_hooks, read_settings, write_settings


def test_merge_into_empty_settings(tmp_path):
    settings_file = tmp_path / 'settings.json'
    settings_file.write_text('{}')
    hooks_to_add = {
        'UserPromptSubmit': [{'matcher': '', 'hooks': [{'type': 'command', 'command': 'python3 test.py'}]}]
    }
    merge_hooks(str(settings_file), hooks_to_add)
    result = json.loads(settings_file.read_text())
    assert 'hooks' in result
    assert 'UserPromptSubmit' in result['hooks']


def test_merge_does_not_duplicate_existing_hook(tmp_path):
    settings_file = tmp_path / 'settings.json'
    existing = {'hooks': {'UserPromptSubmit': [
        {'matcher': '', 'hooks': [{'type': 'command', 'command': 'python3 test.py'}]}
    ]}}
    settings_file.write_text(json.dumps(existing))
    merge_hooks(str(settings_file), {'UserPromptSubmit': [
        {'matcher': '', 'hooks': [{'type': 'command', 'command': 'python3 test.py'}]}
    ]})
    result = json.loads(settings_file.read_text())
    assert len(result['hooks']['UserPromptSubmit']) == 1


def test_merge_preserves_existing_unrelated_hooks(tmp_path):
    settings_file = tmp_path / 'settings.json'
    existing = {'hooks': {'PostToolUse': [
        {'matcher': 'Bash', 'hooks': [{'type': 'command', 'command': 'python3 other.py'}]}
    ]}}
    settings_file.write_text(json.dumps(existing))
    merge_hooks(str(settings_file), {'UserPromptSubmit': [
        {'matcher': '', 'hooks': [{'type': 'command', 'command': 'python3 new.py'}]}
    ]})
    result = json.loads(settings_file.read_text())
    assert 'PostToolUse' in result['hooks']
    assert 'UserPromptSubmit' in result['hooks']


def test_sets_cleanup_period(tmp_path):
    settings_file = tmp_path / 'settings.json'
    settings_file.write_text('{}')
    merge_hooks(str(settings_file), {}, set_cleanup_period=True)
    result = json.loads(settings_file.read_text())
    assert result.get('cleanupPeriodDays') == 99999


def test_cleanup_period_not_overridden_if_higher(tmp_path):
    settings_file = tmp_path / 'settings.json'
    settings_file.write_text('{"cleanupPeriodDays": 999999}')
    merge_hooks(str(settings_file), {}, set_cleanup_period=True)
    result = json.loads(settings_file.read_text())
    assert result['cleanupPeriodDays'] == 999999
```

- [ ] **Step 2: Run tests — expect fail**

```bash
python -m pytest tests/tcs-helper/test_merge_hooks.py -v 2>&1 | head -10
```

Expected: `ModuleNotFoundError: No module named 'merge_hooks'`

- [ ] **Step 3: Implement `merge_hooks.py`**

Create `plugins/tcs-helper/scripts/merge_hooks.py`:

```python
#!/usr/bin/env python3
"""Standalone utility to merge hook definitions into ~/.claude/settings.json.
Called by tcs-helper:setup. Additive — never overwrites existing hooks."""
import json
import os
import sys


def read_settings(settings_path: str) -> dict:
    """Read settings.json; return {} if not found or invalid."""
    try:
        with open(settings_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def write_settings(settings_path: str, settings: dict) -> None:
    """Write settings.json with formatting."""
    os.makedirs(os.path.dirname(settings_path), exist_ok=True)
    with open(settings_path, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)
        f.write('\n')


def hook_already_exists(existing_hooks: list, new_hook: dict) -> bool:
    """Check if a hook entry with the same command already exists."""
    new_cmd = new_hook.get('hooks', [{}])[0].get('command', '')
    for existing in existing_hooks:
        for h in existing.get('hooks', []):
            if h.get('command', '') == new_cmd:
                return True
    return False


def merge_hooks(
    settings_path: str,
    hooks_to_add: dict,
    set_cleanup_period: bool = False
) -> dict:
    """Merge hooks into settings.json. Returns report of what was added vs skipped."""
    settings = read_settings(settings_path)
    if 'hooks' not in settings:
        settings['hooks'] = {}

    report = {'added': [], 'skipped': []}

    for event, new_entries in hooks_to_add.items():
        if event not in settings['hooks']:
            settings['hooks'][event] = []
        for entry in new_entries:
            if hook_already_exists(settings['hooks'][event], entry):
                cmd = entry.get('hooks', [{}])[0].get('command', '')
                report['skipped'].append(f'{event}: {cmd}')
            else:
                settings['hooks'][event].append(entry)
                cmd = entry.get('hooks', [{}])[0].get('command', '')
                report['added'].append(f'{event}: {cmd}')

    if set_cleanup_period:
        current = settings.get('cleanupPeriodDays', 0)
        if current < 99999:
            settings['cleanupPeriodDays'] = 99999

    write_settings(settings_path, settings)
    return report


def main():
    """CLI: merge_hooks.py <hooks_json_path> <settings_json_path> [--set-cleanup-period]"""
    if len(sys.argv) < 3:
        print('Usage: merge_hooks.py <hooks.json> <settings.json> [--set-cleanup-period]',
              file=sys.stderr)
        sys.exit(1)
    hooks_path = sys.argv[1]
    settings_path = sys.argv[2]
    set_cleanup = '--set-cleanup-period' in sys.argv

    with open(hooks_path, 'r') as f:
        hooks_config = json.load(f)

    hooks_to_add = hooks_config.get('hooks', {})
    report = merge_hooks(settings_path, hooks_to_add, set_cleanup_period=set_cleanup)

    for item in report['added']:
        print(f'  ✓ Added: {item}')
    for item in report['skipped']:
        print(f'  · Skipped (exists): {item}')


if __name__ == '__main__':
    main()
```

- [ ] **Step 4: Create `hooks/hooks.json`**

Create `plugins/tcs-helper/hooks/hooks.json`:

```json
{
  "hooks": {
    "UserPromptSubmit": [{
      "matcher": "",
      "hooks": [{"type": "command",
        "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/scripts/capture_learning.py\" \"${PWD}\""}]
    }],
    "SessionStart": [{
      "matcher": "",
      "hooks": [{"type": "command",
        "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/scripts/session_start_reminder.py\" \"${PWD}\""}]
    }],
    "PreCompact": [{
      "matcher": "",
      "hooks": [{"type": "command",
        "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/scripts/check_learnings.py\" \"${PWD}\""}]
    }],
    "PostToolUse": [{
      "matcher": "Bash",
      "hooks": [{"type": "command",
        "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/scripts/post_commit_reminder.py\""}]
    }]
  }
}
```

- [ ] **Step 5: Run tests — expect pass**

```bash
python -m pytest tests/tcs-helper/test_merge_hooks.py -v
```

Expected: All 5 tests PASS

- [ ] **Step 6: Run full test suite**

```bash
python -m pytest tests/tcs-helper/ -v
```

Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add plugins/tcs-helper/scripts/merge_hooks.py plugins/tcs-helper/hooks/ tests/tcs-helper/test_merge_hooks.py
git commit -m "feat(memory): add merge_hooks.py and hooks/hooks.json"
```

---

## Task 4: Templates (Phase 1)

**Files:** All files under `plugins/tcs-helper/templates/`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p plugins/tcs-helper/templates/stacks
```

- [ ] **Step 2: Write `templates/claude-root.md`** (< 100 lines)

```markdown
# [Project Name]

## Core Philosophy
<!-- 2-3 lines: what this project is, key principles -->

## Memory & Context
@docs/ai/memory/memory.md

## Routing Rules
<!-- Run /memory-add to capture learnings. Routing reference: docs/ai/memory/routing-reference.md -->
- Personal/workflow corrections → global (~/.claude/includes/)
- Repo conventions/style → docs/ai/memory/general.md
- Tool/CI/build knowledge → docs/ai/memory/tools.md
- Domain/business rules → docs/ai/memory/domain.md
- Architectural decisions → docs/ai/memory/decisions.md
- Current focus/blockers → docs/ai/memory/context.md
- Bugs/fixes → docs/ai/memory/troubleshooting.md

## Stack-Specific Rules
<!-- Generated by tcs-helper:setup based on detected stack -->
```

- [ ] **Step 3: Write remaining CLAUDE.md templates**

`templates/claude-src.md`:
```markdown
# src/ — Code Area Rules

## TDD
- RED: Write failing test first. No implementation before a failing test.
- GREEN: Minimal code to make the test pass. Nothing more.
- REFACTOR: Clean up only after GREEN. Run tests again.

## Contracts
- Domain rules live in docs/ai/memory/domain.md — link implementations to these
- Public interfaces must match the SDD contract

## Conventions
<!-- Stack-specific import order, module conventions — added by setup -->
```

`templates/claude-test.md`:
```markdown
# test/ — Test Area Rules

## Naming
- File: `test_<module>.py` / `<module>.test.ts` — mirrors src/ structure
- Function/describe: `test_<what>_<when>_<expected>` or `describe('<unit>') it('<behavior>')`

## Coverage expectations
- All public interfaces must have tests
- Happy path + at least one error path per function

## Test data
- Use fixtures/factories, not hardcoded production-like data
- Isolate: each test creates its own data; don't share mutable state
```

`templates/claude-docs.md`:
```markdown
# docs/ — Documentation Rules

## When to update what
- New learning → run /memory-add (not manual file edits)
- Significant architectural decision → docs/adr/ + pointer in decisions.md
- New major feature → update README + relevant docs/

## Critical Documentation Pattern
Always add significant new docs to the Critical Documentation section in docs/ai/memory/memory.md
```

`templates/claude-ai.md`:
```markdown
# docs/ai/ — Memory Bank Rules

## Maintenance
- /memory-add — capture learnings from this session
- /memory-sync — verify @imports and index are in sync
- /memory-cleanup — archive resolved issues and prune stale context (run monthly)
- /memory-promote — detect promotable domain patterns → reusable skills (run when domain.md grows)

## Category definitions
- general.md: naming, code style, git workflow (longlived)
- tools.md: CI, build, local dev quirks (longlived/medium)
- domain.md: business rules, data models (medium)
- decisions.md: architecture choices, ADR links (medium)
- context.md: current sprint focus, blockers (short — prune regularly)
- troubleshooting.md: known bugs + fixes (short — archive when resolved)

## Index budget: ≤ 200 lines
```

- [ ] **Step 4: Write `templates/memory-index.md`**

```markdown
# Memory Index — [Repo Name]

> Routing rules are in CLAUDE.md (root). This file is the index only.
> Budget: ≤ 200 lines. Archive entries when stale. Run /memory-sync to check.

## Files
- [general.md](general.md) — conventions, style, naming [updated: YYYY-MM-DD]
- [tools.md](tools.md) — CI, build, local dev [updated: YYYY-MM-DD]
- [domain.md](domain.md) — business rules, data models [updated: YYYY-MM-DD]
- [decisions.md](decisions.md) — architecture choices [updated: YYYY-MM-DD]
- [context.md](context.md) — current focus [updated: YYYY-MM-DD]
- [troubleshooting.md](troubleshooting.md) — known issues [updated: YYYY-MM-DD]

## Archive
<!-- Archived entries live in archive/YYYY-MM/. Not loaded at session start. -->
<!-- memory-cleanup manages archive creation. Do not list archive files here. -->

## Critical Documentation
<!-- Add important docs here when created — Claude loads these on demand -->
<!-- - [Architecture Overview](../architecture/overview.md) -->
```

- [ ] **Step 5: Write 6 category file templates**

`templates/memory-general.md`:
```markdown
# General — [Repo Name]
<!-- Conventions, naming rules, code style, git workflow. Updated: YYYY-MM-DD -->
<!-- What goes here: how files are named, folder structure, style choices, branch conventions -->
<!-- What does NOT go here: tool-specific quirks (→ tools.md), domain rules (→ domain.md) -->
```

`templates/memory-tools.md`:
```markdown
# Tools — [Repo Name]
<!-- CI, build pipeline, API clients, local dev setup. Updated: YYYY-MM-DD -->
<!-- What goes here: commands that are non-obvious, tool quirks, CI gotchas, env var names -->
<!-- What does NOT go here: domain rules (→ domain.md), code style (→ general.md) -->
```

`templates/memory-domain.md`:
```markdown
# Domain — [Repo Name]
<!-- Business rules, data models, entities, domain language. Updated: YYYY-MM-DD -->
<!-- What goes here: what X means in this codebase, business rules that drive code decisions -->
<!-- Entries that appear frequently may be promotable → run /memory-promote -->
```

`templates/memory-decisions.md`:
```markdown
# Decisions — [Repo Name]
<!-- Architecture choices and rationale. Updated: YYYY-MM-DD -->
<!-- What goes here: why we chose X over Y, ADR links, significant tradeoff choices -->
<!-- Format: YYYY-MM-DD — Decision: [what] — Rationale: [why] -->
```

`templates/memory-context.md`:
```markdown
# Context — [Repo Name]
<!-- Current sprint focus, active work, known blockers. Updated: YYYY-MM-DD -->
<!-- This file is short-lived — prune entries older than 2 weeks via /memory-cleanup -->
```

`templates/memory-troubleshooting.md`:
```markdown
# Troubleshooting — [Repo Name]
<!-- Known issues and proven fixes. Updated: YYYY-MM-DD -->
<!-- Format: ## [Issue title] — Status: open/resolved — [fix description] -->
<!-- Resolved entries are archived by /memory-cleanup, not deleted -->
```

- [ ] **Step 6: Write `templates/routing-reference.md`**

```markdown
# Routing Reference — Scope × Lifetime × Category

| Learning type | Examples | Target scope | Target file |
|---|---|---|---|
| Personal correction | "stop adding semicolons to commit messages" | global | ~/.claude/includes/memory-*.md |
| Workflow preference | "always use worktrees for features" | global | ~/.claude/includes/memory-*.md |
| Project decision | "we use monorepo for all TCS work" | project | ~/Kouzou/projects/<proj>/memory.md |
| Naming convention | "use kebab-case for all file names" | repo | general.md |
| Code style rule | "no `any` types in TypeScript" | repo | general.md |
| Build command quirk | "use `bun run` not `npm run`" | repo | tools.md |
| CI knowledge | "GitHub Actions cache key is `bun.lock`" | repo | tools.md |
| Business rule | "UserRepository returns null for unknown IDs" | repo | domain.md |
| Data model fact | "Order.status is always lowercase" | repo | domain.md |
| Architecture choice | "chose hexagonal over layered" | repo | decisions.md |
| Tech tradeoff | "using SQLite because low concurrency expected" | repo | decisions.md |
| Current sprint goal | "implementing auth this week" | repo | context.md |
| Known blocker | "bun test crashes on M1 with arm64 native modules" | repo | troubleshooting.md |
| Proven fix | "set NODE_OPTIONS=--max-old-space-size=4096 for builds" | repo | troubleshooting.md |
```

- [ ] **Step 7: Write stack override templates**

`templates/stacks/typescript.md`:
```markdown
## TypeScript Rules
- Strict mode: `"strict": true` in tsconfig — no exceptions
- No `any` — use `unknown` + narrowing or define a proper type
- Import order: node builtins → external → internal (enforced by ESLint/biome)
- Prefer explicit return types on public functions
```

`templates/stacks/go.md`:
```markdown
## Go Rules
- Always run `gofmt` and `goimports` before commit (wired to PostToolUse hook)
- Error handling: always check errors; never `_` an error from public API
- Module: use `go.mod` with full module path; no relative imports outside module
```

`templates/stacks/python.md`:
```markdown
## Python Rules
- Type hints required on all public functions (enforced by ruff)
- Use `pyproject.toml`; no `setup.py` or `requirements.txt` unless legacy
- Formatter: ruff (`ruff format .`); linter: ruff (`ruff check .`)
```

`templates/stacks/cloudflare.md`:
```markdown
## Cloudflare Workers Rules
- Use `wrangler.toml` for all environment config; no hardcoded values
- Workers use the Web Standards APIs (fetch, Request, Response) — not Node.js builtins
- KV namespaces bound in `wrangler.toml`; access via `env.NAMESPACE_NAME`
```

`templates/stacks/convex.md`:
```markdown
## Convex Rules
- Mutations are transactional — keep them focused; no external I/O in mutations
- Queries are reactive — no side effects
- Schema in `convex/schema.ts` — update before adding new fields
- Use `v.` validators for all arguments and return types
```

`templates/stacks/generic.md`:
```markdown
## Stack Rules
<!-- Generic fallback — no stack-specific rules detected -->
<!-- Run tcs-helper:setup again after adding package.json / go.mod to get stack-specific rules -->
```

- [ ] **Step 8: Verify all templates exist**

```bash
find plugins/tcs-helper/templates -name '*.md' | sort
```

Expected: 19 files (5 CLAUDE.md templates + memory-index + 6 category + routing-reference + 6 stacks)

- [ ] **Step 9: Commit**

```bash
git add plugins/tcs-helper/templates/
git commit -m "feat(memory): add template files for CLAUDE.md, memory categories, and stacks"
```

---

## Task 5: `/memory-add` Skill (Phase 2 — SKILL.md)

**Files:**
- Create: `plugins/tcs-helper/skills/memory-add/SKILL.md`
- Create: `plugins/tcs-helper/skills/memory-add/reference/routing-rules.md`
- Create: `plugins/tcs-helper/skills/memory-add/reference/category-formats.md`
- Create: `plugins/tcs-helper/skills/memory-add/examples/output-example.md`

- [ ] **Step 1: Create directory**

```bash
mkdir -p plugins/tcs-helper/skills/memory-add/reference
mkdir -p plugins/tcs-helper/skills/memory-add/examples
```

- [ ] **Step 2: Write `SKILL.md`**

```markdown
---
name: memory-add
description: Capture and route session learnings to the correct scope and category file. Run after any session where corrections or new knowledge emerged. Auto-triggers on: reflect, remember, learned, note this, add to memory, route this.
user-invocable: true
argument-hint: "[learning text] | --review-yolo"
allowed-tools: Read, Write, Edit, Bash
---

# memory-add

Capture learnings from this session and route each to the correct scope and category file.

## Interface

```
State {
  learnings: Learning[]       // from queue or argument or manual
  routed: RoutedLearning[]    // scope + category + file + content
  skipped: Learning[]         // duplicates detected
  unclassified: Learning[]    // needs user decision
  yolo: boolean               // YOLO=true env var detected
}
```

## Workflow

### Step 1 — Detect mode

- If argument is `--review-yolo`: go to YOLO Review workflow (see below)
- Check `YOLO` environment variable: if `YOLO=true`, set `yolo: true`
- If `$ARGUMENTS` provided: add as manual learning(s)
- Otherwise: read queue from `~/.claude/projects/<encoded-cwd>/learnings-queue.json`
  - If queue is empty and no arguments: ask "What did you learn this session?"

### Step 2 — Classify each learning (AI reasoning)

For each learning, classify using these keyword signals:

| Keywords | Category | Target |
|---|---|---|
| naming, convention, style, format, indent, case | general | docs/ai/memory/general.md |
| build, CI, deploy, script, command, tool, api, client | tools | docs/ai/memory/tools.md |
| domain, entity, rule, model, business, contract | domain | docs/ai/memory/domain.md |
| decided, chose, decision, tradeoff, architecture, why | decisions | docs/ai/memory/decisions.md |
| working on, focus, sprint, current, this week | context | docs/ai/memory/context.md |
| bug, error, fix, workaround, issue, broken, resolved | troubleshooting | docs/ai/memory/troubleshooting.md |
| personal, always prefer, never use, my workflow | global | ~/.claude/includes/ |

If unclassified → AskUserQuestion: "Which file should this go to? [show list of options]"

### Step 3 — Determine scope

- `personal` / `workflow` → global scope: `~/.claude/includes/memory-<category>.md`
- Explicitly project-scoped fact → project memory (if configured in CLAUDE.md)
- Default → repo scope: `docs/ai/memory/{category}.md`

### Step 4 — Deduplication check

For each learning, Read the target file.
If a semantically identical fact already exists (same meaning, possibly different wording): skip silently, add to `skipped[]`.
Cross-scope duplicates are NOT checked here (handled by memory-cleanup).

### Step 5 — Write (or stage if YOLO)

**Normal mode:** Append to target file:
```
<!-- YYYY-MM-DD -->
- [learning text]
```
Then update `memory.md` index: change `[updated: YYYY-MM-DD]` for the affected file.

**YOLO mode (`YOLO=true`):** Do NOT write to target files. Instead, append to `docs/ai/memory/yolo-review.md`:
```markdown
- [ ] **Target:** `docs/ai/memory/tools.md`
  [learning text]
  *(YYYY-MM-DD)*
```

### Step 6 — Report

Show summary:
- ✓ Routed N learnings: [file → count]
- · Skipped N (duplicates)
- ? Unclassified: [if any, already resolved via AskUserQuestion]

Clear processed items from queue file.

---

## YOLO Review Workflow (`--review-yolo`)

1. Read `docs/ai/memory/yolo-review.md`
2. If file doesn't exist or is empty: report "No pending YOLO entries"
3. For each unchecked entry: show target file and content
4. AskUserQuestion: "Accept all / Select / Skip all"
5. For accepted entries: write to target file using normal append format
6. Remove accepted entries from yolo-review.md (leave rejected ones, or clear if all accepted)
7. Report: N entries written, N rejected

## Always
- Read the target file before appending (deduplication check)
- Add date comment before new entries
- Update memory.md index last-updated date after any repo-scope write
- Exit 0 and report clearly even when nothing was routed

## Never
- Write to target files in YOLO mode (only to yolo-review.md)
- Silently fail — always report what was done and what was skipped
- Create new memory files that aren't in the 6 standard categories (use existing files or ask)
```

- [ ] **Step 3: Write `reference/routing-rules.md`**

Reference the routing-reference.md template for the full table. Add examples for edge cases:
```markdown
# Routing Rules — Extended Reference

See also: `plugins/tcs-helper/templates/routing-reference.md`

## Edge cases

**"Use TypeScript strict mode"** — Is this a personal preference or a repo convention?
- If said during work in a specific repo → repo/general.md (code style)
- If said as a blanket preference → global

**"Our UserRepository must return null"** — domain rule about a specific class → domain.md

**"We decided to use hexagonal architecture"** → decisions.md (not domain.md — it's a decision, not a rule)

**"The CI is broken on main today"** → context.md (short-lived, current state)

**"Fix: set NODE_OPTIONS=--max-old-space-size=4096"** → troubleshooting.md

## Multi-scope learning
If a single message contains learnings at multiple scopes, split them and route each independently.
```

- [ ] **Step 4: Write `reference/category-formats.md`**

```markdown
# Category Entry Formats

## All files
```
<!-- YYYY-MM-DD -->
- [learning in one clear sentence, actionable]
```

## general.md
```
<!-- 2026-03-25 -->
- File names use kebab-case (not camelCase): `user-repository.ts` not `userRepository.ts`
```

## decisions.md
```
<!-- 2026-03-25 -->
- 2026-03-25 — Chose SQLite over Postgres — Rationale: expected low concurrency; simpler ops
```

## troubleshooting.md
```
<!-- 2026-03-25 -->
## bun test crash on M1 — Status: open
NODE_OPTIONS=--max-old-space-size=4096 fixes OOM on large test suites

## bun lock conflict — Status: resolved
Run `bun install --frozen-lockfile` to reproduce; `bun install` to fix
```

## What NOT to include
- Long prose explanations — keep it to one actionable sentence
- Code snippets longer than 3 lines (link to a doc file instead)
- Things that belong in the codebase itself (put them in code comments or README)
```

- [ ] **Step 5: Write `examples/output-example.md`**

```markdown
# /memory-add — Example Output

## Input
Running after a session where:
1. User corrected "no, use fd not find — it's faster and respects .gitignore"
2. User said "remember: UserRepository must return null for unknown email lookups, never throw"
3. User said "we decided to use hexagonal architecture for this project"

## Output

```
📋 Processing 3 learnings from queue...

Classifying...
  1. "no, use fd not find" → tools.md (tool correction)
  2. "remember: UserRepository must return null" → domain.md (explicit domain rule)
  3. "decided to use hexagonal architecture" → decisions.md (architecture decision)

Checking for duplicates...
  1. tools.md — no existing entry for fd/find ✓
  2. domain.md — no existing entry for UserRepository ✓
  3. decisions.md — no existing entry for hexagonal ✓

Writing...
  ✓ docs/ai/memory/tools.md — 1 entry added
  ✓ docs/ai/memory/domain.md — 1 entry added
  ✓ docs/ai/memory/decisions.md — 1 entry added
  ✓ docs/ai/memory/memory.md — index updated (3 files)

Done. 3 learnings routed, 0 skipped, 0 unclassified.
Queue cleared.
```
```

- [ ] **Step 6: Verify SKILL.md is under 25KB**

```bash
wc -c plugins/tcs-helper/skills/memory-add/SKILL.md
```

Expected: < 25600 bytes

- [ ] **Step 7: Commit**

```bash
git add plugins/tcs-helper/skills/memory-add/
git commit -m "feat(memory): add /memory-add skill with routing, YOLO mode, and deduplication"
```

---

## Task 6: `memory-sync` Skill (Phase 3)

**Files:**
- Create: `plugins/tcs-helper/skills/memory-sync/SKILL.md`
- Create: `plugins/tcs-helper/skills/memory-sync/examples/output-example.md`

- [ ] **Step 1: Create directory**

```bash
mkdir -p plugins/tcs-helper/skills/memory-sync/examples
```

- [ ] **Step 2: Write `SKILL.md`**

```markdown
---
name: memory-sync
description: Verify that CLAUDE.md @imports and memory.md index are in sync with actual docs/ai/memory/ files. Detects missing imports, orphaned files, routing rules in wrong location, and index budget issues. Run when adding memory files or periodically.
user-invocable: true
argument-hint: "[--fix]"
allowed-tools: Read, Write, Edit, Bash
---

# memory-sync

Audit the memory bank structure and report (or fix) synchronization issues.

## Workflow

### Step 1 — Gather state (code via Bash)

```bash
# List all .md files in docs/ai/memory/ (excluding archive/)
find docs/ai/memory -maxdepth 1 -name '*.md' | sort
# Count lines in memory.md
wc -l docs/ai/memory/memory.md
# Check CLAUDE.md for @imports
grep '@docs/ai/memory' CLAUDE.md
```

### Step 2 — Run checks

**Check 1: CLAUDE.md has @import for memory.md**
- Read CLAUDE.md — look for `@docs/ai/memory/memory.md`
- If missing: WARN — "CLAUDE.md is missing @docs/ai/memory/memory.md import"
- If `--fix`: add `@docs/ai/memory/memory.md` to the Memory & Context section

**Check 2: Audit each @ import**
- For each `@` line in CLAUDE.md: verify the file exists
- Flag broken @imports (file doesn't exist)
- Note: additional @imports beyond memory.md should be justified — report them for review

**Check 3: memory.md lists all category files**
- Read docs/ai/memory/memory.md
- Compare listed files against files found in Step 1
- WARN for each file in filesystem but not in index (orphan)
- WARN for each file in index but not in filesystem (stale entry)

**Check 4: No routing rules in memory.md**
- Read docs/ai/memory/memory.md
- If it contains lines matching routing patterns (→ general.md, → tools.md, etc.): WARN

**Check 5: memory.md line budget**
- If line count ≥ 200: ERROR — "memory.md at budget limit"
- If line count ≥ 160: WARN — "memory.md approaching budget (N/200 lines)"
- Otherwise: OK

### Step 3 — Report

```
memory-sync report:
  ✓ @import present in CLAUDE.md
  ✓ All 6 category files listed in memory.md
  ✓ No orphaned files
  ✓ Routing rules in CLAUDE.md (not memory.md)
  ⚠ memory.md: 164/200 lines — approaching budget
```

If issues found and `--fix` passed: apply auto-fixable items (missing @import only); flag manual items.

## Always
- Never modify memory content — only add missing structural entries
- Report clearly even when everything is OK

## Never
- Delete entries from memory.md (that's memory-cleanup's job)
- Add `@` imports for files that aren't strictly needed on every session start
```

- [ ] **Step 3: Write `examples/output-example.md`**

```markdown
# memory-sync — Example Outputs

## OK case
```
memory-sync report — 2026-03-25
  ✓ @import: @docs/ai/memory/memory.md present in CLAUDE.md
  ✓ Index: all 6 category files listed, no orphans
  ✓ Routing rules: in CLAUDE.md only
  ✓ Budget: 87/200 lines
All checks passed.
```

## Missing @import
```
memory-sync report — 2026-03-25
  ✗ @import: @docs/ai/memory/memory.md NOT found in CLAUDE.md
    Fix: add "@docs/ai/memory/memory.md" under "## Memory & Context" in CLAUDE.md
    Run with --fix to apply automatically.
  ✓ Index: all 6 category files listed
  ...
1 issue found.
```

## Budget warning
```
memory-sync report — 2026-03-25
  ✓ @import: present
  ✓ Index: in sync
  ⚠ Budget: 173/200 lines — approaching limit. Run /memory-cleanup to prune.
1 warning.
```
```

- [ ] **Step 4: Commit**

```bash
git add plugins/tcs-helper/skills/memory-sync/
git commit -m "feat(memory): add /memory-sync skill"
```

---

## Task 7: `memory-cleanup` Skill (Phase 4)

**Files:**
- Create: `plugins/tcs-helper/skills/memory-cleanup/SKILL.md`

- [ ] **Step 1: Create directory**

```bash
mkdir -p plugins/tcs-helper/skills/memory-cleanup
```

- [ ] **Step 2: Write `SKILL.md`**

```markdown
---
name: memory-cleanup
description: Reduce memory bank size by archiving resolved troubleshooting, pruning stale context, and consolidating near-duplicates. Human-in-the-loop — always presents candidates before acting. Run monthly or when memory.md approaches 200 lines.
user-invocable: true
argument-hint: "[--dry-run]"
allowed-tools: Read, Write, Edit, Bash
---

# memory-cleanup

Review and prune the memory bank. Always show candidates to the user before any changes.

## Workflow

### Step 1 — Scan all category files

Read all 6 category files in `docs/ai/memory/`. Build a list of candidates for each operation:

**Troubleshooting candidates:** entries containing "resolved" or "Status: resolved"
**Context candidates:** entries with a date older than 14 days (check date comments `<!-- YYYY-MM-DD -->`)
**Duplicate candidates:** entries in domain.md or general.md with highly similar meaning

### Step 2 — Present candidates (AskUserQuestion for each category)

For each non-empty candidate list:

> "Found N candidates in troubleshooting.md to archive (Status: resolved):
> 1. [entry text]
> 2. [entry text]
> Archive all / Select / Skip"

**Preservation rules — never propose these for removal:**
- Entries containing "TODO" or "ROADMAP"
- Entries in decisions.md (archive only if explicitly superseded)
- Any entry the user chose to keep in a previous run

### Step 3 — Execute approved operations

**Archive:** Move entry to `docs/ai/memory/archive/YYYY-MM/{filename}` (create file if needed, append if exists). Remove from source file.

**Prune:** Delete entry from source file (only for explicitly stale context entries the user approved).

**Consolidate duplicates:** Show both entries, ask user which wording to keep. Write winner, remove loser.

### Step 4 — Update index

After any changes: update `memory.md` last-updated dates for modified files.

### Step 5 — Report

```
memory-cleanup complete:
  - troubleshooting.md: 2 entries archived → archive/2026-03/
  - context.md: 1 stale entry pruned
  - domain.md: 1 duplicate consolidated
  memory.md: 87 lines (was 134 before cleanup)
```

## Always
- Show candidates before acting — no silent changes
- Use archive not delete for resolved troubleshooting
- Update memory.md index after any file change

## Never
- Delete historical decisions (only archive if explicitly superseded and user confirms)
- Remove TODOs or roadmap items
- Act without user review
```

- [ ] **Step 3: Commit**

```bash
git add plugins/tcs-helper/skills/memory-cleanup/
git commit -m "feat(memory): add /memory-cleanup skill"
```

---

## Task 8: `memory-promote` Skill (Phase 5)

**Files:**
- Create: `plugins/tcs-helper/scripts/extract_session_learnings.py`
- Test: `tests/tcs-helper/test_extract_session_learnings.py`
- Create: `plugins/tcs-helper/skills/memory-promote/SKILL.md`

- [ ] **Step 1: Write failing test for `extract_session_learnings.py`**

Create `tests/tcs-helper/test_extract_session_learnings.py`:

```python
"""Tests for extract_session_learnings.py — reads .jsonl session files."""
import json
import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../plugins/tcs-helper/scripts'))
import extract_session_learnings as esl


def test_extract_messages_from_jsonl(tmp_path):
    """Extracts user-role messages from a .jsonl session file."""
    session_file = tmp_path / "session.jsonl"
    lines = [
        json.dumps({"type": "message", "role": "user", "content": "always use fd not find"}),
        json.dumps({"type": "message", "role": "assistant", "content": "noted"}),
        json.dumps({"type": "message", "role": "user", "content": "use pytest not unittest"}),
    ]
    session_file.write_text("\n".join(lines))

    messages = esl.extract_user_messages(str(session_file))
    assert len(messages) == 2
    assert "always use fd not find" in messages
    assert "use pytest not unittest" in messages


def test_filter_by_days(tmp_path, monkeypatch):
    """Only returns messages from sessions modified within --days window."""
    import time
    session_file = tmp_path / "old.jsonl"
    session_file.write_text(
        json.dumps({"type": "message", "role": "user", "content": "old message"})
    )
    # Set mtime to 30 days ago
    old_time = time.time() - (30 * 86400)
    os.utime(str(session_file), (old_time, old_time))

    messages = esl.extract_from_project(str(tmp_path), days=7)
    assert messages == []


def test_malformed_lines_skipped(tmp_path):
    """Non-JSON lines are silently skipped."""
    session_file = tmp_path / "session.jsonl"
    session_file.write_text("not-json\n" + json.dumps({"type": "message", "role": "user", "content": "valid"}))

    messages = esl.extract_user_messages(str(session_file))
    assert messages == ["valid"]


def test_no_session_files_returns_empty(tmp_path):
    """Returns empty list when no .jsonl files exist."""
    messages = esl.extract_from_project(str(tmp_path), days=14)
    assert messages == []
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/tcs-helper/test_extract_session_learnings.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'extract_session_learnings'`

- [ ] **Step 3: Write `extract_session_learnings.py`**

Create `plugins/tcs-helper/scripts/extract_session_learnings.py`:

```python
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
from datetime import datetime, timezone


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
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/tcs-helper/test_extract_session_learnings.py -v
```

Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add plugins/tcs-helper/scripts/extract_session_learnings.py tests/tcs-helper/test_extract_session_learnings.py
git commit -m "feat(memory): add extract_session_learnings.py for memory-promote"
```

- [ ] **Step 6: Create skill directory**

```bash
mkdir -p plugins/tcs-helper/skills/memory-promote
```

- [ ] **Step 7: Write `SKILL.md`**

```markdown
---
name: memory-promote
description: Detect mature domain patterns in domain.md that have become reusable knowledge. Analyze session history for repeating patterns (like reflect-skills). Propose as skill candidates. On approval, generate SKILL.md stub at user-chosen scope (global or repo). Run when domain.md grows or periodically.
user-invocable: true
argument-hint: "[--days N] [--dry-run]"
allowed-tools: Read, Write, Bash
---

# memory-promote

Detect promotable patterns in domain.md and generate skill stubs.

## Workflow

### Step 1 — Gather evidence (code via Bash)

```bash
# Find session files for this repo
ENCODED=$(python3 -c "import sys; p=sys.argv[1]; print(p.replace('/','-').lstrip('-'))" "$(pwd)")
ls ~/.claude/projects/$ENCODED/*.jsonl 2>/dev/null | head -20

# Extract user messages from session files (if available)
# Uses extract_session_learnings.py from scripts/
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/extract_session_learnings.py" "$(pwd)" --days "${DAYS:-14}"
```

### Step 2 — Semantic pattern analysis (AI reasoning)

Read `docs/ai/memory/domain.md`. Cross-reference with session messages from Step 1.

For each domain.md entry and each cluster of similar session messages:
- Group by intent (same concept expressed differently = one pattern)
- Score: repetition count (across sessions) + reusability (could this apply to another repo?) + abstraction level
- Confidence:
  - High: appears ≥3 sessions AND is clearly reusable
  - Medium: appears ≥2 sessions OR strong reusability signal
  - Low: domain.md only, no session evidence

Skip entries that are already pointers (`→ see skill:` format).

### Step 3 — Propose candidates

For each candidate (High or Medium confidence):

> **Candidate: [name]**
> Evidence: [summary — N sessions, domain.md entry]
> Confidence: High/Medium/Low
> Proposed skill name: `[kebab-case-name]`

AskUserQuestion: "Approve / Skip / Rename"

### Step 4 — On approval: choose scope

AskUserQuestion:
> "Where should this skill be generated?
> 1. Global — ~/.claude/skills/[name]/SKILL.md (available in all sessions)
> 2. Repo — .claude/skills/[name]/SKILL.md (only in this repo)
> (Note: project-level skills don't exist in Claude Code — only global or repo)"

### Step 5 — Generate SKILL.md stub

```markdown
---
name: [skill-name]
description: [one-line description based on pattern]. Promoted from docs/ai/memory/domain.md on YYYY-MM-DD.
user-invocable: false
---

# [Skill Name]

<!-- TODO: Fill in this skill based on the promoted pattern -->

## Pattern

[The domain.md entry that was promoted, as a starting point]

## When to apply

<!-- TODO: Define trigger conditions -->

## How to apply

<!-- TODO: Define the pattern steps -->
```

### Step 6 — Update domain.md

Replace the promoted entry with:
```
→ see skill: [skill-name] ([global/repo])
```

Update memory.md index.

### Step 7 — Report

```
memory-promote complete:
  ✓ Generated: ~/.claude/skills/hexagonal-arch/SKILL.md
  ✓ domain.md entry replaced with pointer
  · Skipped: 2 candidates (low confidence)
```

## Always
- Show evidence for each candidate before asking for approval
- Inform user that project-level skills don't exist (only global or repo)
- Generate stub only — leave TODO markers for the user to fill in

## Never
- Delete domain.md entries — replace with pointer only
- Generate skills with confidence = Low without explicit user override
```

- [ ] **Step 8: Commit**

```bash
git add plugins/tcs-helper/skills/memory-promote/
git commit -m "feat(memory): add /memory-promote skill — detect and promote domain patterns"
```

---

## Task 9: `setup` Skill (Phase 6)

**Files:**
- Create: `plugins/tcs-helper/skills/setup/SKILL.md`

- [ ] **Step 1: Create directory**

```bash
mkdir -p plugins/tcs-helper/skills/setup
```

- [ ] **Step 2: Write `SKILL.md`**

```markdown
---
name: setup
description: One-shot project onboarding for TCS repos. Detects tech stack, generates docs/ai/memory/ structure and lean CLAUDE.md files, installs memory hooks. Run once in a new repo or to add memory structure to an existing one.
user-invocable: true
argument-hint: ""
allowed-tools: Read, Write, Edit, Bash
---

# setup

Provision the TCS memory system for this repo.

## Workflow

### Step 1 — Detect stack and existing state (code)

```bash
# Stack detection — check for manifest files
[ -f package.json ] && echo "node"
[ -f go.mod ] && echo "go"
[ -f pyproject.toml ] || [ -f setup.py ] && echo "python"
# Check Cloudflare / Convex specifics
grep -l "cloudflare" package.json 2>/dev/null && echo "cloudflare"
grep -l "convex" package.json 2>/dev/null && echo "convex"
# CI detection
[ -d .github/workflows ] && echo "github-actions"
# Existing structure
[ -f CLAUDE.md ] && echo "has-claude-md"
[ -d docs/ai/memory ] && echo "has-memory-structure"
```

### Step 2 — Preview structure (AI — show before acting)

> "I'll create the following structure:
>
> docs/ai/memory/
>   memory.md (index)
>   general.md, tools.md, domain.md, decisions.md, context.md, troubleshooting.md
>
> CLAUDE.md (will ADD memory section — existing content preserved)
> src/CLAUDE.md, test/CLAUDE.md, docs/CLAUDE.md, docs/ai/CLAUDE.md
>
> Stack detected: TypeScript — will apply typescript.md overrides to src/CLAUDE.md
>
> Proceed? [yes/no]"

### Step 3 — Generate memory structure (code)

```bash
# Create directories
mkdir -p docs/ai/memory

# Copy category templates
TMPL="${CLAUDE_PLUGIN_ROOT}/templates"
for cat in general tools domain decisions context troubleshooting; do
  cp "$TMPL/memory-${cat}.md" "docs/ai/memory/${cat}.md"
done
cp "$TMPL/memory-index.md" "docs/ai/memory/memory.md"
# Replace placeholder with actual repo name
REPO_NAME=$(basename "$(pwd)")
sed -i.bak "s/\[Repo Name\]/${REPO_NAME}/g" docs/ai/memory/*.md
rm -f docs/ai/memory/*.bak
```

### Step 4 — Generate CLAUDE.md files (code + AI for existing CLAUDE.md)

For each of: root, src/, test/, docs/, docs/ai/
- If file doesn't exist: copy from template and apply stack overrides
- If file exists: Read it, add memory section non-destructively (don't overwrite existing content)
  - Check if `@docs/ai/memory/memory.md` already present — skip if so
  - Check if Routing Rules section exists — skip if so
  - Add both sections after existing content

Stack override application: read `templates/stacks/<detected-stack>.md` and append to `src/CLAUDE.md`.

### Step 5 — Install hooks (code)

```bash
SETTINGS="${HOME}/.claude/settings.json"
HOOKS="${CLAUDE_PLUGIN_ROOT}/hooks/hooks.json"
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/merge_hooks.py" "$HOOKS" "$SETTINGS" --set-cleanup-period
```

Report which hooks were added vs already present.

### Step 6 — Optional extras (AI — AskUserQuestion)

> "Setup complete! Optional additions:
> 1. Create docs/adr/ for Architecture Decision Records
> 2. Add format-on-save hook for TypeScript (biome)
> Skip optional steps? [yes/no/select]"

### Step 7 — Summary

Show:
- Files created/modified
- Hooks installed
- YOLO=true usage instructions
- "Run /memory-add to capture learnings, /memory-sync to verify structure"

## Always
- Non-destructive: never overwrite existing CLAUDE.md content
- Idempotent: running twice produces no duplicates
- Report every file created/modified

## Never
- Overwrite existing @imports or custom sections in CLAUDE.md
- Install hooks without user confirmation (the preview in Step 2 covers this)
```

- [ ] **Step 3: Commit**

```bash
git add plugins/tcs-helper/skills/setup/
git commit -m "feat(memory): add tcs-helper:setup skill with stack detection and hook installation"
```

---

## Task 10: Register Everything in plugin.json

**Files:**
- Modify: `plugins/tcs-helper/.claude-plugin/plugin.json`

- [ ] **Step 1: Update plugin.json**

Read the current `plugins/tcs-helper/.claude-plugin/plugin.json` first, then update it to include the new components. The final file should look like:

```json
{
  "name": "tcs-helper",
  "version": "2.0.0",
  "description": "Helper tools for The Custom Agentic Startup — skill authoring, memory system, and project onboarding",
  "author": {
    "name": "Marcus Breiden"
  },
  "homepage": "https://github.com/MMoMM-org/the-custom-startup",
  "repository": "https://github.com/MMoMM-org/the-custom-startup",
  "license": "MIT",
  "keywords": [
    "skill-authoring",
    "plugin-development",
    "memory-system",
    "project-onboarding",
    "utilities"
  ],
  "skills": "skills/",
  "hooks": "hooks/hooks.json",
  "templates": "templates/"
}
```

Note: `"skills": "skills/"` registers all skill directories under `skills/` (including the existing `skill-author` and all 5 new skills). `"hooks": "hooks/hooks.json"` registers the hook definitions created in Task 2.

- [ ] **Step 2: Verify plugin loads**

```bash
# Check plugin.json is valid JSON
python3 -m json.tool plugins/tcs-helper/.claude-plugin/plugin.json
```

Expected: Valid JSON output, no errors

- [ ] **Step 3: Commit**

```bash
git add plugins/tcs-helper/.claude-plugin/plugin.json
git commit -m "chore(memory): bump tcs-helper to v2.0.0, register skills + hooks + templates"
```

---

## Task 11: Integration Smoke Test

- [ ] **Step 1: Run full Python test suite**

```bash
python -m pytest tests/tcs-helper/ -v --tb=short
```

Expected: All tests PASS

- [ ] **Step 2: Verify all skill files exist**

```bash
find plugins/tcs-helper/skills -name 'SKILL.md' | sort
```

Expected:
```
plugins/tcs-helper/skills/memory-add/SKILL.md
plugins/tcs-helper/skills/memory-cleanup/SKILL.md
plugins/tcs-helper/skills/memory-promote/SKILL.md
plugins/tcs-helper/skills/memory-sync/SKILL.md
plugins/tcs-helper/skills/setup/SKILL.md
plugins/tcs-helper/skills/skill-author/SKILL.md
```

- [ ] **Step 3: Verify all templates exist**

```bash
find plugins/tcs-helper/templates -name '*.md' | wc -l
```

Expected: 19

- [ ] **Step 4: Verify hooks.json is valid**

```bash
python3 -m json.tool plugins/tcs-helper/hooks/hooks.json
```

Expected: Valid JSON, 4 hook events

- [ ] **Step 5: Verify SKILL.md files are under 25KB**

```bash
for f in $(find plugins/tcs-helper/skills -name 'SKILL.md'); do
  size=$(wc -c < "$f")
  echo "$size $f"
done
```

Expected: All < 25600 bytes

- [ ] **Step 6: Final commit and changelog entry**

```bash
# Update CHANGELOG if it exists
git add .
git commit -m "feat(memory): complete M2 memory system — all skills, templates, and hooks"
```

---

## Quick Reference

| Command | Purpose | When to run |
|---|---|---|
| `/memory-add` | Capture + route session learnings | End of every session |
| `/memory-add --review-yolo` | Review staged YOLO entries | After YOLO sessions |
| `/memory-sync` | Check @imports + index | When adding memory files |
| `/memory-cleanup` | Archive resolved issues, prune stale | Monthly |
| `/memory-promote` | Promote domain patterns to skills | When domain.md grows |
| `/setup` | Provision memory structure in new repo | Once per new repo |

**YOLO mode:** Set `YOLO=true` before starting Claude to stage all memory writes for review.
