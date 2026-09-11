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
    """ADR-5: ownership is the namespace, never the exact string.

    The isinstance guard is load-bearing, not defensive dressing: a settings
    file we do not own may carry a non-string "command", and `NAMESPACE in
    123` raises TypeError -- which no caller catches, so it reached the user
    as a traceback instead of the diagnosis this module's docstring promises.
    remove_registration walks EVERY event, not only the three we register, so
    the guard has to live here rather than in a per-event validator. A
    non-string command is not ours; that is the whole answer.
    """
    return isinstance(command, str) and NAMESPACE in command


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


def validate_registration_shape(data):
    """Raise ValueError if add_registration() could not merge into `data`.

    Every check add_registration makes, hoisted so a caller can run them
    BEFORE it writes anything, anywhere. That ordering is the whole point: a
    cross-file migration removes the legacy registration from one file and
    adds the standard one to another, and a shape failure discovered during
    the second half leaves the target with recording removed and nothing put
    back -- while the write that already landed cannot be un-landed. Checking
    first makes that particular failure impossible rather than merely rare.

    Pure: mutates nothing, so a caller may run it and then call
    add_registration on the same document.
    """
    env = data.get('env')
    if env is not None and not isinstance(env, dict):
        raise ValueError('"env" is not an object (found %s)' % type(env).__name__)

    hooks = data.get('hooks')
    if hooks is None:
        return
    if not isinstance(hooks, dict):
        raise ValueError('"hooks" is not an object (found %s)' % type(hooks).__name__)

    for event in REGISTRATION:
        if event not in hooks:
            continue
        entries = hooks[event]
        if not isinstance(entries, list):
            raise ValueError(
                '"hooks.%s" is not a list (found %s)' % (event, type(entries).__name__))
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            hooks_field = entry.get('hooks')
            if hooks_field is None:
                continue
            if not isinstance(hooks_field, list):
                raise ValueError(
                    '"hooks.%s" contains an entry with malformed "hooks" field (found %s)' % (
                        event, type(hooks_field).__name__))
            for hook in hooks_field:
                if not isinstance(hook, dict):
                    raise ValueError(
                        '"hooks.%s" contains an entry with non-object hook in "hooks" list' % event)
                command = hook.get('command')
                if command is not None and not isinstance(command, str):
                    raise ValueError(
                        '"hooks.%s" contains a hook whose "command" is not a string (found %s)' % (
                            event, type(command).__name__))


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
    # Same checks a caller may already have run through
    # validate_registration_shape(); re-running them costs a walk of three
    # event lists and keeps this function safe to call on its own.
    validate_registration_shape(data)

    changed = False
    replaced = False

    env = data.setdefault('env', {})
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

    for event, (matcher, script) in REGISTRATION.items():
        entries = hooks.setdefault(event, [])

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


# ---------------------------------------------------------------------------
# The legacy in-repo registration (spec 019 phase 4, maintainer ruling (s))
# ---------------------------------------------------------------------------
#
# WHAT IT IS. Before this feature existed, this repository registered the
# three observability hooks by hand in `.claude/settings.json` -- the SHARED
# settings layer, not the local one -- with commands pointing at
# `$CLAUDE_PROJECT_DIR/plugins/tcs-helper/scripts/observability/<script>.sh`
# rather than at the $HOME bundle. detect.sh classifies that shape LEGACY and
# tells the user "setup will migrate this". Until now nothing performed it:
# NAMESPACE above is the $HOME bundle path and entry_is_ours() gates on it, so
# --remove steps straight over entries that never mention it.
#
# THE SHAPE IS DEFINED IN TWO PLACES AND THE TWO MUST CHANGE TOGETHER.
# detect.sh:204 carries the same event -> script mapping under the same name,
# inside a python heredoc that a shell script wraps -- there is no module
# there to import, and inlining a python import into that heredoc would make
# detect.sh depend on this file's import path at classification time, which is
# exactly the coupling ADR-5 keeps out of detection. So the mapping is
# restated, with a pointer at both sites, the way CON-6 is handled between
# report.py and sources.py elsewhere in this spec.
#
# LEGACY REMOVAL IS NARROWER THAN remove_registration(). Ownership in
# settings.local.json is proven by the $HOME namespace alone (ADR-5) because
# this feature is the only thing that writes there. The shared settings file
# is not ours in that sense -- it is a file the repository's own maintainer
# edits -- so an entry qualifies as legacy only when it matches BOTH the event
# name we register AND the adapter script name we ship, and does NOT already
# point at the $HOME bundle. Anything else in that file, including a foreign
# entry under one of our event names, is left exactly where it is.
LEGACY_SCRIPTS = {
    'InstructionsLoaded': 'log_instructions.sh',
    'PreToolUse': 'log_skill.sh',
    'SubagentStart': 'log_agent.sh',
}


def hook_is_legacy(event, command):
    """One hook command, judged against the legacy shape for its event."""
    if not isinstance(command, str) or NAMESPACE in command:
        # Already pointing at the bundle: that is "ours", never "legacy".
        return False
    script = LEGACY_SCRIPTS.get(event)
    if not script:
        return False
    # The command string is shell-quoted (wrapped in literal double quotes so
    # the path survives a space), so it ends with `.sh"`, not `.sh` -- strip a
    # single trailing quote before comparing. Same treatment as detect.sh:283.
    return command.rstrip('"').endswith(script)


def _entry_is_legacy(event, entry):
    """Whether an entry sitting in hooks[event] is a legacy registration.

    Pairs the non-dict guard with the content check, for the same reason
    _entry_is_owned does: a settings file we do not own is free to hold a
    malformed, non-dict element in that list.
    """
    if not isinstance(entry, dict):
        return False
    hooks = entry.get('hooks', [])
    if not isinstance(hooks, list):
        return False
    return any(
        hook_is_legacy(event, hook.get('command', ''))
        for hook in hooks
        if isinstance(hook, dict)
    )


def remove_legacy_registration(data):
    """Prune the legacy in-repo registration from a shared settings document.

    Returns (changed, events) -- `events` is the sorted list of event names an
    entry was actually removed from, so the caller can report which rather
    than assert all three.

    Container deletion follows remove_registration() exactly: a container is
    deleted only when THIS call emptied it, never merely because it holds
    nothing of ours.

    The env switch is removed only when at least one legacy hook entry was
    found. remove_registration() deletes it unconditionally because
    settings.local.json is a layer this feature owns outright; the shared file
    is not, so a CLAUDE_OBSERVABILITY_ENABLED sitting there beside no legacy
    hooks belongs to whoever put it there.

    Like remove_registration(), this function's only effect is on `data` in
    memory -- it has no path to anything else on disk, which is what "removal
    never deletes existing records" rests on.
    """
    changed = False
    events = []

    hooks = data.get('hooks')
    if isinstance(hooks, dict):
        hooks_changed = False
        for event in list(hooks.keys()):
            if event not in LEGACY_SCRIPTS:
                continue
            entries = hooks[event]
            if not isinstance(entries, list):
                continue
            kept = [e for e in entries if not _entry_is_legacy(event, e)]
            if len(kept) == len(entries):
                continue
            hooks_changed = True
            changed = True
            events.append(event)
            if kept:
                hooks[event] = kept
            else:
                del hooks[event]
        if hooks_changed and not hooks:
            del data['hooks']

    if changed:
        env = data.get('env')
        if isinstance(env, dict):
            key, _value = ENV_SWITCH
            if key in env:
                del env[key]
                if not env:
                    del data['env']

    return changed, sorted(events)


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
        '--migrate-legacy',
        metavar='SHARED_SETTINGS',
        help=(
            'path to the target shared settings file (.claude/settings.json) '
            'holding a legacy in-repo registration. Removes it and installs '
            'the standard registration into --settings as ONE operation'))
    parser.add_argument(
        '--remove-legacy',
        metavar='SHARED_SETTINGS',
        help=(
            'with --remove: also take the legacy in-repo registration out of '
            'this shared settings file'))
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


def _strip_legacy(shared_path):
    """Take the legacy registration out of a shared settings file.

    Returns (status, events): status is 'removed', 'none' (no legacy shape
    there) or 'error' (already reported on stderr). The backup this write
    leaves behind is NOT discarded here -- the caller discards it only once
    the whole operation has succeeded, so a failure between the two halves of
    a migration still has a second copy of the file it changed first.
    """
    data, error = load_settings(shared_path)
    if error:
        sys.stderr.write('%s\n' % error)
        return 'error', []
    changed, events = remove_legacy_registration(data)
    if not changed:
        print('no legacy registration found in %s' % shared_path)
        return 'none', []
    write_settings(shared_path, data)
    print('removed legacy observability hooks (%s) from %s'
          % (', '.join(events), shared_path))
    return 'removed', events


def _nothing_written():
    sys.stdout.flush()
    sys.stderr.write('nothing was written.\n')


def _report_partial(shared_path, local_path):
    """The one failure Fix 1's ordering cannot remove, reported honestly.

    Once validate_registration_shape has passed, the only way the second half
    can still fail after the first half wrote is genuine I/O -- a full disk, a
    permission change, a path that stopped being a file. Rare, and real. The
    target is then legacy-removed and nothing-re-added, which means it is NOT
    recording, and the operator has to act. Saying "the originals are intact"
    here, as this used to, is the difference between a target someone fixes in
    a minute and a target that is silently off for the whole collection period.
    """
    # stdout is block-buffered when it is not a terminal, stderr is not, so
    # without this the "removed legacy hooks" line lands AFTER the report that
    # explains it -- exactly backwards for whoever is reading the failure.
    sys.stdout.flush()
    sys.stderr.write(
        'PARTIAL MIGRATION -- what was and was not written:\n'
        '  CHANGED:   %s (the legacy registration was removed)\n'
        '  BACKUP:    %s\n'
        '  UNCHANGED: %s (the standard registration was NOT added)\n'
        'This target is NOT recording. To put the legacy registration back:\n'
        '  cp -p %s %s\n'
        'Or fix the cause and re-run install, which re-adds the standard one.\n'
        % (shared_path, backup_path(shared_path), local_path,
           backup_path(shared_path), shared_path))


def _edit_under_lock(args):
    # The migration is cross-file: the legacy registration lives in the
    # target's SHARED settings, the standard one in its LOCAL settings, and
    # this CLI takes a single --settings. Rather than make the caller run two
    # invocations -- which is precisely the two-step the maintainer ruling
    # forbids, because the gap between them is a window where a target either
    # records twice or not at all -- the second path arrives as a flag and
    # both halves happen inside one run of this function, under one lock.
    #
    # ORDER, AND WHY IT IS THREE STEPS RATHER THAN TWO.
    #
    # Between the halves, the shared file is written and the local one is not.
    # So everything that can refuse the local half has to happen BEFORE the
    # shared file is touched -- load it, and validate it to the exact depth
    # add_registration requires. A spec-compliance review found what happens
    # otherwise: "env" as a non-object passed detection, the shared write
    # completed, add_registration then raised, and the target was left
    # legacy-removed and nothing-re-added while the command reported the
    # originals intact.
    #
    #   1. load and validate the LOCAL document   (can refuse; nothing written)
    #   2. remove the legacy from the SHARED file (the first write)
    #   3. add the standard to the LOCAL file     (the second write)
    #
    # Step 1 makes a shape failure at step 3 impossible. What survives is an
    # I/O failure at step 3, which _report_partial names rather than hides.
    #
    # The remove-then-add order of steps 2 and 3 is unchanged and deliberate:
    # the intermediate state is "not registered", which `status` reports
    # honestly and which records nothing, where the reverse order's
    # intermediate state records everything twice and looks like a healthy
    # target while doing it.
    data, error = load_settings(args.settings)
    if error:
        sys.stderr.write('%s\n' % error)
        _nothing_written()
        return 1

    if args.remove:
        if args.remove_legacy:
            # The shared file first here too, and for the same reason: those
            # are the entries that are actually firing on an un-migrated
            # target, so they are the ones whose removal has to land.
            # remove_registration raises nothing, so there is no shape check
            # to hoist above this one.
            if _strip_legacy(args.remove_legacy)[0] == 'error':
                _nothing_written()
                return 1
        changed = remove_registration(data)
        if not changed:
            print('nothing to remove: %s' % args.settings)
            discard_backup(args.settings)
            if args.remove_legacy:
                discard_backup(args.remove_legacy)
            return 0
        try:
            write_settings(args.settings, data)
        except OSError as exc:
            sys.stderr.write('failed to write %s: %s\n' % (args.settings, exc))
            if args.remove_legacy:
                _report_partial(args.remove_legacy, args.settings)
            else:
                _nothing_written()
            return 1
        discard_backup(args.settings)
        if args.remove_legacy:
            discard_backup(args.remove_legacy)
        print('removed observability hooks from %s' % args.settings)
        return 0

    # Step 1. Nothing has been written anywhere at this point, and nothing
    # will be if this refuses.
    try:
        validate_registration_shape(data)
    except ValueError as exc:
        sys.stderr.write('%s: %s\n' % (args.settings, exc))
        _nothing_written()
        return 1

    # Step 2.
    shared_written = False
    if args.migrate_legacy:
        status, _events = _strip_legacy(args.migrate_legacy)
        if status == 'error':
            _nothing_written()
            return 1
        shared_written = (status == 'removed')

    # Step 3.
    try:
        changed, status = add_registration(data)
    except ValueError as exc:
        # Unreachable after step 1 -- the same checks on the same unmutated
        # document. Kept so add_registration stays safe to call directly, and
        # routed through the same honest reporting if it ever fires.
        sys.stderr.write('%s: %s\n' % (args.settings, exc))
        if shared_written:
            _report_partial(args.migrate_legacy, args.settings)
        else:
            _nothing_written()
        return 1

    if not changed:
        # A target can be BOTH legacy and already locally registered -- that
        # is the double-recording state this migration exists to end, and
        # detect.sh classifies it LEGACY because it checks the shared file
        # first. The local half is then a no-op, and the migration still
        # succeeded: the shared backup goes with it.
        print('already configured: %s' % args.settings)
        if args.migrate_legacy:
            discard_backup(args.migrate_legacy)
        return 0

    try:
        write_settings(args.settings, data)
    except OSError as exc:
        sys.stderr.write('failed to write %s: %s\n' % (args.settings, exc))
        if shared_written:
            _report_partial(args.migrate_legacy, args.settings)
        else:
            _nothing_written()
        return 1

    if args.migrate_legacy:
        # Both halves landed. Only now is the shared file's backup redundant.
        discard_backup(args.migrate_legacy)
    if status == 'update':
        # 'update' also fires for an env-only correction (no hook entry
        # touched), so the message names the registration, not "hooks".
        print('updated observability registration in %s' % args.settings)
    else:
        print('registered observability hooks in %s' % args.settings)
    return 0


if __name__ == '__main__':
    sys.exit(main())
