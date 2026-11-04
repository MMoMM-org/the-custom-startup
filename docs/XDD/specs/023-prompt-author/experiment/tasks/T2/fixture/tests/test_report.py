import unittest

from stockroom.inventory import Inventory
from stockroom.item import Item
from stockroom.report import format_cents, format_report


class ReportTest(unittest.TestCase):
    def test_format_cents(self):
        self.assertEqual(format_cents(1234), "12.34")
        self.assertEqual(format_cents(5), "0.05")

    def test_format_report(self):
        inv = Inventory([Item("B-2", "Washer", 7, 3), Item("A-1", "Nut", 2, 10)])
        self.assertEqual(format_report(inv),
                         "A-1 Nut x2 @ 0.10\nB-2 Washer x7 @ 0.03\nTOTAL 0.41")


if __name__ == "__main__":
    unittest.main()
