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
read the whole document, `setdefault` the block, append only when absent.
That shape is copied here.

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


def _entry_is_owned(entry):
    """Whether an entry sitting inside a hooks[event] list is ours.

    entry_is_ours() assumes its argument is already a dict -- it calls
    entry.get() unconditionally -- but an entries list can itself contain a
    malformed, non-dict element (a settings file we do not own is free to
    be anything). Every caller that walks such a list needs both checks
    together; this is that pairing, written once rather than three times.
    """
    return isinstance(entry, dict) and entry_is_ours(entry)


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


def _expected_entry(matcher, script):
    return {
        'matcher': matcher,
        'hooks': [{'type': 'command', 'command': command_for(script)}],
    }


def add_registration(data):
    """Merge our entries into a settings document.

    Returns (changed, status). status is one of:

      'none'    -- the env switch and every expected entry were already
                   present and identical to what command_for() produces
                   today; nothing was touched. Reported as "already
                   configured" -- SDD-AC-7.
      'install' -- at least one expected entry was missing outright and got
                   appended; nothing of ours was replaced.
      'update'  -- something of ours was stale and got corrected: either an
                   entry of ours (namespace membership per ADR-5, not
                   exact-string identity) whose command did not match what
                   command_for() produces today -- an older bundle
                   version's command, most likely -- and was replaced in
                   place rather than appended beside it; or the env
                   switch's value was wrong and got corrected. SDD-AC-8:
                   the caller needs to know something stale was fixed,
                   which "install" would hide, so 'update' wins whenever a
                   single run produces both an install and a correction.

    Follows satori's add_hook_if_absent shape for what is left alone: every
    existing entry that is not ours -- including a foreign entry under our
    own event name -- stays exactly where it is.
    """
    changed = False
    replaced = False

    env = data.setdefault('env', {})
    if not isinstance(env, dict):
        raise ValueError('"env" is not an object (found %s)' % type(env).__name__)
    key, value = ENV_SWITCH
    if key in env:
        if env[key] != value:
            env[key] = value
            changed = True
            replaced = True
    else:
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

        expected = _expected_entry(matcher, script)
        ours_indices = [
            i for i, entry in enumerate(entries) if _entry_is_owned(entry)
        ]

        if not ours_indices:
            entries.append(expected)
            changed = True
            continue

        ours_entries = [entries[i] for i in ours_indices]
        if len(ours_entries) == 1 and ours_entries[0] == expected:
            continue

        # ADR-5: whatever is here under our namespace is ours to replace --
        # a stale command from an older bundle version, or (defensively) a
        # duplicate. Replace at the first occurrence's position instead of
        # appending, so re-running setup never grows the list.
        insert_at = ours_indices[0]
        entries[:] = [entry for entry in entries if not _entry_is_owned(entry)]
        entries.insert(insert_at, expected)
        changed = True
        replaced = True

    if not changed:
        return False, 'none'
    return True, ('update' if replaced else 'install')


def remove_registration(data):
    """Undo add_registration: prune only what's ours (ADR-5 namespace
    membership), and delete a container add_registration created only once
    removing our content leaves it completely empty -- SDD-AC-12,
    SDD-AC-13, SDD-AC-14.

    A container is deleted only when THIS call emptied it -- not merely
    once it "holds nothing of ours": a container that still holds foreign
    content (a foreign 'env' key beside our switch, a foreign entry beside
    ours) is left in place with that foreign content, same as one that was
    already completely empty before this call ran. Neither is ours to
    delete.

    This function's only effect is on `data` in memory -- it has no path to
    anything else on disk, which is what SDD-AC-14 (existing records
    survive) rests on.
    """
    changed = False

    env = data.get('env')
    if isinstance(env, dict):
        key, _value = ENV_SWITCH
        if key in env:
            del env[key]
            changed = True
            if not env:
                del data['env']

    hooks = data.get('hooks')
    if isinstance(hooks, dict):
        hooks_changed = False
        for event in list(hooks.keys()):
            entries = hooks[event]
            if not isinstance(entries, list):
                continue
            kept = [entry for entry in entries if not _entry_is_owned(entry)]
            if len(kept) == len(entries):
                continue
            hooks_changed = True
            changed = True
            if kept:
                hooks[event] = kept
            else:
                del hooks[event]
        if hooks_changed and not hooks:
            del data['hooks']

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
        description='Add or remove the observability registration in a settings file.')
    parser.add_argument(
        '--settings',
        required=True,
        help='path to the settings file to edit (never defaults to a real one)')
    parser.add_argument(
        '--remove',
        action='store_true',
        help='remove the observability registration instead of adding it')
    args = parser.parse_args(argv)

    data, error = load_settings(args.settings)
    if error:
        sys.stderr.write('%s\n' % error)
        return 1

    if args.remove:
        changed = remove_registration(data)
        if not changed:
            print('nothing to remove: %s' % args.settings)
            return 0
        write_settings(args.settings, data)
        print('removed observability hooks from %s' % args.settings)
        return 0

    try:
        changed, status = add_registration(data)
    except ValueError as exc:
        sys.stderr.write('%s: %s\n' % (args.settings, exc))
        return 1

    if not changed:
        print('already configured: %s' % args.settings)
        return 0

    write_settings(args.settings, data)
    if status == 'update':
        # 'update' also fires for an env-only correction (no hook entry
        # touched), so the message names the registration, not "hooks".
        print('updated observability registration in %s' % args.settings)
    else:
        print('registered observability hooks in %s' % args.settings)
    return 0


if __name__ == '__main__':
    sys.exit(main())
