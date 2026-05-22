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
