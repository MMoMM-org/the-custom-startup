#!/usr/bin/env bats
#
# tests/bats/lib_strip_linear.bats
#
# spec 021 (observability v2), Phase 1, T1.5 -- linear clause stripping.
#
# _strip_quoted and _strip_heredocs (scripts/lib/pattern_match.sh) run in the
# PreToolUse guard on every git-bearing Bash call. Until T1.5 _strip_quoted
# walked one character per iteration with `${cmd:$i:1}`, which re-scans the
# string from the start each time: 157 ms at 2 KB, 3.2 s at 10 KB (SDD/Known
# Technical Issues). T1.5 rewrote both functions to consume runs in bulk. That
# is a pure performance change, so:
#
#   1. the differential tests hold the new code to the OLD code, frozen
#      verbatim below as _ref_strip_quoted / _ref_strip_heredocs (the oracle,
#      copied from pattern_match.sh at f07afee). Byte-identical output for a
#      fixed corpus and for thousands of generated inputs, in the C locale and
#      in a UTF-8 locale (the guard runs in the caller's locale, and in UTF-8 a
#      multibyte character inside quotes is one space, not one per byte);
#   2. the scale tests bound both functions at 20 KB (absolute budget, SDD:
#      well under 100 ms) and require linear growth from 20 KB to 200 KB.
#
# The generator is an explicit LCG, not $RANDOM: the same inputs on bash 3.2
# and 5.x. Outputs go to files and are compared with cmp, so trailing newlines
# survive (command substitution would strip them).
#
# bash 3.2 compatible. bats `run` forbids process substitution; the drivers
# are temp files.

load 'lib/helpers'

setup() {
  PLUGIN_ROOT="$(cd "${BATS_TEST_DIRNAME}/../.." && pwd)"
  LIB="${PLUGIN_ROOT}/scripts/lib/pattern_match.sh"
  UTF8_LOCALE="$(_utf8_locale)"
}

# The first UTF-8 locale in which a two-byte character counts as one. Empty
# when there is none: the tests that need it then fail loudly rather than
# quietly comparing in the C locale twice.
_utf8_locale() {
  local loc
  for loc in C.UTF-8 C.utf8 en_US.UTF-8 en_US.utf8; do
    if [ "$(LC_ALL="$loc" bash -c 'x=$(printf "\303\251"); printf "%s" "${#x}"' 2>/dev/null)" = "1" ]; then
      printf '%s' "$loc"
      return 0
    fi
  done
}

# ---------------------------------------------------------------------------
# The oracle: the pre-T1.5 functions, verbatim (renamed). Do not "fix" these;
# they define the behaviour the rewrite must keep.
# ---------------------------------------------------------------------------

_ref_strip_quoted() {
  local cmd="$1"
  local out=""
  local i=0
  local len=${#cmd}
  local state="N"        # N=normal (code), S=single-quoted, D=double-quoted
  local stack=""         # one saved state char per open $( — innermost first
  local ch prev="" nxt
  while [ "$i" -lt "$len" ]; do
    ch="${cmd:$i:1}"
    nxt="${cmd:$((i + 1)):1}"
    case "$state" in
      S)
        if [ "$ch" = "'" ]; then state="N"; fi
        out="${out} "
        ;;
      D)
        # $( ... ) inside a double-quoted string is still CODE. Enter it in
        # normal state so its command is matched, and remember to come back
        # to D — otherwise the substitution's own quotes desync the outer one.
        if [ "$ch" = '$' ] && [ "$nxt" = "(" ]; then
          stack="D${stack}"
          state="N"
          out="${out}  "
          prev="("
          i=$((i + 2))
          continue
        fi
        if [ "$ch" = '"' ] && [ "$prev" != "\\" ]; then state="N"; fi
        out="${out} "
        ;;
      N)
        if [ "$ch" = '$' ] && [ "$nxt" = "(" ]; then
          stack="N${stack}"
          out="${out}  "
          prev="("
          i=$((i + 2))
          continue
        fi
        case "$ch" in
          "'") state="S"; out="${out} " ;;
          '"') state="D"; out="${out} " ;;
          ')')
            if [ -n "$stack" ]; then
              state="${stack:0:1}"
              stack="${stack:1}"
              out="${out} "
            else
              out="${out}${ch}"
            fi
            ;;
          *) out="${out}${ch}" ;;
        esac
        ;;
    esac
    prev="$ch"
    i=$((i + 1))
  done
  printf '%s' "$out"
}

_ref_strip_heredocs() {
  local cmd="$1"
  local out="" NL line rest delim="" trimmed
  NL=$'\n'
  while IFS= read -r line; do
    if [ -n "$delim" ]; then
      trimmed="${line#"${line%%[![:space:]]*}"}"
      if [ "$line" = "$delim" ] || [ "$trimmed" = "$delim" ]; then
        delim=""
      fi
      out="${out}${NL}"
      continue
    fi
    out="${out}${line}${NL}"
    case "$line" in
      *"<<"*)
        rest="${line#*<<}"
        # `<<<` is a here-string, not a heredoc.
        case "$rest" in
          "<"*) continue ;;
        esac
        # A heredoc feeding an interpreter carries code; leave it in scope.
        # Named explicitly, not as [a-z]*sh — that also matches the "sh" in
        # `git stash`, which would leave a stash command's heredoc in scope.
        if [[ "$line" =~ (^|[^[:alnum:]_])(sh|bash|zsh|ksh|dash|csh|tcsh|fish|python[0-9.]*|perl|ruby|node|awk|sed|eval)([[:space:]]|$) ]]; then
          continue
        fi
        rest="${rest#-}"
        rest="${rest#"${rest%%[![:space:]]*}"}"
        delim="${rest%%[[:space:]]*}"
        delim="${delim%%[<>|;&]*}"
        delim="${delim//\'/}"
        delim="${delim//\"/}"
        ;;
    esac
  done <<< "$cmd"
  printf '%s' "$out"
}

# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------

# _diff_corpus: the fixed cases, one per call of _diff_emit. The parity corpus
# (plugins/tcs-helper/tests/bats/observability-git-parity.bats), the
# pattern_match regression cases, and edges of the run-at-a-time scanner:
# a delimiter at the very start or end, `$` at the end, `$(` split across what
# the scanner treats as runs, backslashes before quotes, empty runs.
_diff_corpus() {
  local NL=$'\n' TAB=$'\t' i
  _diff_emit "git commit -m 'revert: git reset --hard HEAD~1 and git push --force'"
  _diff_emit "git commit -m \"docs: explain git clean -fd and git checkout .\""
  _diff_emit "gh pr create --title 'x' --body 'never run git push --force or bash -c here'"
  _diff_emit "git commit -F - <<'EOF'${NL}fix: git reset --hard is described here${NL}bash -c 'rm -rf x'${NL}EOF"
  _diff_emit "cat <<-EOF${NL}${TAB}git push --force${NL}${TAB}EOF${NL}git status"
  _diff_emit "git commit -F - <<EOF${NL}body mentions git branch -D${NL}EOF${NL}git push origin main"
  _diff_emit "bash <<'EOF'${NL}git reset --hard${NL}EOF"
  _diff_emit "python3 <<EOF${NL}import os${NL}EOF"
  for i in sh bash zsh ksh dash csh tcsh fish python3.12 perl ruby node awk sed eval; do
    _diff_emit "${i} <<'EOF'${NL}git reset --hard${NL}EOF"
  done
  _diff_emit "git stash <<'EOF'${NL}git reset --hard${NL}EOF"
  _diff_emit "git stash list <<EOF${NL}describes git reset --hard${NL}EOF"
  _diff_emit "cat <<EOF|grep x${NL}git reset --hard${NL}EOF${NL}git push"
  _diff_emit "cat <<EOF&&git status${NL}git reset --hard${NL}EOF${NL}git push"
  _diff_emit "git commit -F - <<\"EOF\"${NL}git reset --hard${NL}EOF${NL}git push"
  _diff_emit "bash -c"
  _diff_emit "my_bash -c 'git reset --hard'"
  _diff_emit "/bin/bash -c 'x'"
  _diff_emit "bash -c 'git reset --hard'"
  _diff_emit "sh -c \"git push --force\""
  _diff_emit "eval 'git clean -fd'"
  _diff_emit "eval \"\$cmd\""
  _diff_emit "git commit -m 'run bash -c something' && echo ok"
  _diff_emit "cat <<'EOF'${NL}bash -c 'x'${NL}eval y${NL}EOF"
  _diff_emit "cat >> t.bats <<'EOF'${NL}  git reset --hard${NL}  run bash -c \"true\"${NL}EOF"
  _diff_emit "git commit -m \"\$(git rev-parse HEAD)\""
  _diff_emit "echo \"\$(printf \"x\") git reset --hard\""
  _diff_emit "echo \$(echo 'a b') && git status"
  _diff_emit "x=\"\$(cd \"\$(dirname \"\$0\")\" && pwd)\" git push"
  _diff_emit "echo \"\$(echo 'it''s') tail\""
  _diff_emit "git commit -m \"\$(cat <<'EOF'${NL}message with git reset --hard${NL}EOF${NL})\""
  _diff_emit 'git commit -m "$(echo "$(printf "git reset --hard")")"'
  _diff_emit 'echo "$(date "+%F")" && git reset --hard'
  _diff_emit 'echo "$(git reset --hard)"'
  _diff_emit 'x=$(git stash clear)'
  _diff_emit "echo \"\$(bash -c 'git reset --hard')\""
  _diff_emit "cat <<< 'git reset --hard'"
  _diff_emit 'cat <<< git reset --hard'
  _diff_emit "grep <<< \"git push --force\" && git status"
  _diff_emit "echo \"say \\\"git reset --hard\\\" now\" ; git status"
  _diff_emit "echo 'unterminated quote git reset --hard"
  _diff_emit "git commit -F - <<EOF${NL}unterminated heredoc body git reset --hard"
  _diff_emit "echo ) stray paren; git status"
  _diff_emit "git status"
  _diff_emit "ls -la | git commit -n"
  _diff_emit ""
  _diff_emit "${NL}${NL}git status${NL}"
  # Scanner edges.
  _diff_emit "'"
  _diff_emit '"'
  _diff_emit '$'
  _diff_emit ')'
  _diff_emit '$('
  _diff_emit '$()'
  _diff_emit '$$('
  _diff_emit '$)'
  _diff_emit 'a$'
  _diff_emit '"$'
  _diff_emit '"$('
  _diff_emit '"$("'
  _diff_emit "''"
  _diff_emit '""'
  _diff_emit '"\"'
  _diff_emit '"\\"x"'
  _diff_emit '"a\"b" c'
  _diff_emit '"\$(x)"'
  _diff_emit '"$\"(x)"'
  _diff_emit '\"x'
  _diff_emit "\\'x'"
  _diff_emit '"x\'
  _diff_emit '"x\$(y)"'
  _diff_emit '"$(")"'
  _diff_emit "\$('x)')"
  _diff_emit '$(()))'
  _diff_emit '$(a $(b "c)" d) e) f) g'
  _diff_emit '"$(a "$(b)" c)" d "e"'
  _diff_emit "a'b\"c\$d)e"
  _diff_emit '))))'
  _diff_emit '$($($($('
  _diff_emit "x.${NL}."
  _diff_emit '.'
  _diff_emit "echo * ? [a] *.sh"
  _diff_emit "\"é\" 'ü' ok"
  _diff_emit "git commit -m \"日本語のメッセージ \$(git rev-parse HEAD) — fin\""
  _diff_emit "echo '$(printf '\001\177')' \"$(printf '\001')\$(x)\" $(printf '\177')"
  _diff_emit "$(printf 'a\377b "\303" \303(x) c')"
  _diff_emit "cat <<EOF${NL}EOF ${NL}  EOF${NL}git push"
  _diff_emit "cat <<  EOF${NL}x${NL}EOF"
  _diff_emit "cat <<'E O'${NL}x${NL}E O${NL}git push"
  _diff_emit "cat <<${NL}x${NL}git push"
  _diff_emit "cat <<EOF <<END${NL}a${NL}EOF${NL}b${NL}END${NL}git push"
  _diff_emit "a <<-${TAB}EOF${NL}x${NL}${TAB}EOF${NL}y"
  _diff_emit "echo x\\${NL}<<EOF${NL}body${NL}EOF"
}

# _diff_generate <count> <seed>: random mixes of the tokens that steer the
# two scanners. An LCG, so bash 3.2 and 5.x see the same inputs.
_diff_generate() {
  local count="$1" seed="$2" NL=$'\n' TAB=$'\t' n i k s r
  local -a pool
  pool=("'" '"' '$(' '$' '(' ')' '\' '\"' '`' '<<' '<<-' "<<'EOF'" '<<"EOF"'
    '<<EOF' '<<<' 'EOF' "${TAB}EOF" "${NL}" "${NL}" "${NL}EOF${NL}" ' ' ' ' "${TAB}"
    '&&' '||' '|' ';' '&' 'git ' 'reset --hard' 'bash ' 'sh ' 'python3 ' 'stash'
    'cat ' '-c ' 'eval ' 'x' 'abc' 'é' '日本' "$(printf '\001')" "$(printf '\177')"
    "$(printf '\377')" "$(printf '\303')" '*' '?' '[a]' '.' '-' '"$(' '$("' "')" '\\')
  n=${#pool[@]}
  i=0
  while [ "$i" -lt "$count" ]; do
    seed=$(( (seed * 1103515245 + 12345) % 2147483648 ))
    k=$(( (seed >> 16) % 40 + 1 ))
    s=""
    while [ "$k" -gt 0 ]; do
      seed=$(( (seed * 1103515245 + 12345) % 2147483648 ))
      r=$(( (seed >> 16) % n ))
      s="${s}${pool[$r]}"
      k=$((k - 1))
    done
    _diff_emit "$s"
    i=$((i + 1))
  done
}

# _diff_emit <input>: run one input through the oracle and the code under
# test, appending each output plus a numbered separator to its own file.
_diff_emit() {
  _DIFF_N=$((_DIFF_N + 1))
  printf '%s' "$1" >> "$_DIFF_DIR/inputs"
  printf '\n#%d#\n' "$_DIFF_N" >> "$_DIFF_DIR/inputs"
  case "$_DIFF_FN" in
    quoted)
      _ref_strip_quoted "$1" >> "$_DIFF_DIR/ref"
      _strip_quoted "$1" >> "$_DIFF_DIR/new"
      ;;
    heredocs)
      _ref_strip_heredocs "$1" >> "$_DIFF_DIR/ref"
      _strip_heredocs "$1" >> "$_DIFF_DIR/new"
      ;;
  esac
  printf '\n#%d#\n' "$_DIFF_N" >> "$_DIFF_DIR/ref"
  printf '\n#%d#\n' "$_DIFF_N" >> "$_DIFF_DIR/new"
}

# _differential <quoted|heredocs> <locale> <generated-count>
#   Runs the corpus plus generated inputs in a child bash under <locale>;
#   fails with the first diverging case.
_differential() {
  local fn="$1" loc="$2" count="$3" dir driver
  [ -n "$loc" ] || { echo "no locale given (no UTF-8 locale on this host?)" >&2; return 1; }
  dir="$BATS_TEST_TMPDIR/diff-$fn-$loc"
  mkdir -p "$dir" || return 1
  driver="$dir/driver.sh"
  {
    declare -f _ref_strip_quoted _ref_strip_heredocs _diff_corpus _diff_generate _diff_emit
    printf '%s\n' 'source "$1" || exit 97' '_DIFF_FN="$2"; _DIFF_DIR="$3"; _DIFF_N=0' \
      '_diff_corpus' '_diff_generate "$4" 20261012' 'printf "%s\n" "$_DIFF_N" > "$_DIFF_DIR/count"'
  } > "$driver"
  LC_ALL="$loc" bash "$driver" "$LIB" "$fn" "$dir" "$count" || { echo "driver failed" >&2; return 1; }
  [ -s "$dir/ref" ] || { echo "empty oracle output" >&2; return 1; }
  printf '%s inputs (%s, %s)\n' "$(cat "$dir/count")" "$fn" "$loc" >&3
  if ! cmp -s "$dir/ref" "$dir/new"; then
    echo "outputs differ ($fn, $loc); first difference:" >&2
    diff "$dir/ref" "$dir/new" | head -20 >&2
    return 1
  fi
}

@test "differential: _strip_quoted matches the oracle byte for byte (C locale)" {
  _differential quoted C "${TCS_STRIP_DIFF_COUNT:-1500}"
}

@test "differential: _strip_quoted matches the oracle byte for byte (UTF-8 locale)" {
  _differential quoted "$UTF8_LOCALE" "${TCS_STRIP_DIFF_COUNT:-1500}"
}

@test "differential: _strip_heredocs matches the oracle byte for byte (C locale)" {
  _differential heredocs C "${TCS_STRIP_DIFF_COUNT:-1500}"
}

@test "differential: _strip_heredocs matches the oracle byte for byte (UTF-8 locale)" {
  _differential heredocs "$UTF8_LOCALE" "${TCS_STRIP_DIFF_COUNT:-1500}"
}

# ---------------------------------------------------------------------------
# Scale
# ---------------------------------------------------------------------------

# _scale <quoted|heredocs> <locale>
#   Times the function on a realistic command repeated to 2 KB, 20 KB and
#   200 KB, inside one child bash (perl timer: BSD date has no %N; the cost of
#   the timer itself is measured and subtracted). Steps stop at the first one
#   over budget, so quadratic code fails at 2 KB or 20 KB instead of running
#   200 KB for twenty minutes. Requires:
#     - 2 KB and 20 KB each under the budget (SDD: well under 100 ms at 20 KB);
#     - 200 KB at most 15x the 20 KB time (linear growth, with a 10 ms floor
#       so a tiny baseline cannot make the ratio meaningless).
_scale() {
  local fn="$1" loc="$2" budget driver out t2 t20 t200 floor=10
  [ -n "$loc" ] || { echo "no locale given (no UTF-8 locale on this host?)" >&2; return 1; }
  budget="$(_perf_budget 100)"
  driver="$BATS_TEST_TMPDIR/scale-$fn.sh"
  cat > "$driver" <<'DRIVER_EOF'
source "$1" || exit 97
fn="$2"; budget="$3"; NL=$'\n'
if [ "$fn" = _strip_quoted ]; then
  u="git commit -m \"fix: \$(git rev-parse HEAD) it's a \\\"quoted\\\" note é\" && echo 'a b' | tr x y; (cd sub) ${NL}"
else
  u="git commit -F - <<'EOF'${NL}body names git reset --hard and \$(x) é${NL}second line 'q'${NL}EOF${NL}bash <<EOF${NL}echo hi${NL}EOF${NL}git status${NL}"
fi
ms() { perl -MTime::HiRes -e 'printf "%d", Time::HiRes::time()*1000'; }
a=$(ms); b=$(ms); overhead=$((b - a))
for n in 2000 20000 200000; do
  s="$u"; while [ "${#s}" -lt "$n" ]; do s="$s$s"; done; s="${s:0:$n}"
  t0=$(ms); "$fn" "$s" > /dev/null; t1=$(ms)
  t=$((t1 - t0 - overhead)); [ "$t" -ge 0 ] || t=0
  printf '%s ' "$t"
  if [ "$n" -lt 200000 ] && [ "$t" -ge "$budget" ]; then echo; exit 0; fi
done
echo
DRIVER_EOF
  out="$(LC_ALL="$loc" bash "$driver" "$LIB" "$fn" "$budget")" || { echo "driver failed" >&2; return 1; }
  printf '%s %s ms at 2/20/200 KB: %s\n' "$fn" "$loc" "$out" >&3
  set -- $out
  t2="${1:-}"; t20="${2:-}"; t200="${3:-}"
  [ -n "$t2" ] && [ "$t2" -lt "$budget" ] || { echo "2 KB took ${t2}ms (budget ${budget}ms)" >&2; return 1; }
  [ -n "$t20" ] && [ "$t20" -lt "$budget" ] || { echo "20 KB took ${t20}ms (budget ${budget}ms)" >&2; return 1; }
  [ "$t20" -ge "$floor" ] || t20="$floor"
  [ -n "$t200" ] && [ "$t200" -le $((t20 * 15)) ] \
    || { echo "200 KB took ${t200}ms, more than 15x the 20 KB ${t20}ms" >&2; return 1; }
}

@test "scale: _strip_quoted is under budget at 20 KB and linear to 200 KB (C locale)" {
  _scale _strip_quoted C
}

@test "scale: _strip_quoted is under budget at 20 KB and linear to 200 KB (UTF-8 locale)" {
  _scale _strip_quoted "$UTF8_LOCALE"
}

@test "scale: _strip_heredocs is under budget at 20 KB and linear to 200 KB (C locale)" {
  _scale _strip_heredocs C
}

@test "scale: _strip_heredocs is under budget at 20 KB and linear to 200 KB (UTF-8 locale)" {
  _scale _strip_heredocs "$UTF8_LOCALE"
}
