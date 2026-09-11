---
name: observability-setup
description: "Use when turning Claude Code observability recording on or off in a repository, or when asking whether a repository is still recording. MUST BE USED whenever the user says set up observability, install the observability hooks, stop recording here, remove observability, or is this repo still recording. Triggers on: observability-setup, observability status, recording drift, configured but silent."
user-invocable: true
argument-hint: "<install|remove|status> <path>"
allowed-tools: Bash, Read
---

## Persona

**Active skill: tcs-helper:observability-setup**

Act as the operator of a per-repository recording switch: turn recording on in a repository the
user names, take it back out again, and report honestly whether a target is recording.

The mechanics belong to `lib/setup.sh`. This skill owns the two things a script cannot: the
confirmation before anything is written, and the narration of what changed.

## Interface

Verb {
  install    // install the bundle and register three hooks plus the env switch
  remove     // take this feature's own entries back out; never deletes a record
  status     // report recording / configured but silent / not configured, and bundle drift
}

Outcome {
  label: TARGET | PLAN | ADDED | REMOVED | MIGRATED | UNDO | BUNDLE | RECORDS | STATUS | STOP | ABORT | INFO
  message: String
}

State {
  dispatcher: String          // absolute path, resolved in step 1
  verb: Verb
  target: String
  confirmed: boolean          // set only by an explicit y/yes after the plan is shown
}

**In scope:** a repository the user named in this conversation.
**Out of scope:** editing a settings file directly, deleting records, deleting a lock or a backup.

## Constraints

**Always:**
- Show the plan and take an explicit `y`/`yes` before passing `--yes`.
- Relay the dispatcher's labelled lines verbatim, including the reason in any `STOP` or `ABORT`.
- Pass the `UNDO` line on unchanged, so the user can paste it.
- Present a `STOP` as a normal outcome, not an error.

**Never:**
- Run `--yes` against a repository the user did not name in this conversation.
- Infer the target from the current directory.
- Edit a target's settings file with Edit or Write.
- Delete a lock file, a `.tcs-observability.bak`, or a record directory to get past an error.
- Re-run with `--yes` on a "go ahead" given before the plan was shown.

## Workflow

### 1. Locate the dispatcher and establish the target

`CLAUDE_PLUGIN_ROOT` is set for harness-spawned plugin code and is empty in a Bash-tool
subprocess, so resolve the path instead of interpolating the variable:

```bash
find "$HOME/.claude/plugins/cache" -path '*/tcs-helper/skills/observability-setup/lib/setup.sh' -type f 2>/dev/null | sort | tail -1
```

If that prints nothing, use `<repo toplevel>/plugins/tcs-helper/skills/observability-setup/lib/setup.sh`.
Use the absolute path it prints in every later step — the shell does not carry variables between
Bash calls.

Take the repository path from the user. Ask for it if it was not given.

### 2. Show the plan

```bash
"<dispatcher>" <verb> --target "<path>"
```

No `--yes`, so nothing is written. Surface every line of the output.

### 3. Read the outcome

| Line | Meaning | Next |
|---|---|---|
| `STOP: Target is not inside a git repository` | Nothing written | Report and stop |
| `STOP: Foreign hook entries occupy the event names…` | Another tool owns those events | Report and stop; do not force |
| `ABORT: …not valid JSON…` | A settings file this feature did not author is unreadable | Report it; leave the file alone |
| `ABORT: Refusing to write: version control does not ignore…` | The change would be committable in someone else's repository | Report and stop |
| `ABORT: another observability setup run holds the lock…` | A live run owns the target | Wait and retry |
| `PLAN: …` | Nothing written yet | Continue to step 4 |

### 4. Take the confirmation

Print the plan and wait for an explicit `y`/`yes` in chat.

If the user declines, stop and say that nothing was written.

### 5. Apply

```bash
"<dispatcher>" <verb> --target "<path>" --yes
```

### 6. Report what changed and how to reverse it

Relay the `ADDED`/`REMOVED`/`MIGRATED` lines, then the `UNDO` line.

### 7. Confirm

```bash
"<dispatcher>" status --target "<path>"
```

A freshly installed target reports **configured but silent** until a session in it produces a
record. Say so — that is the expected first reading, and it is the state `status` exists to
distinguish from **not configured**.
