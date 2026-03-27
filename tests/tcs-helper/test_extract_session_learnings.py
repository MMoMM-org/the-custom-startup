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
