# tcs-patterns

A catalogue of 21 opinionated pattern skills (architecture, security, testing, language platforms, DevOps, integrations) and an installer that puts only the ones your repository needs into that repository.

> **From 2.0.0 the plugin no longer ships the 21 patterns as plugin skills.** After updating, none of them is active until you run the setup in a repository. Anyone who used `/tcs-patterns:ddd` now gets `/tcs-ddd` after installing it. See [What changed](#what-changed).

## Install a selection

```
/plugin install tcs-patterns@the-custom-startup
```

Then, inside the repository you want patterns for:

```
/tcs-patterns:patterns-setup install
```

The setup scans the repository, proposes the patterns its files justify (with the evidence), asks at most three questions about concerns it could not decide from files, shows what each pattern adds to the skill listing, and writes only what you confirm. It then offers to commit the result. It needs a git repository.

Each pattern is copied to `.claude/skills/tcs-<name>/`, so it is a normal repository skill: it activates on its trigger terms, and teammates get it once the files are committed. An uncommitted install exists only on your machine.

## The four verbs

```
/tcs-patterns:patterns-setup <install|update|remove|status> [path]
```

| Verb | What it does |
|------|--------------|
| `install` | Scan, ask, propose, confirm, write, offer to commit. |
| `update` | Refresh installed patterns whose catalogue version moved on. A pattern you edited locally is shown as a diff and replaced only if you say so. |
| `remove` | Delete a pattern and its manifest entry. Local edits are shown as a diff first and deleted only on your say-so. |
| `status` | Report what is installed, at which version, what has drifted, and any leftovers of an interrupted run. Reads only. |

`[path]` defaults to the session's working directory. A manifest, `.claude/skills/.tcs-patterns-manifest`, records what was installed.

## Read a pattern without installing it

```
/tcs-patterns:pattern <pattern-name>
```

Shows the pattern's full body exactly as shipped and writes nothing. An unknown name lists the available patterns.

## Drift advisory

Installed patterns are copies, so they go stale when the catalogue improves. If `tcs-git-helpers` is installed, its session-start brief adds a line when an installed pattern is behind the catalogue (`run /tcs-patterns:patterns-setup update`) or has left the catalogue (`run /tcs-patterns:patterns-setup status`). A repository without installed patterns sees nothing. Without `tcs-git-helpers`, run `status` yourself.

## What changed

Claude Code lists every available skill's name and description in every session, and that listing is budgeted. 21 plugin skills spent about 5,900 characters of it in every repository, on patterns most repositories never use. Selective install moves them out of the listing until you ask for them.

- **Through 1.x:** all 21 were active everywhere as `/tcs-patterns:<name>`.
- **From 2.0.0:** none is active until installed, and an installed pattern is `/tcs-<name>` (`/tcs-ddd`, not `/tcs-patterns:ddd`). The `tcs-` prefix keeps them apart from your own skills; the installer refuses to overwrite a skill it did not write.
- The plugin description's promise, "install only the patterns relevant to your stack", is now what the plugin does.

Rolling back to 1.x restores the 21 plugin skills; an installed `tcs-<name>` then coexists with the plugin's `<name>`, which duplicates content but does not collide.

## Hooks

The plugin still registers one write-time guard that is independent of the installed patterns: `block-eslint-disable.sh` denies `eslint-disable` in Obsidian plugin repositories. Details: [guide](../../docs/guides/tcs-patterns.md#hooks).

## More

- [Catalogue and usage guide](../../docs/guides/tcs-patterns.md)
- [CHANGELOG](CHANGELOG.md)
