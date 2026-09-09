#!/usr/bin/env python3
"""Add the observability registration to a target's local settings layer.

WHAT THIS WRITES INTO -- and why that is the dangerous part.

The target is `.claude/settings.local.json` in a repository the maintainer of
this code does not own (ADR-1). That file is deliberately untracked, so unlike
every other artifact this spec produces, a mistake here cannot be recovered
from version control. Everything below that reads as excessive care is aimed
at that single fact.

THE PRECEDENT, AND WHERE IT STOPS BEING ONE.

`modules/satori/scripts/install-hooks.sh:70-87` is the model for the MERGE:
read the whole document, `setdefault` the block, append only when absent,
reassign. That shape is copied here.

`:97-99` is the ANTI-model for the WRITE:

    with open(settings_file, 'w') as f:     # truncates first
        json.dump(data, f, indent=2)        # rewrites second

An interruption between those two lines leaves the maintainer with an empty
file and no way back. T2.5 replaces the write below with backup ->
temp-write -> rename under a lock. Until then this module writes only after a
successful parse, and never truncates a file it has not fully read.

TWO DEFAULTS THAT LOOK LIKE STYLE AND ARE NOT.

  * `ensure_ascii=False` -- json.dump defaults to True and would silently
    rewrite a foreign literal 'ä' as '\\u00e4'. The document still parses to
    the same object, so this passes every assertion made on parsed values
    while the maintainer's bytes have changed. This repository has been
    bitten by that default before (SDD-AC-10).
  * `indent=2` plus a trailing newline -- matches what the harness and every
    editor in this repository write, so our edit does not show up as a
    whole-file reformat in someone's diff.

OWNERSHIP IS THE PATH NAMESPACE (ADR-5). An entry is ours when its command
points into `$HOME/.claude/observability/`. Not exact string equality, which
is what satori uses: that silently produces a duplicate group whenever the
command changes, with no way left to recognise or remove the old one.
"""
import argparse
import json
import os
import sys

# The bundle is referenced through $HOME rather than an absolute path (ADR-2):
# one command string has to work on the host and inside a container, and an
# absolute path has no upgrade story.
NAMESPACE = '$HOME/.claude/observability/'

ENV_SWITCH = ('CLAUDE_OBSERVABILITY_ENABLED', '1')

# event -> (matcher, script). PreToolUse is matched to Skill alone; the other
# two carry no matcher because their events fire once, not per tool.
REGISTRATION = {
    'InstructionsLoaded': ('', 'log_instructions.sh'),
    'PreToolUse': ('Skill', 'log_skill.sh'),
    'SubagentStart': ('', 'log_agent.sh'),
}


def command_for(script):
    """The command string as it is written into settings.

    The inner quotes are part of the value: the harness runs the command
    through a shell, and $HOME can contain spaces.
    """
    return '"%s%s"' % (NAMESPACE, script)


def is_ours(command):
    """ADR-5: ownership is the namespace, never the exact string."""
    return NAMESPACE in command


def entry_is_ours(entry):
    """Check if any hook in an entry is ours. Validates hook structure.

    A malformed entry (hooks not a list, or list containing non-dicts) is
    treated as not ours, not as an error. The caller will validate structure.
    """
    hooks = entry.get('hooks', [])
    if not isinstance(hooks, list):
        return False
    return any(
        is_ours(hook.get('command', ''))
        for hook in hooks
        if isinstance(hook, dict)
    )


def load_settings(path):
    """Returns (data, error). An absent file is an empty document, not an error.

    A parse failure is returned rather than raised so the caller can report a
    diagnosis and leave the file alone -- SDD-AC-5 asks for a diagnosis rather
    than a traceback, and the file must not be touched.
    """
    if not os.path.isfile(path):
        return {}, None
    try:
        with open(path, 'r', encoding='utf-8') as handle:
            text = handle.read()
    except OSError as exc:
        return None, 'cannot read %s: %s' % (path, exc)
    if not text.strip():
        # An empty file is an empty document. Treating it as a parse error
        # would refuse to configure a target whose settings file was created
        # by `touch` -- a state with nothing wrong with it.
        return {}, None
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, 'cannot parse %s as JSON: %s' % (path, exc)
    if not isinstance(data, dict):
        return None, '%s does not hold a JSON object (found %s)' % (
            path, type(data).__name__)
    return data, None


def add_registration(data):
    """Merge our entries into a settings document. Returns True if it changed.

    Follows satori's add_hook_if_absent shape: append only when absent, leave
    every existing entry -- including foreign entries under our own event
    names -- exactly where it is.
    """
    changed = False

    env = data.setdefault('env', {})
    if not isinstance(env, dict):
        raise ValueError('"env" is not an object (found %s)' % type(env).__name__)
    key, value = ENV_SWITCH
    if env.get(key) != value:
        env[key] = value
        changed = True

    hooks = data.setdefault('hooks', {})
    if not isinstance(hooks, dict):
        raise ValueError('"hooks" is not an object (found %s)' % type(hooks).__name__)

    for event, (matcher, script) in REGISTRATION.items():
        entries = hooks.setdefault(event, [])
        if not isinstance(entries, list):
            raise ValueError(
                '"hooks.%s" is not a list (found %s)' % (event, type(entries).__name__))

        # Validate that existing entries have proper structure before examining them
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            hooks_field = entry.get('hooks')
            if hooks_field is not None and not isinstance(hooks_field, list):
                raise ValueError(
                    '"hooks.%s" contains an entry with malformed "hooks" field (found %s)' % (
                        event, type(hooks_field).__name__))
            if isinstance(hooks_field, list):
                for hook in hooks_field:
                    if not isinstance(hook, dict):
                        raise ValueError(
                            '"hooks.%s" contains an entry with non-object hook in "hooks" list' % event)

        if any(entry_is_ours(entry) for entry in entries if isinstance(entry, dict)):
            continue
        entries.append({
            'matcher': matcher,
            'hooks': [{'type': 'command', 'command': command_for(script)}],
        })
        changed = True

    return changed


def write_settings(path, data):
    """Write the document back.

    Deliberately NOT satori's truncate-then-rewrite. T2.5 wraps this in
    backup -> temp file -> rename under a lock; the signature is already the
    one that change needs, so no caller moves when it lands.
    """
    parent = os.path.dirname(os.path.abspath(path))
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)
    text = json.dumps(data, indent=2, ensure_ascii=False) + '\n'
    with open(path, 'w', encoding='utf-8') as handle:
        handle.write(text)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Add the observability registration to a settings file.')
    parser.add_argument(
        '--settings',
        required=True,
        help='path to the settings file to edit (never defaults to a real one)')
    args = parser.parse_args(argv)

    data, error = load_settings(args.settings)
    if error:
        sys.stderr.write('%s\n' % error)
        return 1

    try:
        changed = add_registration(data)
    except ValueError as exc:
        sys.stderr.write('%s: %s\n' % (args.settings, exc))
        return 1

    if not changed:
        print('already configured: %s' % args.settings)
        return 0

    write_settings(args.settings, data)
    print('registered observability hooks in %s' % args.settings)
    return 0


if __name__ == '__main__':
    sys.exit(main())
