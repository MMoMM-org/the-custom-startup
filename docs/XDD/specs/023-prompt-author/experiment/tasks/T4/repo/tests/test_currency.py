import unittest

from ledgerlite.currency import UnknownCurrency, convert


class ConvertTest(unittest.TestCase):
    def test_to_eur(self):
        self.assertAlmostEqual(convert(40, "GBP"), 50.0)

    def test_between_foreign_currencies(self):
        self.assertAlmostEqual(convert(10, "GBP", to="USD"), 10 * 1.25 / 0.875)

    def test_case_insensitive(self):
        self.assertAlmostEqual(convert(2, "usd"), 1.75)

    def test_unknown_currency(self):
        with self.assertRaises(UnknownCurrency):
            convert(1, "XYZ")


if __name__ == "__main__":
    unittest.main()
