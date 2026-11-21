#!/bin/bash
# scripts/lib/merge_findings.sh — review findings that should stop a PR merge (#292)
#
# Sourced by block-bad-git-ops.sh for the MERGE_WITH_FINDINGS rule. A PR is
# not ready to merge while it has:
#   - unresolved, non-outdated review threads
#   - a reviewer whose latest review is CHANGES_REQUESTED
#   - reviews or comments by someone other than the author after the last commit
#   - open code-scanning alerts on refs/pull/<n>/merge
#   - checks still running on the head commit (findings often arrive with them)
#
# Green checks are no substitute: CodeQL concludes `success` with medium
# findings and posts them as review threads (MMoMM-org/obsidian-dynbedded#50).
#
# Every gh call fails open: a lookup that fails drops its source, and a PR
# that cannot be resolved at all yields no findings. Each call is bounded by
# `timeout 5` when timeout(1) exists.
#
# bash 3.2 compatible. Stdout carries data only; notes go to stderr.

_mf_gh() {
  if command -v timeout >/dev/null 2>&1; then
    timeout 5 gh "$@"
  else
    gh "$@"
  fi
}

_MF_PR_FIELDS="number,url,author,commits,reviews,latestReviews,comments,statusCheckRollup"

_MF_THREADS_QUERY='query($owner: String!, $name: String!, $number: Int!) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      reviewThreads(first: 100) {
        nodes {
          isResolved isOutdated path line originalLine
          comments(first: 1) { nodes { author { login } body } }
        }
      }
    }
  }
}'

# jq program: {pr, threads, alerts} → {total, counts, items[]}. Null-safe, so
# a source that failed (null) or a sparse stub contributes nothing.
# shellcheck disable=SC2016  # jq variables, not shell
_MF_RENDER='
def first_line: (. // "") | split("\n") | map(select(test("\\S"))) | (.[0] // "")
  | sub("^#+\\s*"; "") | .[0:70];
(.pr // {}) as $pr
| ($pr.author.login // "") as $author
| (($pr.commits // []) | last | .committedDate // "") as $last
| [ (.threads // [])[] | select((.isResolved | not) and (.isOutdated | not))
    | "unresolved thread \(.path // "?"):\(.line // .originalLine // "?") \(.comments.nodes[0].author.login // "?"): \(.comments.nodes[0].body | first_line)" ] as $threads
| [ ($pr.latestReviews // [])[] | select(.state == "CHANGES_REQUESTED")
    | "changes requested by \(.author.login // "?")" ] as $changes
| [ (.alerts // [])[]
    | "code scanning alert #\(.number) \(.rule.id // "?") \(.most_recent_instance.location.path // "?"):\(.most_recent_instance.location.start_line // "?")" ] as $alerts
| [ (($pr.reviews // [])[]
      | select((.author.login // "") != $author and (.submittedAt // "") > $last
               and ((.body // "") | test("\\S")))
      | "review by \(.author.login // "?") after the last commit: \(.body | first_line)"),
    (($pr.comments // [])[]
      | select((.author.login // "") != $author and (.createdAt // "") > $last
               and (.isMinimized | not))
      | "comment by \(.author.login // "?") after the last commit: \(.body | first_line)") ] as $new
| [ ($pr.statusCheckRollup // [])[]
    | select(if has("status") then .status != "COMPLETED"
             else ((.state // "") == "PENDING" or (.state // "") == "EXPECTED") end)
    | "check still running: \(.name // .context // "?")" ] as $pending
| { total: ([$threads, $changes, $alerts, $new, $pending] | map(length) | add),
    counts: [ (if ($threads | length) > 0 then "\($threads | length) unresolved thread(s)" else empty end),
              (if ($changes | length) > 0 then "\($changes | length) change request(s)" else empty end),
              (if ($alerts | length) > 0 then "\($alerts | length) code scanning alert(s)" else empty end),
              (if ($new | length) > 0 then "\($new | length) new comment(s)" else empty end),
              (if ($pending | length) > 0 then "\($pending | length) running check(s)" else empty end) ],
    items: ($threads + $changes + $alerts + $new + $pending) }
'

# _merge_findings_collect <selector> <repo>
#   Prints {pr, threads, alerts} for the PR that `gh pr view <selector>
#   [-R <repo>]` resolves (empty selector: the current branch's PR).
#   Returns 1, printing nothing, when the PR cannot be resolved.
_merge_findings_collect() {
  local selector="$1" repo="$2" pr threads alerts url owner name number
  local -a args
  args=(pr view)
  [ -n "$selector" ] && args+=("$selector")
  [ -n "$repo" ] && args+=(-R "$repo")
  args+=(--json "$_MF_PR_FIELDS")

  pr=$(_mf_gh "${args[@]}" 2>/dev/null) || pr=""
  url=$(printf '%s' "$pr" | jq -r '.url // empty' 2>/dev/null) || url=""
  case "$url" in
    https://*/*/*/pull/*) ;;
    *) return 1 ;;
  esac
  # https://<host>/<owner>/<name>/pull/<number>
  url="${url#https://*/}"
  owner="${url%%/*}"; url="${url#*/}"
  name="${url%%/*}"
  number="${url##*/}"

  threads=$(_mf_gh api graphql -f query="$_MF_THREADS_QUERY" \
      -F owner="$owner" -F name="$name" -F number="$number" 2>/dev/null \
    | jq -c '.data.repository.pullRequest.reviewThreads.nodes // null' 2>/dev/null) || threads=""
  if [ -z "$threads" ] || [ "$threads" = "null" ]; then
    printf 'tcs-git-helpers: review threads of PR #%s unavailable — not checked\n' "$number" >&2
    threads="null"
  fi

  # No analysis (404 "no analysis found") and code scanning switched off both
  # mean "no alerts"; neither is worth a note.
  alerts=$(_mf_gh api "repos/${owner}/${name}/code-scanning/alerts?ref=refs/pull/${number}/merge&state=open&per_page=100" \
      2>/dev/null | jq -c 'if type == "array" then . else null end' 2>/dev/null) || alerts=""
  [ -z "$alerts" ] && alerts="null"

  jq -nc --argjson pr "$pr" --argjson threads "$threads" --argjson alerts "$alerts" \
    '{pr: $pr, threads: $threads, alerts: $alerts}' 2>/dev/null || return 1
  return 0
}

# _merge_findings_render
#   stdin: {pr, threads, alerts}. Prints nothing when the PR is clean;
#   otherwise line 1 is the summary ("2 unresolved thread(s), …") and each
#   further line is one finding.
_merge_findings_render() {
  jq -r "$_MF_RENDER"' | if .total > 0 then (.counts | join(", ")), .items[] else empty end' \
    2>/dev/null || true
}
