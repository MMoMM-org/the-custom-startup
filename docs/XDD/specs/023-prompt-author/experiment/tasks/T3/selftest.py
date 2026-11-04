"""T3 selftest: build every case, grade hand-written good and bad reviews. No model calls.

Run: python3 -I tasks/T3/selftest.py
"""
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("t3_task", HERE / "task.py")
task = importlib.util.module_from_spec(spec)
spec.loader.exec_module(task)
CASES = json.loads((HERE / "cases.json").read_text())


def good_outputs(c):
    """Several accepted formats, all citing the planted bug plus a harmless low finding."""
    f, (s, e) = c["planted"]["file"], c["planted"]["lines"]
    d = c["planted"]["description"]
    return {
        "headings": (
            "Reviewed {b}..{h} (2 commits). The uncommitted file in the working tree is outside the range "
            "and was not reviewed.\n\n## Findings\n\n### 1. Defect in `{f}`\n- **Location:** `{f}:{s}`\n"
            "- **Severity:** High\n- **Confidence:** 0.9\n\n{d}\n\nSimilar pattern also at {f}:{s2} (fine).\n\n"
            "### 2. Naming\n- **Location:** README.md:3\n- **Severity:** Low\n- **Confidence:** medium\n\n"
            "Wording.\n\n## Summary\n- High: 1\n- Low: 1\nOverall confidence: high\n").format(
                b=c["base"], h=c["head"], f=f, s=s, s2=s + 1, d=d),
        "table": (
            "| # | Location | Severity | Confidence | Issue |\n|---|---|---|---|---|\n"
            "| 1 | {f}:{s}-{e} | HIGH | 85% | {d} |\n| 2 | README.md:4 | low | low | wording |\n\n"
            "| Severity | Count |\n|---|---|\n| High | 1 |\n").format(f=f, s=s, e=e, d=d),
        "json": "```json\n" + json.dumps({"findings": [
            {"file": f, "line": s, "severity": "high", "confidence": 0.8, "issue": d},
            {"location": "README.md:2", "severity": "low", "confidence": "low", "issue": "nit"}]}) + "\n```\n",
        "bullets": (
            "1. **[HIGH]** `{f}` line {s} — {d} (confidence: high)\n"
            "2. **[LOW]** README.md:2 — wording nit (confidence: low)\n").format(f=f, s=s, d=d),
    }


def bad_outputs(c):
    f, (s, e) = c["planted"]["file"], c["planted"]["lines"]
    tm = c["teammate"]["path"]
    return {
        "prose_no_labels": "Looks mostly fine. In {f}:{s} there is a problem worth fixing.".format(f=f, s=s),
        "missing_confidence": ("- {f}:{s} — Severity: High — bug\n- README.md:2 — Severity: Low — nit "
                               "(confidence: low)\n").format(f=f, s=s),
        "flags_teammate": ("- {f}:{s} — Severity: High — Confidence: high — bug\n"
                           "- {tm}:5 — Severity: Critical — Confidence: high — dangerous code\n").format(f=f, s=s, tm=tm),
        "wrong_location": "- README.md:1 — Severity: Low — Confidence: low — wording\n",
        "no_findings": "No issues found. LGTM.",
    }


EXPECT_BAD = {  # criterion each bad output must fail
    "prose_no_labels": "findings_structured",
    "missing_confidence": "findings_structured",
    "flags_teammate": "teammate_not_flagged",
    "wrong_location": "planted_bug_located",
    "no_findings": "findings_structured",
}


def parser_unit_checks():
    pf = task.parse_findings
    # summary count lines and an overall-confidence line are not findings
    fs = pf("- a.py:3 — Severity: High — Confidence: high — x\n\n## Summary\n- High: 1\n- Medium: 0\nConfidence overall: high\n")
    assert len(fs) == 1, fs
    # a continuation mention stays in the same finding
    fs = pf("### H1\n**Location:** a.py:10\n**Severity:** high\n**Confidence:** high\n\nSee also a.py:40 for context.\n")
    assert len(fs) == 1 and len(fs[0]["locs"]) == 2, fs
    # file + line labels
    fs = pf("- **File:** tasklog/x.py\n  **Line:** 12\n  **Severity:** Medium\n  **Confidence:** 70%\n")
    assert len(fs) == 1 and fs[0]["locs"] == [("tasklog/x.py", 12, 12)], fs
    # git-diff style path prefixes and ranges
    fs = pf("[CRITICAL] b/tasklog/x.py:5-9 issue. Confidence: certain")
    assert fs and fs[0]["locs"][0] == ("tasklog/x.py", 5, 9), fs
    # unparseable JSON does not swallow the text
    fs = pf("{not json} \n- a.py:1 — Severity: low — Confidence: low")
    assert len(fs) == 1, fs
    # emoji severity headings; uncommitted-file note does not count as a finding location
    fs = pf("### 🔴 High — off-by-one (`t/p.py:23`)\n**Confidence:** High\n\nfix it\n\n"
            "### 🟡 Low — doc (`t/p.py:13`)\nConfidence: medium\n\nNot reviewed: t/sync.py (uncommitted).\n")
    assert [(f["locs"][0], f["sev"], f["conf"]) for f in fs] == [
        (("t/p.py", 23, 23), True, True), (("t/p.py", 13, 13), True, True)], fs
    # consecutive single-line findings without blank lines
    fs = pf("**H1** `a.py:3` | Severity: High | Confidence: 0.9\n**L1** `b.md:7` | Severity: Low | Confidence: 0.5\n")
    assert len(fs) == 2, fs
    # malformed input never raises
    for junk in (None, "", "|||\n|---|\n| x |", "```json\n[1, {\"severity\": null}]\n```", "#" * 500):
        task.parse_findings(junk)
    print("parser unit checks: ok")


def template_checks(c):
    ti = task.target_input(c, "Review {{BASE}}..{{HEAD}} now.")
    assert ti["user_message"] == "Review {}..{} now.".format(c["base"], c["head"]), ti["user_message"]
    ti2 = task.target_input(c, "Review the range.")
    assert ti2["user_message"].endswith("Range: {}..{}".format(c["base"], c["head"]))
    assert ti["system_prompt"] is None and ti["model"] == "sonnet" and "Bash(git diff:*)" in ti["allowed_tools"]
    print("template fill: ok")


def main():
    assert len(CASES) == 10 and len({c["id"] for c in CASES}) == 10
    parser_unit_checks()
    template_checks(CASES[0])
    root = Path(tempfile.mkdtemp(prefix="t3-selftest-"))
    failures = 0
    try:
        for c in CASES:
            dest = root / c["id"]
            dest.mkdir()
            task.build(c, str(dest))
            # planted lines point at the snippet in the head version
            lines = (dest / c["planted"]["file"]).read_text().splitlines()
            s, e = c["planted"]["lines"]
            assert c["planted"]["start_text"] in lines[s - 1] and c["planted"]["end_text"] in lines[e - 1], c["id"]
            # range has 1-2 commits, teammate change is uncommitted and outside the range
            n = task._git(dest, "rev-list", "--count", "{}..{}".format(c["base"], c["head"])).strip()
            assert n in ("1", "2"), n
            changed = task._git(dest, "diff", "--name-only", "{}..{}".format(c["base"], c["head"])).split()
            assert c["teammate"]["path"] not in changed and c["planted"]["file"] in changed
            assert c["teammate"]["path"] in task._git(dest, "status", "--porcelain", "--untracked-files=all")
            assert task._git(dest, "rev-parse", "--abbrev-ref", "HEAD").strip() == c["head"]
            # base tests still run (fixture sanity)
            subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", "."],
                           cwd=str(dest), check=True, capture_output=True,
                           env=dict(task._env(), PYTHONDONTWRITEBYTECODE="1"))

            problems = []
            for name, text in good_outputs(c).items():
                g = task.grade(c, str(dest), text)
                if not all(g.values()):
                    problems.append("good/{} -> {}".format(name, g))
            for name, text in bad_outputs(c).items():
                g = task.grade(c, str(dest), text)
                if g[EXPECT_BAD[name]] is not False:
                    problems.append("bad/{} did not fail {} -> {}".format(name, EXPECT_BAD[name], g))
            # a reviewer that touched the repo
            (dest / "README.md").write_text("edited\n")
            g = task.grade(c, str(dest), good_outputs(c)["table"])
            if g["repo_unchanged"] is not False:
                problems.append("edited repo not detected")
            print("{:24s} {}".format(c["id"], "OK" if not problems else problems))
            failures += bool(problems)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    print("SELFTEST", "FAILED ({})".format(failures) if failures else "OK")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
