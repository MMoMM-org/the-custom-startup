<!--
Auto-merge is armed on most pull requests here, so this body is the last place
anybody looks before the change lands. The `docs-sync` check enforces the
surfaces it can name; the list below covers the ones it deliberately does not,
because requiring them on every change would be wrong more often than right.
-->

## What and why

<!-- What changed, and what problem it addresses. -->

## Documentation

Surfaces that are easy to miss in this repo. Tick what applies, strike what does not.

- [ ] `CHANGELOG.md` — an entry under the right `[Unreleased] — <topic>` heading
- [ ] `README.md` — the feature bullets still describe the behaviour accurately
- [ ] `docs/` — the guide or reference page for what changed
- [ ] Config that ships to users — `scripts/statusline.toml` and friends
- [ ] The interactive configurator — it writes its **own** config file, so a new
      key missing there does not exist for anyone who set things up through the
      wizard
- [ ] Plugin `CHANGELOG.md` / `README.md`, if a plugin changed

If `docs-sync` names a surface this change genuinely does not touch, waive it
here with a reason of at least 20 characters — one line per surface:

```
Docs: <path> — <why this change does not touch that surface>
```

## Verification

<!--
What was actually run, and what it said. "Tests pass" is not verification;
`520 passed, 1 skipped` is.
-->

Closes #
