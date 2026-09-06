#!/usr/bin/env bash
#
# .claude/observability/logwrite.sh
#
# Self-contained writer for spec 018 (observability of what loads and
# fires). ADR-1: this is NOT sourced from any plugin. `.claude/` is
# gitignored wholesale in this repo (see .gitignore) and, more importantly,
# a hook script must work standalone with nothing else guaranteed to be on
# disk — so this file duplicates the per-repo data-directory contract in
# plugins/tcs-git-helpers/scripts/lib/plugin_data.sh on purpose, rather than
# sourcing it.
#
# The harness sets
#     CLAUDE_PLUGIN_DATA = $HOME/.claude/plugins/data/<plugin>-<repo basename>
# for code it spawns itself, but hooks invoked outside the harness (or by
# git) get nothing. The fallback below reconstructs that exact shape rather
# than inventing a new one: a fallback that lands elsewhere would put the
# writer and any future reader of this data in different directories, with
# no error to show for it — just data that silently never appears where a
# reader looks for it.
#
# tests/bats/observability-writer.bats executes this resolver alongside
# plugin_data.sh's _plugin_data_dir and asserts they agree in shape (same
# parent directory, same repo-basename derivation, same trailing-slash
# handling) — that test is what keeps this deliberate copy honest, the same
# pattern plugins/tcs-git-helpers/tests/bats/cache-path-parity.bats uses for
# the plugin's own resolvers.
#
# Scope: this file implements the data-directory resolver (T1.1), the
# append/escape/truncate/rotate write path (T1.2) — `_observability_write` —
# and the extraction and reduction helpers (T1.3): `_observability_field`,
# `_observability_detail_enabled`, `_observability_program_name` and
# `_observability_redact_path`, plus the reduction gate inside
# `_observability_write`. It still knows nothing about which fields a given
# `kind` carries: `_observability_write` takes generic `key=value` pairs and
# decides only whether each one survives reduced mode. Mapping a payload to a
# kind's fields belongs to the adapters (phase 2), which do not exist yet.
#
# Conventions:
#   - Pure bash 3.2: no `declare -A`, no `mapfile`, no `${var^^}` (CON-1).
#   - Safe to source under `set -uo pipefail`.
#   - CON-3: LC_ALL=C is exported below, before any formatting or arithmetic
#     in this file (a comma-decimal locale corrupts formatted numbers).
#   - CON-5: every failure path in `_observability_write` is silent and
#     returns 0 — no stdout (CON-4: a hook's stdout is parsed as JSON), no
#     stderr either, so a caller's own streams are never touched by ours.

export LC_ALL=C

# Print the absolute path to this repo's observability data directory.
#
# Resolution order (ADR-1, mirroring _plugin_data_dir):
#   1. $CLAUDE_OBSERVABILITY_DATA, if set — trailing slashes stripped.
#   2. $HOME/.claude/plugins/data/observability-<repo basename>
#
# Args:
#   $1, optional — a pre-resolved `git rev-parse --show-toplevel` value.
#       Passing it (even as an empty string, meaning "outside a repo") skips
#       this function's own git fork; omitting the argument entirely keeps
#       the original zero-arg behaviour exactly, which is what T1.1's tests
#       call and must keep passing unchanged. This is CON-7: a caller such
#       as _observability_write that must ALSO resolve the toplevel for the
#       `repo` field (below) forks git once and hands the result in here,
#       rather than this resolver forking it again independently.
#
# Returns:
#   0 — path printed to stdout
#   1 — not inside a git repository (nothing printed). A caller that must
#       still produce a record outside a repo applies the $PWD-basename
#       fallback itself (SDD/Error Handling, matching _audit_log) — this
#       resolver does not do that fallback.
_observability_data_dir() {
  # 1. Explicit override wins — tests redirect with it.
  if [ -n "${CLAUDE_OBSERVABILITY_DATA:-}" ]; then
    local d="$CLAUDE_OBSERVABILITY_DATA"
    # Strip trailing slashes so an override ending in "/" cannot put two
    # callers in paths that differ only by a slash.
    while [ "$d" != "/" ] && [ "${d%/}" != "$d" ]; do d="${d%/}"; done
    printf '%s' "$d" || true
    return 0
  fi

  # 2. Derive from repo identity, reproducing the harness's own shape.
  local repo_path repo_name
  if [ $# -ge 1 ]; then
    repo_path="$1"                  # pre-resolved by the caller
  else
    repo_path="$(git rev-parse --show-toplevel 2>/dev/null)" || repo_path=""
  fi
  [ -n "$repo_path" ] || return 1
  repo_name="$(basename "$repo_path")"
  printf '%s/.claude/plugins/data/observability-%s' "$HOME" "$repo_name"
}

# ---------------------------------------------------------------------------
# T1.2 — append, escape, truncate, rotate.
#
# Public entry point: _observability_write kind=<kind> session=<session_id>
#   [key=value ...]
# `ts` and `repo` are computed here and cannot be overridden by a caller —
# they are frozen, always-present fields (SDD/Application Data Models).
# Any other key=value pair is written through verbatim, in the order given,
# after the four frozen fields — this is deliberately generic: the writer
# knows nothing about which fields a given `kind` carries. That belongs to
# the adapters (phase 2). The one judgement it does make about a caller's
# field is T1.3's reduction gate: whether the field survives reduced mode.
# A key may carry a `detail:` prefix to mark it detail-only.
# ---------------------------------------------------------------------------

# JSON-escape one value without forking an external process. Named with the
# file's _observability_* prefix (previously _json_escape) for consistency —
# nothing else in this file stands outside that convention. bash 3.2
# supports ${var//x/y}, so this needs nothing beyond the shell itself.
# Ground truth for the field set and rotation chain is audit_log.sh, but
# that helper's fallback path forks a stream editor once per field; at
# several hook invocations per tool call that fork is the difference
# between fitting the hook-path overhead budget and not (SDD/Implementation
# Examples).
#
# Every remaining C0 control byte (0x01-0x1F, minus \t \n \r handled
# above — 0x00 cannot occur, bash strings cannot hold a NUL byte) is also
# escaped, as \u00XX. This deliberately goes further than audit_log.sh's
# own escaping (backslash and double-quote only, not even \n) — that
# precedent is judged against the wrong consumer here. report.py (ADR-6) is
# Python, and the SDD has it read with errors='replace', skipping and
# counting a line it cannot parse. The command-line JSON query tool used
# elsewhere in this repo's own offline test suite (name withheld from this
# comment on purpose — this file has a test asserting that name is absent
# from its own source text) accepts a raw control byte in a string
# leniently, but Python's json.loads REJECTS it outright ("Invalid
# control character") — so an unescaped 0x1B in a path would not just look
# odd, it would make report.py silently drop the whole record as
# unparseable. That is exactly the "records wrong things" failure CON-9
# says this design must avoid, and phase 3 is where it would surface, far
# from its cause. Still fork-free (ADR-5, CON-7): every substitution below
# is ${var//x/y}, same as the five above it, so a value with none of these
# bytes costs 33 no-op pattern checks, not a process.
_observability_json_escape() {
  local s="$1"
  s="${s//\\/\\\\}"
  s="${s//\"/\\\"}"
  s="${s//$'\n'/\\n}"
  s="${s//$'\r'/\\r}"
  s="${s//$'\t'/\\t}"
  s="${s//$'\x01'/\\u0001}"
  s="${s//$'\x02'/\\u0002}"
  s="${s//$'\x03'/\\u0003}"
  s="${s//$'\x04'/\\u0004}"
  s="${s//$'\x05'/\\u0005}"
  s="${s//$'\x06'/\\u0006}"
  s="${s//$'\x07'/\\u0007}"
  s="${s//$'\x08'/\\u0008}"
  s="${s//$'\x0b'/\\u000b}"
  s="${s//$'\x0c'/\\u000c}"
  s="${s//$'\x0e'/\\u000e}"
  s="${s//$'\x0f'/\\u000f}"
  s="${s//$'\x10'/\\u0010}"
  s="${s//$'\x11'/\\u0011}"
  s="${s//$'\x12'/\\u0012}"
  s="${s//$'\x13'/\\u0013}"
  s="${s//$'\x14'/\\u0014}"
  s="${s//$'\x15'/\\u0015}"
  s="${s//$'\x16'/\\u0016}"
  s="${s//$'\x17'/\\u0017}"
  s="${s//$'\x18'/\\u0018}"
  s="${s//$'\x19'/\\u0019}"
  s="${s//$'\x1a'/\\u001a}"
  s="${s//$'\x1b'/\\u001b}"
  s="${s//$'\x1c'/\\u001c}"
  s="${s//$'\x1d'/\\u001d}"
  s="${s//$'\x1e'/\\u001e}"
  s="${s//$'\x1f'/\\u001f}"
  printf '%s' "$s" || true
}

# Replace any byte that cannot be part of well-formed UTF-8 with '?'
# (CON-10: POSIX paths may hold arbitrary bytes; JSON requires UTF-8). Pure
# bash 3.2: byte values come from `printf '%d' "'$c"`, a builtin, not an
# external process. Every byte under 0x80 is plain ASCII and always valid.
# Above that, a lead byte is checked, its declared count of continuation
# bytes (0x80-0xBF) is verified, AND — for the four lead bytes where
# sequence length alone is not sufficient (RFC 3629 Table 3-7) — the FIRST
# continuation byte's range is checked too:
#   0xE0  first continuation must be >= 0xA0   (else an overlong 3-byte form)
#   0xED  first continuation must be <  0xA0   (else a UTF-16 surrogate half,
#                                                U+D800-U+DFFF)
#   0xF0  first continuation must be >= 0x90   (else an overlong 4-byte form)
#   0xF4  first continuation must be <= 0x8F   (else > U+10FFFF)
# Anything that does not fit — a bad lead byte, a truncated sequence, a
# stray continuation byte on its own, or one of the four structurally
# invalid cases above — becomes '?'. The common case (no byte >= 0x80 at
# all) short-circuits on the first glob check below and never enters the
# byte-by-byte loop.
_observability_sanitize_utf8() {
  local s="$1"
  case "$s" in
    *[!\ -~]*) ;;                 # contains a byte outside printable ASCII
    *) printf '%s' "$s" || true; return 0 ;;
  esac

  local len=${#s} i=0 out="" c ord need j ok seq cbyte cord raw_ord
  while [ "$i" -lt "$len" ]; do
    c="${s:$i:1}"
    raw_ord="$(printf '%d' "'$c")" || raw_ord=0
    ord=$(( raw_ord & 0xFF ))
    if [ "$ord" -lt 128 ]; then
      out="$out$c"
      i=$((i + 1))
      continue
    fi
    if   [ "$ord" -ge 194 ] && [ "$ord" -le 223 ]; then need=1
    elif [ "$ord" -ge 224 ] && [ "$ord" -le 239 ]; then need=2
    elif [ "$ord" -ge 240 ] && [ "$ord" -le 244 ]; then need=3
    else
      out="${out}?"
      i=$((i + 1))
      continue
    fi
    ok=1
    seq="$c"
    j=1
    while [ "$j" -le "$need" ]; do
      if [ $((i + j)) -ge "$len" ]; then ok=0; break; fi
      cbyte="${s:$((i + j)):1}"
      raw_ord="$(printf '%d' "'$cbyte")" || raw_ord=0
      cord=$(( raw_ord & 0xFF ))
      if [ "$cord" -lt 128 ] || [ "$cord" -gt 191 ]; then ok=0; break; fi
      if [ "$j" -eq 1 ]; then
        case "$ord" in
          224) [ "$cord" -ge 160 ] || { ok=0; break; } ;;   # 0xE0: overlong 3-byte
          237) [ "$cord" -lt 160 ] || { ok=0; break; } ;;   # 0xED: surrogate half
          240) [ "$cord" -ge 144 ] || { ok=0; break; } ;;   # 0xF0: overlong 4-byte
          244) [ "$cord" -le 143 ] || { ok=0; break; } ;;   # 0xF4: > U+10FFFF
        esac
      fi
      seq="$seq$cbyte"
      j=$((j + 1))
    done
    if [ "$ok" -eq 1 ]; then
      out="$out$seq"
      i=$((i + need + 1))
    else
      out="${out}?"
      i=$((i + 1))
    fi
  done
  printf '%s' "$out" || true
}

# Sanitize, cut to the 256-BYTE field limit, then escape — in that order,
# so a cut that lands mid-sequence is healed by a second sanitize pass
# rather than leaking a broken byte. Prints "<0|1>\x1f<escaped value>": the
# leading flag is 1 when the value was cut, so the caller can decide whether
# to add `truncated: true` without a second length check.
#
# Bytes, deliberately, not characters: LC_ALL=C (top of file) makes bash
# treat every string as a raw byte sequence, so ${#clean} and ${clean:0:N}
# already count and slice by BYTE, not by decoded codepoint — a value with
# 200 multi-byte characters is well under 256 of THOSE but can be well over
# 256 bytes. Character-counting would mean decoding UTF-8 by hand on every
# field of every record, which CON-7's hot-path budget cannot afford; bytes
# is also the unit audit_log.sh's own 256-char limit is effectively using
# (LC_ALL=C there too), so this matches the cited precedent more closely
# than character-counting would. If a cut lands inside a multi-byte
# sequence, the second _observability_sanitize_utf8 pass below replaces the
# now-broken tail with '?' rather than emitting invalid UTF-8.
_observability_prepare_field() {
  local raw="$1" clean trunc=0
  clean="$(_observability_sanitize_utf8 "$raw")" || clean=""
  if [ "${#clean}" -gt 256 ]; then      # byte count under LC_ALL=C
    clean="${clean:0:256}"              # byte-offset slice under LC_ALL=C
    clean="$(_observability_sanitize_utf8 "$clean")" || clean=""
    trunc=1
  fi
  printf '%d\37%s' "$trunc" "$(_observability_json_escape "$clean")" || true
}

# Portable file size in bytes; 0 if the file is missing. Mirrors
# _audit_log_size exactly (ADR-8: audit_log.sh is ground truth).
_observability_size() {
  local f="$1"
  [ -f "$f" ] || { printf '0' || true; return 0; }
  if stat -f%z "$f" 2>/dev/null; then
    return 0
  fi
  stat -c%s "$f" 2>/dev/null || printf '0' || true
}

# Rotate when size >= 1024000 bytes. Chain: .jsonl -> .1 -> .2 -> .3
# (oldest). No .4 is EVER produced because there is no "mv .3 .4" step
# anywhere in this chain — that is the actual guarantee; it does not come
# from the .3 discard below (a mutation test confirmed this: removing the
# discard leaves "no .4" fully intact).
#
# What the discard actually does: nothing, in the common case. If .2 is
# present, `mv .2 .3` unconditionally overwrites .3 whether or not it was
# discarded first (that's just how `mv` behaves) — every test built around
# a full .1/.2/.3 chain exercises exactly that no-op case. It matters only
# when .3 is present and .2 is NOT (a partial chain, e.g. left behind by an
# earlier failed rotation): without the discard, a stale .3 would sit there
# untouched forever, since nothing else ever clears it when .2 stays empty;
# with it, that stale .3 is dropped on the next rotation instead.
#
# Silent on every failure — mid-chain breakage is swallowed and the next
# write simply appends to whatever file exists (SDD/Error Handling).
_observability_rotate_if_oversized() {
  local f="$1"
  [ -f "$f" ] || return 0
  local size
  size="$(_observability_size "$f")" || size=0
  case "$size" in
    ''|*[!0-9]*) return 0 ;;
  esac
  [ "$size" -lt 1024000 ] && return 0
  # Each line below must independently survive a `set -e` caller: under
  # errexit, `cond && cmd` aborts the whole script if cond is true AND cmd
  # fails (confirmed empirically) — a bare trailing `true` after the LAST
  # line only protects that one line, not the ones before it, so every line
  # gets its own `|| true` (SDD/Error Handling: "rotation fails mid-chain:
  # swallow; the next write appends to whatever exists").
  [ -f "$f.3" ] && { rm -f "$f.3" 2>/dev/null || true; }
  [ -f "$f.2" ] && { mv "$f.2" "$f.3" 2>/dev/null || true; }
  [ -f "$f.1" ] && { mv "$f.1" "$f.2" 2>/dev/null || true; }
  mv "$f" "$f.1" 2>/dev/null || true
  return 0
}

# The `repo` field's value: the git toplevel basename, never the absolute
# path (redaction, R-3). Falls back to $PWD's basename outside a git repo,
# matching _audit_log's own fallback.
#
# Args:
#   $1, optional — a pre-resolved `git rev-parse --show-toplevel` value,
#       same convention as _observability_data_dir above: pass it (even
#       empty) to skip this function's own fork; omit it to let this
#       function resolve the toplevel itself. _observability_write always
#       passes it, so in practice this function forks nothing — the one
#       fork it would otherwise do is shared with the data-dir resolution.
_observability_repo_field() {
  local repo_path
  if [ $# -ge 1 ]; then
    repo_path="$1"
  else
    repo_path="$(git rev-parse --show-toplevel 2>/dev/null)" || repo_path=""
  fi
  [ -n "$repo_path" ] || repo_path="${PWD:-}"
  printf '%s' "${repo_path##*/}" || true
}

# ---------------------------------------------------------------------------
# T1.3 — extraction and reduction.
#
# Two independent switches, both default off (ADR-4). Redaction is OURS: the
# harness's OTEL_LOG_* family governs only Anthropic's own export, and hook
# stdin always arrives COMPLETE — there is no environment variable that
# redacts it. A design that assumed otherwise would record everything while
# looking safe.
#
#   CLAUDE_OBSERVABILITY_ENABLED=1   recording happens at all (checked in
#                                    _observability_write, above)
#   CLAUDE_OBSERVABILITY_DETAIL=1    adds the sensitive fields; requires the
#                                    first to have any effect
# ---------------------------------------------------------------------------

# Extract one string field from a JSON payload without forking.
#
# Named _observability_field, not `_field` as the SDD's example writes it, for
# the same reason _json_escape became _observability_json_escape: this file is
# SOURCED into hook adapters, and `_field` is a name a future adapter (or
# anything else sourced alongside it) could plausibly define for itself. A
# collision here would be silent and would corrupt every record.
#
# Args: $1 payload, $2 key.
# Prints the value, or nothing. Always returns 0 (CON-5) — a hook adapter
# running under `set -e` must never abort because a field was missing.
#
# Measured: the command-line JSON query tool the SDD compares against costs
# ~21 ms per call (its name is withheld here on purpose — this file has a
# test asserting that name is absent from its own source text, so that "the
# writer forks no stream editor or JSON parser" can be checked statically);
# this costs ~0 ms, because it forks nothing (ADR-5, CON-7).
#
#   local body="${1#*\"$2\":\"}"   everything after the literal  "key":"
#   [ "$body" = "$1" ] -> absent   parameter expansion that finds NO match
#                                  returns the string UNCHANGED
#   printf '%s' "${body%%\"*}"     up to the closing quote
#
# THE SECOND LINE IS THE REDACTION-CRITICAL LINE OF THE WHOLE DESIGN. Without
# it, a request for an absent key returns the ENTIRE payload — which, on a
# Bash PreToolUse, is the full command line, credentials included. It has its
# own test (tests/bats/observability-writer.bats, "a payload missing the
# requested key yields empty, never the whole payload"), which scans the raw
# record bytes for a token-shaped canary rather than looking up a field: a
# check of `field == ""` alone would stay green while the payload leaked into
# some other field.
#
# The opening quote in the pattern is load-bearing too, in a quieter way: the
# search is for `"key":"`, not `key":"`, so a short key cannot match inside a
# longer one — `path` misses `"file_path":"` because the byte before `path`
# there is `_`, not a quote. Dropping it would make every short key silently
# pick up a longer neighbour's value. Also tested.
#
# Known limits, both accepted (SDD/Known Technical Issues — "a string
# operation, not a JSON parser"):
#   - A value containing an escaped quote (\") is cut at that quote, because
#     `${body%%\"*}` stops at the first `"` BYTE. The extractor therefore
#     UNDER-captures. It never over-captures, which is the direction that
#     would leak; the escaper downstream keeps the resulting dangling
#     backslash legal JSON. Both directions are tested.
#   - A key name appearing inside another field's VALUE can be matched. The
#     result is still a value from within the payload, never the payload
#     itself, so the redaction guarantee holds; the field could be wrong.
_observability_field() {
  local payload="${1:-}" key="${2:-}"
  # An empty key would make the pattern `*"":"`, which matches unrelated
  # text. Nothing legitimately asks for it.
  [ -n "$key" ] || { printf '' || true; return 0; }
  local body="${payload#*\"$key\":\"}"
  if [ "$body" = "$payload" ]; then   # key absent — NOT the whole payload
    printf '' || true
    return 0
  fi
  printf '%s' "${body%%\"*}" || true
  return 0
}

# True only when BOTH switches are on. Detail mode is subordinate by design:
# two affirmative steps, as the harness's own telemetry requires. Returns 1
# (reduced mode) in every other case, including both unset — the default.
_observability_detail_enabled() {
  [ "${CLAUDE_OBSERVABILITY_ENABLED:-}" = "1" ] || return 1
  [ "${CLAUDE_OBSERVABILITY_DETAIL:-}" = "1" ] || return 1
  return 0
}

# The program name of a Bash call: argv[0] only, never an argument.
#
# This is the keep half of the keep/drop table's Bash row, and it mirrors the
# harness's own `bash_command` (always) versus `full_command` (gated) split —
# chosen because it is the split someone has already thought about, and
# because keeping the verb is what makes a reduced record diagnostic rather
# than merely safe.
#
# A path-qualified argv[0] is reduced to its last component. The program NAME
# is what the table keeps; the directory it happens to live in is an absolute
# path, and on a real machine frequently an absolute HOME path — exactly what
# the drop half forbids. Fork-free: leading whitespace is removed with a
# pattern expansion, not with a call to anything.
_observability_program_name() {
  local cmd="${1:-}" lead first
  # ${cmd%%[^[:space:]]*} removes the longest suffix that starts with a
  # non-space character, i.e. everything from argv[0] onwards — what is left
  # is exactly the leading whitespace run.
  lead="${cmd%%[^[:space:]]*}"
  first="${cmd#"$lead"}"
  first="${first%%[[:space:]]*}"           # argv[0]: up to the next space
  printf '%s' "${first##*/}" || true       # name only, never the directory
  return 0
}

# Reduce a filesystem path to something safe to record (R-3).
#
#   inside the repo   -> repo-relative       docs/ai/memory/active.md
#   the toplevel      -> "."
#   already relative  -> unchanged
#   anywhere else     -> basename only       CLAUDE.md
#
# The last case is the one that matters: an absolute path outside the repo is
# very often under $HOME, and the keep/drop table forbids absolute home paths.
# Reducing to the basename keeps the record diagnostic (which file) without
# recording where the user keeps their home directory.
#
# Args:
#   $1 the path.
#   $2, optional — a pre-resolved `git rev-parse --show-toplevel` value, the
#      same convention _observability_data_dir and _observability_repo_field
#      use: pass it (even empty) to skip this function's own fork, omit it to
#      let this function resolve it. Adapters always pass it, so in the hook
#      path this function forks nothing (CON-7).
_observability_redact_path() {
  local p="${1:-}" top
  [ -n "$p" ] || { printf '' || true; return 0; }
  if [ $# -ge 2 ]; then
    top="$2"
  else
    top="$(git rev-parse --show-toplevel 2>/dev/null)" || top=""
  fi
  if [ -n "$top" ]; then
    if [ "$p" = "$top" ]; then
      printf '.' || true
      return 0
    fi
    case "$p" in
      "$top"/*)
        printf '%s' "${p#"$top"/}" || true
        return 0
        ;;
    esac
  fi
  case "$p" in
    /*) printf '%s' "${p##*/}" || true ;;   # absolute, outside the repo
    *)  printf '%s' "$p" || true ;;         # already relative
  esac
  return 0
}

# Field names the writer refuses to emit in reduced mode, as a defence in
# depth behind the `detail:` prefix below. The prefix is how an adapter SAYS
# "this field is sensitive"; this list is what happens when an adapter forgets
# to say it. Every name here is a category the keep/drop table drops outright:
# Bash arguments and hook command strings, file contents, transcript_path,
# absolute cwd, and any prompt or response text.
#
# A space-delimited string rather than an array: bash 3.2 has no associative
# arrays (CON-1), and membership is one glob test with no loop and no fork.
_OBSERVABILITY_DETAIL_ONLY_FIELDS=" command full_command hook_command content file_content transcript_path cwd prompt prompt_text response response_text "

# Is this field name emitted only in detail mode? Returns 0 if so. An empty
# name is not — the membership pattern below would otherwise match on the
# delimiter alone.
_observability_field_is_detail_only() {
  local name="${1:-}"
  [ -n "$name" ] || return 1
  case "$_OBSERVABILITY_DETAIL_ONLY_FIELDS" in
    *" $name "*) return 0 ;;
  esac
  return 1
}

# Append one JSON-object line to this repo's observability event log.
# Always returns 0 and never writes to stdout or stderr (CON-4, CON-5): a
# hook's stdout is parsed as JSON and its exit status must never change
# because recording failed, so every error path below is silent.
_observability_write() {
  [ "${CLAUDE_OBSERVABILITY_ENABLED:-}" = "1" ] || return 0

  # Resolve the repository toplevel ONCE per record (CON-7) and thread it
  # into both consumers below — the data-directory resolver's repo-derived
  # branch and the `repo` field — instead of each forking `git rev-parse`
  # independently. That independent double-fork is precisely the defect
  # SDD/Implementation Examples calls out in audit_log.sh's own
  # _plugin_data_dir ("git×2-3... because _plugin_data_dir calls git
  # rev-parse again"); this writer exists to not repeat it. When
  # CLAUDE_OBSERVABILITY_DATA is set, _observability_data_dir below does no
  # git fork of its own either way — but the `repo` field still needs the
  # toplevel, so this one fork happens on every call, override or not.
  local repo_toplevel
  repo_toplevel="$(git rev-parse --show-toplevel 2>/dev/null)" || repo_toplevel=""

  local data_dir
  data_dir="$(_observability_data_dir "$repo_toplevel" 2>/dev/null)" || data_dir=""
  if [ -z "$data_dir" ]; then
    # Outside a git repository: _observability_data_dir declines by design
    # (T1.1) and leaves this fallback to the caller (SDD/Error Handling,
    # matching _audit_log) — same shape, $PWD's basename standing in for
    # the repo name.
    data_dir="$HOME/.claude/plugins/data/observability-${PWD##*/}"
  fi

  local events_dir="$data_dir/observability"
  local events_file="$events_dir/events.jsonl"

  mkdir -p "$events_dir" 2>/dev/null || return 0

  _observability_rotate_if_oversized "$events_file" || true

  local ts
  ts="$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)" || ts=""
  [ -z "$ts" ] && ts="1970-01-01T00:00:00Z"

  # repo_field is resolved into its own guarded scalar, never inlined into the
  # array literal below: a failing command substitution embedded directly in
  # an array assignment aborts the whole script under a `set -e` caller
  # (confirmed empirically) exactly like a bare scalar assignment does.
  local repo_field
  repo_field="$(_observability_repo_field "$repo_toplevel")" || repo_field=""

  # Ordered field lists: the four frozen fields first, in the frozen order,
  # then whatever the caller passed, in the order given.
  local -a field_names=(ts kind session repo)
  local -a field_values=("$ts" "" "" "$repo_field")

  # T1.3, the reduction gate. Resolved ONCE per record rather than per field:
  # it reads two environment variables that cannot change mid-record, and a
  # per-field call would put a function invocation in the hot path for every
  # field of every event (CON-7).
  local detail_on=0
  if _observability_detail_enabled; then detail_on=1; fi

  local kv key val is_detail
  for kv in "$@"; do
    key="${kv%%=*}"
    val="${kv#*=}"

    # A field is detail-only either because the CALLER said so, with a
    # `detail:` prefix on the key, or because its NAME is one the keep/drop
    # table drops outright. The prefix is the mechanism; the name list is the
    # fail-safe for an adapter that forgets to use it. Order matters: strip
    # the prefix first, so `detail:cwd` and `cwd` are the same field.
    is_detail=0
    case "$key" in
      detail:*) is_detail=1; key="${key#detail:}" ;;
    esac
    if _observability_field_is_detail_only "$key"; then is_detail=1; fi

    # Reduced mode (the default): the field is not written at all — not
    # emptied, not renamed, not summarised. Absent.
    if [ "$is_detail" -eq 1 ] && [ "$detail_on" -ne 1 ]; then
      continue
    fi

    case "$key" in
      kind)    field_values[1]="$val" ;;
      session) field_values[2]="$val" ;;
      ts|repo) : ;;  # frozen — computed above, not caller-settable
      *)
        field_names[${#field_names[@]}]="$key"
        field_values[${#field_values[@]}]="$val"
        ;;
    esac
  done

  local json="{" first=1 any_truncated=0
  local n=${#field_names[@]} idx prepared trunc_flag escaped
  for ((idx = 0; idx < n; idx++)); do
    prepared="$(_observability_prepare_field "${field_values[$idx]}")" || prepared=""
    trunc_flag="${prepared%%$'\37'*}"
    escaped="${prepared#*$'\37'}"
    [ "$trunc_flag" = "1" ] && any_truncated=1
    if [ "$first" -eq 1 ]; then
      first=0
    else
      json="$json,"
    fi
    json="$json\"${field_names[$idx]}\":\"$escaped\""
  done
  [ "$any_truncated" -eq 1 ] && json="$json,\"truncated\":true"
  json="$json}"

  # 2>/dev/null must precede the append redirection: a failed `>>` open is
  # reported by the shell itself, before the command ever runs, so a
  # trailing `2>/dev/null` placed after it is too late to suppress that
  # message (CON-5 — this must stay silent on stderr too).
  printf '%s\n' "$json" 2>/dev/null >>"$events_file" || true
  return 0
}
