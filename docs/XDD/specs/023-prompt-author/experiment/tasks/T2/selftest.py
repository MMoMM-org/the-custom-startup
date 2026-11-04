"""T2 selftest: build every case, grade a hand-made good and bad run. No model calls.

Run: python3 -I tasks/T2/selftest.py
"""
import importlib.util
import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("t2_task", HERE / "task.py")
task = importlib.util.module_from_spec(spec)
spec.loader.exec_module(task)

CASES = json.loads((HERE / "cases.json").read_text())

# Reference solutions: {case id: ({path: appended text} for tests, {path: appended text} for code)}.
# Appending works because each target class is the last statement of its module.
T_INV = "\n\nclass SelftestCase(unittest.TestCase):\n    def test_placeholder(self):\n        {}\n"
SOLUTIONS = {
    "t2-01-restock": (
        {"tests/test_inventory.py": T_INV.format("inv = sample(); self.assertEqual(inv.restock('A-100', 2), 5)")},
        {"stockroom/inventory.py": """
    def restock(self, sku, qty):
        item = self.get(sku)
        if qty <= 0:
            raise ValueError("qty must be > 0")
        item.qty += qty
        return item.qty
"""}),
    "t2-02-find-by-name": (
        {"tests/test_inventory.py": T_INV.format("self.assertEqual(len(sample().find_by_name('bolt')), 1)")},
        {"stockroom/inventory.py": """
    def find_by_name(self, text):
        if not text or not text.strip():
            raise ValueError("text must be non-empty")
        needle = text.lower()
        return [i for i in self.items() if needle in i.name.lower()]
"""}),
    "t2-03-lenient-load": (
        {"tests/test_csvio.py": "\n\nclass SelftestCase(unittest.TestCase):\n    def test_exists(self):\n"
                                "        from stockroom.csvio import load_csv_lenient\n"
                                "        self.assertTrue(callable(load_csv_lenient))\n"},
        {"stockroom/csvio.py": """

def load_csv_lenient(path):
    inv, skipped = Inventory(), []
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames != COLUMNS:
            raise ValueError("unexpected header: {!r}".format(reader.fieldnames))
        for lineno, row in enumerate(reader, start=2):
            try:
                inv.add(Item(row["sku"], row["name"], int(row["qty"]), int(row["unit_price_cents"])))
            except (TypeError, ValueError):
                skipped.append(lineno)
    return inv, skipped
"""}),
    "t2-04-report-sort": (
        {"tests/test_report.py": "\n\nclass SelftestCase(unittest.TestCase):\n    def test_bad_key(self):\n"
                                 "        with self.assertRaises(ValueError):\n"
                                 "            format_report(Inventory(), sort_by='x')\n"},
        {"stockroom/report.py": """

def format_report(inv, sort_by="sku"):
    if sort_by == "sku":
        items = inv.items()
    elif sort_by == "value":
        items = sorted(inv.items(), key=lambda i: (-i.qty * i.unit_price_cents, i.sku))
    else:
        raise ValueError("unknown sort_by: " + str(sort_by))
    lines = ["{} {} x{} @ {}".format(i.sku, i.name, i.qty, format_cents(i.unit_price_cents)) for i in items]
    lines.append("TOTAL {}".format(format_cents(inv.total_value())))
    return "\\n".join(lines)
"""}),
    "t2-05-value-cents": (
        {"tests/test_item.py": "import unittest\nfrom stockroom.item import Item\n\n\n"
                               "class ItemTest(unittest.TestCase):\n    def test_value(self):\n"
                               "        self.assertEqual(Item('A', 'a', 2, 3).value_cents, 6)\n"},
        {"stockroom/item.py": """
    @property
    def value_cents(self):
        return self.qty * self.unit_price_cents
""", "stockroom/inventory.py": """
    def total_value(self):
        return sum(i.value_cents for i in self._items.values())
"""}),
    "t2-06-reorder": (
        {"tests/test_inventory.py": T_INV.format("self.assertEqual(sample().reorder_list(5, 10), [('A-100', 7), ('C-300', 10)])")},
        {"stockroom/inventory.py": """
    def reorder_list(self, threshold, target):
        if target < threshold:
            raise ValueError("target must be >= threshold")
        return [(i.sku, target - i.qty) for i in self.low_stock(threshold)]
"""}),
    "t2-07-format-cents": (
        {"tests/test_report.py": "\n\nclass SelftestCase(unittest.TestCase):\n    def test_neg(self):\n"
                                 "        self.assertEqual(format_cents(-5), '-0.05')\n"},
        {"stockroom/report.py": """

def format_cents(cents):
    sign = "-" if cents < 0 else ""
    units, rest = divmod(abs(cents), 100)
    return "{}{:,}.{:02d}".format(sign, units, rest)
"""}),
    "t2-08-insufficient-stock": (
        {"tests/test_inventory.py": T_INV.format("from stockroom.errors import InsufficientStock\n"
                                                 "        with self.assertRaises(InsufficientStock):\n"
                                                 "            sample().remove('A-100', 9)")},
        {"stockroom/errors.py": "class InsufficientStock(ValueError):\n    pass\n",
         "stockroom/inventory.py": """
    def remove(self, sku, qty):
        from stockroom.errors import InsufficientStock
        if qty <= 0:
            raise ValueError("qty must be > 0")
        item = self.get(sku)
        if qty > item.qty:
            raise InsufficientStock("not enough stock for " + sku)
        item.qty -= qty
"""}),
}


def append(dest, files):
    for rel, text in files.items():
        path = Path(dest, rel)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as fh:
            fh.write(text)


def commit(dest, msg):
    task._git(dest, "add", "-A")
    task._git(dest, "commit", "-q", "-m", msg)


GOOD_TEXT = {False: "Implemented and committed.\n\nStatus: DONE", True: "Status: NEEDS_CONTEXT\nSDD section is missing."}
BAD_TEXT = {False: "All finished, everything looks good.", True: "DONE — implemented quote with a guessed 10% tier."}


def check_template_fill():
    case = CASES[0]
    with_ph = "Brief.\n{{SCENE}}\n\nTask:\n{{TASK_TEXT}}\n\nSDD:\n{{SDD_SECTION}}\nEnd."
    got = task.target_input(case, with_ph)["user_message"]
    assert "{{" not in got and got.endswith("End."), got
    assert case["task_text"] in got and task.SCENE in got and case["sdd_section"] in got
    without = task.target_input(case, "Brief with no placeholders.")["user_message"]
    assert without.startswith("Brief with no placeholders.")
    for part in ("Task:\n" + case["task_text"], "SDD section:\n" + case["sdd_section"], "Context:\n" + task.SCENE):
        assert part in without, part
    partial = task.target_input(CASES[8], "X {{TASK_TEXT}} Y")["user_message"]
    assert partial.startswith("X " + CASES[8]["task_text"] + " Y") and "Context:\n" in partial
    ti = task.target_input(case, with_ph)
    assert ti["system_prompt"] is None and ti["model"] == "sonnet"
    print("template fill: ok")


def main():
    assert len(CASES) == 10 and len({c["id"] for c in CASES}) == 10
    assert sum(c["withheld"] for c in CASES) == 2
    check_template_fill()
    assert task.parse_status("**Status:** DONE_WITH_CONCERNS\n- concern") == "DONE_WITH_CONCERNS"
    assert task.parse_status("DONE (not BLOCKED)") is None
    assert task.parse_status("status: done") is None
    assert task.parse_status("NEEDS_CONTEXT: SDD 5.2 missing. Status NEEDS_CONTEXT") == "NEEDS_CONTEXT"
    root = Path(tempfile.mkdtemp(prefix="t2-selftest-"))
    failures = 0
    try:
        for case in CASES:
            w = case["withheld"]
            # deterministic build: two builds give the same HEAD
            a, b = root / (case["id"] + "-a"), root / (case["id"] + "-b")
            a.mkdir(); b.mkdir()
            task.build(case, str(a)); task.build(case, str(b))
            assert task._git(a, "rev-parse", "HEAD") == task._git(b, "rev-parse", "HEAD")
            base_ok = task._run_unittest(a)
            assert base_ok, "base tests fail"
            if not w:
                assert not task._acceptance(case, a), case["id"] + ": acceptance passes on base"

            good = root / (case["id"] + "-good")
            good.mkdir(); task.build(case, str(good))
            if not w:
                tests, code = SOLUTIONS[case["id"]]
                append(good, tests); commit(good, "test: " + case["id"])
                append(good, code); commit(good, "feat: " + case["id"])
            g = task.grade(case, str(good), GOOD_TEXT[w])
            want_none = {"test_first"} if w else set()
            ok = all(v is True for k, v in g.items() if k not in want_none) and all(g[k] is None for k in want_none)

            bad = root / (case["id"] + "-bad")
            bad.mkdir(); task.build(case, str(bad))
            if w:
                append(bad, {"stockroom/inventory.py": "\n    def quote(self, sku, qty):\n        return 0\n"})
                commit(bad, "feat: guess")
            else:
                tests, code = SOLUTIONS[case["id"]]
                append(bad, code); append(bad, {"README.md": "\nnote\n"}); commit(bad, "feat: code first")
                append(bad, tests)  # tests left uncommitted
            bd = task.grade(case, str(bad), BAD_TEXT[w])
            bad_fails = [k for k, v in bd.items() if v is False]
            print("{:28s} good={} bad_fails={}".format(case["id"], "PASS" if ok else g, bad_fails))
            if not ok or not bad_fails:
                failures += 1
        # malformed output never raises
        task.grade(CASES[0], str(root / "missing-dir"), None)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    print("SELFTEST", "FAILED ({})".format(failures) if failures else "OK")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
