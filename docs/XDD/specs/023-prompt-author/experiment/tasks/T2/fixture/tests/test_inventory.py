import unittest

from stockroom.inventory import Inventory
from stockroom.item import Item


def sample():
    return Inventory([
        Item("B-200", "Bolt M6", 40, 15),
        Item("A-100", "Anchor", 3, 250),
        Item("C-300", "Clamp", 0, 999),
    ])


class InventoryTest(unittest.TestCase):
    def test_items_sorted_by_sku(self):
        self.assertEqual([i.sku for i in sample().items()], ["A-100", "B-200", "C-300"])

    def test_duplicate_sku_rejected(self):
        inv = sample()
        with self.assertRaises(ValueError):
            inv.add(Item("A-100", "Other", 1, 1))

    def test_get_unknown_raises_key_error(self):
        with self.assertRaises(KeyError):
            sample().get("Z-999")

    def test_remove_reduces_qty(self):
        inv = sample()
        inv.remove("B-200", 5)
        self.assertEqual(inv.get("B-200").qty, 35)

    def test_remove_rejects_non_positive(self):
        with self.assertRaises(ValueError):
            sample().remove("B-200", 0)

    def test_total_value(self):
        self.assertEqual(sample().total_value(), 40 * 15 + 3 * 250)

    def test_low_stock(self):
        self.assertEqual([i.sku for i in sample().low_stock(5)], ["A-100", "C-300"])


if __name__ == "__main__":
    unittest.main()
