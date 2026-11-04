import os
import tempfile
import unittest

from stockroom.csvio import dump_csv, load_csv
from stockroom.inventory import Inventory
from stockroom.item import Item


class CsvTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "inv.csv")

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, text):
        with open(self.path, "w", encoding="utf-8") as fh:
            fh.write(text)

    def test_round_trip(self):
        inv = Inventory([Item("A-1", "Nut", 2, 10), Item("B-2", "Washer", 7, 3)])
        dump_csv(inv, self.path)
        self.assertEqual(load_csv(self.path).items(), inv.items())

    def test_bad_header(self):
        self.write("sku,title,qty,unit_price_cents\n")
        with self.assertRaises(ValueError):
            load_csv(self.path)

    def test_malformed_row_names_line(self):
        self.write("sku,name,qty,unit_price_cents\nA-1,Nut,2,10\nB-2,Washer,many,3\n")
        with self.assertRaisesRegex(ValueError, "line 3"):
            load_csv(self.path)


if __name__ == "__main__":
    unittest.main()
