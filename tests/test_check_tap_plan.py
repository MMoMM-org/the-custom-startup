"""scripts/ci/check-tap-plan.py — every planned TAP test must report a result (#178).

The three fixtures under tests/fixtures/tap/ are verbatim bats 1.13.0 output,
not hand-written TAP, so the parser is tested against the format it reads in
CI. abort.tap holds the case this exists for: a failing `setup_file` whose
`not ok 1 setup_file failed` takes the first test's number, after which that
file's remaining tests (#2, #3, one of them a skip) emit nothing.
"""

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "ci" / "check-tap-plan.py"
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "tap"


def run(tap_path, summary=None):
    env = {"PATH": "/usr/bin:/bin"}
    if summary is not None:
        env["GITHUB_STEP_SUMMARY"] = str(summary)
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(tap_path)],
        capture_output=True, text=True, env=env,
    )


def write_tap(tmp_path, text):
    path = tmp_path / "run.tap"
    path.write_text(text, encoding="utf-8")
    return path


def test_a_complete_run_with_a_skip_passes_and_counts_the_skip_separately():
    r = run(FIXTURES / "clean-with-skip.tap")
    assert r.returncode == 0, r.stdout
    assert r.stdout.splitlines()[0] == (
        "plan 2 · executed 1 (passed 1, failed 0) · skipped 1 · missing 0"
    )


def test_a_failing_test_is_counted_but_is_not_this_checks_concern():
    # The bats step itself fails the job for a `not ok`; this check only
    # answers whether every planned test reported.
    r = run(FIXTURES / "failing.tap")
    assert r.returncode == 0, r.stdout
    assert "executed 3 (passed 2, failed 1) · skipped 1 · missing 0" in r.stdout


def test_a_setup_file_abort_fails_and_names_the_unreported_tests():
    r = run(FIXTURES / "abort.tap")
    assert r.returncode == 1
    assert r.stdout.splitlines()[0] == (
        "plan 7 · executed 4 (passed 2, failed 2) · skipped 1 · missing 2"
    )
    assert "::error::2 planned test(s) never reported a result: #2-3" in r.stdout


def test_the_check_agrees_with_bats_own_executed_warning():
    # The expected value comes from bats' own trailer in the same fixture,
    # not from this parser: bats counts every reported line (skips included)
    # as executed, so its shortfall is exactly the unreported tests.
    text = (FIXTURES / "abort.tap").read_text(encoding="utf-8")
    m = re.search(r"# bats warning: Executed (\d+) instead of expected (\d+) tests", text)
    assert m, "fixture lost its bats trailer"
    shortfall = int(m.group(2)) - int(m.group(1))
    r = run(FIXTURES / "abort.tap")
    assert "missing %d" % shortfall in r.stdout


def test_output_lines_prefixed_by_bats_are_not_counted_as_results(tmp_path):
    tap = write_tap(tmp_path, "1..1\nnot ok 1 x\n# ok 2 printed by the test\n#   ok 3\n")
    r = run(tap)
    assert r.returncode == 0, r.stdout
    assert "executed 1 (passed 0, failed 1)" in r.stdout


def test_a_missing_plan_line_fails(tmp_path):
    text = (FIXTURES / "clean-with-skip.tap").read_text(encoding="utf-8")
    r = run(write_tap(tmp_path, text.replace("1..2\n", "", 1)))
    assert r.returncode == 1
    assert "::error::no TAP plan line (1..N) found" in r.stdout


def test_a_duplicated_test_number_fails(tmp_path):
    text = (FIXTURES / "clean-with-skip.tap").read_text(encoding="utf-8")
    r = run(write_tap(tmp_path, text.replace("1..2\n", "1..3\n", 1) + "ok 2 again\n"))
    assert r.returncode == 1
    assert "reported twice: #2" in r.stdout
    assert "missing 1" in r.stdout


def test_the_summary_line_is_appended_to_the_github_step_summary(tmp_path):
    summary = tmp_path / "summary.md"
    summary.write_text("existing\n", encoding="utf-8")
    run(FIXTURES / "clean-with-skip.tap", summary=summary)
    assert summary.read_text(encoding="utf-8") == (
        "existing\n**clean-with-skip.tap**: "
        "plan 2 · executed 1 (passed 1, failed 0) · skipped 1 · missing 0\n"
    )
