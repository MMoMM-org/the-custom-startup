"""Read and write inventories as CSV files.

Columns: sku,name,qty,unit_price_cents (header row required).
"""

import csv

from stockroom.inventory import Inventory
from stockroom.item import Item

COLUMNS = ["sku", "name", "qty", "unit_price_cents"]


def load_csv(path):
    """Load an Inventory from `path`. Raises ValueError on a malformed row."""
    inv = Inventory()
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames != COLUMNS:
            raise ValueError("unexpected header: {!r}".format(reader.fieldnames))
        for lineno, row in enumerate(reader, start=2):
            try:
                item = Item(row["sku"], row["name"], int(row["qty"]),
                            int(row["unit_price_cents"]))
            except (TypeError, ValueError) as exc:
                raise ValueError("line {}: {}".format(lineno, exc))
            inv.add(item)
    return inv


def dump_csv(inv, path):
    """Write `inv` to `path`, items sorted by SKU."""
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(COLUMNS)
        for item in inv.items():
            writer.writerow([item.sku, item.name, item.qty, item.unit_price_cents])
