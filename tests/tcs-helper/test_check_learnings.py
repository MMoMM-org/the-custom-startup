"""Tests for the PreCompact hook — check_learnings.py.

The script backs up the learnings queue before context compaction.
Because CLAUDE_DIR is hardcoded in reflect_utils, tests that need to control
the backup destination import the script's main() directly and patch the
module-level CLAUDE_DIR constant via monkeypatch.

Tests that only need to verify exit behaviour (empty queue, malformed input)
use subprocess.run with TCS_QUEUE_OVERRIDE so they never touch ~/.claude.
"""
import importlib
import json
import os
import re
import sys
import subprocess
import pytest

SCRIPTS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '../../plugins/tcs-helper/scripts')
)
SCRIPT_PATH = os.path.join(SCRIPTS_DIR, 'check_learnings.py')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run_script(queue_path=None, extra_env=None):
    """Invoke check_learnings.py as a subprocess, returning the CompletedProcess."""
    env = os.environ.copy()
    if queue_path is not None:
        env['TCS_QUEUE_OVERRIDE'] = str(queue_path)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, SCRIPT_PATH],
        capture_output=True,
        env=env,
    )


def load_main_with_patched_claude_dir(monkeypatch, claude_dir: str):
    """Import (or reload) check_learnings with CLAUDE_DIR pointing to claude_dir.

    Returns the main() callable from the freshly-loaded module.
    """
    # Patch reflect_utils first so the constant is overridden before main imports it
    if 'lib.reflect_utils' in sys.modules:
        monkeypatch.setattr(sys.modules['lib.reflect_utils'], 'CLAUDE_DIR', claude_dir)
    if 'reflect_utils' in sys.modules:
        monkeypatch.setattr(sys.modules['reflect_utils'], 'CLAUDE_DIR', claude_dir)

    # Reload check_learnings so it picks up the patched constant
    if 'check_learnings' in sys.modules:
        del sys.modules['check_learnings']

    # Ensure scripts dir is importable
    if SCRIPTS_DIR not in sys.path:
        sys.path.insert(0, SCRIPTS_DIR)

    import check_learnings
    monkeypatch.setattr(check_learnings, 'CLAUDE_DIR', claude_dir)
    return check_learnings.main


# ---------------------------------------------------------------------------
# Subprocess-level tests (no backup dir involved)
# ---------------------------------------------------------------------------

def test_empty_queue_exits_zero_without_creating_backup(tmp_path):
    """An empty queue file should cause the script to exit cleanly (exit 0)."""
    queue_file = tmp_path / 'queue.json'
    queue_file.write_text('[]')

    result = run_script(queue_path=queue_file)

    assert result.returncode == 0


def test_missing_queue_file_exits_zero(tmp_path):
    """A missing queue file (override path doesn't exist) is treated as empty — no crash."""
    nonexistent = tmp_path / 'no-such-file.json'

    result = run_script(queue_path=nonexistent)

    assert result.returncode == 0


def test_malformed_json_queue_exits_zero(tmp_path):
    """Invalid JSON in the queue file must not crash the script — exits 0 gracefully."""
    queue_file = tmp_path / 'queue.json'
    queue_file.write_text('{ this is not valid json !!!')

    result = run_script(queue_path=queue_file)

    assert result.returncode == 0


# ---------------------------------------------------------------------------
# Import-level tests (backup dir controlled via monkeypatch)
# ---------------------------------------------------------------------------

def test_populated_queue_creates_backup_file(monkeypatch, tmp_path, sample_queue_items):
    """A non-empty queue should produce a backup file inside the controlled backup dir."""
    fake_claude_dir = str(tmp_path / 'fake-claude')
    queue_file = tmp_path / 'queue.json'
    queue_file.write_text(json.dumps(sample_queue_items))

    monkeypatch.setenv('TCS_QUEUE_OVERRIDE', str(queue_file))

    main = load_main_with_patched_claude_dir(monkeypatch, fake_claude_dir)

    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 0

    backup_dir = os.path.join(fake_claude_dir, 'learnings-backups')
    assert os.path.isdir(backup_dir), 'learnings-backups/ directory should have been created'

    backups = os.listdir(backup_dir)
    assert len(backups) == 1, 'exactly one backup file should be created'


def test_backup_directory_is_created_automatically(monkeypatch, tmp_path, sample_queue_items):
    """The backup directory must be created if it does not already exist."""
    fake_claude_dir = str(tmp_path / 'brand-new-claude-dir')
    # Confirm the directory really does not exist yet
    assert not os.path.exists(fake_claude_dir)

    queue_file = tmp_path / 'queue.json'
    queue_file.write_text(json.dumps(sample_queue_items))
    monkeypatch.setenv('TCS_QUEUE_OVERRIDE', str(queue_file))

    main = load_main_with_patched_claude_dir(monkeypatch, fake_claude_dir)

    with pytest.raises(SystemExit):
        main()

    backup_dir = os.path.join(fake_claude_dir, 'learnings-backups')
    assert os.path.isdir(backup_dir)


def test_backup_file_name_format(monkeypatch, tmp_path, sample_queue_items):
    """Backup file name must match pre-compact-YYYYMMDD-HHMMSS.json."""
    fake_claude_dir = str(tmp_path / 'fake-claude')
    queue_file = tmp_path / 'queue.json'
    queue_file.write_text(json.dumps(sample_queue_items))
    monkeypatch.setenv('TCS_QUEUE_OVERRIDE', str(queue_file))

    main = load_main_with_patched_claude_dir(monkeypatch, fake_claude_dir)

    with pytest.raises(SystemExit):
        main()

    backup_dir = os.path.join(fake_claude_dir, 'learnings-backups')
    filenames = os.listdir(backup_dir)
    assert len(filenames) == 1
    pattern = re.compile(r'^pre-compact-\d{8}-\d{6}\.json$')
    assert pattern.match(filenames[0]), (
        f"Backup filename '{filenames[0]}' does not match 'pre-compact-YYYYMMDD-HHMMSS.json'"
    )


def test_backup_contains_original_queue_contents(monkeypatch, tmp_path, sample_queue_items):
    """Backup file content must match the original queue items exactly."""
    fake_claude_dir = str(tmp_path / 'fake-claude')
    queue_file = tmp_path / 'queue.json'
    queue_file.write_text(json.dumps(sample_queue_items))
    monkeypatch.setenv('TCS_QUEUE_OVERRIDE', str(queue_file))

    main = load_main_with_patched_claude_dir(monkeypatch, fake_claude_dir)

    with pytest.raises(SystemExit):
        main()

    backup_dir = os.path.join(fake_claude_dir, 'learnings-backups')
    backup_file = os.path.join(backup_dir, os.listdir(backup_dir)[0])
    with open(backup_file) as f:
        backed_up = json.load(f)

    assert backed_up == sample_queue_items
