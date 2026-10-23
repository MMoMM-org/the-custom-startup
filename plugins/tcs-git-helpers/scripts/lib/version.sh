#!/usr/bin/env bash
#
# scripts/lib/version.sh
#
# tcs-git-helpers — dotted-numeric version ordering, shared by the
# SessionStart drift hint and git-setup's conflict detector (#221).
#
# Conventions:
#   - Pure bash 3.2: no `[[ =~ ]]`, no `sort -V` (not portable to BSD).
#   - Accepts an optional leading 'v' on either side.

# Return 0 iff version $1 is strictly newer than version $2. Both must be
# dotted numerics (e.g. 2.2.39); anything else returns 1, so a caller falls
# back to treating the pair as "older/different" — the pre-#221 behaviour.
# Missing trailing components count as 0 (2.2 == 2.2.0).
_version_newer() {
  local a="${1#v}" b="${2#v}"
  case "$a" in ''|*[!0-9.]*|.*|*.|*..*) return 1 ;; esac
  case "$b" in ''|*[!0-9.]*|.*|*.|*..*) return 1 ;; esac
  local x y
  while [ -n "$a" ] || [ -n "$b" ]; do
    x="${a%%.*}"; y="${b%%.*}"
    x=$((10#${x:-0})); y=$((10#${y:-0}))
    [ "$x" -gt "$y" ] && return 0
    [ "$x" -lt "$y" ] && return 1
    case "$a" in *.*) a="${a#*.}" ;; *) a="" ;; esac
    case "$b" in *.*) b="${b#*.}" ;; *) b="" ;; esac
  done
  return 1
}
