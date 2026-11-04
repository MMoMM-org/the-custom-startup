"""Selftest for T4: reference solutions + good CLAUDE.md pass every criterion; a bad repo
state (hand-edited generated file, bare unittest, false CLAUDE.md claims) fails.
No model calls.  Run: python3 -I tasks/T4/selftest.py
"""
import importlib.util
import json
import os
import subprocess
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("t4task", os.path.join(HERE, "task.py"))
task = importlib.util.module_from_spec(spec)
spec.loader.exec_module(task)
cases = json.load(open(os.path.join(HERE, "cases.json")))
assert len(cases) == 5 and len({c["id"] for c in cases}) == 5

GOOD_MD = """# ledgerlite

Small CSV ledger reports converted to EUR. Package code in `ledgerlite/`, tests in `tests/`.

## Commands

```bash
./scripts/dev.sh test    # sets LEDGERLITE_HOME=tests/fixtures, runs unittest discovery
./scripts/dev.sh lint    # style check + generated-file freshness check
./scripts/dev.sh gen     # regenerate ledgerlite/_rates.py
```

Bare `python3 -m unittest` fails: the tests need `LEDGERLITE_HOME`, which `./scripts/dev.sh test` sets.

## Gotcha

`ledgerlite/_rates.py` is generated from `data/rates.csv` by `scripts/gen_rates.py`.
Never edit it by hand: change `data/rates.csv`, then run `./scripts/dev.sh gen`.
The README is out of date on both points; see [the dev script](scripts/dev.sh).

Try it: `python3 -m ledgerlite.cli report --by month tests/fixtures/ledger.csv`
"""

BAD_MD = """# ledgerlite
Run `python3 run_tests.py` or `npm test`. Entry point: `src/ledgerlite/app.py`.
```
./scripts/dev.sh check
make lint
```
"""


def sub(path, old, new):
    with open(path) as fh:
        text = fh.read()
    assert old in text, (path, old)
    with open(path, "w") as fh:
        fh.write(text.replace(old, new, 1))


def solve(case_id, d):
    p = lambda *x: os.path.join(d, *x)
    if case_id == "t4-01-chf":
        with open(p("data", "rates.csv"), "a") as fh:
            fh.write("CHF,1.05\n")
        subprocess.run(["./scripts/dev.sh", "gen"], cwd=d, check=True)
    elif case_id == "t4-02-parens":
        sub(p("ledgerlite", "parser.py"),
            '    text = (raw or "").strip().replace(",", "")\n',
            '    text = (raw or "").strip().replace(",", "")\n'
            '    negative = text.startswith("(") and text.endswith(")")\n'
            '    if negative:\n'
            '        text = "-" + text[1:-1]\n')
    elif case_id == "t4-03-top":
        sub(p("ledgerlite", "report.py"), "def format_table(totals):\n",
            "def format_table(totals, top=None):\n")
        sub(p("ledgerlite", "report.py"), "    for key, value in rows:\n",
            "    for key, value in rows[:top] if top else rows:\n")
        sub(p("ledgerlite", "cli.py"),
            '    rep.add_argument("file", nargs="?",\n',
            '    rep.add_argument("--top", type=int, default=None)\n'
            '    rep.add_argument("file", nargs="?",\n')
        sub(p("ledgerlite", "cli.py"),
            "report.format_table(report.totals_by(transactions, args.by))",
            "report.format_table(report.totals_by(transactions, args.by), args.top)")
    elif case_id == "t4-04-rounding":
        sub(p("ledgerlite", "report.py"),
            "    euros = int(value)\n    cents = int((value - euros) * 100)\n",
            "    euros, cents = divmod(int(round(value * 100)), 100)\n")
    elif case_id == "t4-05-convert":
        sub(p("ledgerlite", "cli.py"), "    return root\n",
            '    conv = sub.add_parser("convert", help="convert an amount")\n'
            '    conv.add_argument("amount", type=float)\n'
            '    conv.add_argument("currency")\n'
            '    conv.add_argument("--to", default="EUR")\n'
            "    return root\n")
        sub(p("ledgerlite", "cli.py"), "    return 2\n",
            '    if args.command == "convert":\n'
            "        try:\n"
            "            value = convert(args.amount, args.currency, to=args.to)\n"
            "        except UnknownCurrency as exc:\n"
            '            print("unknown currency: {}".format(exc.args[0]), file=sys.stderr)\n'
            "            return 1\n"
            "        print(report.format_amount(value), file=out)\n"
            "        return 0\n"
            "    return 2\n")
        sub(p("ledgerlite", "cli.py"), "from . import config, report\n",
            "from . import config, report\nfrom .currency import UnknownCurrency, convert\n")


def write_md(d, text):
    with open(os.path.join(d, "CLAUDE.md"), "w") as fh:
        fh.write(text)


snap = task.repo_snapshot()
assert "scripts/dev.sh" in snap and "hidden" not in snap.lower()
lint_good = task.lint_claude_md(GOOD_MD, task.REPO_SRC)
print("lint good:", lint_good)
assert lint_good["false_claims"] == [] and lint_good["commands_checked"] >= 4
lint_bad = task.lint_claude_md(BAD_MD, task.REPO_SRC)
print("lint bad:", lint_bad["false_claims"])
assert len(lint_bad["false_claims"]) == 5, lint_bad

for case in cases:
    ti = task.target_input(case, GOOD_MD)
    assert ti["files"] == {"CLAUDE.md": GOOD_MD} and ti["system_prompt"] is None
    assert ti["user_message"].startswith("Project CLAUDE.md:")
    with tempfile.TemporaryDirectory() as d:
        task.build(case, d)
        g0 = task.grade(case, d, "")          # untouched repo, no CLAUDE.md
        assert g0["tests_pass"] is False and g0["used_documented_test_cmd"] is False, g0
        assert g0["claims_true"] is False
        write_md(d, GOOD_MD)
        solve(case["id"], d)
        proc = subprocess.run(["./scripts/dev.sh", "test"], cwd=d, capture_output=True)
        assert proc.returncode == 0, proc.stderr.decode()
        g = task.grade(case, d, "done")
        print("good", case["id"], g)
        assert all(g.values()), g

    with tempfile.TemporaryDirectory() as d:
        task.build(case, d)
        write_md(d, BAD_MD)
        solve(case["id"], d)
        with open(os.path.join(d, "ledgerlite", "_rates.py"), "a") as fh:
            fh.write("EUR_PER_UNIT['CHF'] = 1.05\t \n")      # hand edit + lint violation
        g = task.grade(case, d, "done")
        print("bad ", case["id"], g)
        assert g == {"used_documented_test_cmd": False, "tests_pass": True,
                     "gotcha_respected": False, "lint_pass": False, "claims_true": False,
                     "claude_md_within_budget": True}, g

with tempfile.TemporaryDirectory() as d:
    task.build(cases[0], d)
    write_md(d, "x" * (task.SIZE_BUDGET_BYTES + 1))
    assert task.grade(cases[0], d, "")["claude_md_within_budget"] is False
    out = subprocess.run(["git", "-C", d, "log", "--oneline"], capture_output=True, text=True)
    assert len(out.stdout.splitlines()) == 1

print("T4 selftest OK")
