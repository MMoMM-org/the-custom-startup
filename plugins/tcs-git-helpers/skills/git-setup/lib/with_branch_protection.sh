#!/usr/bin/env bash
# tcs-git-helpers: v1.0.0
# skills/git-setup/lib/with_branch_protection.sh — apply the ADR-12 single-coder
# branch-protection preset on the target repo's default branch.
#
# Spec refs:
#   - PRD §Feature S1 acceptance criteria (AC1-AC7)
#   - ADR-12 (single-coder preset: no PR-review-required, no force-push,
#             no deletions, allow_force_pushes=false, allow_deletions=false,
#             enforce_admins=false; required_status_checks left null in v1.0;
#             plus PATCH delete_branch_on_merge=true)
#   - integration §2.3 (GitHub API endpoints), §6 (failure modes),
#     §9 (token-scope UX matrix)
#   - references/gh-token-hygiene.md
#
# Constraints (CON-1, CON-3, CON-4):
#   - bash 3.2
#   - shellcheck-clean
#   - No `coreutils timeout` dependency
#   - Fail-CLOSED on gh failure (this is NOT a hot-path hook).
#   - Does NOT auto-commit; does NOT roll back unrelated parent-skill steps.
#
# Test hooks (consumed only by tests/bats/skill_git_setup.bats; ignore in prod):
#   TCS_BP_YES=1                          skip the main ruleset y/N prompt.
#   TCS_BP_ALLOW_EXCESS_SCOPES=1          skip the excessive-scope y/N prompt
#                                         (S1 AC3 — distinct security gate).
#   GH_STUB_*                             gh CLI mock — see tests/fixtures/gh_stubs/.

set -euo pipefail

REF_DOC="references/gh-token-hygiene.md"
PRESET_VERSION="adr-12-single-coder"

_log()  { printf '[tcs-git-helpers:git-setup] %s\n' "$*"; }
_warn() { printf '[tcs-git-helpers:git-setup] WARN: %s\n' "$*" >&2; }
_err()  { printf '[tcs-git-helpers:git-setup] ERROR: %s\n' "$*" >&2; }

# --- pre-flight: git repo + GitHub remote ----------------------------------

_repo_root() {
  if git rev-parse --show-toplevel 2>/dev/null; then return 0; fi
  _err "not inside a git repository"
  return 1
}

# Parse owner/repo from `git remote get-url origin` (HTTPS or SSH).
_parse_owner_repo() {
  local url
  url="$(git remote get-url origin 2>/dev/null || true)"
  if [ -z "$url" ]; then
    _err "no 'origin' remote configured; cannot determine owner/repo"
    _err "see $REF_DOC"
    return 1
  fi
  case "$url" in
    https://github.com/*|http://github.com/*)
      url="${url#https://github.com/}"
      url="${url#http://github.com/}"
      ;;
    git@github.com:*)
      url="${url#git@github.com:}"
      ;;
    ssh://git@github.com/*)
      url="${url#ssh://git@github.com/}"
      ;;
    *)
      _err "origin remote is not a GitHub URL: $url"
      _err "see $REF_DOC"
      return 1
      ;;
  esac
  url="${url%.git}"
  printf '%s\n' "$url"
}

# --- token scope pre-flight (integration §9) -------------------------------

# Parse the `Token scopes: 'a', 'b', 'c'` line into a comma-separated string.
_gh_scopes_csv() {
  gh auth status 2>&1 \
    | grep -oE "Token scopes: '[^|]+" \
    | sed -E "s/.*: '//;s/', '/,/g;s/'$//" \
    | tr -d '\n'
}

# Returns 0 when $1 (scope name) appears in $2 (csv).
_csv_has() {
  local needle="$1" csv="$2"
  case ",$csv," in
    *,"$needle",*) return 0 ;;
  esac
  return 1
}

# Validate scopes per integration §9 / gh-token-hygiene.md:
#   - missing `repo`             → block (exit 5)
#   - excessive scopes present   → warn + (TCS_BP_ALLOW_EXCESS_SCOPES=1) proceed; (interactive) confirm
_check_scopes() {
  local csv excessive_found=""
  csv="$(_gh_scopes_csv)"
  if [ -z "$csv" ]; then
    _err "could not parse 'Token scopes:' from gh auth status output"
    _err "ensure 'gh auth login' has been run; see $REF_DOC"
    return 5
  fi
  if ! _csv_has "repo" "$csv"; then
    _err "missing required 'repo' scope (current: $csv)"
    _err "fix: gh auth refresh -s repo"
    _err "see $REF_DOC"
    return 5
  fi
  local s
  for s in admin:org delete_repo admin:repo_hook admin:public_key \
           admin:enterprise site_admin; do
    if _csv_has "$s" "$csv"; then
      excessive_found="${excessive_found:+$excessive_found, }$s"
    fi
  done
  if [ -n "$excessive_found" ]; then
    _warn "token has excessive scope(s): $excessive_found"
    _warn "branch-protection only needs 'repo'; rotate to a minimal token"
    _warn "see $REF_DOC and https://github.com/settings/tokens"
    # S1 AC3: a distinct, security-relevant confirmation. NOT bypassable by
    # TCS_BP_YES=1 — that flag covers only the main ruleset prompt below.
    # An elevated-scope token is a real safety signal (Marcus may have it
    # legitimately, or by accident via GitHub's UX) and deserves its own gate.
    if [ "${TCS_BP_ALLOW_EXCESS_SCOPES:-0}" != "1" ]; then
      printf '[tcs-git-helpers:git-setup] Proceed despite elevated token scopes? [y/N] ' >&2
      local reply=""
      if ! IFS= read -r reply; then reply=""; fi
      case "$reply" in
        y|Y|yes|YES|Yes) ;;
        *)
          _err "aborted: excessive token scopes not confirmed"
          return 1
          ;;
      esac
    fi
  fi
  return 0
}

# --- planned preset --------------------------------------------------------

# Build the JSON body Marcus is about to PUT. Single-coder per ADR-12.
# In v1.0 `required_status_checks` is left null; v1.1 will enumerate
# `.github/workflows/*` once Marcus confirms which checks are required.
_build_preset_body() {
  cat <<'EOF'
{"required_status_checks":null,"enforce_admins":false,"required_pull_request_reviews":null,"restrictions":null,"allow_force_pushes":false,"allow_deletions":false,"required_linear_history":false,"required_conversation_resolution":false}
EOF
}

_print_preset() {
  _log "Planned single-coder branch-protection ruleset ($PRESET_VERSION):"
  _log "  enforce_admins                   = false"
  _log "  required_pull_request_reviews    = null   (single coder; no review block)"
  _log "  required_status_checks           = null"
  _log "  restrictions                     = null"
  _log "  allow_force_pushes               = false"
  _log "  allow_deletions                  = false"
  _log "  required_linear_history          = false"
  _log "  required_conversation_resolution = false"
  _log "Plus: PATCH repos/<owner>/<repo> delete_branch_on_merge=true"
}

# --- idempotency: compare existing protection against preset ---------------

# Echoes "1" when the GET response is equivalent to the preset; "0" otherwise.
# gh's GET nests booleans (e.g. "enforce_admins":{"enabled":false}); the
# preset PUT body uses flat booleans. Normalize before comparing.
_existing_matches_preset() {
  local owner="$1" repo="$2" branch="$3"
  local body
  if ! body="$(gh api "repos/$owner/$repo/branches/$branch/protection" 2>/dev/null)"; then
    printf '0\n'
    return 0
  fi
  if ! command -v jq >/dev/null; then
    local match=1
    case "$body" in
      *'"required_pull_request_reviews":null'*) ;;
      *) match=0 ;;
    esac
    case "$body" in
      *'"allow_force_pushes":{"enabled":false}'*|*'"allow_force_pushes":false'*) ;;
      *) match=0 ;;
    esac
    case "$body" in
      *'"allow_deletions":{"enabled":false}'*|*'"allow_deletions":false'*) ;;
      *) match=0 ;;
    esac
    case "$body" in
      *'"enforce_admins":{"enabled":false}'*|*'"enforce_admins":false'*) ;;
      *) match=0 ;;
    esac
    printf '%s\n' "$match"
    return 0
  fi
  # Normalize gh's nested {"enabled":bool} envelopes to plain booleans so the
  # PUT-shaped preset can be diffed exactly. Using `//` would misfire here:
  # `false // x` evaluates `x` because jq treats `false` as "absent".
  local normalized target
  normalized="$(printf '%s' "$body" | jq -c '
    def flat(field):
      if (field | type) == "object" then (field.enabled // false)
      elif field == null then false
      else field end;
    {
      required_status_checks:           (.required_status_checks // null),
      enforce_admins:                   flat(.enforce_admins),
      required_pull_request_reviews:    (.required_pull_request_reviews // null),
      restrictions:                     (.restrictions // null),
      allow_force_pushes:               flat(.allow_force_pushes),
      allow_deletions:                  flat(.allow_deletions),
      required_linear_history:          flat(.required_linear_history),
      required_conversation_resolution: flat(.required_conversation_resolution)
    }')"
  target="$(_build_preset_body | jq -c '.')"
  if [ "$normalized" = "$target" ]; then
    printf '1\n'
  else
    printf '0\n'
  fi
}

# --- main flow -------------------------------------------------------------

main() {
  if ! command -v gh >/dev/null; then
    _err "gh CLI not found on PATH; install from https://cli.github.com/"
    _err "see $REF_DOC"
    exit 1
  fi

  local root owner_repo owner repo branch
  root="$(_repo_root)" || exit 1
  cd "$root"

  owner_repo="$(_parse_owner_repo)" || exit 1
  owner="${owner_repo%%/*}"
  repo="${owner_repo#*/}"

  # Token-scope pre-flight (integration §9; references/gh-token-hygiene.md).
  _check_scopes || exit 5

  # Detect default branch via gh; fall back to git remote HEAD probe.
  if ! branch="$(gh api "repos/$owner/$repo" --jq .default_branch 2>/dev/null)" \
       || [ -z "$branch" ]; then
    branch="$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null \
              | sed 's@^origin/@@')"
  fi
  if [ -z "$branch" ]; then branch="main"; fi

  _log "Target: $owner/$repo  default branch: $branch"
  _print_preset

  # Idempotency check (S1 AC7): skip the PUT when existing protection matches.
  local existing
  existing="$(_existing_matches_preset "$owner" "$repo" "$branch")"
  if [ "$existing" = "1" ]; then
    _log "Branch protection already up to date — no changes needed."
    if ! gh api -X PATCH "repos/$owner/$repo" \
           -f delete_branch_on_merge=true >/dev/null 2>&1; then
      _warn "delete_branch_on_merge PATCH failed (non-fatal); see $REF_DOC"
    fi
    return 0
  fi

  # Confirmation gate (S1 AC1): prompt before any write unless --yes / TCS_BP_YES=1.
  if [ "${TCS_BP_YES:-0}" != "1" ]; then
    printf '[tcs-git-helpers:git-setup] Apply this branch-protection ruleset? [y/N] ' >&2
    local reply=""
    if ! IFS= read -r reply; then reply=""; fi
    case "$reply" in
      y|Y|yes|YES|Yes) ;;
      *)
        _log "Aborted by user; no changes made."
        exit 0
        ;;
    esac
  fi

  # PUT the preset (integration §2.3). Pipe via stdin so the body shape
  # matches the planned ruleset exactly. Capture the gh exit code via
  # PIPESTATUS so the `set -e` shell propagates failures correctly.
  local put_status=0
  set +e
  _build_preset_body \
    | gh api -X PUT --input - \
        "repos/$owner/$repo/branches/$branch/protection" \
        >/dev/null
  put_status=${PIPESTATUS[1]}
  set -e
  if [ "$put_status" -ne 0 ]; then
    _err "gh api PUT branches/$branch/protection failed (exit $put_status)"
    _err "see $REF_DOC for token / scope troubleshooting"
    # Fail-CLOSED: do NOT roll back unrelated parent-skill steps (S1 AC5).
    exit "$put_status"
  fi
  _log "Applied branch-protection preset on $owner/$repo @ $branch."

  # delete_branch_on_merge PATCH — idempotent on the GH side (S1 AC7).
  if ! gh api -X PATCH "repos/$owner/$repo" \
         -f delete_branch_on_merge=true >/dev/null 2>&1; then
    _warn "delete_branch_on_merge PATCH failed (non-fatal); see $REF_DOC"
  else
    _log "Set delete_branch_on_merge=true on $owner/$repo."
  fi

  _log "Done. Setup did NOT auto-commit; review and commit any local changes manually."
}

main "$@"
