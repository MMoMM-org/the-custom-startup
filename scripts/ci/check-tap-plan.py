#!/usr/bin/env python3
"""
scripts/ci/check-tap-plan.py — fail when a TAP stream reports fewer results than it planned.

Written for #178. A bats `setup_file` failure aborts the rest of its file, and
those tests emit no TAP line at all. In run 37360478496 the plan said 1..1187,
the log showed one `not ok`, and 35 tests had simply vanished. bats does print
`# bats warning: Executed N instead of expected M tests`, but in a 1500-line
log that line is easy to miss, and a reader counting `ok` lines also counts
skips as passes. This check states the numbers on one line and fails the job
when any planned test went unreported.

Usage: check-tap-plan.py <tap-file>

Prints:  plan N · executed E (passed P, failed F) · skipped S · missing M
and appends the same line to $GITHUB_STEP_SUMMARY when that is set.

Exit 1 (with a GitHub `::error::` annotation) when:
  - there is no `1..N` plan line,
  - a planned test number has no result line (missing numbers are listed as ranges),
  - a test number is reported twice.

Only lines starting at column 0 with `ok <n>` / `not ok <n>` count as results.
bats prefixes every line of a failing test's output with `# `, so test output
cannot be mistaken for a result.
"""

import os
import re
import sys

PLAN = re.compile(r"^1\.\.(\d+)\s*$")
RESULT = re.compile(r"^(not ok|ok) (\d+)(?: |$)(.*)$")
SKIP = re.compile(r"#\s*skip\b", re.IGNORECASE)


def tally(lines):
    plan = None
    seen = {}
    duplicates = []
    passed = failed = skipped = 0
    for line in lines:
        if plan is None:
            m = PLAN.match(line)
            if m:
                plan = int(m.group(1))
                continue
        m = RESULT.match(line)
        if not m:
            continue
        number = int(m.group(2))
        if number in seen:
            duplicates.append(number)
        seen[number] = True
        if m.group(1) == "not ok":
            failed += 1
        elif SKIP.search(m.group(3)):
            skipped += 1
        else:
            passed += 1
    missing = [] if plan is None else [n for n in range(1, plan + 1) if n not in seen]
    return {
        "plan": plan,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "missing": missing,
        "duplicates": duplicates,
    }


def ranges(numbers):
    out, start, prev = [], None, None
    for n in numbers:
        if start is None:
            start = prev = n
        elif n == prev + 1:
            prev = n
        else:
            out.append(str(start) if start == prev else "%d-%d" % (start, prev))
            start = prev = n
    if start is not None:
        out.append(str(start) if start == prev else "%d-%d" % (start, prev))
    return ", ".join(out)


def summary_line(t):
    return "plan %s · executed %d (passed %d, failed %d) · skipped %d · missing %d" % (
        t["plan"] if t["plan"] is not None else "?",
        t["passed"] + t["failed"],
        t["passed"],
        t["failed"],
        t["skipped"],
        len(t["missing"]),
    )


def main(argv):
    if len(argv) != 2:
        print("usage: check-tap-plan.py <tap-file>", file=sys.stderr)
        return 2
    with open(argv[1], encoding="utf-8", errors="replace") as fh:
        t = tally(fh.read().splitlines())

    line = summary_line(t)
    print(line)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write("**%s**: %s\n" % (os.path.basename(argv[1]), line))

    problems = []
    if t["plan"] is None:
        problems.append("no TAP plan line (1..N) found")
    if t["missing"]:
        problems.append(
            "%d planned test(s) never reported a result: #%s"
            % (len(t["missing"]), ranges(t["missing"]))
        )
    if t["duplicates"]:
        problems.append("test number(s) reported twice: #%s" % ranges(sorted(set(t["duplicates"]))))
    for p in problems:
        print("::error::%s" % p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
