# Solution Design — stockroom (spec: inventory-feature)

## 1. Overview

`stockroom` keeps an in-memory inventory of SKUs. All amounts of money are integers in cents; there is no floating point anywhere in the library. Standard library only.

## 2. Modules

| Module | Responsibility |
|---|---|
| `stockroom/item.py` | `Item(sku, name, qty, unit_price_cents)` — validates non-empty sku, qty >= 0, price >= 0 |
| `stockroom/inventory.py` | `Inventory` — items keyed by SKU |
| `stockroom/csvio.py` | CSV import/export, columns `sku,name,qty,unit_price_cents` |
| `stockroom/report.py` | Plain-text reports |

## 3. Interfaces

### 3.1 Inventory

- `add(item)` — `TypeError` if not an `Item`, `ValueError` on duplicate SKU.
- `get(sku)` — `KeyError` if unknown.
- `remove(sku, qty)` — `ValueError` if `qty <= 0`.
- `items()` — all items sorted by SKU.
- `total_value()` — sum of `qty * unit_price_cents`, in cents.
- `low_stock(threshold)` — items with `qty < threshold`, sorted by SKU.

### 3.2 CSV

- `load_csv(path)` — header must equal the column list exactly; a malformed row raises `ValueError` naming the 1-based file line.
- `dump_csv(inv, path)` — header row, then items sorted by SKU.

### 3.3 Reports

- `format_cents(cents)` — `'D.CC'`.
- `format_report(inv)` — one line `<sku> <name> x<qty> @ <unit price>` per item sorted by SKU, then `TOTAL <total value>`.

## 4. Conventions

- Errors are raised, never printed or swallowed.
- Every public function has a unit test under `tests/`, one test module per library module.
