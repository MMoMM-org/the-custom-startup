import datetime
import unittest

from ledgerlite.parser import ParseError, parse_csv

HEADER = "date,amount,currency,category,description\n"


class ParseCsvTest(unittest.TestCase):
    def test_parses_rows(self):
        txs = parse_csv(HEADER + "2026-01-03,12.50,eur,groceries,market\n")
        self.assertEqual(len(txs), 1)
        self.assertEqual(txs[0].date, datetime.date(2026, 1, 3))
        self.assertEqual(txs[0].amount, 12.5)
        self.assertEqual(txs[0].currency, "EUR")

    def test_thousands_separator(self):
        txs = parse_csv(HEADER + '2026-01-03,"1,234.50",EUR,rent,\n')
        self.assertEqual(txs[0].amount, 1234.5)

    def test_blank_lines_are_skipped(self):
        txs = parse_csv(HEADER + ",,,,\n2026-01-03,1,EUR,misc,\n")
        self.assertEqual(len(txs), 1)

    def test_empty_category_becomes_uncategorized(self):
        txs = parse_csv(HEADER + "2026-01-03,1,EUR,,\n")
        self.assertEqual(txs[0].category, "uncategorized")

    def test_missing_column(self):
        with self.assertRaises(ParseError) as ctx:
            parse_csv("date,amount\n2026-01-01,1\n")
        self.assertEqual(ctx.exception.line, 1)

    def test_bad_amount_reports_line(self):
        with self.assertRaises(ParseError) as ctx:
            parse_csv(HEADER + "2026-01-03,1,EUR,a,\n2026-01-04,abc,EUR,b,\n")
        self.assertEqual(ctx.exception.line, 3)


if __name__ == "__main__":
    unittest.main()
