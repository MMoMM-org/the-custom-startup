#!/usr/bin/env bash
# Developer entry point. Usage: ./scripts/dev.sh <test|lint|fmt|gen> [args]
set -euo pipefail
cd "$(dirname "$0")/.."

cmd="${1:-}"
shift || true

case "$cmd" in
  test)
    export LEDGERLITE_HOME="$PWD/tests/fixtures"
    status=0
    python3 -m unittest discover -s tests -t . "$@" || status=$?
    printf '%s\n' "$status" > .dev-test-stamp
    exit "$status"
    ;;
  lint)
    python3 scripts/lint.py ledgerlite tests scripts
    python3 scripts/gen_rates.py --check
    ;;
  fmt)
    python3 scripts/lint.py --fix ledgerlite tests scripts
    ;;
  gen)
    python3 scripts/gen_rates.py
    ;;
  *)
    echo "usage: $0 <test|lint|fmt|gen>" >&2
    exit 2
    ;;
esac
