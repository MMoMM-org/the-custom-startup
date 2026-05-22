#!/usr/bin/env python3
"""
Test: pre-push rule-enforcer template rendering.

Tests for:
  - templates/githooks/pre-push-rule-enforcer.sh.j2
  - templates/githooks/tcs-helper-rule-enforcer-version

Uses stdlib only — no jinja2 dependency.
Renders via str.replace() with sample contexts for both response_style values.

Run:
  python3 plugins/tcs-helper/templates/githooks/test_pre_push_template.py
"""

import os
import re
import subprocess
import sys
import tempfile

TEMPLATES_DIR = os.path.dirname(os.path.abspath(__file__))

SAMPLE_CONTEXT_BLOCK = {
    "{{rule_description}}": "CHANGELOG must be touched before pushing feat: commits",
    "{{detection_pattern}}": (
        'grep -q "feat:" "$commits_file" && '
        '! grep -qF "CHANGELOG" "$diff_file"'
    ),
    "{{response_style}}": "Block",
    "{{warning_message}}": (
        "Rule violated: CHANGELOG must be touched before pushing feat: commits"
    ),
}

SAMPLE_CONTEXT_NUDGE = {
    "{{rule_description}}": "README should be updated when docs/ changes land",
    "{{detection_pattern}}": (
        'grep -q "docs/" "$commits_file" && '
        '! grep -qF "README" "$diff_file"'
    ),
    "{{response_style}}": "Nudge",
    "{{warning_message}}": (
        "Reminder: README should be updated when docs/ changes land"
    ),
}

VERSION_MARKER_PATTERN = re.compile(r"^[a-z]?\d+$")


def render(template_text, context):
    """Render template by replacing all placeholder keys with context values."""
    result = template_text
    for placeholder, value in context.items():
        result = result.replace(placeholder, value)
    return result


def load_file(filename):
    path = os.path.join(TEMPLATES_DIR, filename)
    if not os.path.exists(path):
        return None, path
    with open(path) as f:
        return f.read(), path


def test_template_exists():
    """RED gate: template file must exist."""
    text, path = load_file("pre-push-rule-enforcer.sh.j2")
    if text is None:
        print(f"MISSING: {path}")
        return False, None
    print(f"PASS template_exists: {path}")
    return True, text


def test_version_marker_exists():
    """RED gate: version marker file must exist and contain single non-empty line."""
    text, path = load_file("tcs-helper-rule-enforcer-version")
    if text is None:
        print(f"MISSING: {path}")
        return False
    lines = [l for l in text.splitlines() if l.strip()]
    if len(lines) != 1:
        print(f"FAIL version_marker: expected 1 non-empty line, got {len(lines)} in {path}")
        return False
    marker = lines[0].strip()
    if not VERSION_MARKER_PATTERN.match(marker):
        print(
            f"FAIL version_marker: '{marker}' does not match ^[a-z]?\\d+$ in {path}"
        )
        return False
    print(f"PASS version_marker: '{marker}' matches expected format")
    return True


def test_shebang(rendered, label):
    """Assert rendered script starts with #!/bin/bash."""
    first_line = rendered.splitlines()[0] if rendered else ""
    if first_line == "#!/bin/bash":
        print(f"PASS shebang [{label}]: #!/bin/bash present")
        return True
    print(f"FAIL shebang [{label}]: first line is '{first_line}', expected '#!/bin/bash'")
    return False


def test_pipefail(rendered, label):
    """Assert rendered script contains set -uo pipefail."""
    if "set -uo pipefail" in rendered:
        print(f"PASS pipefail [{label}]: set -uo pipefail present")
        return True
    print(f"FAIL pipefail [{label}]: 'set -uo pipefail' not found")
    return False


def test_block_exits(rendered):
    """Block style: exit 1 must appear in the warning/block branch."""
    if "exit 1" in rendered:
        print("PASS block_exits: 'exit 1' found in Block render")
        return True
    print("FAIL block_exits: 'exit 1' not found in Block render")
    return False


def test_nudge_exits(rendered):
    """Nudge style: exit 0 must be the terminal (last) exit statement in the script.

    exit 1 may appear in a dead Block branch but must not be the last exit.
    This validates that a Nudge hook always lets the push through after warning.
    """
    if "exit 0" not in rendered:
        print("FAIL nudge_exit0: 'exit 0' not found in Nudge render")
        return False

    lines = rendered.splitlines()
    # Find the last exit statement in the script
    last_exit = None
    for line in reversed(lines):
        stripped = line.strip()
        if stripped.startswith("exit "):
            last_exit = stripped
            break

    if last_exit is None:
        print("FAIL nudge_last_exit: no exit statement found in Nudge render")
        return False

    if last_exit == "exit 0":
        print("PASS nudge_exits: terminal exit is 'exit 0' — push proceeds after warning")
        return True

    print(f"FAIL nudge_last_exit: last exit is '{last_exit}', expected 'exit 0'")
    return False


def test_shellcheck(rendered, label):
    """Run shellcheck on rendered .sh — skip cleanly if not installed."""
    with tempfile.NamedTemporaryFile(suffix=".sh", mode="w", delete=False) as f:
        f.write(rendered)
        tmp_path = f.name

    try:
        result = subprocess.run(
            ["shellcheck", "-s", "bash", tmp_path],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            print(f"PASS shellcheck [{label}]: rendered .sh is shellcheck clean")
            return True
        print(f"FAIL shellcheck [{label}]: returncode={result.returncode}")
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr)
        return False
    except FileNotFoundError:
        print(f"SKIP shellcheck [{label}]: shellcheck binary not found")
        return True
    finally:
        os.unlink(tmp_path)


def _make_git_repo_with_md_commit():
    """Create a temp git repo with one commit touching a .md file. Return (repo_dir, sha)."""
    repo_dir = tempfile.mkdtemp()
    env = dict(os.environ, GIT_AUTHOR_NAME="T", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="T", GIT_COMMITTER_EMAIL="t@t")
    subprocess.run(["git", "init", "-b", "main", repo_dir], check=True, capture_output=True, env=env)
    md_path = os.path.join(repo_dir, "NOTES.md")
    with open(md_path, "w") as f:
        f.write("hello\n")
    subprocess.run(["git", "-C", repo_dir, "add", "NOTES.md"], check=True, capture_output=True, env=env)
    subprocess.run(["git", "-C", repo_dir, "commit", "-m", "add notes"], check=True, capture_output=True, env=env)
    result = subprocess.run(["git", "-C", repo_dir, "rev-parse", "HEAD"], check=True, capture_output=True, text=True, env=env)
    sha = result.stdout.strip()
    return repo_dir, sha


def test_new_branch_push_fires_block(template_text):
    """New-branch push (REMOTE_SHA=zeros) must NOT bypass detection — Block exits 1."""
    context = {
        "{{rule_description}}": "no .md files",
        "{{detection_pattern}}": 'grep -q \\.md$ "$diff_file"',
        "{{response_style}}": "Block",
        "{{warning_message}}": "md file detected",
    }
    rendered = render(template_text, context)

    with tempfile.NamedTemporaryFile(suffix=".sh", mode="w", delete=False) as f:
        f.write(rendered)
        hook_path = f.name
    os.chmod(hook_path, 0o755)

    repo_dir, local_sha = _make_git_repo_with_md_commit()
    zeros = "0000000000000000000000000000000000000000"
    stdin_line = f"refs/heads/my-branch {local_sha} refs/heads/my-branch {zeros}\n"

    try:
        result = subprocess.run(
            [hook_path, "origin", "git@example.com:repo.git"],
            input=stdin_line,
            capture_output=True,
            text=True,
            cwd=repo_dir,
        )
        if result.returncode == 1:
            print("PASS new_branch_push_fires_block: Block fired on new-branch push (exit 1)")
            return True
        print(
            f"FAIL new_branch_push_fires_block: expected exit 1, got {result.returncode}\n"
            f"  stdout: {result.stdout!r}\n  stderr: {result.stderr!r}"
        )
        return False
    finally:
        os.unlink(hook_path)
        import shutil
        shutil.rmtree(repo_dir, ignore_errors=True)


def test_new_branch_push_noop_when_no_violation(template_text):
    """New-branch push where detection pattern does NOT match must exit 0 (no false positive)."""
    context = {
        "{{rule_description}}": "no .rs files",
        "{{detection_pattern}}": 'grep -q \\.rs$ "$diff_file"',
        "{{response_style}}": "Block",
        "{{warning_message}}": "rs file detected",
    }
    rendered = render(template_text, context)

    with tempfile.NamedTemporaryFile(suffix=".sh", mode="w", delete=False) as f:
        f.write(rendered)
        hook_path = f.name
    os.chmod(hook_path, 0o755)

    repo_dir, local_sha = _make_git_repo_with_md_commit()
    zeros = "0000000000000000000000000000000000000000"
    stdin_line = f"refs/heads/my-branch {local_sha} refs/heads/my-branch {zeros}\n"

    try:
        result = subprocess.run(
            [hook_path, "origin", "git@example.com:repo.git"],
            input=stdin_line,
            capture_output=True,
            text=True,
            cwd=repo_dir,
        )
        if result.returncode == 0:
            print("PASS new_branch_push_noop: no violation on new-branch push — exit 0")
            return True
        print(
            f"FAIL new_branch_push_noop: expected exit 0, got {result.returncode}\n"
            f"  stdout: {result.stdout!r}\n  stderr: {result.stderr!r}"
        )
        return False
    finally:
        os.unlink(hook_path)
        import shutil
        shutil.rmtree(repo_dir, ignore_errors=True)


def test_warning_message_shell_injection_safe(template_text):
    """R2: warning_message containing command substitution must be stored in a variable.

    Asserts:
      - The rendered file contains the _WARN_MSG= assignment pattern.
      - The literal $(echo PWNED) appears as data inside a quoted string, not as a
        bare statement that would be evaluated by the shell.
    """
    injection_payload = "$(echo PWNED)"
    context = {
        "{{rule_description}}": "test rule",
        "{{detection_pattern}}": "false",
        "{{response_style}}": "Block",
        "{{warning_message}}": injection_payload,
    }
    rendered = render(template_text, context)

    # Must assign to a variable first (R2 fix)
    if '_WARN_MSG=' not in rendered:
        print("FAIL shell_injection_safe: rendered script missing '_WARN_MSG=' assignment")
        return False

    # The payload must appear inside a quoted string assignment, not as a bare statement
    expected_assignment = f'_WARN_MSG="{injection_payload}"'
    if expected_assignment not in rendered:
        print(
            f"FAIL shell_injection_safe: expected quoted assignment "
            f"'{expected_assignment}' not found in rendered script"
        )
        return False

    # The printf must reference $_ WARN_MSG variable, not the raw payload
    if f'printf \'rule-enforcer [%s]: %s\\n\' "$HOOK_STYLE" "{injection_payload}"' in rendered:
        print(
            "FAIL shell_injection_safe: raw payload appears unquoted in printf — "
            "variable indirection not applied"
        )
        return False

    print(
        "PASS shell_injection_safe: warning_message with command-sub stored in "
        "_WARN_MSG variable, not passed directly to printf"
    )
    return True


def run_tests():
    """Run all tests. Return exit 0 on GREEN, exit 1 on RED."""
    print("=" * 60)
    print("Pre-push rule-enforcer template tests")
    print("=" * 60)

    template_ok, template_text = test_template_exists()
    marker_ok = test_version_marker_exists()

    if not template_ok or not marker_ok:
        print("\nRED: required files missing — this is expected before implementation.")
        print(
            "Create pre-push-rule-enforcer.sh.j2 and "
            "tcs-helper-rule-enforcer-version to turn GREEN."
        )
        sys.exit(1)

    rendered_block = render(template_text, SAMPLE_CONTEXT_BLOCK)
    rendered_nudge = render(template_text, SAMPLE_CONTEXT_NUDGE)

    results = []

    # Shebang + pipefail for both renders
    results.append(test_shebang(rendered_block, "Block"))
    results.append(test_shebang(rendered_nudge, "Nudge"))
    results.append(test_pipefail(rendered_block, "Block"))
    results.append(test_pipefail(rendered_nudge, "Nudge"))

    # Response style exit code branches
    results.append(test_block_exits(rendered_block))
    results.append(test_nudge_exits(rendered_nudge))

    # shellcheck (optional — skip if not installed)
    results.append(test_shellcheck(rendered_block, "Block"))
    results.append(test_shellcheck(rendered_nudge, "Nudge"))

    # New-branch push: REMOTE_SHA=zeros must not bypass detection
    results.append(test_new_branch_push_fires_block(template_text))
    results.append(test_new_branch_push_noop_when_no_violation(template_text))

    # R2: shell injection via warning_message must be neutralised by variable indirection
    results.append(test_warning_message_shell_injection_safe(template_text))

    passed = sum(1 for r in results if r)
    total = len(results)

    print("-" * 60)
    print(f"Results: {passed}/{total} passed")

    if passed == total:
        print("GREEN")
        sys.exit(0)
    else:
        print("RED")
        sys.exit(1)


if __name__ == "__main__":
    run_tests()
