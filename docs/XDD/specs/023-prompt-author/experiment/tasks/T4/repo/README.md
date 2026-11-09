# ledgerlite

Small CSV ledger reports, converted to EUR.

    python3 -m ledgerlite.cli report --by month path/to/ledger.csv

Without a file argument the report reads `$LEDGERLITE_HOME/ledger.csv`.

## Development

Run the tests with `python3 -m unittest`.

Exchange rates are in `ledgerlite/_rates.py`.
