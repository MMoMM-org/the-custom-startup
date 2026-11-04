"""Parse ledger CSV files into Transaction objects.

Expected header: date,amount,currency,category[,description]
"""

import csv
import datetime
import io

from .model import Transaction

REQUIRED = ("date", "amount", "currency", "category")


class ParseError(ValueError):
    def __init__(self, line, message):
        super().__init__("line {}: {}".format(line, message))
        self.line = line


def _parse_amount(raw, line):
    text = (raw or "").strip().replace(",", "")
    try:
        return float(text)
    except ValueError:
        raise ParseError(line, "bad amount {!r}".format(raw)) from None


def _parse_date(raw, line):
    try:
        return datetime.date.fromisoformat((raw or "").strip())
    except ValueError:
        raise ParseError(line, "bad date {!r}".format(raw)) from None


def parse_csv(text):
    reader = csv.DictReader(io.StringIO(text))
    missing = [c for c in REQUIRED if c not in (reader.fieldnames or [])]
    if missing:
        raise ParseError(1, "missing columns: " + ", ".join(missing))
    transactions = []
    for line, row in enumerate(reader, start=2):
        if not any((value or "").strip() for value in row.values()):
            continue
        transactions.append(Transaction(
            date=_parse_date(row["date"], line),
            amount=_parse_amount(row["amount"], line),
            currency=(row["currency"] or "").strip().upper(),
            category=(row["category"] or "").strip() or "uncategorized",
            description=(row.get("description") or "").strip(),
        ))
    return transactions


def parse_file(path):
    with open(path, encoding="utf-8") as fh:
        return parse_csv(fh.read())
