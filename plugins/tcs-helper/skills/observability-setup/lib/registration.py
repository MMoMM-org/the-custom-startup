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
file and no way back. write_settings() below replaces that with backup ->
temp-write -> rename, run under a lock held across the whole load-merge-write
sequence. The real file is only ever opened for reading; the new document
reaches it through os.replace() alone.

WHY THE TEMP FILE IS NOT IN $TMPDIR, THOUGH BOTH IN-REPO PRECEDENTS PUT IT
THERE. `install.sh:729-731` and `scripts/the-custom-startup-configure-statusline.sh:176-180`
both `mktemp` and `mv` onto the settings file. `mktemp` creates in $TMPDIR,
which on the machine this was written on is a DIFFERENT FILESYSTEM from the
repositories being configured (st_dev 16777234 vs 16777245). Across a
filesystem boundary `mv` is copy-then-unlink, not a rename -- and the direct
Python translation is worse than merely non-atomic: os.rename() raises EXDEV
and the obvious rescue, shutil.move(), falls back to copying INTO the
destination, which opens and truncates the real file. That is precisely the
window this module exists to close, reintroduced while looking like house
style. So the temp file is created in the TARGET's own directory and replaced
with os.replace(). Follow the precedent's intent, not its literal shape --
please do not "fix" this back to mktemp.

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
import shutil
import stat
import sys

import lock

# The bundle is referenced through $HOME rather than an absolute path (ADR-2):
# one command string has to work on the host and inside a container, and an
# absolute path has no upgrade story.
NAMESPACE = '$HOME/.claude/observability/'

ENV_SWITCH = ('CLAUDE_OBSERVABILITY_ENABLED', '1')

# The three sidecar files, all beside the settings file they belong to and all
# sharing one infix so a single ignore rule covers the set.
BACKUP_SUFFIX = '.tcs-observability.bak'
LOCK_SUFFIX = '.tcs-observability.lock'
TEMP_SUFFIX = '.tcs-observability.tmp'

# Deliberately NOT tempfile.mkstemp: a random name cannot be handed to
# `git check-ignore` before it exists, and the Safety requirement binds the
# temp file exactly as it binds the backup. A fixed name is safe because it is
# only ever created while this process holds the lock.


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


def backup_path(path):
    return str(path) + BACKUP_SUFFIX


def lock_path(path):
    return str(path) + LOCK_SUFFIX


def temp_path(path):
    return str(path) + TEMP_SUFFIX


def written_paths(path):
    """Every path this module can create in a target, the target included.

    The declaration the "Safety" quality requirement is checked against: no
    file this feature writes in a target may be reachable by version control.
    Enforcing that -- refusing a target where any of these is committable --
    is SDD-AC-6, which belongs to detection and to the command that composes
    it, not here. This module's obligation is to keep the list honest, so a
    path added to write_settings without being added here is a bug.
    """
    target = os.path.abspath(str(path))
    return [target, backup_path(target), lock_path(target), temp_path(target)]


# ---------------------------------------------------------------------------
# The write
# ---------------------------------------------------------------------------

def _fsync_dir(directory):
    """Best-effort: make the rename itself durable, not just its contents."""
    try:
        fd = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def discard_backup(path):
    """Removal takes the backup with it -- at most one exists per target, and
    none outlives the registration it was taken for."""
    try:
        os.unlink(backup_path(path))
    except OSError:
        pass


def write_settings(path, data):
    """Replace the document without ever opening the real file for writing.

    backup -> temp-write -> rename (see the module docstring for why the temp
    file lives in the target's own directory). SDD-AC-9: if anything fails
    between the backup and the rename, the original is untouched and the
    backup is the second copy of it.
    """
    parent = os.path.dirname(os.path.abspath(path))
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)
    text = json.dumps(data, indent=2, ensure_ascii=False) + '\n'

    mode = 0o600
    if os.path.isfile(path):
        mode = stat.S_IMODE(os.stat(path).st_mode)
        # copy2, not copy: the backup keeps the original's mode and times, so
        # restoring it by hand restores the file the maintainer had.
        shutil.copy2(path, backup_path(path))

    temp = temp_path(path)
    fd = os.open(temp, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp, mode)
        os.replace(temp, path)
    except BaseException:
        # Including KeyboardInterrupt: a Ctrl-C here must not leave a stray
        # temp file in a repository we do not own.
        try:
            os.unlink(temp)
        except OSError:
            pass
        raise
    _fsync_dir(parent)


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
    parser.add_argument(
        '--lock-held-by-caller',
        action='store_true',
        help=(
            'do not acquire the per-target lock: the caller already holds it '
            'for a longer sequence. Only lib/setup.sh passes this'))
    args = parser.parse_args(argv)

    # The lock is acquired before the document is read, not before it is
    # written, so two concurrent runs serialize across the whole load-merge-
    # write sequence rather than racing to a merge each computed alone
    # (SDD/Runtime View step 2).
    #
    # A caller that already owns THIS lock skips the acquisition rather than
    # deadlocking against itself. The lock is a cooperative file, not a
    # reentrant primitive: lib/setup.sh takes it before detection so the whole
    # detect->write sequence serializes, which is a strictly longer hold than
    # this module could take on its own, and it uses this same path and the
    # same `<pid>:<epoch>` format so a direct CLI run still contends with it
    # correctly. The flag suppresses only the acquisition here -- the lock
    # itself still exists and is still honoured by everyone else.
    parent = os.path.dirname(os.path.abspath(args.settings))
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)
    if args.lock_held_by_caller:
        return _edit_under_lock(args)
    lock_file = lock_path(args.settings)
    if not lock.acquire_lock(lock_file):
        sys.stderr.write('another observability setup run holds %s\n' % lock_file)
        return 1
    try:
        return _edit_under_lock(args)
    finally:
        lock.release_lock(lock_file)


def _edit_under_lock(args):
    data, error = load_settings(args.settings)
    if error:
        sys.stderr.write('%s\n' % error)
        return 1

    if args.remove:
        changed = remove_registration(data)
        if not changed:
            print('nothing to remove: %s' % args.settings)
            discard_backup(args.settings)
            return 0
        write_settings(args.settings, data)
        discard_backup(args.settings)
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
