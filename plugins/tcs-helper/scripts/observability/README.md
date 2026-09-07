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
