"""In-memory inventory keyed by SKU."""

from stockroom.item import Item


class Inventory:
    """Holds Items keyed by SKU."""

    def __init__(self, items=None):
        self._items = {}
        for item in items or []:
            self.add(item)

    def add(self, item):
        """Add a new Item. Raises ValueError if the SKU already exists."""
        if not isinstance(item, Item):
            raise TypeError("expected Item")
        if item.sku in self._items:
            raise ValueError("duplicate sku: " + item.sku)
        self._items[item.sku] = item

    def get(self, sku):
        """Return the Item for `sku`. Raises KeyError if unknown."""
        return self._items[sku]

    def remove(self, sku, qty):
        """Take `qty` units of `sku` out of stock."""
        if qty <= 0:
            raise ValueError("qty must be > 0")
        item = self.get(sku)
        item.qty = max(0, item.qty - qty)

    def items(self):
        """All Items sorted by SKU."""
        return [self._items[k] for k in sorted(self._items)]

    def total_value(self):
        """Sum of qty * unit_price_cents over all items, in cents."""
        return sum(i.qty * i.unit_price_cents for i in self._items.values())

    def low_stock(self, threshold):
        """Items whose qty is strictly below `threshold`, sorted by SKU."""
        return [i for i in self.items() if i.qty < threshold]

    def __len__(self):
        return len(self._items)
