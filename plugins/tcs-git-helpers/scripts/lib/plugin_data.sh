#!/usr/bin/env bash
#
# scripts/lib/plugin_data.sh
#
# tcs-git-helpers — the one plugin-side resolver for the per-repo data
# directory. Sourced by lib/cache.sh and lib/audit_log.sh.
#
# The harness sets
#     CLAUDE_PLUGIN_DATA = ${HOME}/.claude/plugins/data/<plugin>-<repo basename>
# but only for code it spawns itself. Git-spawned hooks (core.hooksPath) and
# Bash-tool subprocesses get nothing, so the fallback has to reconstruct that
# shape rather than invent one — a fallback that lands elsewhere makes the
# writer and the reader use different directories, and a reader then serves a
# stale cache with no error to show for it.
#
# templates/githooks/lib-bundle.sh carries the same rule in _resolve_data_dir.
# That copy is unavoidable: the bundle is installed byte-verbatim into consumer
# repos and cannot source anything from the plugin. tests/bats/cache-path-parity.bats
# executes both and asserts they agree — that test is what keeps the copies honest.
#
# Layout under the data dir:
#   cache/                     stale-branch, PR-state and nudge files
#   audit/overrides.jsonl      override audit trail
#
# Conventions:
#   - Pure bash 3.2: no `declare -A`, no `mapfile`.
#   - Safe to source under `set -uo pipefail`.

# Print the absolute path to this repo's plugin data directory.
#
# Returns:
#   0  — path printed to stdout
#   1  — not inside a git repository (nothing printed)
_plugin_data_dir() {
  # 1. Explicit override wins — the harness sets it, and tests redirect with it.
  if [ -n "${CLAUDE_PLUGIN_DATA:-}" ]; then
    local d="$CLAUDE_PLUGIN_DATA"
    # Strip trailing slashes. Python's pathlib collapses them and printf does
    # not, so an override ending in "/" would put the shell writer and the
    # Python reader in paths that differ only by a slash — the same class of
    # split this resolver exists to close.
    while [ "$d" != "/" ] && [ "${d%/}" != "$d" ]; do d="${d%/}"; done
    printf '%s' "$d"
    return 0
  fi

  # 2. Derive from repo identity, reproducing the harness's own shape.
  local repo_path repo_name
  repo_path="$(git rev-parse --show-toplevel 2>/dev/null)" || return 1
  repo_name="$(basename "$repo_path")"
  printf '%s/.claude/plugins/data/tcs-git-helpers-%s' "$HOME" "$repo_name"
}
