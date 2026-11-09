"""Command line entry point: python3 -m ledgerlite.cli report [--by category|month] [FILE]"""

import argparse
import sys

from . import config, report
from . import parser as ledger_parser


def build_parser():
    root = argparse.ArgumentParser(prog="ledgerlite")
    sub = root.add_subparsers(dest="command", required=True)
    rep = sub.add_parser("report", help="totals per group in EUR")
    rep.add_argument("--by", choices=("category", "month"), default="category")
    rep.add_argument("file", nargs="?",
                     help="ledger CSV (default: $LEDGERLITE_HOME/ledger.csv)")
    return root


def main(argv=None, out=None):
    out = out or sys.stdout
    args = build_parser().parse_args(argv)
    if args.command == "report":
        path = args.file or config.default_ledger()
        transactions = ledger_parser.parse_file(path)
        print(report.format_table(report.totals_by(transactions, args.by)), file=out)
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
