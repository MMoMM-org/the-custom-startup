import os
import unittest

from ledgerlite import config, report
from ledgerlite.parser import parse_file

LEDGER = os.path.join(config.home(), "ledger.csv")


class ReportTest(unittest.TestCase):
    def setUp(self):
        self.txs = parse_file(LEDGER)

    def test_totals_by_category(self):
        totals = report.totals_by(self.txs, "category")
        self.assertEqual(totals, {"groceries": 20.25, "travel": 50.0,
                                  "coffee": 3.25, "software": 87.5})

    def test_totals_by_month(self):
        totals = report.totals_by(self.txs, "month")
        self.assertEqual(totals, {"2026-01": 65.75, "2026-02": 95.25})

    def test_format_amount(self):
        self.assertEqual(report.format_amount(12.5), "12.50")
        self.assertEqual(report.format_amount(-3.25), "-3.25")

    def test_table_sorted_descending(self):
        table = report.format_table(report.totals_by(self.txs, "category"))
        groups = [line.split()[0] for line in table.splitlines()[1:-1]]
        self.assertEqual(groups, ["software", "travel", "groceries", "coffee"])
        self.assertTrue(table.splitlines()[-1].endswith("161.00"))


if __name__ == "__main__":
    unittest.main()
