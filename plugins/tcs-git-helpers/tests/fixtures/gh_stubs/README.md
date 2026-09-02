# gh_stubs/ — offline `gh` mock for tcs-git-helpers tests

Mock `gh` CLI binary that returns canned JSON for offline testing of all
`gh`-dependent flows (M1 push-to-closed-PR, M3 squash-merge resume,
M6 stale-branch surfacing, S1 branch protection).

## How tests use it

```bash
PATH="$FIXTURE_DIR/gh_stubs:$PATH" \
  GH_STUB_SCENARIO=closed-pr \
  bash some-hook-under-test.sh
```

`gh_stubs/gh` is found ahead of the real `gh` on PATH and serves
canned JSON / exit codes from `responses/<scenario>/<op>.json`.

## Wire-format invariants

The stub mirrors real `gh` envelope shape exactly — per project-memory
feedback `test-stubs-mirror-real-wire-format.md`:

| Operation | Envelope |
|---|---|
| `gh pr list --json …`        | JSON **array** (`[]` when empty, never `null`) |
| `gh pr view <n> --json mergeCommit` | JSON **object** `{"mergeCommit":{"oid":"…"}}` or `{"mergeCommit":null}` |
| `gh api <endpoint>`          | JSON object whose shape matches the GitHub REST endpoint |

If a hook reads `.[0].state` from the array or `.mergeCommit.oid` from the
object, the stub satisfies the same path as production.

## Scenarios

Each scenario is a directory under `responses/`. The wrapper looks up
`responses/$GH_STUB_SCENARIO/<op>.json`; if missing, it falls back to
`responses/default/<op>.json`. Operations: `pr-list`, `pr-view`, `api`.

| Scenario | Used by | Behavior |
|---|---|---|
| `default`               | unspecified flows | empty `pr-list`, null `pr-view` |
| `closed-pr`             | M1 deny-push-to-closed | `pr-list` returns CLOSED, number 42 |
| `merged-pr`             | M1 deny-push-to-merged + M3 squash detection | `pr-list` returns MERGED, number 43; `pr-view` returns merge-commit oid |
| `merged-pr-no-sha`      | M1 fall-through when the merge commit is unknown | `pr-list` returns MERGED, number 99; `pr-view` returns `{"mergeCommit":null}` |
| `open-pr`               | M2 allow-when-PR-open | `pr-list` returns OPEN, number 44 |
| `no-pr`                 | M2 deny-branch-from-unfinished | `pr-list` returns `[]` |
| `squash-merged-batch`   | M6 post-merge stale-branch listing | `pr-list` returns 6 merged PRs (mirrors Kado state) |
| `stale-3-branches`      | M6 post-merge cache write + runtime contract | `pr-list` returns 4 merged PRs, one of which (`feat/not-local`) has no local branch |
| `branch-protected`      | S1 branch-protection PUT response | `api` returns successful PUT envelope |

## Failure scenarios (non-zero exit)

These exit non-zero before consulting `responses/`. They exercise the
fail-open path mandated by CON-4.

| Scenario | Exit | Stderr message |
|---|---:|---|
| `no-auth`       | 4 | `error: not authenticated. Run: gh auth login` |
| `rate-limited`  | 4 | `error: GraphQL: API rate limit exceeded for installation` |
| `network-fail`  | 1 | `error: dial tcp: lookup api.github.com: no such host` |
| `timeout`       | 124 | `gh-stub: simulated timeout` (matches `/usr/bin/timeout`) |

## Adding a scenario

1. Create `responses/<name>/<op>.json` (e.g. `responses/dependabot-pr/pr-list.json`).
2. Validate shape with `jq -e .` (the bats sanity test enforces this).
3. Add a row to the table above documenting which feature flow consumes it.
   This is enforced: `fixtures_sanity.bats` derives the scenario list from
   `responses/` and from the failure-mode `case` block in `gh`, and fails on
   any scenario this file does not mention. Both `merged-pr-no-sha` and
   `stale-3-branches` went undocumented for months under the previous test,
   which hard-coded four names.
4. Reference it from the relevant bats test via `GH_STUB_SCENARIO=<name>`.
