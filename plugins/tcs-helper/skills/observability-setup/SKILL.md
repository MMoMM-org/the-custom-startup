---
name: observability-setup
description: "Use when turning Claude Code observability recording on or off in a repository, or when asking whether a repository is still recording. MUST BE USED whenever the user says set up observability, install the observability hooks, stop recording here, remove observability, or is this repo still recording. Triggers on: observability-setup, observability status, recording drift."
user-invocable: true
argument-hint: "<install|remove|status> <path>"
allowed-tools: Bash, Read
---

## Persona

**Active skill: tcs-helper:observability-setup**

Turns recording on in a repository the operator names, takes it back out again, and reports
honestly whether a target is recording. One command with three verbs, never three commands.

The mechanics live in `lib/setup.sh` and are not restated here. This file owns the two things a
script cannot: the **confirmation** before anything is written, and the **narration** of what
changed. Everything else is one call.

## Interface

```
setup.sh <install|remove|status> --target <path> [--yes] [--plan]
```

| Verb | What it does |
|---|---|
| `install` | Installs the bundle into `$HOME/.claude/observability/` and registers three hooks plus the env switch in the target's `.claude/settings.local.json` |
| `remove` | Takes this feature's own entries back out. Never deletes a record |
| `status` | Reports the target as **recording**, **configured but silent**, or **not configured**, plus the installed bundle's version against this plugin's |

Without `--yes`, `install` and `remove` report the plan and write nothing. `--plan` forces that
same no-write path even when `--yes` is given. `status` is read-only in every mode.

## Flow

### 1. Establish the target

The operator names a repository. Never assume the current one, and never run against a repository
whose path you inferred.

### 2. Show the plan

```bash
"${CLAUDE_PLUGIN_ROOT}/skills/observability-setup/lib/setup.sh" install --target "<path>"
```

No `--yes`, so this writes nothing. Surface **all** of its output to the user — the `TARGET`,
`PLAN`, and any `STOP`/`ABORT` line — verbatim. Do not summarise a refusal; the reason is the
useful part.

### 3. Take the confirmation

This is the step the dispatcher cannot own (SDD/Runtime View step 5).

- Print the plan and wait for an explicit `y`/`yes` in chat before going further.
- If the user declines, stop here and say that nothing was written. Nothing was: step 2 wrote
  nothing, which is why the plan step exists.
- Never re-run with `--yes` on the strength of a general "go ahead" given before the plan was
  shown.

### 4. Apply

```bash
"${CLAUDE_PLUGIN_ROOT}/skills/observability-setup/lib/setup.sh" install --target "<path>" --yes
```

### 5. Report what changed, and how to reverse it

Relay the dispatcher's own lines. The `ADDED`/`REMOVED` line names the entries; the `UNDO` line is
the exact command that reverses the change — pass it on rather than paraphrasing it, so the
operator can paste it.

### 6. Confirm

```bash
"${CLAUDE_PLUGIN_ROOT}/skills/observability-setup/lib/setup.sh" status --target "<path>"
```

A freshly installed target reports **configured but silent** until a session in it produces a
record. That is the expected first reading, not a failure — and it is exactly the state that
`status` exists to distinguish from *not configured at all*.

## How to read an outcome

The dispatcher's exit status is the short answer; the labelled lines are the long one.

| Line | Meaning | Exit |
|---|---|---|
| `STOP: Target is not inside a git repository` | Nothing was written. Not a failure | 0 |
| `STOP: Foreign hook entries occupy the event names…` | Another tool already owns those events. Nothing was changed, and nothing should be forced | 0 |
| `ABORT: …not valid JSON…` | A settings file this feature did not author is unreadable. It was left exactly as it was — never repair it | non-zero |
| `ABORT: Refusing to write: version control does not ignore…` | The change would be committable in a repository we do not own. This is the one refusal that protects a third party | non-zero |
| `ABORT: another observability setup run holds the lock…` | A live run owns the target. Wait and retry; never delete the lock file | non-zero |

A `STOP` is a normal outcome. Say so plainly rather than presenting it as an error.

## Constraints

- **Never run `--yes` against a repository the operator did not name in this conversation.**
- Never edit a target's settings file by hand, with `Edit` or otherwise. The dispatcher's write path
  is backup → temp file → atomic rename, and a hand edit has none of that.
- Never delete a lock file, a `.tcs-observability.bak`, or a record directory to get past an error.
- `remove` is not a data-deletion tool. Records already written survive it, deliberately.
