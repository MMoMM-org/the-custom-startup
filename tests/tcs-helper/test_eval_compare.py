"""Tests for eval_compare.py, the plugin-eval before/after comparison (spec 023, T2.3, C4).

The fixture plugin-eval-xdd-tdd-no-trigger.json is one real `claude plugin eval
--json` result (tcs-workflow, case xdd-tdd-no-trigger, 1 run, --ablation none,
Claude Code 2.1.316, captured 2026-11-05). Other inputs are derived from it in
the tests: renamed cases, flipped grader verdicts, a with-only grader, a
without arm. `run` is exercised against a fake `claude` on PATH that records
its argv and writes the fixture to --json; nothing calls a model.
"""
import copy
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "plugins/tcs-helper/skills/prompt-author/scripts"
SCRIPT = SCRIPTS / "eval_compare.py"
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "eval_compare" \
    / "plugin-eval-xdd-tdd-no-trigger.json"

# Top-level report fields prompt_eval.py writes; eval_compare must write the same shape.
REPORT_FIELDS = {"versions", "target", "judge", "runs", "label", "judge_validation", "cost_usd",
                 "max_cost_usd", "partial", "notes", "cases", "per_criterion", "all_pass",
                 "errored_runs", "judge_errors", "paired_difference", "sign_test", "verdict",
                 "recommendation", "error_rates"}


def _load_module():
    if not SCRIPT.is_file():
        pytest.fail("eval_compare.py does not exist yet: {}".format(SCRIPT))
    spec = importlib.util.spec_from_file_location("eval_compare_under_test", str(SCRIPT))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def ec():
    return _load_module()


def real():
    return json.loads(FIXTURE.read_text())


def with_cases(data, names, readme_passes):
    """DATA with its one case cloned under NAMES; readme-written set to READMEPASSES."""
    out = copy.deepcopy(data)
    template = out["cases"][0]
    out["cases"] = []
    for name in names:
        case = copy.deepcopy(template)
        case["name"] = name
        for run in case["arms"]["with"]:
            for grader in run["graders"]:
                if grader["name"] == "readme-written":
                    grader["passed"] = readme_passes
        out["cases"].append(case)
    return out


def dump(path, data):
    path.write_text(json.dumps(data))
    return path


def report_of(out):
    return json.loads((Path(out) / "report.json").read_text())


# ------------------------------------------------------------------ compare

def test_real_fixture_pair_gives_the_prompt_eval_report_shape(ec, tmp_path):
    before = dump(tmp_path / "before.json", real())
    after = dump(tmp_path / "after.json", with_cases(real(), ["xdd-tdd-no-trigger"], True))
    out = tmp_path / "out"
    assert ec.main(["compare", str(before), str(after), "--out", str(out)]) == 0
    rep = report_of(out)
    assert REPORT_FIELDS <= set(rep)
    assert rep["cases"] == {"n": 1, "ids": ["xdd-tdd-no-trigger"]}
    assert rep["per_criterion"]["readme-written"] == {"kind": "deterministic", "a": 0.0, "b": 1.0}
    assert rep["per_criterion"]["skill-not-fired"] == {"kind": "deterministic", "a": 1.0,
                                                       "b": 1.0}
    assert rep["all_pass"] == {"a": 0.0, "b": 1.0}
    assert rep["verdict"] == "insufficient cases"
    assert rep["runs"] == 1
    assert rep["cost_usd"] == pytest.approx(2 * 0.2006746)
    assert rep["judge_validation"] == {"readme-written": "not_run", "skill-not-fired": "not_run"}
    assert rep["versions"]["a"]["path"] == str(before)
    md = (out / "report.md").read_text().splitlines()
    assert md[1].startswith("Verdict: insufficient cases")
    assert md[2].startswith("Judge validation: not run")
    assert md[3].startswith("Cost: $0.4013")
    assert md[4].startswith("Label: ")


def test_five_flipped_cases_give_b_better(ec, tmp_path):
    names = ["case{}".format(i) for i in range(5)]
    before = dump(tmp_path / "before.json", with_cases(real(), names, False))
    after = dump(tmp_path / "after.json", with_cases(real(), names, True))
    out = tmp_path / "out"
    assert ec.main(["compare", str(before), str(after), "--out", str(out)]) == 0
    rep = report_of(out)
    assert rep["verdict"] == "b better"
    assert rep["paired_difference"]["n_cases"] == 5
    assert rep["sign_test"]["b_better"] == 5
    assert rep["recommendation"]["version"] == "b"


def test_no_difference_has_no_size_recommendation(ec, tmp_path):
    names = ["case{}".format(i) for i in range(5)]
    before = dump(tmp_path / "before.json", with_cases(real(), names, True))
    out = tmp_path / "out"
    assert ec.main(["compare", str(before), str(before), "--out", str(out)]) == 0
    rep = report_of(out)
    assert rep["verdict"] == "no measurable difference"
    assert rep["recommendation"] is None


def test_mismatched_case_sets_exit_1_and_list_the_mismatch(ec, tmp_path, capsys):
    before = dump(tmp_path / "before.json", with_cases(real(), ["shared", "gone"], True))
    after = dump(tmp_path / "after.json", with_cases(real(), ["shared", "new"], True))
    out = tmp_path / "out"
    assert ec.main(["compare", str(before), str(after), "--out", str(out)]) == 1
    err = capsys.readouterr().err
    assert "gone" in err and "new" in err
    rep = report_of(out)
    assert rep["case_mismatch"] == {"only_before": ["gone"], "only_after": ["new"]}
    assert rep["verdict"] is None and "case sets differ" in rep["verdict_withheld"]
    md = (out / "report.md").read_text()
    assert "gone" in md and "new" in md


def test_with_only_graders_and_the_without_arm_are_ignored_and_noted(ec, tmp_path):
    data = real()
    case = data["cases"][0]
    case["graders"].append({"name": "skill-fired", "type": "tool_used", "weight": 1,
                            "config": {"tool": "Skill"}})
    for run in case["arms"]["with"]:
        run["graders"].append({"name": "skill-fired", "passed": False, "weight": 1,
                               "explanation": "", "withOnly": True, "scored": False})
    case["arms"]["without"] = [copy.deepcopy(case["arms"]["with"][0])]
    case["arms"]["without"][0]["graders"][0]["passed"] = True
    before = dump(tmp_path / "before.json", data)
    out = tmp_path / "out"
    assert ec.main(["compare", str(before), str(before), "--out", str(out)]) == 0
    rep = report_of(out)
    assert "skill-fired" not in rep["per_criterion"]
    assert rep["per_criterion"]["readme-written"]["a"] == 0.0
    notes = " ".join(rep["notes"])
    assert "skill-fired" in notes and "with-only" in notes
    assert "without" in notes


def test_llm_grader_without_verdict_is_a_judge_error(ec, tmp_path):
    data = real()
    case = data["cases"][0]
    case["graders"].append({"name": "rubric", "type": "llm", "weight": 1, "config": {}})
    case["arms"]["with"][0]["graders"].append({"name": "rubric", "passed": None, "weight": 1,
                                               "withOnly": False, "scored": True})
    before = dump(tmp_path / "before.json", data)
    out = tmp_path / "out"
    ec.main(["compare", str(before), str(before), "--out", str(out)])
    rep = report_of(out)
    assert rep["per_criterion"]["rubric"]["kind"] == "judge"
    assert rep["judge_errors"] == {"a": 1, "b": 1}
    assert rep["judge_validation"]["rubric"] == "not_validated"


def test_errored_run_is_counted(ec, tmp_path):
    data = real()
    data["cases"][0]["arms"]["with"][0]["error"] = "timeout"
    before = dump(tmp_path / "before.json", data)
    out = tmp_path / "out"
    ec.main(["compare", str(before), str(FIXTURE), "--out", str(out)])
    assert report_of(out)["errored_runs"] == {"a": 1, "b": 0}


@pytest.mark.parametrize("content", ["not json", "[]", json.dumps({"schemaVersion": 2,
                                                                   "cases": []})])
def test_unreadable_input_exits_1(ec, tmp_path, content, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text(content)
    assert ec.main(["compare", str(bad), str(FIXTURE), "--out", str(tmp_path / "out")]) == 1
    assert "bad.json" in capsys.readouterr().err


def test_partial_input_marks_the_report_partial_and_exits_2(ec, tmp_path):
    data = real()
    data["partial"] = True
    before = dump(tmp_path / "before.json", data)
    out = tmp_path / "out"
    assert ec.main(["compare", str(before), str(FIXTURE), "--out", str(out)]) == 2
    assert report_of(out)["partial"] is True


def _git(*args, cwd):
    env = dict(os.environ, GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_NOSYSTEM="1")
    return subprocess.run(["git", "-C", str(cwd)] + list(args), check=True, env=env,
                          capture_output=True, encoding="utf-8").stdout


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    root = tmp_path / "repo"
    case = root / "plugins" / "p" / "evals" / "c1"
    case.mkdir(parents=True)
    (case / "prompt.md").write_text("base version\n")
    _git("init", "-q", cwd=root)
    _git("-c", "user.name=t", "-c", "user.email=t@t", "add", "-A", cwd=root)
    _git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "base", cwd=root)
    (case / "prompt.md").write_text("working tree version\n")
    return root


def test_compare_refuses_an_out_inside_a_repo(ec, repo, capsys):
    out = repo / "results"
    assert ec.main(["compare", str(FIXTURE), str(FIXTURE), "--out", str(out)]) == 1
    assert not out.exists()


def test_compare_imports_the_stats_module_without_prompt_eval():
    code = ("import sys; sys.path.insert(0, {!r}); import eval_compare; "
            "assert 'prompt_eval_stats' in sys.modules; "
            "assert 'prompt_eval' not in sys.modules; print('ok')").format(str(SCRIPTS))
    res = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True,
                         encoding="utf-8")
    assert res.stdout.strip() == "ok", res.stderr


# ------------------------------------------------------------------ run

FAKE_CLAUDE = r'''#!/usr/bin/env python3
import json, os, shutil, sys
argv = sys.argv[1:]
log = os.environ["FAKE_CLAUDE_LOG"]
with open(log, "a") as handle:
    target = argv[2]
    prompt = os.path.join(target, "evals", "c1", "prompt.md")
    handle.write(json.dumps({"argv": argv, "prompt": open(prompt).read()
                             if os.path.isfile(prompt) else None}) + "\n")
calls = sum(1 for _ in open(log))
if os.environ.get("FAKE_CLAUDE_FAIL_ON") == str(calls):
    sys.exit(3)
shutil.copy(os.environ["FAKE_CLAUDE_FIXTURE"], argv[argv.index("--json") + 1])
os.makedirs(argv[argv.index("--output-dir") + 1], exist_ok=True)
'''


@pytest.fixture
def fake_claude(tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    script = bin_dir / "claude"
    script.write_text(FAKE_CLAUDE)
    script.chmod(0o755)
    log = tmp_path / "claude-calls.jsonl"
    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ["PATH"])
    monkeypatch.setenv("FAKE_CLAUDE_LOG", str(log))
    monkeypatch.setenv("FAKE_CLAUDE_FIXTURE", str(FIXTURE))
    monkeypatch.delenv("FAKE_CLAUDE_FAIL_ON", raising=False)

    def calls():
        if not log.is_file():
            return []
        return [json.loads(line) for line in log.read_text().splitlines()]
    return calls


def run_argv(repo, out, cost="1", base="HEAD"):
    return ["run", "--plugin", str(repo / "plugins" / "p"), "--case", "c1", "--base", base,
            "--runs", "1", "--max-cost-usd", cost, "--out", str(out)]


def _flag(argv, name):
    return argv[argv.index(name) + 1]


def worktrees(repo):
    return [line for line in _git("worktree", "list", "--porcelain", cwd=repo).splitlines()
            if line.startswith("worktree ")]


def test_run_evaluates_base_in_a_worktree_then_the_working_tree(ec, repo, fake_claude, tmp_path):
    out = tmp_path / "out"
    assert ec.main(run_argv(repo, out)) == 0
    before, after = fake_claude()
    assert before["prompt"] == "base version\n"
    assert after["prompt"] == "working tree version\n"
    assert before["argv"][2] != after["argv"][2]
    assert Path(after["argv"][2]).resolve() == (repo / "plugins" / "p").resolve()
    for call, side in ((before, "before"), (after, "after")):
        argv = call["argv"]
        assert argv[:2] == ["plugin", "eval"]
        assert "--no-publish" in argv and "--trust-plugin" in argv and "--scaffold" not in argv
        assert _flag(argv, "--ablation") == "none"
        assert Path(_flag(argv, "--json")) == (out / (side + ".json")).resolve()
        assert Path(_flag(argv, "--output-dir")) == (out / side).resolve()
        assert float(_flag(argv, "--max-cost-usd")) == pytest.approx(0.5)
        assert _flag(argv, "--case") == "c1" and _flag(argv, "--runs") == "1"
    assert len(worktrees(repo)) == 1
    assert not Path(before["argv"][2]).exists()
    rep = report_of(out)
    assert REPORT_FIELDS <= set(rep)
    assert rep["versions"]["a"]["ref"] == "HEAD" and rep["versions"]["b"]["ref"] == "working tree"


@pytest.mark.parametrize("fail_on", ["1", "2"])
def test_run_removes_the_worktree_when_plugin_eval_fails(ec, repo, fake_claude, tmp_path,
                                                         monkeypatch, fail_on, capsys):
    monkeypatch.setenv("FAKE_CLAUDE_FAIL_ON", fail_on)
    out = tmp_path / "out"
    assert ec.main(run_argv(repo, out)) == 1
    assert "plugin eval" in capsys.readouterr().err
    assert len(fake_claude()) == int(fail_on)
    assert len(worktrees(repo)) == 1
    assert not Path(fake_claude()[0]["argv"][2]).exists()
    assert not (out / "report.json").exists()


def test_run_refuses_an_out_inside_the_repo(ec, repo, fake_claude, capsys):
    out = repo / "eval-out"
    assert ec.main(run_argv(repo, out)) == 1
    assert fake_claude() == []
    assert len(worktrees(repo)) == 1
    assert "git work tree" in capsys.readouterr().err


def test_run_refuses_an_unknown_base_ref(ec, repo, fake_claude, tmp_path):
    assert ec.main(run_argv(repo, tmp_path / "out", base="no-such-ref")) == 1
    assert fake_claude() == []
    assert len(worktrees(repo)) == 1


@pytest.mark.parametrize("cost", ["0", "-1"])
def test_run_requires_a_positive_cost_ceiling(ec, repo, fake_claude, tmp_path, cost):
    assert ec.main(run_argv(repo, tmp_path / "out", cost=cost)) == 1
    assert fake_claude() == []
