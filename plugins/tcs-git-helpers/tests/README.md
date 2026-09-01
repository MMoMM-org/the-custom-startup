# tcs-git-helpers — Test Suite

## Layout

| Directory | Contents |
|---|---|
| `bats/` | Unit and contract tests for hooks, git hooks, and `lib/` helpers |
| `bats/lib/` | Shared bats helpers |
| `integration/` | `verify-tcs-rollout.sh` — checks an installed rollout in a real repo |
| `e2e/` | `dogfood.sh` and the bundle-lifecycle test |
| `fixtures/` | Generated repos (`repos/build.sh`) and CLI stubs (`gh_stubs/`) |
| `python/` | Python-side tests |

## Registration-locking pattern

Tests that verify *registrations* rather than behaviour — that a hook is wired into
`hooks/hooks.json` at all — belong in a dedicated file (`hooks-json.bats`), not scattered
across the behavioural tests. Resolve the plugin root from `BATS_TEST_DIRNAME`:

```bash
PLUGIN_ROOT="${BATS_TEST_DIRNAME}/../.."
HOOKS_JSON="${PLUGIN_ROOT}/hooks/hooks.json"
```

Then assert with `jq` across five axes: the file is valid JSON, every required entry point is
present, each script is registered under the correct matcher, paths use the
`${CLAUDE_PLUGIN_ROOT}` convention, and no unknown top-level keys have appeared (which catches
upstream schema drift). A single matcher-plus-script pair looks like:

```bash
jq -e '.hooks.PreToolUse[] | select(.matcher == "Bash")
       | .hooks[] | select(.command | contains("block-bad-git-ops.sh"))' "$HOOKS_JSON"
```

The point is that adding or renaming a hook cannot silently drift out of sync with the
documentation — the registration test fails before anyone notices at runtime.

## Traps specific to this suite

Two are easy to hit and hard to diagnose; both are recorded in `docs/ai/memory/tools.md`:

- `mktemp -d` without an `XXXXXX` template fails under the harness sandbox, and the fallback
  path lets a fixture's `git init` leak commits onto the parent branch.
- A bare `! cmd` only fails a bats test when it is the last command in the body.
