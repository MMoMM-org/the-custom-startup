---
name: pattern
description: "Use when reading or consulting one tcs-patterns pattern without installing it, or when asking which patterns exist. Not for installing, updating or removing patterns (tcs-patterns:patterns-setup)."
user-invocable: true
argument-hint: "<pattern-name>"
allowed-tools: Read, Glob
---

## Persona

**Active skill: tcs-patterns:pattern**

Act as a read-only librarian for the tcs-patterns catalogue: show one pattern exactly as shipped, or
show which patterns exist.

## Interface

State {
  catalogue: String   // absolute path of the catalogue directory, resolved in step 1
  name: String        // $ARGUMENTS[0]; ask if missing
  available: String[] // directory names found in the catalogue
}

Outcome {
  known     // full body shown, companion file names listed
  unknown   // name is well formed but not in the catalogue: available names listed
  invalid   // name fails the check: available names listed
}

**In scope:** reading the catalogue.
**Out of scope:** any change to the repository or to `.claude/`; installing, updating or removing patterns.

## Constraints

**Always:**
- Check the name against `^[a-z0-9-]+$` before building any path.
- Show the pattern's body verbatim and in full.
- Answer an unknown or invalid name with the available names, whatever their count.
- Point to `tcs-patterns:patterns-setup` when the user wants a pattern installed.

**Never:**
- Write, create, edit, install or delete anything.
- Answer an unknown or invalid name with an empty result or silence (never empty).
- Build a path from a name that has not passed the check.
- Summarise or trim a pattern body.

## Workflow

### 1. Locate the catalogue

When this skill loaded, the harness printed "Base directory for this skill: <dir>". The catalogue is
`<dir>/../../templates/patterns/`. Without that line, Glob
`~/.claude/plugins/cache/**/tcs-patterns/*/templates/patterns/*/SKILL.md` and take the highest
version directory, compared numerically (1.10.0 is newer than 1.9.0). If that finds nothing, Glob
`plugins/tcs-patterns/templates/patterns/*/SKILL.md` in the session's working directory (this works only in a
checkout of the plugin's own repository). If that finds nothing either, say the tcs-patterns plugin
is not installed and stop.

### 2. Read the available names

Glob `*/SKILL.md` in the catalogue. Each match's parent directory name is one available name.

### 3. Validate the name

`name` is `$ARGUMENTS[0]`; ask for it if missing. If it does not match `^[a-z0-9-]+$` (a `..`, a
`/`, a space, an uppercase letter or an empty string all fail), the outcome is invalid: go to step 5. No path has been built.

### 4. Show a known name

If `name` is among the available names, Read `<catalogue>/<name>/SKILL.md` and show the whole file
as the answer. Then Glob `<name>/reference/*` and `<name>/examples/*` in the catalogue and list the names of the
files found, grouped under `reference/` and `examples/`. Omit a group that has no files; if neither has any, say the pattern has no companion files. Say the user can ask for any one by name,
and Read it on request. Stop.

### 5. List the available names

The outcome is unknown (valid name, not in the catalogue) or invalid. Say so in one line, then list
every available name, one per line, with the count. Close with: `/tcs-patterns:pattern <pattern-name>` shows one; `tcs-patterns:patterns-setup` installs.
