import io
import os
import unittest

from ledgerlite import cli, config


class CliTest(unittest.TestCase):
    def run_cli(self, *argv):
        out = io.StringIO()
        code = cli.main(list(argv), out=out)
        return code, out.getvalue()

    def test_report_uses_default_ledger(self):
        code, text = self.run_cli("report")
        self.assertEqual(code, 0)
        self.assertIn("software", text)

    def test_report_by_month(self):
        path = os.path.join(config.home(), "ledger.csv")
        code, text = self.run_cli("report", "--by", "month", path)
        self.assertEqual(code, 0)
        self.assertIn("2026-02", text)


if __name__ == "__main__":
    unittest.main()
