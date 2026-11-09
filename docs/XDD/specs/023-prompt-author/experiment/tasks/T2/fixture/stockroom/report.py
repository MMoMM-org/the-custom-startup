"""Plain-text stock reports."""


def format_cents(cents):
    """Format an integer amount of cents as 'D.CC' (e.g. 1234 -> '12.34')."""
    return "{}.{:02d}".format(cents // 100, cents % 100)


def format_report(inv):
    """One line per item, sorted by SKU, then a TOTAL line.

    Line format: '<sku> <name> x<qty> @ <unit price>'.
    """
    lines = []
    for item in inv.items():
        lines.append("{} {} x{} @ {}".format(
            item.sku, item.name, item.qty, format_cents(item.unit_price_cents)))
    lines.append("TOTAL {}".format(format_cents(inv.total_value())))
    return "\n".join(lines)
