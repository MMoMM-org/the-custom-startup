# Observability of what loads and fires

This is a small, off-by-default recorder for three things Claude Code does that are otherwise
invisible from inside a session: which instruction files get loaded, which skills fire, and which
subagents get dispatched. It exists so a later question — "is anyone actually using this memory
file / skill / agent?" — has real data to answer from, instead of a guess.

It writes nothing anywhere unless you turn it on.

## The two switches

Both are environment variables, both default off, and you set them in the environment the Claude
Code session (or the hook process) runs in — for example in your shell profile, or wherever you
already set `CLAUDE_PROJECT_DIR` and similar.

| Variable | Effect |
|---|---|
| `CLAUDE_OBSERVABILITY_ENABLED=1` | Turns recording on at all. Unset (or anything other than `1`): nothing is recorded, no directory or file is ever created. |
| `CLAUDE_OBSERVABILITY_DETAIL=1` | Adds a handful of more sensitive fields to each record (see "What is recorded", below). **Has no effect unless `CLAUDE_OBSERVABILITY_ENABLED=1` is also set** — it is a second, independent affirmative step, not an upgrade you can flip on its own. |

Turning `ENABLED` off again does not delete anything already written — it just stops new records
from being added. See "How to delete it", below, for actually clearing the record.

## Where the record lives

One file per repository, named `events.jsonl`, one JSON object per line (JSONL — newline-delimited
JSON). It lives **outside this repository's working tree**, so `git add -A` cannot reach it and it
never ends up in a commit or a diff by accident:

```
$HOME/.claude/plugins/data/observability-<repo-name>/observability/events.jsonl
```

`<repo-name>` is this repository's directory name (its git toplevel's basename) — for this repo,
that resolves to `$HOME/.claude/plugins/data/observability-the-custom-startup/observability/events.jsonl`.

If you ever need the exact path without doing that arithmetic by hand, run `selfcheck.sh` (below)
— it prints it as the first thing it does, whether or not recording is on.

You can override where it lives entirely by setting `CLAUDE_OBSERVABILITY_DATA` to a directory of
your choosing; the file then lives at `<that directory>/observability/events.jsonl`. Ordinary use
does not need this — it exists mainly so tests can point recording at an isolated, disposable
directory.

The file rotates once it passes roughly 1 MB: the current file becomes `events.jsonl.1`, the
previous `.1` becomes `.2`, the previous `.2` becomes `.3`, and anything older than that is
discarded. There is never an `events.jsonl.4` or beyond.

## How to read it

It's plain JSONL — one JSON object per line, readable with anything that reads JSON lines. A few
ways, from simplest to most capable:

```bash
# Print it as-is (each line is already a complete, readable JSON object):
cat "$HOME/.claude/plugins/data/observability-the-custom-startup/observability/events.jsonl"

# Pretty-print each line, if you have jq:
jq . "$HOME/.claude/plugins/data/observability-the-custom-startup/observability/events.jsonl"

# Filter to just skill firings:
jq 'select(.kind == "skill")' "$HOME/.claude/plugins/data/observability-the-custom-startup/observability/events.jsonl"
```

Every line carries four fields no matter what kind of event it is — `ts` (UTC timestamp), `kind`
(what happened — `instruction`, `skill`, `agent`, or `state`), `session` (the session it happened
in), and `repo` (this repo's name, never an absolute path) — plus a handful of fields specific to
that `kind`. A line may also carry `"truncated":true` if one of its fields was cut down to the
256-byte-per-field limit.

### Is it actually working right now?

Run the self-check script — it answers "is this actually recording?" honestly, including the case
that's easy to get wrong: an empty log with recording turned on is not the same thing as recording
being off, and this script says which one you're looking at rather than guessing from whether a
file happens to exist yet.

```bash
plugins/tcs-helper/scripts/observability/selfcheck.sh
```

It prints whether each switch is on, the record's path, and whether recording is confirmed working
(it proves this by writing a small check-in record and reading it back — not by assuming success).
Exit status is `0` when recording is off (a choice) or confirmed working, and `1` when it's turned
on but genuinely cannot write (for example, an unwritable directory) — so `selfcheck.sh || echo
"observability is broken"` is a reasonable thing to put in a script.

Running it while recording is on adds one more line to the log, of `kind: state` — that's the
check-in record itself, and it's the mechanism the script uses to prove writing actually works,
not an accident.

## What is recorded, and what is deliberately not

By default (`DETAIL` off), each record keeps only what is needed to know *that* something loaded or
fired, and roughly what it was — never its content:

- **Kept:** which instruction file loaded and why, which skill or agent ran, file paths (made
  relative to this repo, or reduced to just a filename if outside it), the size of a loaded file,
  and — for a Bash tool call — only the program name (e.g. `git`, `npm`), never its arguments.
- **Dropped:** command-line arguments, file contents, the full text of any Write/Edit change,
  `transcript_path`, your absolute home-directory path, and any prompt or response text.

Setting `CLAUDE_OBSERVABILITY_DETAIL=1` (on top of `ENABLED=1`) adds the dropped fields back in.
Turn it on only when you specifically need that level of detail, and turn it back off afterward —
it is the one switch that can put sensitive command lines or file contents into the log.

## How to delete it

There's no special command for this — it's an ordinary file. Stop recording first if you don't want
more lines added while you're doing this (`unset CLAUDE_OBSERVABILITY_ENABLED` or set it to
anything other than `1`), then remove the file or the whole per-repo directory:

```bash
# Just the log (rotated backups included):
rm -f "$HOME/.claude/plugins/data/observability-the-custom-startup/observability/events.jsonl"*

# Or the whole per-repo data directory:
rm -rf "$HOME/.claude/plugins/data/observability-the-custom-startup"
```

Nothing else in the repository references this directory, and it was never part of the git working
tree, so deleting it cannot break anything else.

## Registering the hooks

The recorder only sees anything once the three hooks below are registered in **this repository's
own** `.claude/settings.json` (not a plugin's `hooks.json` — see the caveat right after the
snippet for why that distinction matters). Merge this into the `"hooks"` object of that file,
alongside anything already there for the same event names:

```json
{
  "hooks": {
    "InstructionsLoaded": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR/plugins/tcs-helper/scripts/observability/log_instructions.sh\""
          }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "Skill",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR/plugins/tcs-helper/scripts/observability/log_skill.sh\""
          }
        ]
      }
    ],
    "SubagentStart": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR/plugins/tcs-helper/scripts/observability/log_agent.sh\""
          }
        ]
      }
    ]
  }
}
```

`InstructionsLoaded`'s matcher is not a tool name — for this event, the *load reason*
(`session_start`, `compact`, `include`, and so on) doubles as the matcher, so an empty string here
means "every load, regardless of reason," which is what this recorder wants. `PreToolUse`'s matcher
of `Skill` means this hook only fires for `Skill` tool calls, not every tool call. `SubagentStart`
has no equivalent filter, hence the empty matcher there too.

**Why `$CLAUDE_PROJECT_DIR`, not `$CLAUDE_PLUGIN_ROOT`.** A hook registered by a *plugin's own*
`hooks.json` gets `$CLAUDE_PLUGIN_ROOT` set for it automatically. A hook registered in a
*repository's own* `.claude/settings.json` — which is what these three are — does **not**; that
variable simply isn't set at invocation time for this kind of registration. `$CLAUDE_PROJECT_DIR`
(or a plain absolute path) is what actually resolves regardless of the current working directory at
the moment the hook fires.

**A caveat worth knowing before you register `InstructionsLoaded` in particular.** Claude Code only
does its eager instruction-loading bookkeeping at all when *some* `InstructionsLoaded` hook is
registered — with none registered, it skips that work entirely. Registering the hook above switches
that bookkeeping on, as a fixed cost of registration, independent of whether `CLAUDE_OBSERVABILITY_ENABLED`
is set. In other words: recording being off means no *records* are written, not that the hook costs
nothing to have registered at all. If that eager-load cost matters to you and you are not currently
recording, the honest move is to not register the `InstructionsLoaded` hook until you actually want
to turn recording on.

## Investigating one slow hook: `timed-wrapper.sh`

The three adapters above answer "did X load/fire" questions. They cannot answer "which specific hook
is slow" — and neither can the harness's own telemetry. The spec's README (its T1.4 section) measured
six hook configurations directly and found per-hook duration is not recoverable from configuration
alone: hooks sharing one `(event, matcher)` pair collapse into a single measurement group no matter
how many distinct matcher strings are registered, and hooks within a group run in parallel, so
subtracting the group total does not recover an individual hook's duration either.

`timed-wrapper.sh` exists to answer that one question directly, by standing in for the real hook
command while you investigate. It is not meant to stay installed — put it in place for the duration
of one investigation, read what it wrote, then take it back out (see "How to remove it", below).

### How to install it

Wrap the real hook command in this repository's own `.claude/settings.json` — the same file the
"Registering the hooks" snippet above uses, and for the same reason: a repo's own registration gets
no `$CLAUDE_PLUGIN_ROOT`. Say you want to know whether a `PreToolUse`/`Bash` hook at
`/abs/path/to/real-hook.sh` is the slow one:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR/plugins/tcs-helper/scripts/observability/timed-wrapper.sh\" --event PreToolUse --matcher Bash -- /abs/path/to/real-hook.sh"
          }
        ]
      }
    ]
  }
}
```

The CLI shape is fixed: `timed-wrapper.sh --event <hook_event> --matcher <matcher> -- <real hook
command> [args...]`. `--event` and `--matcher` are what label the resulting record, and they arrive as
command-line arguments — never read from the hook's own payload — because the wrapper must never
touch stdin at all: a hook's JSON payload arrives there, and consuming any of it would silently hand
the wrapped command an empty payload for as long as the wrapper stayed installed. Everything after
`--` is the real hook command, run exactly as it would have run directly, with its own stdin, stdout,
stderr and exit status passed through unchanged.

Recording also needs `CLAUDE_OBSERVABILITY_ENABLED=1` set, the same switch the three adapters use —
without it, the wrapper runs the real hook command transparently and writes nothing.

### What it records, and where

Each invocation writes one `kind: hook` record, carrying the four common fields "Where the record
lives" and "How to read it" (above) already describe — `ts`, `kind`, `session`, `repo` — plus:

| Field | Value |
|---|---|
| `hook_event` | whatever you passed to `--event` |
| `matcher` | whatever you passed to `--matcher` |
| `ms` | the wrapped command's own wall-clock duration, in milliseconds |
| `exit` | the wrapped command's own exit status |
| `scope_note` | always `single` — see below |

It lands in the same `events.jsonl` everything else in this recorder writes to, at the path "Where
the record lives" describes, with the same rotation and the same `CLAUDE_OBSERVABILITY_DATA`
override. There is no separate file for wrapper records.

### Privacy: what is, and is not, in that record

Everything this records stays on this machine: the record is a line appended to a file under your
home directory, and nothing about it is transmitted anywhere. What the record does **not** contain —
the real hook command's own command line, any of its arguments, or anything from the hook payload
(the wrapper never reads that payload; see "How to install it"). Each hook record contains nine
fields: `ts` (UTC timestamp), `kind` (fixed as `"hook"`), `session` (the session identifier from
`$CLAUDE_CODE_SESSION_ID` — see "Caveats, stated plainly" below for its unverified status), `repo`
(the repository's directory name only, not its full path — deliberate redaction per the spec's R-3
rule), `hook_event` (from `--event`), `matcher` (from `--matcher`), `ms` (duration in milliseconds),
`exit` (exit status), and `scope_note` (always `"single"`). The only strings that come from what you
yourself typed are `hook_event` and `matcher`; all other fields are system-generated, measurements,
or fixed labels. Nothing is copied or inferred from the wrapped command. Every one of these claims
is checkable directly against `timed-wrapper.sh`'s own source: it contains no `read` and no
`cat` of stdin, and never touches file descriptor 0.

### `scope_note: single` — read this before trusting a number

Every record `timed-wrapper.sh` writes carries `scope_note: single`: the duration is one hook
invocation's own wall-clock time, not pooled with anything else. The record schema's `scope_note`
field also has a `batch` value in its enum, but this design never writes it — `batch` exists only as
a label for the harness's own aggregate `hook_execution_complete` figure, the number the T1.4 spike
found cannot be split into per-hook durations by configuration alone. If you ever see `batch`
attached to a duration, it describes several hooks' combined time, not one hook's; reading it as one
hook's own cost is exactly the misreading this whole mechanism exists to prevent, which is why every
duration in the report is labelled with which kind it is rather than left for you to guess.

### How to remove it

Edit `.claude/settings.json` again and put the original hook command back exactly where the wrapped
one was — that is the entire removal procedure. There is nothing else to undo: `timed-wrapper.sh` is
not a daemon, it installs nothing outside that one registration line, and it leaves no running
process or cached state behind. Once the registration is reverted, nothing of it remains anywhere in
the hook execution path. The only trace left behind is the records it already wrote while it was
installed — ordinary `kind: hook` lines in `events.jsonl`, no different in kind from the records the
three adapters above write, and removed the same way (see "How to delete it").

### Caveats, stated plainly

- **`session` is unverified.** The `session` field comes from the `$CLAUDE_CODE_SESSION_ID`
  environment variable, not from the hook payload — the wrapper never reads the payload at all. Two
  things about that variable are not yet confirmed: whether it reaches a hook the harness itself
  spawns, and whether its value actually matches the payload's own `session_id`. Treat `session` on a
  hook record as unverified until both are checked against a live session. When the variable is
  absent, the field is left empty rather than filled with a guess, so a hook record may simply fail to
  join to that session's other records — it does not silently join to the wrong one.
- **Overhead is two different numbers, and only one of them is specific to this wrapper.** The
  wrapper's own marginal cost — what it adds on top of running the real hook directly — was measured
  at roughly 0.85 ms on Linux (aarch64), against this feature's 1 ms budget. That is not the same
  number as the cost of actually writing a record: using the same shared writer path this wrapper also
  calls, the measured end-to-end cost of writing one record (measured for an instruction-load event,
  in the same research pass) came out close to 13 ms — `solution.md`'s Quality Requirements section
  has the full breakdown. Both figures are from a Linux container; the macOS figure has not been
  measured yet, and neither number should be assumed to transfer.
