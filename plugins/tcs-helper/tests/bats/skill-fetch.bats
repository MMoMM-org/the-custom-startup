#!/usr/bin/env bats
#
# tests/bats/skill-fetch.bats
#
# #297: skill-import fetches a skill pinned to one commit into a staging
# directory and records where it came from.
# File under test: plugins/tcs-helper/scripts/skill_fetch.sh
#
# gh is a stub that serves a fake repository tree and logs every call, so
# the tests also prove each request names the pinned SHA and never a branch.
#
# bash 3.2 compatible.

bats_require_minimum_version 1.5.0

load 'lib/assert'

SHA=0123456789abcdef0123456789abcdef01234567

setup() {
  REPO="$(git -C "$BATS_TEST_DIRNAME" rev-parse --show-toplevel)"
  FETCH="$REPO/plugins/tcs-helper/scripts/skill_fetch.sh"
  SRC="$BATS_TEST_TMPDIR/src"
  STAGE="$BATS_TEST_TMPDIR/stage"
  export GH_LOG="$BATS_TEST_TMPDIR/gh.log"
  export FAKE_SRC="$SRC"
  export FAKE_TREE="$BATS_TEST_TMPDIR/tree.json"
  mkdir -p "$SRC/plugins/p/skills/s/scripts" "$SRC/plugins/p/hooks" "$SRC/other" "$BATS_TEST_TMPDIR/bin"
  printf -- '---\nname: s\n---\n' > "$SRC/plugins/p/skills/s/SKILL.md"
  printf '#!/bin/bash\necho hi\n' > "$SRC/plugins/p/skills/s/scripts/run.sh"
  printf '{}\n' > "$SRC/plugins/p/hooks/hooks.json"
  printf 'x\n' > "$SRC/other/file.md"
  cat > "$FAKE_TREE" <<'EOF'
{"truncated": false, "tree": [
  {"path": "plugins/p/skills/s", "type": "tree", "mode": "040000"},
  {"path": "plugins/p/skills/s/SKILL.md", "type": "blob", "mode": "100644"},
  {"path": "plugins/p/skills/s/scripts/run.sh", "type": "blob", "mode": "100755"},
  {"path": "plugins/p/skills/s/link", "type": "blob", "mode": "120000"},
  {"path": "plugins/p/skills/s-other/SKILL.md", "type": "blob", "mode": "100644"},
  {"path": "plugins/p/hooks/hooks.json", "type": "blob", "mode": "100644"},
  {"path": "other/file.md", "type": "blob", "mode": "100644"}
]}
EOF
  cat > "$BATS_TEST_TMPDIR/bin/gh" <<'EOF'
#!/bin/bash
printf '%s\n' "$*" >> "$GH_LOG"
for a in "$@"; do
  case "$a" in
    repos/*/git/trees/*) cat "$FAKE_TREE"; exit 0 ;;
    repos/*/contents/*)
      p="${a#repos/*/contents/}"; p="${p%%\?ref=*}"
      cat "$FAKE_SRC/$p"; exit $? ;;
  esac
done
exit 1
EOF
  chmod +x "$BATS_TEST_TMPDIR/bin/gh"
  PATH="$BATS_TEST_TMPDIR/bin:$PATH"
}

@test "F1 fetches the skill directory, not its sibling with a shared prefix" {
  run bash "$FETCH" o/r "$SHA" "$STAGE" plugins/p/skills/s
  [ "$status" -eq 0 ]
  [ -f "$STAGE/plugins/p/skills/s/SKILL.md" ]
  [ -f "$STAGE/plugins/p/skills/s/scripts/run.sh" ]
  [ ! -e "$STAGE/plugins/p/skills/s-other" ]
  [ ! -e "$STAGE/other" ]
}

@test "F2 keeps the executable bit from the tree mode" {
  run bash "$FETCH" o/r "$SHA" "$STAGE" plugins/p/skills/s
  [ -x "$STAGE/plugins/p/skills/s/scripts/run.sh" ]
  [ ! -x "$STAGE/plugins/p/skills/s/SKILL.md" ]
}

@test "F3 skips symlinks and says so" {
  run bash "$FETCH" o/r "$SHA" "$STAGE" plugins/p/skills/s
  _has "$output" $'SKIPPED\tplugins/p/skills/s/link\tsymlink'
  [ ! -e "$STAGE/plugins/p/skills/s/link" ]
}

@test "F4 a single plugin-level file can be added" {
  run bash "$FETCH" o/r "$SHA" "$STAGE" plugins/p/skills/s plugins/p/hooks/hooks.json
  [ "$status" -eq 0 ]
  [ -f "$STAGE/plugins/p/hooks/hooks.json" ]
}

@test "P1 every request names the pinned SHA" {
  run bash "$FETCH" o/r "$SHA" "$STAGE" plugins/p/skills/s
  [ "$status" -eq 0 ]
  log=$(cat "$GH_LOG")
  _has "$log" "repos/o/r/git/trees/$SHA?recursive=1"
  _has "$log" "repos/o/r/contents/plugins/p/skills/s/SKILL.md?ref=$SHA"
  _lacks "$log" "HEAD"
  [ "$(grep -c "$SHA" "$GH_LOG")" -eq "$(wc -l < "$GH_LOG")" ]
}

@test "P2 a branch name instead of a SHA is refused before any request" {
  run bash "$FETCH" o/r main "$STAGE" plugins/p/skills/s
  [ "$status" -eq 2 ]
  [ ! -e "$GH_LOG" ]
}

@test "M1 manifest records source, SHA, paths and files" {
  run bash "$FETCH" o/r "$SHA" "$STAGE" plugins/p/skills/s
  m="$STAGE/.tcs-import.json"
  [ "$(jq -r .source "$m")" = "o/r" ]
  [ "$(jq -r .sha "$m")" = "$SHA" ]
  [ "$(jq -r '.paths[0]' "$m")" = "plugins/p/skills/s" ]
  [ "$(jq -r '.files | length' "$m")" -eq 2 ]
  [ "$(jq -r '.fetched_at' "$m")" != "null" ]
}

@test "T1 a truncated tree fails instead of fetching part of the skill" {
  jq '.truncated = true' "$FAKE_TREE" > "$FAKE_TREE.t" && mv "$FAKE_TREE.t" "$FAKE_TREE"
  run bash "$FETCH" o/r "$SHA" "$STAGE" plugins/p/skills/s
  [ "$status" -eq 3 ]
}

@test "T2 a path that matches nothing fails" {
  run bash "$FETCH" o/r "$SHA" "$STAGE" plugins/p/skills/nope
  [ "$status" -eq 3 ]
}

@test "T3 a tree path with .. is refused" {
  # Resolves to $BATS_TEST_TMPDIR/x from both the stage and the fake source,
  # so without the check the download would succeed and truncate it.
  printf 'keep\n' > "$BATS_TEST_TMPDIR/x"
  jq '.tree += [{"path":"plugins/p/skills/s/../../../../../x","type":"blob","mode":"100644"}]' \
    "$FAKE_TREE" > "$FAKE_TREE.t" && mv "$FAKE_TREE.t" "$FAKE_TREE"
  run bash "$FETCH" o/r "$SHA" "$STAGE" plugins/p/skills/s
  [ "$status" -eq 3 ]
  _has "$output" "unsafe path"
  [ "$(cat "$BATS_TEST_TMPDIR/x")" = "keep" ]
}

@test "S1 skill-import fetches through the pinned script and scans before install" {
  f="$REPO/plugins/tcs-helper/skills/skill-import/SKILL.md"
  body=$(cat "$f")
  _has "$body" 'scripts/skill_fetch.sh'
  _has "$body" 'scripts/skill_security_scan.sh'
  _has "$body" '.tcs-import.json'
  _lacks "$body" 'git/trees/HEAD'
  _lacks "$body" 'contents/{plugin_path}'
}

@test "S2 skill-evaluate runs the scan and gates ABSORB on it" {
  f="$REPO/plugins/tcs-helper/skills/skill-evaluate/SKILL.md"
  body=$(cat "$f")
  _has "$body" 'scripts/skill_security_scan.sh'
  _has "$body" 'Issue ABSORB or ABSORB_ADAPT while a security flag is unacknowledged'
  _has "$body" 'allowed-tools: Read, Glob, Grep, Bash, AskUserQuestion'
}
