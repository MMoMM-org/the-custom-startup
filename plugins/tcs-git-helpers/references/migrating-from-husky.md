# Migrating from Husky (and lefthook, pre-commit, simple-git-hooks)

> Why setup aborts when another hook tool is detected, and the per-tool
> removal sequence that lets `/tcs-git-helpers:git-setup` proceed cleanly.

## What goes wrong

The repo already has Husky (or lefthook, or pre-commit, or
simple-git-hooks) installed. `/tcs-git-helpers:git-setup` detects the
conflict and aborts before doing anything, citing this document.

The root cause: every popular git-hook manager works by setting
`core.hooksPath` (or its equivalent) to a directory the manager owns.
- **Husky v8/v9** points `core.hooksPath` at `.husky/`.
- **Husky v4** writes hook scripts into `.git/hooks/` directly via a
  `package.json` `husky.hooks` field, which collides with any tool that
  expects `core.hooksPath` clean.
- **lefthook** writes to `.git/hooks/<name>` shims that exec
  `lefthook run <name>`.
- **pre-commit** (the Python tool) writes to `.git/hooks/pre-commit`
  that exec the `pre-commit` venv.
- **simple-git-hooks** writes hook scripts based on a `package.json`
  field.

The plugin's `.githooks/` layer needs `core.hooksPath=.githooks` (or
the equivalent — Marcus's setup approves the prompt). If another tool
already owns that config, two outcomes are possible, both bad:

1. **Silent coexistence:** the plugin overwrites `core.hooksPath`,
   removing the other tool's hooks from the loop. The other tool's
   contributors expect their hooks to fire; they don't. Confusing,
   silent, and reversible only if someone notices.
2. **Race:** if both tools' install scripts run on `npm install` /
   `pip install`, whoever runs last wins, and the result depends on
   `package.json` script order. Non-deterministic.

ADR-10 chose the conservative path: detect the collision at setup
time, abort with a reference to this document, and require an explicit
migration before proceeding. No auto-merge; no silent overwrite.

The same logic applies to `.git/hooks/*` non-`.sample` files: they
won't fire under our `core.hooksPath=.githooks`, but they exist for a
reason, and the user should know they're being shadowed.

## How to detect

The setup skill checks (in order, per integration.md §5):

```bash
# Husky v8/v9 — directory exists with non-_/ files
[ -d .husky ] && find .husky -mindepth 1 -not -path '.husky/_/*' -type f | head -1

# Husky v4 — package.json fields
jq -r '.husky.hooks // empty' package.json 2>/dev/null
jq -r '.scripts.prepare // empty' package.json 2>/dev/null | grep -q "husky install"

# lefthook — config file at repo root
ls lefthook.yml lefthook.yaml .lefthook.yml 2>/dev/null

# pre-commit (Python) — config file at repo root
[ -f .pre-commit-config.yaml ]

# simple-git-hooks — package.json field
jq -r '."simple-git-hooks" // empty' package.json 2>/dev/null

# Custom core.hooksPath (any value other than empty or .githooks)
hooks_path=$(git config --get core.hooksPath 2>/dev/null)
[ -n "$hooks_path" ] && [ "$hooks_path" != ".githooks" ]

# Existing .git/hooks/* non-sample files
find .git/hooks -type f -not -name '*.sample' 2>/dev/null
```

The first four cause **abort**. The custom `core.hooksPath` causes
**abort** (different value than `.githooks`). The last (`.git/hooks/*`
files) causes **warn only** — those won't fire under
`core.hooksPath=.githooks`, but the user should know they're being
shadowed.

To verify your own state independently:

```bash
git config --get core.hooksPath
ls .husky/ lefthook.yml .pre-commit-config.yaml 2>/dev/null
jq '.husky // ."simple-git-hooks" // empty' package.json 2>/dev/null
```

If all return empty / nothing, setup will proceed without prompting
about migration.

## Fix

Remove the existing hook tool, then run `/tcs-git-helpers:git-setup`. The
sequences below are non-destructive — they all leave the underlying
hook *content* in commit history (so it can be ported), they only
remove the *installation* of the tool.

### Husky v8/v9

```bash
# 1. Audit existing hooks — list what each does
ls .husky/
# For each non-_/ file, read it; identify which checks it performs.

# 2. Remove Husky from package.json
npm uninstall husky          # or: yarn remove husky / pnpm remove husky
# Remove the `prepare`: `husky install` script if it remains:
jq 'del(.scripts.prepare)' package.json > package.json.tmp \
  && mv package.json.tmp package.json

# 3. Remove the .husky/ directory
git rm -r .husky
git commit -m "chore: remove husky in preparation for tcs-git-helpers"

# 4. Reset core.hooksPath (Husky may have set it; clear it)
git config --unset core.hooksPath

# 5. Verify the slate is clean
git config --get core.hooksPath    # → empty
ls .husky 2>/dev/null              # → no such directory

# 6. Now run setup
/tcs-git-helpers:git-setup
```

### Husky v4

```bash
# 1. Remove the .husky.hooks field from package.json
jq 'del(.husky)' package.json > package.json.tmp \
  && mv package.json.tmp package.json

# 2. Remove the husky dependency
npm uninstall husky

# 3. Husky v4 wrote shims into .git/hooks/ — clean those (they're
#    auto-regenerated by Husky's install hook, which is now gone).
#    SAFE because .git/hooks/* is not committed to the repo.
ls .git/hooks/
# For each non-.sample file, inspect it; if it references husky, remove it:
rm .git/hooks/pre-commit .git/hooks/commit-msg   # adjust to actual list

# 4. Verify
git config --get core.hooksPath    # → empty (v4 didn't set it)

# 5. Run setup
/tcs-git-helpers:git-setup
```

### lefthook

```bash
# 1. Audit
cat lefthook.yml         # or .yaml / .lefthook.yml
# Note which checks each hook block runs.

# 2. Uninstall the binary's git-side hooks
lefthook uninstall

# 3. Remove the config and dependency
git rm lefthook.yml      # adjust to actual filename
# Node:    npm uninstall lefthook
# Go bin:  brew uninstall lefthook (if installed via brew)

# 4. Reset core.hooksPath
git config --unset core.hooksPath

# 5. Run setup
/tcs-git-helpers:git-setup
```

### pre-commit (Python)

```bash
# 1. Audit
cat .pre-commit-config.yaml

# 2. Uninstall the git-side hooks
pre-commit uninstall

# 3. Remove the config (commit history retains it)
git rm .pre-commit-config.yaml

# 4. (Optional) Remove the venv if it was project-local
rm -rf .venv-pre-commit  # or wherever the env was

# 5. Reset core.hooksPath
git config --unset core.hooksPath

# 6. Run setup
/tcs-git-helpers:git-setup
```

### simple-git-hooks

```bash
# 1. Audit
jq '."simple-git-hooks"' package.json

# 2. Remove the package.json field and dependency
jq 'del(."simple-git-hooks")' package.json > package.json.tmp \
  && mv package.json.tmp package.json
npm uninstall simple-git-hooks

# 3. simple-git-hooks writes to .git/hooks/ — same clean as Husky v4
#    (inspect each non-.sample file; remove the ones referencing the tool)
ls .git/hooks/
# rm <relevant files>

# 4. Run setup
/tcs-git-helpers:git-setup
```

### Porting custom hook content

If any of the removed hooks did something the plugin's defaults don't
cover (a project-specific lint, a custom commit-message check, a build
trigger), the plugin's `.githooks/` baseline is template-driven. Add
your custom logic by:

1. Run setup first to install the baseline.
2. Edit the relevant `.githooks/<hook>` and append your check.
3. Or: add the path to `.githooks/exclude-paths` if your check
   conflicts with one of the built-in template lines (rare, but the
   exclude file exists for this).
4. Commit the customization with `[skip-format-check]` if the commit
   message itself is exempted (see
   [`conventional-commits.md`](conventional-commits.md)).

## Prevention

- **Don't install Husky / lefthook / pre-commit in repos you also want
  the plugin to manage.** New projects should adopt
  `tcs-git-helpers` from day one via `/tcs-git-helpers:git-setup`.
- **For shared / multi-contributor repos** (rare in Marcus's
  single-coder workflow, CON-8), pick *one* hook manager and stick with
  it. Document the choice in the repo's `README` or `CONTRIBUTING`.
- **If a teammate proposes adding Husky / lefthook to a TCS-managed
  repo:** point them at this document. The plugin covers the
  Conventional-Commits + pre-commit-checks surface that those tools
  are typically used for; the migration cost goes the other way.

## Why

Husky and the other hook managers are popular for legitimate reasons:
they handle the install step (write to `.git/hooks/`) automatically on
`npm install`, they integrate with `package.json` scripts, and they
make hook customization a code-review surface (everyone sees the YAML
or `.husky/` file).

The plugin's `.githooks/` directory plays the same role for TCS-managed
repos. The collision is structural: both want to own
`core.hooksPath`. Per ADR-10, the resolution is conservative — abort
and document the migration — rather than try to merge the two states
silently.

The single-coder workflow context (CON-8) tilts the decision further:
multi-contributor features that Husky / lefthook offer (per-author
config, hook-bypass-for-CI flags, install-on-clone scripts) are mostly
unnecessary for Marcus. The plugin's `.githooks/` baseline plus
`.config` covers his actual needs (Conventional Commits, pre-commit
content checks, `pre-push` to closed PRs) without the extra surface.

A note on `prepare` scripts: Husky's `prepare: husky install` runs
arbitrary npm code on `npm install`, which is itself a small supply-
chain risk (per integration.md §5). Removing Husky also removes that
attack surface — minor, but worth noting.

---

## See also

- [`sandbox-and-git-config.md`](sandbox-and-git-config.md) — why `core.hooksPath` is the canonical bypass and why setup is the only writer.
- [`best-practices.md`](best-practices.md) — §2 defense in depth requires a clean `.githooks/` layer.
- [`conventional-commits.md`](conventional-commits.md) — the format the plugin's `commit-msg` enforces (Husky's `commitlint` covers similar ground).
- ADR-10 in `docs/XDD/specs/011-tcs-git-helpers/solution.md` — the abort-not-merge decision.
