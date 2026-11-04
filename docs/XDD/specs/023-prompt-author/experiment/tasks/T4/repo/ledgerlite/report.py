"""Aggregate transactions and render plain-text tables."""

from collections import defaultdict

from .currency import to_eur


def _group_key(transaction, by):
    if by == "category":
        return transaction.category
    if by == "month":
        return transaction.date.strftime("%Y-%m")
    raise ValueError("unknown grouping {!r}".format(by))


def totals_by(transactions, by):
    totals = defaultdict(float)
    for tx in transactions:
        totals[_group_key(tx, by)] += to_eur(tx)
    return dict(totals)


def format_amount(value):
    sign = "-" if value < 0 else ""
    value = abs(value)
    euros = int(value)
    cents = int((value - euros) * 100)
    return "{}{}.{:02d}".format(sign, euros, cents)


def format_table(totals):
    rows = sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))
    width = max([len(k) for k in totals] + [5])
    lines = ["{:<{w}}  {:>10}".format("group", "EUR", w=width)]
    for key, value in rows:
        lines.append("{:<{w}}  {:>10}".format(key, format_amount(value), w=width))
    lines.append("{:<{w}}  {:>10}".format(
        "total", format_amount(sum(totals.values())), w=width))
    return "\n".join(lines)
