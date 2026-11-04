"""A single stock-keeping unit held in the inventory."""


class Item:
    """One SKU with its on-hand quantity and unit price in cents."""

    def __init__(self, sku, name, qty, unit_price_cents):
        if not sku:
            raise ValueError("sku must be non-empty")
        if qty < 0:
            raise ValueError("qty must be >= 0")
        if unit_price_cents < 0:
            raise ValueError("unit_price_cents must be >= 0")
        self.sku = sku
        self.name = name
        self.qty = qty
        self.unit_price_cents = unit_price_cents

    def __eq__(self, other):
        if not isinstance(other, Item):
            return NotImplemented
        return (self.sku, self.name, self.qty, self.unit_price_cents) == (
            other.sku, other.name, other.qty, other.unit_price_cents)

    def __repr__(self):
        return "Item({!r}, {!r}, {!r}, {!r})".format(
            self.sku, self.name, self.qty, self.unit_price_cents)
