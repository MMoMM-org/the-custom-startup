#!/usr/bin/env python3
"""Before/after comparison of a plugin's eval suite (spec 023, C4, SDD-ADR-3).

  eval_compare.py run --plugin DIR --case GLOB --base REF --runs N --max-cost-usd X --out DIR
  eval_compare.py compare BEFORE.json AFTER.json --out DIR

`claude plugin eval` compares with- against without-plugin only, so a version
comparison takes two runs. `run` checks out REF in a git worktree under DIR,
runs the suite there (before) and on the working tree (after), each with half
the ceiling, removes the worktree (also on failure) and compares. Every run
gets --ablation none --no-publish --trust-plugin --json and --output-dir under
DIR (and --threshold 0, so exit 1 means a failed run, not a low score); these are
fixed here, never passed through. DIR must be outside any git
work tree unless gitignored.

`compare` reads two `plugin eval --json` files and writes report.md and
report.json in prompt_eval.py's shape: per-grader pass rates, all-pass, the
paired difference over cases with its CI, the sign test, cost.

  - Only the with-plugin arm is compared; a without arm is ignored and noted.
  - Graders marked withOnly (plugin-fired indicators) are not part of the
    score: they are left out and noted. A grader with scored false counts as
    no result for that run.
  - An llm grader whose verdict is missing is a judge error; llm graders stay
    not_validated (labelling needs prompt_eval.py's per-run files).

Exit: 0 done | 1 case sets differ, unreadable input, refused out dir or ref,
plugin eval failed, error rate above 20% | 2 cost ceiling hit in either run
(partial report). Stdlib only, Python 3.8+.
"""
import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from prompt_eval_stats import (  # noqa: E402  (after the sys.path line above)
    build_report, out_dir_problem, render_markdown, write_report)

EXIT_OK, EXIT_INVALID, EXIT_CEILING = 0, 1, 2
SCHEMA_VERSION = 1
SIDES = ("before", "after")
WORKTREE_DIR = "base-worktree"
# Files run writes into --out; a reused --out loses only these.
RUN_OUTPUTS = ("before.json", "after.json", "before", "after", "before.log", "after.log",
               "report.json", "report.md")
PLUGIN_EVAL_TIMEOUT_S = 3600
POSIX = os.name == "posix"


class Refused(Exception):
    pass


# ------------------------------------------------------------------ compare

def load_result(path):
    """A `plugin eval --json` result, or Refused naming the file."""
    try:
        with open(str(path), "rb") as handle:
            data = json.loads(handle.read().decode("utf-8-sig", errors="replace"))
    except (OSError, ValueError) as exc:
        raise Refused("cannot read {} ({})".format(path, type(exc).__name__))
    if not isinstance(data, dict) or not isinstance(data.get("cases"), list):
        raise Refused("{} is not a plugin eval --json result (no cases list)".format(path))
    if data.get("schemaVersion") != SCHEMA_VERSION:
        raise Refused("{}: schemaVersion {!r} is not supported (expected {})".format(
            path, data.get("schemaVersion"), SCHEMA_VERSION))
    return data


def runs_of(data, version, ignored):
    """Per-run results in build_report's shape, from the with arm of each case.
    IGNORED collects what was left out: {"with_only": set, "arms": set}."""
    results, validation, runs = [], {}, 0
    for case in data["cases"]:
        if not isinstance(case, dict) or not isinstance(case.get("name"), str):
            continue
        types = {g.get("name"): g.get("type") for g in case.get("graders") or []
                 if isinstance(g, dict)}
        arms = case.get("arms") or {}
        ignored["arms"].update(a for a in arms if a != "with")
        with_runs = arms.get("with") or []
        runs = max(runs, len(with_runs))
        for number, run in enumerate(with_runs, 1):
            criteria = {}
            for grader in run.get("graders") or []:
                name = grader.get("name")
                if grader.get("withOnly"):
                    ignored["with_only"].add(name)
                    continue
                kind = "judge" if types.get(name) == "llm" else "deterministic"
                validation.setdefault(name, "not_validated" if kind == "judge" else "not_run")
                passed = grader.get("passed")
                decided = isinstance(passed, bool) and grader.get("scored", True) is not False
                criteria[name] = {"kind": kind, "result": passed if decided else None,
                                  "judge_error": kind == "judge" and not decided
                                  and grader.get("scored", True) is not False}
            results.append({"version": version, "case": case["name"], "run": number,
                            "errored": run.get("error") is not None, "criteria": criteria})
    return results, validation, runs


def _case_names(data):
    return {c["name"] for c in data["cases"] if isinstance(c, dict)
            and isinstance(c.get("name"), str)}


def compare(before_path, after_path, out, max_cost_usd=None, refs=None):
    """Write the report for two plugin-eval results; returns the exit code."""
    problem = out_dir_problem(out)
    if problem:
        raise Refused(problem)
    data = {"a": load_result(before_path), "b": load_result(after_path)}
    paths = {"a": before_path, "b": after_path}
    refs = refs or {}
    ignored = {"with_only": set(), "arms": set()}
    results, validation, runs = [], {}, 0
    for version in ("a", "b"):
        mine, states, n = runs_of(data[version], version, ignored)
        results += mine
        for name, state in states.items():
            validation.setdefault(name, state)
        runs = max(runs, n)

    notes = []
    if ignored["with_only"]:
        notes.append("with-only graders ignored (plugin-fired indicators, not part of the "
                     "score): {}".format(", ".join(sorted(ignored["with_only"]))))
    if ignored["arms"]:
        notes.append("arms other than with ignored ({}): the comparison is before against "
                     "after on the with-plugin arm".format(", ".join(sorted(ignored["arms"]))))
    only_before = sorted(_case_names(data["a"]) - _case_names(data["b"]))
    only_after = sorted(_case_names(data["b"]) - _case_names(data["a"]))
    mismatch = None
    if only_before or only_after:
        mismatch = "case sets differ (only in before: {}; only in after: {})".format(
            ", ".join(only_before) or "none", ", ".join(only_after) or "none")
        notes.append(mismatch)

    versions = {}
    for version, side in (("a", "before"), ("b", "after")):
        versions[version] = {"path": str(paths[version]), "side": side,
                             "suite": (data[version].get("suite") or {}).get("root")}
        if version in refs:
            versions[version]["ref"] = refs[version]
    claude_version = data["b"].get("claudeVersion") or data["a"].get("claudeVersion")
    partial = any(bool(data[v].get("partial")) for v in data)
    meta = {
        "title": "eval_compare report",
        "versions": versions,
        "target": "claude plugin eval (Claude Code {})".format(claude_version or "unknown"),
        "judge": {"id": "plugin eval llm graders", "source": "plugin eval --judge-model "
                                                            "default"},
        "author": None, "runs": runs, "kind": "plugin-eval",
        "label": "plugin eval, with-plugin arm, before vs after",
        "judge_validation": validation,
        "cost_usd": round(sum(float(data[v].get("costUsd") or 0.0) for v in data), 6),
        "max_cost_usd": max_cost_usd, "partial": partial,
        "case_ids": sorted(_case_names(data["a"]) | _case_names(data["b"])), "notes": notes,
    }
    report = build_report(meta, results)
    if mismatch:
        report.update({"verdict": None, "recommendation": None, "verdict_withheld": mismatch,
                       "case_mismatch": {"only_before": only_before, "only_after": only_after}})
    Path(out).mkdir(parents=True, exist_ok=True)
    write_report(out, report)
    print("{}: {}".format(Path(out) / "report.md", render_markdown(report).splitlines()[1]))
    if mismatch:
        print("eval_compare.py: {}".format(mismatch), file=sys.stderr)
        return EXIT_INVALID
    if partial:
        return EXIT_CEILING
    if report["verdict"] is None:
        print("eval_compare.py: {}; no verdict".format(report.get("verdict_withheld")),
              file=sys.stderr)
        return EXIT_INVALID
    return EXIT_OK


# ------------------------------------------------------------------ run

def _git(root, *args):
    return subprocess.run(["git", "-C", str(root)] + list(args), capture_output=True,
                          encoding="utf-8", errors="replace", timeout=60)


def _run_logged(cmd, cwd, log_path, timeout_s=PLUGIN_EVAL_TIMEOUT_S):
    """Return code of CMD with stdout and stderr in LOG_PATH; on timeout or
    interrupt the child's whole process group is killed."""
    with open(str(log_path), "w", encoding="utf-8") as log:
        try:
            proc = subprocess.Popen(cmd, cwd=str(cwd), stdin=subprocess.DEVNULL, stdout=log,
                                    stderr=subprocess.STDOUT, start_new_session=POSIX)
        except OSError as exc:
            raise Refused("plugin eval could not start ({})".format(type(exc).__name__))
        try:
            return proc.wait(timeout=timeout_s)
        except BaseException:
            if POSIX:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except OSError:
                    proc.kill()
            else:
                proc.kill()
            proc.wait()
            raise


def plugin_eval_cmd(plugin, args, out, side):
    """The fixed plugin eval command; --no-publish and --output-dir are not optional."""
    return ["claude", "plugin", "eval", str(plugin),
            "--case", args.case, "--runs", str(args.runs),
            "--ablation", "none", "--no-publish", "--trust-plugin",
            "--threshold", "0",
            "--max-cost-usd", str(round(args.max_cost_usd / 2.0, 6)),
            "--json", str(out / (side + ".json")),
            "--output-dir", str(out / side)]


def _plugin_eval(plugin, cwd, args, out, side):
    """Run one side; returns its JSON path or raises Refused."""
    log = out / (side + ".log")
    try:
        code = _run_logged(plugin_eval_cmd(plugin, args, out, side), cwd, log)
    except subprocess.TimeoutExpired:
        raise Refused("plugin eval ({}) timed out after {}s; log: {}".format(
            side, PLUGIN_EVAL_TIMEOUT_S, log))
    result = out / (side + ".json")
    if code not in (EXIT_OK, EXIT_CEILING) or not result.is_file():
        raise Refused("plugin eval ({}) exited {} without a result; log: {}".format(
            side, code, log))
    return result


def _clear_previous_run(out):
    for name in RUN_OUTPUTS:
        path = out / name
        if path.is_symlink() or path.is_file():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(str(path))


def _remove_worktree(root, worktree):
    if _git(root, "worktree", "remove", "--force", str(worktree)).returncode != 0:
        shutil.rmtree(str(worktree), ignore_errors=True)
    _git(root, "worktree", "prune")


def run(args):
    if args.max_cost_usd is None or args.max_cost_usd <= 0:
        raise Refused("--max-cost-usd must be positive")
    if args.runs < 1:
        raise Refused("--runs must be at least 1")
    problem = out_dir_problem(args.out)
    if problem:
        raise Refused(problem)
    plugin = Path(args.plugin)
    if not plugin.is_dir():
        raise Refused("--plugin is not a directory: {}".format(plugin))
    top = _git(plugin, "rev-parse", "--show-toplevel")
    if top.returncode != 0 or not top.stdout.strip():
        raise Refused("--plugin {} is not inside a git repository".format(plugin))
    root = Path(top.stdout.strip())
    rel = os.path.relpath(os.path.realpath(str(plugin)), os.path.realpath(str(root)))
    if _git(root, "rev-parse", "--verify", "--quiet", args.base + "^{commit}").returncode != 0:
        raise Refused("--base {} is not a commit in {}".format(args.base, root))

    out = Path(args.out).resolve()
    worktree = out / WORKTREE_DIR
    if os.path.lexists(str(worktree)):
        raise Refused("{} exists (left by an aborted run?); remove it with git worktree remove "
                      "--force {}".format(worktree, worktree))
    try:
        out.mkdir(parents=True, exist_ok=True)
        _clear_previous_run(out)
    except OSError as exc:
        raise Refused("cannot prepare --out {} ({})".format(out, type(exc).__name__))
    added = _git(root, "worktree", "add", "--detach", "--quiet", str(worktree), args.base)
    if added.returncode != 0:
        raise Refused("git worktree add failed for {}".format(args.base))
    try:
        before = _plugin_eval(worktree / rel, worktree, args, out, "before")
    finally:
        _remove_worktree(root, worktree)
    after = _plugin_eval(root / rel, root, args, out, "after")
    return compare(before, after, out, max_cost_usd=args.max_cost_usd,
                   refs={"a": args.base, "b": "working tree"})


# ------------------------------------------------------------------ main

class ArgumentError(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ArgumentError(message)


def _parse_args(argv):
    parser = _Parser(prog="eval_compare.py", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd")
    run_p = sub.add_parser("run", help="plugin eval at REF and on the working tree, compared")
    run_p.add_argument("--plugin", required=True)
    run_p.add_argument("--case", required=True)
    run_p.add_argument("--base", required=True)
    run_p.add_argument("--runs", type=int, default=3)
    run_p.add_argument("--max-cost-usd", type=float, required=True)
    run_p.add_argument("--out", required=True)
    cmp_p = sub.add_parser("compare", help="compare two plugin eval --json files")
    cmp_p.add_argument("before")
    cmp_p.add_argument("after")
    cmp_p.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    if args.cmd not in ("run", "compare"):
        raise ArgumentError("a subcommand is required: run or compare")
    return args


def main(argv=None):
    try:
        args = _parse_args(sys.argv[1:] if argv is None else argv)
        if args.cmd == "compare":
            return compare(args.before, args.after, args.out)
        return run(args)
    except (ArgumentError, Refused) as exc:
        print("eval_compare.py: {}".format(exc), file=sys.stderr)
        return EXIT_INVALID


if __name__ == "__main__":
    sys.exit(main())
