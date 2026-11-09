"""Currency conversion using the generated rate table."""

from ._rates import EUR_PER_UNIT


class UnknownCurrency(KeyError):
    pass


def convert(amount, currency, to="EUR"):
    source, target = currency.upper(), to.upper()
    for code in (source, target):
        if code not in EUR_PER_UNIT:
            raise UnknownCurrency(code)
    return amount * EUR_PER_UNIT[source] / EUR_PER_UNIT[target]


def to_eur(transaction):
    return convert(transaction.amount, transaction.currency)
