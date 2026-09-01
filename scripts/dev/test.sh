#!/usr/bin/env bash
#
# scripts/dev/test.sh — run the whole test suite locally.
#
#   ./scripts/dev/test.sh            # provision if needed, then run both suites
#   ./scripts/dev/test.sh pytest     # python suites only
#   ./scripts/dev/test.sh bats       # bats suites only
#   ./scripts/dev/test.sh setup      # provision .venv and exit
#
# Provisions everything into .venv/ (gitignored): pytest and PyYAML via pip,
# bats via npm. Re-running is cheap — provisioning is skipped when the tools
# are already there.
#
# Why bats lands in .venv too: it is a bash program, not a pip package, so npm
# installs it under .venv/node_modules and we symlink it into .venv/bin. That
# keeps a single directory to activate and a single directory to throw away.
#
# Note for the Docker dev container: .venv/ is a bind mount shared with the
# macOS host, so a venv built on one side has an interpreter path that does not
# exist on the other. This script detects that and rebuilds in place rather
# than failing with `bad interpreter`.
#
# bash 3.2 compatible (macOS default /bin/bash).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VENV="$REPO_ROOT/.venv"
BATS_VERSION="1.13.0"

cd "$REPO_ROOT"

_log() { printf '\033[1m==>\033[0m %s\n' "$*"; }
_err() { printf 'error: %s\n' "$*" >&2; }

# ---------------------------------------------------------------------------
# Provisioning
# ---------------------------------------------------------------------------

_venv_is_usable() {
  [ -x "$VENV/bin/python" ] && "$VENV/bin/python" -c 'pass' >/dev/null 2>&1
}

_provision() {
  if ! _venv_is_usable; then
    if [ -d "$VENV" ]; then
      # Empty it rather than remove it: in the dev container .venv is a bind
      # mount and cannot be removed, only emptied. `python3 -m venv` on a
      # half-populated directory leaves a dangling bin/python in place, so the
      # wipe has to happen first.
      _log "clearing unusable .venv"
      find "$VENV" -mindepth 1 -maxdepth 1 -exec rm -rf {} +
    fi
    _log "creating .venv"
    python3 -m venv "$VENV"
  fi

  if ! "$VENV/bin/python" -c 'import pytest, yaml' >/dev/null 2>&1; then
    _log "installing python test dependencies"
    "$VENV/bin/python" -m pip install --quiet --disable-pip-version-check \
      -r "$REPO_ROOT/requirements-dev.txt"
  fi

  if [ ! -x "$VENV/bin/bats" ]; then
    if ! command -v npm >/dev/null 2>&1; then
      _err "npm is required to install bats (see https://bats-core.readthedocs.io for alternatives)"
      return 1
    fi
    _log "installing bats ${BATS_VERSION}"
    npm install --silent --prefix "$VENV" --no-save "bats@${BATS_VERSION}"
    ln -sf ../node_modules/.bin/bats "$VENV/bin/bats"
  fi
}

# ---------------------------------------------------------------------------
# Suites
# ---------------------------------------------------------------------------

# Collected from the repo root, not from tests/ — the root conftest.py sets the
# collection rules and several suites live next to the code they cover.
_run_pytest() {
  _log "pytest"
  "$VENV/bin/pytest" -q "$@"
}

_run_bats() {
  _log "bats"
  # The bats suites shell out to `python3` for YAML validation, so the venv has
  # to be on PATH — not just referenced by absolute path.
  PATH="$VENV/bin:$PATH" \
    "$VENV/bin/bats" --recursive --print-output-on-failure "$@" plugins/*/tests/bats
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

target="${1:-all}"
[ "$#" -gt 0 ] && shift

case "$target" in
  setup)
    _provision
    _log "ready — .venv/bin/{pytest,bats}"
    ;;
  pytest)
    _provision
    _run_pytest "$@"
    ;;
  bats)
    _provision
    _run_bats "$@"
    ;;
  all)
    _provision
    # Run both even if the first fails, so one red suite does not hide the
    # state of the other. Exit non-zero if either did.
    rc=0
    _run_pytest || rc=1
    _run_bats || rc=1
    if [ "$rc" -ne 0 ]; then
      _err "test suites failed"
    else
      _log "all suites passed"
    fi
    exit "$rc"
    ;;
  *)
    _err "unknown target '$target' (expected: all, pytest, bats, setup)"
    exit 2
    ;;
esac
