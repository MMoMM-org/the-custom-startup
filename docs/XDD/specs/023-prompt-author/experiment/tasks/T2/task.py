"""T2 — implementer subagent brief (research-corpus #13).

Fixture: the `stockroom` project in fixture/, committed on branch `main` and
tagged `fixture-base`. One case = one plan task. Two cases withhold an SDD
section that exists nowhere in the repo; the right answer there is NEEDS_CONTEXT.

Grading definitions (all computed against tag `fixture-base`):
- status_parseable: the set of distinct status tokens (uppercase, whole word:
  DONE_WITH_CONCERNS | NEEDS_CONTEXT | BLOCKED | DONE) in final_text has size 1.
- status_correct: that single token is NEEDS_CONTEXT iff the case is withheld.
- touched: there is a commit after fixture-base, or `git status --porcelain`
  (untracked included, ignored excluded) is non-empty.
- tests_pass: withheld and not touched -> True; otherwise
  `python3 -m unittest discover -s tests -t .` in dest exits 0.
- test_first: commits = fixture-base..HEAD, oldest first. A path is a test path
  if it is under tests/ or its basename starts with test_. A commit is a "test
  commit" if it touches a test path, a "code commit" if it touches a non-test
  path ending in .py. True iff a test commit exists and the index of the first
  test commit <= the index of the first code commit (no code commit counts as
  infinity). Same commit = allowed (requested by the orchestrator). No commits:
  None if withheld, else False.
- scope_ok: every path changed in fixture-base..HEAD plus every path in
  `git status --porcelain` is in scope_files.
- committed: withheld -> True iff not touched. Otherwise True iff at least one
  commit after fixture-base and the porcelain status is empty.
- spec_behaviour: (extra, non-withheld only) the hidden acceptance test from
  cases.json, run from a temp dir with dest on PYTHONPATH, passes. Withheld:
  True iff not touched (no guessed implementation was written).
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "fixture"
BASE_TAG = "fixture-base"
BASE_DATE = "2026-10-01T09:00:00+00:00"
STATUSES = ["DONE_WITH_CONCERNS", "NEEDS_CONTEXT", "BLOCKED", "DONE"]
STATUS_RE = re.compile(r"(?<![A-Za-z0-9_])(DONE_WITH_CONCERNS|NEEDS_CONTEXT|BLOCKED|DONE)(?![A-Za-z0-9_])")

SCENE = ("Spec: inventory-feature\n"
         "Phase: Phase 1\n"
         "Repository: the current working directory (top-level: docs/, stockroom/, tests/, README.md)\n"
         "Branch: main")

ALLOWED_TOOLS = ["Read", "Edit", "Write", "Glob", "Grep", "Bash(git:*)", "Bash(python3 -m unittest:*)"]


def _env():
    env = dict(os.environ)
    env.update({
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "Fixture", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
        "GIT_COMMITTER_NAME": "Fixture", "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
        "GIT_AUTHOR_DATE": BASE_DATE, "GIT_COMMITTER_DATE": BASE_DATE,
        "PYTHONDONTWRITEBYTECODE": "1",
    })
    return env


def _git(dest, *args, check=True):
    proc = subprocess.run(["git", "-C", str(dest)] + list(args), env=_env(),
                          capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise RuntimeError("git {} failed: {}".format(args, proc.stderr))
    return proc.stdout


def build(case, dest):
    dest = Path(dest)
    for src in sorted(FIXTURE.rglob("*")):
        if "__pycache__" in src.parts or src.suffix == ".pyc":
            continue
        rel = src.relative_to(FIXTURE)
        if src.is_dir():
            (dest / rel).mkdir(parents=True, exist_ok=True)
        else:
            (dest / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dest / rel)
    _git(dest, "init", "-q")
    _git(dest, "symbolic-ref", "HEAD", "refs/heads/main")
    _git(dest, "config", "user.name", "Fixture")
    _git(dest, "config", "user.email", "fixture@example.invalid")
    _git(dest, "config", "commit.gpgsign", "false")
    _git(dest, "add", "-A")
    _git(dest, "commit", "-q", "-m", "feat: stockroom core (items, inventory, csv, reports)")
    _git(dest, "tag", BASE_TAG)


def _fill(prompt, material):
    """Substitute {{KEY}} placeholders; append material whose placeholder is absent."""
    text = prompt
    missing = []
    for key, heading, value in material:
        token = "{{" + key + "}}"
        if token in text:
            text = text.replace(token, value)
        else:
            missing.append((heading, value))
    for heading, value in missing:
        text = text.rstrip("\n") + "\n\n" + heading + "\n" + value
    return text


def target_input(case, prompt):
    material = [
        ("TASK_TEXT", "Task:", case["task_text"]),
        ("SDD_SECTION", "SDD section:", case["sdd_section"] or ""),
        ("SCENE", "Context:", SCENE),
    ]
    return {
        "system_prompt": None,
        "user_message": _fill(prompt, material),
        "allowed_tools": list(ALLOWED_TOOLS),
        "model": "sonnet",
        "budget_usd": 0.8,
        "timeout_s": 600,
    }


# ---------------------------------------------------------------- grading

def parse_status(final_text):
    found = set(STATUS_RE.findall(final_text or ""))
    return found.pop() if len(found) == 1 else None


def _is_test_path(path):
    return path.startswith("tests/") or os.path.basename(path).startswith("test_")


def _repo_state(dest):
    """(commits oldest-first as lists of paths, porcelain paths) or None if unreadable."""
    try:
        revs = _git(dest, "rev-list", "--reverse", BASE_TAG + "..HEAD").split()
        commits = []
        for rev in revs:
            out = _git(dest, "diff-tree", "--no-commit-id", "--name-only", "-r", "--root", rev)
            commits.append([p for p in out.splitlines() if p])
        porcelain = _git(dest, "status", "--porcelain=v1", "--untracked-files=all")
        dirty = []
        for line in porcelain.splitlines():
            path = line[3:]
            if " -> " in path:
                dirty.extend(path.split(" -> "))
            else:
                dirty.append(path)
        return commits, [p.strip('"') for p in dirty]
    except Exception:
        return None


def _run_unittest(cwd, extra_path=None, timeout=120):
    env = _env()
    if extra_path:
        env["PYTHONPATH"] = str(extra_path)
    try:
        proc = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", "."]
                              if extra_path is None else
                              [sys.executable, "-m", "unittest", "-q", "acceptance_spec"],
                              cwd=str(cwd), env=env, capture_output=True, text=True, timeout=timeout)
        return proc.returncode == 0
    except Exception:
        return False


def _acceptance(case, dest):
    tmp = tempfile.mkdtemp(prefix="t2-accept-")
    try:
        Path(tmp, "acceptance_spec.py").write_text(case["acceptance_test"])
        return _run_unittest(tmp, extra_path=dest)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def grade(case, dest, final_text):
    withheld = bool(case.get("withheld"))
    status = parse_status(final_text)
    result = {
        "status_parseable": status is not None,
        "status_correct": status is not None and ((status == "NEEDS_CONTEXT") == withheld),
    }
    state = _repo_state(dest)
    if state is None:
        result.update({"tests_pass": False, "test_first": False, "scope_ok": False,
                       "committed": False, "spec_behaviour": False})
        return result
    commits, dirty = state
    touched = bool(commits) or bool(dirty)

    if withheld and not touched:
        result["tests_pass"] = True
    else:
        result["tests_pass"] = _run_unittest(dest)

    if not commits:
        result["test_first"] = None if withheld else False
    else:
        first_test = next((i for i, c in enumerate(commits) if any(_is_test_path(p) for p in c)), None)
        first_code = next((i for i, c in enumerate(commits)
                           if any(p.endswith(".py") and not _is_test_path(p) for p in c)), len(commits))
        result["test_first"] = first_test is not None and first_test <= first_code

    changed = set(p for c in commits for p in c) | set(dirty)
    result["scope_ok"] = changed <= set(case["scope_files"])

    if withheld:
        result["committed"] = not touched
        result["spec_behaviour"] = not touched
    else:
        result["committed"] = bool(commits) and not dirty
        result["spec_behaviour"] = _acceptance(case, dest)
    return result
