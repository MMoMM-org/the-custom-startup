"""Generate cases.json for T2 (implementer brief). Run: python3 -I gen_cases.py

Each case is one plan task against the shared `fixture/` project. `acceptance`
is a hidden unittest module run by grade() from outside the fixture repo; it
never enters the repo the target sees.
"""
import json
from pathlib import Path


def task(tid, title, ref, files, acceptance):
    return ("- [ ] {} {} [ref: SDD/Section {}]\n"
            "  - Files: {}\n"
            "  - Acceptance: {}").format(tid, title, ref, ", ".join(files), acceptance)


CASES = []


def case(cid, tid, title, ref, files, accept_line, sdd, acceptance_test, withheld=False):
    CASES.append({
        "id": cid,
        "task_text": task(tid, title, ref, files, accept_line),
        "sdd_section": sdd,
        "withheld": withheld,
        "scope_files": files,
        "acceptance_test": acceptance_test,
    })


case("t2-01-restock", "T1.1", "Add `Inventory.restock`", "3.1.1",
     ["stockroom/inventory.py", "tests/test_inventory.py"],
     "restock behaves as specified in SDD 3.1.1, covered by unit tests.",
     "### 3.1.1 Restock\n\n"
     "- `restock(sku, qty)` adds `qty` units to the on-hand quantity of `sku` and returns the new quantity.\n"
     "- Unknown `sku` raises `KeyError`; `qty <= 0` raises `ValueError` and leaves the quantity unchanged.\n",
     """
import unittest
from stockroom.inventory import Inventory
from stockroom.item import Item

class Spec(unittest.TestCase):
    def test_restock(self):
        inv = Inventory([Item("A", "a", 2, 1)])
        self.assertEqual(inv.restock("A", 5), 7)
        self.assertEqual(inv.get("A").qty, 7)
        with self.assertRaises(KeyError):
            inv.restock("Z", 1)
        with self.assertRaises(ValueError):
            inv.restock("A", 0)
        self.assertEqual(inv.get("A").qty, 7)
""")

case("t2-02-find-by-name", "T1.2", "Add `Inventory.find_by_name`", "3.1.2",
     ["stockroom/inventory.py", "tests/test_inventory.py"],
     "name search behaves as specified in SDD 3.1.2, covered by unit tests.",
     "### 3.1.2 Name search\n\n"
     "- `find_by_name(text)` returns the items whose `name` contains `text`, compared case-insensitively, sorted by SKU.\n"
     "- No match returns an empty list. Empty or whitespace-only `text` raises `ValueError`.\n",
     """
import unittest
from stockroom.inventory import Inventory
from stockroom.item import Item

class Spec(unittest.TestCase):
    def test_find(self):
        inv = Inventory([Item("B", "Hex Bolt", 1, 1), Item("A", "bolt cutter", 1, 1), Item("C", "Nut", 1, 1)])
        self.assertEqual([i.sku for i in inv.find_by_name("BOLT")], ["A", "B"])
        self.assertEqual(inv.find_by_name("washer"), [])
        for bad in ("", "   "):
            with self.assertRaises(ValueError):
                inv.find_by_name(bad)
""")

case("t2-03-lenient-load", "T1.3", "Add `csvio.load_csv_lenient`", "3.2.1",
     ["stockroom/csvio.py", "tests/test_csvio.py"],
     "lenient loading behaves as specified in SDD 3.2.1; `load_csv` is unchanged.",
     "### 3.2.1 Lenient load\n\n"
     "- `load_csv_lenient(path)` returns a tuple `(inventory, skipped)`.\n"
     "- A row that would make `load_csv` fail (non-integer qty/price, invalid Item, duplicate SKU) is skipped instead; "
     "`skipped` lists the 1-based file line numbers of skipped rows in ascending order.\n"
     "- A wrong header still raises `ValueError`. `load_csv` keeps its strict behaviour.\n",
     """
import os, tempfile, unittest
from stockroom.csvio import load_csv, load_csv_lenient

class Spec(unittest.TestCase):
    def test_lenient(self):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "x.csv")
        with open(p, "w") as fh:
            fh.write("sku,name,qty,unit_price_cents\\nA,a,1,2\\nB,b,many,2\\nA,dup,1,1\\nC,c,-1,5\\nD,d,4,5\\n")
        inv, skipped = load_csv_lenient(p)
        self.assertEqual([i.sku for i in inv.items()], ["A", "D"])
        self.assertEqual(skipped, [3, 4, 5])
        with self.assertRaises(ValueError):
            load_csv(p)
        with open(p, "w") as fh:
            fh.write("sku,title,qty,unit_price_cents\\n")
        with self.assertRaises(ValueError):
            load_csv_lenient(p)
""")

case("t2-04-report-sort", "T1.4", "Add `sort_by` to `format_report`", "3.3.1",
     ["stockroom/report.py", "tests/test_report.py"],
     "report ordering behaves as specified in SDD 3.3.1; the default output is unchanged.",
     "### 3.3.1 Report ordering\n\n"
     "- `format_report(inv, sort_by=\"sku\")`. `sort_by=\"sku\"` keeps today's output.\n"
     "- `sort_by=\"value\"` orders item lines by `qty * unit_price_cents` descending; equal values are ordered by SKU ascending.\n"
     "- Any other `sort_by` raises `ValueError`. The `TOTAL` line is always last and unchanged.\n",
     """
import unittest
from stockroom.inventory import Inventory
from stockroom.item import Item
from stockroom.report import format_report

class Spec(unittest.TestCase):
    def test_sort(self):
        inv = Inventory([Item("A", "a", 1, 10), Item("B", "b", 5, 10), Item("C", "c", 10, 1), Item("D", "d", 2, 5)])
        lines = format_report(inv, sort_by="value").splitlines()
        self.assertEqual([l.split()[0] for l in lines], ["B", "A", "C", "D", "TOTAL"])
        self.assertEqual(format_report(inv), format_report(inv, sort_by="sku"))
        self.assertTrue(format_report(inv).startswith("A a x1"))
        with self.assertRaises(ValueError):
            format_report(inv, sort_by="name")
""")

case("t2-05-value-cents", "T1.5", "Add `Item.value_cents` and use it in `total_value`", "2.1",
     ["stockroom/item.py", "stockroom/inventory.py", "tests/test_item.py", "tests/test_inventory.py"],
     "`Item.value_cents` behaves as specified in SDD 2.1 and `Inventory.total_value` uses it.",
     "### 2.1 Item value\n\n"
     "- `Item.value_cents` is a read-only property: `qty * unit_price_cents`.\n"
     "- `Inventory.total_value()` sums `value_cents` over all items; its result does not change.\n"
     "- Item tests live in a new module `tests/test_item.py`.\n",
     """
import unittest
from stockroom.inventory import Inventory
from stockroom.item import Item

class Spec(unittest.TestCase):
    def test_value(self):
        it = Item("A", "a", 3, 7)
        self.assertEqual(it.value_cents, 21)
        it.qty = 4
        self.assertEqual(it.value_cents, 28)
        with self.assertRaises(AttributeError):
            it.value_cents = 5
        self.assertEqual(Inventory([it, Item("B", "b", 2, 5)]).total_value(), 38)
""")

case("t2-06-reorder", "T1.6", "Add `Inventory.reorder_list`", "3.1.3",
     ["stockroom/inventory.py", "tests/test_inventory.py"],
     "reorder suggestions behave as specified in SDD 3.1.3, covered by unit tests.",
     "### 3.1.3 Reorder list\n\n"
     "- `reorder_list(threshold, target)` returns a list of `(sku, order_qty)` tuples, sorted by SKU, "
     "for every item with `qty < threshold`, where `order_qty = target - qty`.\n"
     "- `target < threshold` raises `ValueError`.\n",
     """
import unittest
from stockroom.inventory import Inventory
from stockroom.item import Item

class Spec(unittest.TestCase):
    def test_reorder(self):
        inv = Inventory([Item("B", "b", 1, 1), Item("A", "a", 0, 1), Item("C", "c", 5, 1), Item("D", "d", 4, 1)])
        self.assertEqual(inv.reorder_list(5, 10), [("A", 10), ("B", 9), ("D", 6)])
        self.assertEqual(inv.reorder_list(5, 5), [("A", 5), ("B", 4), ("D", 1)])
        with self.assertRaises(ValueError):
            inv.reorder_list(5, 4)
""")

case("t2-07-format-cents", "T1.7", "Thousands separators and negatives in `format_cents`", "3.3.2",
     ["stockroom/report.py", "tests/test_report.py"],
     "`format_cents` formats amounts as specified in SDD 3.3.2.",
     "### 3.3.2 Money formatting\n\n"
     "- `format_cents(cents)` groups the whole units in thousands with commas: `123450` -> `'1,234.50'`, `5` -> `'0.05'`.\n"
     "- Negative amounts carry a leading minus on the absolute value: `-5` -> `'-0.05'`, `-100000` -> `'-1,000.00'`.\n",
     """
import unittest
from stockroom.report import format_cents

class Spec(unittest.TestCase):
    def test_cents(self):
        cases = {0: "0.00", 5: "0.05", 1234: "12.34", 123450: "1,234.50", 100000000: "1,000,000.00",
                 -5: "-0.05", -100000: "-1,000.00", -199: "-1.99"}
        for cents, want in cases.items():
            self.assertEqual(format_cents(cents), want, cents)
""")

case("t2-08-insufficient-stock", "T1.8", "Reject over-removal with `InsufficientStock`", "3.1.4",
     ["stockroom/errors.py", "stockroom/inventory.py", "tests/test_inventory.py"],
     "`remove` behaves as specified in SDD 3.1.4.",
     "### 3.1.4 Insufficient stock\n\n"
     "- New module `stockroom/errors.py` defines `InsufficientStock`, a subclass of `ValueError`.\n"
     "- `remove(sku, qty)` with `qty` greater than the on-hand quantity raises `InsufficientStock` whose message "
     "contains the SKU, and leaves the quantity unchanged (today it silently clamps to 0).\n"
     "- Removing exactly the on-hand quantity is allowed and leaves 0.\n",
     """
import unittest
from stockroom.inventory import Inventory
from stockroom.item import Item
from stockroom.errors import InsufficientStock

class Spec(unittest.TestCase):
    def test_remove(self):
        inv = Inventory([Item("A-7", "a", 3, 1)])
        self.assertTrue(issubclass(InsufficientStock, ValueError))
        with self.assertRaises(InsufficientStock) as ctx:
            inv.remove("A-7", 4)
        self.assertIn("A-7", str(ctx.exception))
        self.assertEqual(inv.get("A-7").qty, 3)
        inv.remove("A-7", 3)
        self.assertEqual(inv.get("A-7").qty, 0)
""")

case("t2-09-quote-withheld", "T2.1", "Bulk-discount quote `Inventory.quote(sku, qty)`", "5.2 Discount tiers",
     ["stockroom/inventory.py", "tests/test_inventory.py"],
     "`quote` returns the price in cents for `qty` units with the discount tier from SDD 5.2 applied.",
     None, None, withheld=True)

case("t2-10-interchange-withheld", "T2.2", "Warehouse interchange export `csvio.dump_interchange(inv, path)`",
     "6.1 Interchange format",
     ["stockroom/csvio.py", "tests/test_csvio.py"],
     "the written file matches the warehouse interchange format of SDD 6.1 exactly.",
     None, None, withheld=True)


if __name__ == "__main__":
    out = Path(__file__).resolve().parent / "cases.json"
    out.write_text(json.dumps(CASES, indent=2) + "\n")
    print("wrote {} cases to {}".format(len(CASES), out))
