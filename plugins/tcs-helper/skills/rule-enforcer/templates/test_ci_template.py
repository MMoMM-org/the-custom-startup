#!/usr/bin/env python3
"""
Test: CI auto-bump-style template rendering.

Tests for:
  - templates/ci-auto-bump-style.yml.j2
  - templates/ci-auto-bump-style.sh.j2

Uses stdlib only — no jinja2 dependency.
Renders via str.replace() with a sample context dict.

Run:
  python3 plugins/tcs-helper/skills/rule-enforcer/templates/test_ci_template.py
"""

import os
import subprocess
import sys
import tempfile

TEMPLATES_DIR = os.path.dirname(os.path.abspath(__file__))

SAMPLE_CONTEXT = {
    "{{rule_description}}": "CHANGELOG must be touched when feat: commits land",
    "{{workflow_name}}": "enforce-changelog",
    "{{script_name}}": "enforce-changelog",
    "{{detection_logic}}": (
        "# Detect: check if CHANGELOG.md was modified\n"
        "changelog_changed=0\n"
        'while IFS= read -r f; do\n'
        '  case "$f" in\n'
        '    CHANGELOG.md) changelog_changed=1 ;;\n'
        '  esac\n'
        "done <<EOF\n"
        "$changed_files\n"
        "EOF\n"
        'if [ "$changelog_changed" -eq 0 ]; then\n'
        '  printf \'Rule violated: CHANGELOG must be touched when feat: commits land\\n\' >&2\n'
        "  exit 1\n"
        "fi"
    ),
    "{{remediation_logic}}": (
        "# Remediation: append placeholder line to CHANGELOG\n"
        "printf '## Unreleased\\n' >> CHANGELOG.md"
    ),
}


def render(template_text, context):
    """Render template by replacing all placeholder keys with context values."""
    result = template_text
    for placeholder, value in context.items():
        result = result.replace(placeholder, value)
    return result


def load_template(filename):
    path = os.path.join(TEMPLATES_DIR, filename)
    if not os.path.exists(path):
        return None, path
    with open(path) as f:
        return f.read(), path


def test_templates_exist():
    """RED gate: both template files must exist."""
    yml_text, yml_path = load_template("ci-auto-bump-style.yml.j2")
    sh_text, sh_path = load_template("ci-auto-bump-style.sh.j2")
    missing = []
    if yml_text is None:
        missing.append(yml_path)
    if sh_text is None:
        missing.append(sh_path)
    if missing:
        for p in missing:
            print(f"MISSING: {p}")
        return False, yml_text, sh_text
    return True, yml_text, sh_text


def test_yaml_structure(rendered_yaml):
    """Assert rendered YAML has top-level keys: name, on, jobs."""
    try:
        import yaml
        data = yaml.safe_load(rendered_yaml)
        missing_keys = [k for k in ("name", "on", "jobs") if k not in data]
        if missing_keys:
            print(f"FAIL yaml_structure: missing top-level keys {missing_keys}")
            return False
        print("PASS yaml_structure: top-level keys name/on/jobs present")
        return True
    except ImportError:
        # Fallback: manual key check without PyYAML
        print("WARNING: PyYAML not available — falling back to manual key check")
        ok = True
        for key in ("name:", "on:", "jobs:"):
            if key not in rendered_yaml:
                print(f"FAIL yaml_structure (manual): '{key}' not found in rendered YAML")
                ok = False
        if ok:
            print("PASS yaml_structure (manual): name:/on:/jobs: present")
        return ok
    except Exception as e:
        print(f"FAIL yaml_structure: yaml.safe_load raised {e}")
        return False


def test_yaml_parses(rendered_yaml):
    """Assert rendered YAML parses without error."""
    try:
        import yaml
        yaml.safe_load(rendered_yaml)
        print("PASS yaml_parses: yaml.safe_load succeeded")
        return True
    except ImportError:
        print("SKIP yaml_parses: PyYAML not available")
        return True
    except Exception as e:
        print(f"FAIL yaml_parses: {e}")
        return False


def test_sh_shebang(rendered_sh):
    """Assert rendered .sh starts with #!/bin/bash."""
    first_line = rendered_sh.splitlines()[0] if rendered_sh else ""
    if first_line == "#!/bin/bash":
        print("PASS sh_shebang: #!/bin/bash present")
        return True
    print(f"FAIL sh_shebang: first line is '{first_line}', expected '#!/bin/bash'")
    return False


def test_sh_pipefail(rendered_sh):
    """Assert rendered .sh contains set -uo pipefail."""
    if "set -uo pipefail" in rendered_sh:
        print("PASS sh_pipefail: set -uo pipefail present")
        return True
    print("FAIL sh_pipefail: 'set -uo pipefail' not found")
    return False


def test_shellcheck(rendered_sh):
    """Run shellcheck on rendered .sh — skip cleanly if not available."""
    with tempfile.NamedTemporaryFile(suffix=".sh", mode="w", delete=False) as f:
        f.write(rendered_sh)
        tmp_path = f.name

    try:
        result = subprocess.run(
            ["shellcheck", "-s", "bash", tmp_path],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            print("PASS shellcheck: rendered .sh is shellcheck clean")
            return True
        else:
            print(f"FAIL shellcheck: returncode={result.returncode}")
            if result.stdout:
                print(result.stdout)
            if result.stderr:
                print(result.stderr)
            return False
    except FileNotFoundError:
        print("SKIP shellcheck: shellcheck binary not found")
        return True
    finally:
        os.unlink(tmp_path)


def run_tests():
    """Run all tests. Return (passed, total, skipped)."""
    print("=" * 60)
    print("CI template rendering tests")
    print("=" * 60)

    files_ok, yml_text, sh_text = test_templates_exist()
    if not files_ok:
        print("\nRED: template files missing — this is expected before implementation.")
        print("Create ci-auto-bump-style.yml.j2 and ci-auto-bump-style.sh.j2 to turn GREEN.")
        sys.exit(1)

    rendered_yml = render(yml_text, SAMPLE_CONTEXT)
    rendered_sh = render(sh_text, SAMPLE_CONTEXT)

    results = []
    results.append(test_yaml_parses(rendered_yml))
    results.append(test_yaml_structure(rendered_yml))
    results.append(test_sh_shebang(rendered_sh))
    results.append(test_sh_pipefail(rendered_sh))
    results.append(test_shellcheck(rendered_sh))

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
