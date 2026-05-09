#!/usr/bin/env bash
# tcs-git-helpers: v1.0.0
# skills/setup/lib/with_branch_protection.sh — STUB for T5.8.
#
# T5.1 ships this helper as an inert placeholder so the setup skill can
# reference a stable code path. T5.8 will implement the actual `gh api PUT`
# request applying the single-coder branch-protection preset (ADR-12).
#
# Until T5.8 lands, this script:
#   - Prints a banner identifying itself as the T5.8 stub.
#   - Notes the planned ruleset (ADR-12) for visibility.
#   - Exits 0 so that --with-branch-protection in setup workflow doesn't fail.
#
# Spec refs:
#   - ADR-12 (single-coder preset: no PR-review-required, no force-push,
#             no deletions, allow_force_pushes=false, allow_deletions=false,
#             enforce_admins=false, required_status_checks only if
#             .github/workflows/ present)
#   - PRD §Feature S1 acceptance criteria (T5.8 implements; T5.1 stubs)
#   - integration §9 token-scope matrix (T5.8 wires this in)
#
# Constraints:
#   - bash 3.2
#   - shellcheck-clean
#   - No network calls, no `gh` invocation (T5.8 adds those)

set -euo pipefail

cat <<'EOF' >&2
[tcs-git-helpers:setup] --with-branch-protection mode invoked.
[tcs-git-helpers:setup] STUB: real gh-api implementation deferred to T5.8.
[tcs-git-helpers:setup]
[tcs-git-helpers:setup] Planned single-coder ruleset (ADR-12):
[tcs-git-helpers:setup]   - allow_force_pushes=false
[tcs-git-helpers:setup]   - allow_deletions=false
[tcs-git-helpers:setup]   - enforce_admins=false
[tcs-git-helpers:setup]   - required_pull_request_reviews=null  (single coder)
[tcs-git-helpers:setup]   - required_status_checks=only if .github/workflows/ present
[tcs-git-helpers:setup]   - require_branches_to_be_up_to_date_before_merging=true
[tcs-git-helpers:setup]
[tcs-git-helpers:setup] T5.8 will: validate gh auth, check token scopes, prompt
[tcs-git-helpers:setup] for confirmation, then PUT /repos/:owner/:repo/branches/:branch/protection.
EOF

exit 0
