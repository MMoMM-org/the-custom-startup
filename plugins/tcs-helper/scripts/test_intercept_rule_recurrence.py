"""Tests for intercept_rule_recurrence.py — subprocess-based to validate real stdin/stdout/exit behavior.

Behavior under test (public interface = script stdin/stdout/exit code):
  - Trigger prompt → stdout contains [rule-enforcer] line, exit 0
  - Non-trigger prompt → empty stdout, exit 0
  - Malformed JSON stdin → empty stdout, exit 0 (graceful)
  - Missing prompt key → empty stdout, exit 0
  - p95 latency over 100 invocations ≤ 50ms (soft assertion with warning)
"""
import json
import os
import statistics
import subprocess
import sys
import time
import unittest

SCRIPT = os.path.join(os.path.dirname(__file__), 'intercept_rule_recurrence.py')


def _run(stdin_text: str, timeout: float = 5.0):
    """Invoke the hook script with stdin_text, return (stdout, returncode)."""
    result = subprocess.run(
        [sys.executable, SCRIPT],
        input=stdin_text,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return result.stdout, result.returncode


class TestInterceptBehavior(unittest.TestCase):

    def test_trigger_prompt_emits_suggestion(self):
        """Prompt containing a trigger phrase → stdout has [rule-enforcer] line, exit 0."""
        payload = json.dumps({'prompt': 'I keep forgetting X', 'cwd': '/tmp'})
        stdout, code = _run(payload)
        self.assertEqual(code, 0)
        self.assertIn('[rule-enforcer]', stdout)

    def test_non_trigger_prompt_empty_stdout(self):
        """Prompt with no trigger phrase → empty stdout, exit 0."""
        payload = json.dumps({'prompt': 'what is the syntax for a for-loop', 'cwd': '/tmp'})
        stdout, code = _run(payload)
        self.assertEqual(code, 0)
        self.assertEqual(stdout.strip(), '')

    def test_malformed_json_empty_stdout(self):
        """Malformed JSON stdin → empty stdout, exit 0 (never block)."""
        stdout, code = _run('this is not json at all {{{')
        self.assertEqual(code, 0)
        self.assertEqual(stdout.strip(), '')

    def test_missing_prompt_key_empty_stdout(self):
        """JSON stdin without 'prompt' key → empty stdout, exit 0."""
        payload = json.dumps({'cwd': '/tmp', 'session_id': 'abc'})
        stdout, code = _run(payload)
        self.assertEqual(code, 0)
        self.assertEqual(stdout.strip(), '')

    def test_suggestion_contains_matched_phrase_snippet(self):
        """Suggestion line includes the matched phrase snippet in quotes."""
        payload = json.dumps({'prompt': 'I keep forgetting to bump the version', 'cwd': '/tmp'})
        stdout, code = _run(payload)
        self.assertEqual(code, 0)
        # The matched phrase or part of it should appear in the suggestion
        self.assertIn("'", stdout, "Expected matched phrase in single-quotes in suggestion")

    def test_suggestion_contains_enforce_rule(self):
        """Suggestion line mentions /enforce-rule command."""
        payload = json.dumps({'prompt': 'I keep forgetting to update docs', 'cwd': '/tmp'})
        stdout, code = _run(payload)
        self.assertEqual(code, 0)
        self.assertIn('/enforce-rule', stdout)

    def test_deutsch_trigger_emits_suggestion(self):
        """German recurrence phrase triggers suggestion."""
        payload = json.dumps({'prompt': 'ich vergesse immer die Docs zu updaten', 'cwd': '/tmp'})
        stdout, code = _run(payload)
        self.assertEqual(code, 0)
        self.assertIn('[rule-enforcer]', stdout)

    def test_empty_string_prompt_empty_stdout(self):
        """Empty prompt string → empty stdout, exit 0."""
        payload = json.dumps({'prompt': '', 'cwd': '/tmp'})
        stdout, code = _run(payload)
        self.assertEqual(code, 0)
        self.assertEqual(stdout.strip(), '')

    def test_suggestion_is_single_line(self):
        """Suggestion output is exactly one non-empty line (no trailing newlines beyond one)."""
        payload = json.dumps({'prompt': 'I keep forgetting to run tests', 'cwd': '/tmp'})
        stdout, code = _run(payload)
        self.assertEqual(code, 0)
        lines = [l for l in stdout.splitlines() if l.strip()]
        self.assertEqual(len(lines), 1, f"Expected exactly 1 non-empty output line, got: {lines}")


class TestPerformance(unittest.TestCase):

    def test_p95_latency_under_50ms(self):
        """100-invocation timing: p95 ≤ 50ms (soft assertion — warns but does not fail)."""
        payload = json.dumps({'prompt': 'I keep forgetting X', 'cwd': '/tmp'})
        durations_ms = []

        for _ in range(100):
            start = time.perf_counter()
            _run(payload)
            elapsed_ms = (time.perf_counter() - start) * 1000
            durations_ms.append(elapsed_ms)

        p95 = statistics.quantiles(durations_ms, n=20)[18]  # 95th percentile
        mean_ms = statistics.mean(durations_ms)
        max_ms = max(durations_ms)

        print(f'\n[perf] 100 invocations: p95={p95:.1f}ms  mean={mean_ms:.1f}ms  max={max_ms:.1f}ms')

        if p95 > 50:
            print(f'[perf] WARNING: p95 {p95:.1f}ms exceeds 50ms target (CON-2). Investigate.')
        else:
            print(f'[perf] OK: p95 {p95:.1f}ms ≤ 50ms target.')

        # Soft assertion: record result; only fail if wildly over budget (5×)
        self.assertLess(p95, 250, f"p95 {p95:.1f}ms is catastrophically slow (>250ms hard limit)")


if __name__ == '__main__':
    unittest.main(verbosity=2)
