#!/usr/bin/env python3
"""A cooperative lock file, so two setup runs against one target serialize.

`plugins/tcs-git-helpers/skills/git-setup/lib/lock.sh:45-118` ported to
Python, and it lives in its own module for the same reason that one does:
the lock is a self-contained mechanism its caller only starts and stops, and
the precedent keeps it beside the code that uses it rather than inside it.

The contract is one poll loop with two outcomes, not two designs. A lock
released inside the bounded wait is followed by a normal successful run; a
lock still held at the deadline makes acquire_lock() return False, and the
caller reports the contention and exits without writing.

Lock file format, unchanged from the precedent, one line:

    <pid>:<unix-timestamp>

Staleness has three forms and they are not symmetrical. A dead owner or a
timestamp past the TTL is abandoned immediately. Empty or unparseable content
is NOT -- creating the file is the acquisition and the pid line lands on the
next statement, so a live lock reads as empty for a moment, and reclaiming
that would put two runs inside one settings file. Unreadable content is
therefore abandoned only once the file has sat unwritten past LOCK_GRACE.

A stale lock is removed rather than acquired in place, so the next poll
race-creates cleanly and two contenders cannot both win.
"""
import os
import time


# Lock knobs, injectable so a test never has to sit through the real wait.
LOCK_TIMEOUT_ENV = 'TCS_OBSERVABILITY_LOCK_TIMEOUT'
LOCK_TTL_ENV = 'TCS_OBSERVABILITY_LOCK_TTL'
DEFAULT_LOCK_TIMEOUT = 10.0   # lock.sh's TCS_LOCK_TIMEOUT default
DEFAULT_LOCK_TTL = 300        # lock.sh's 5-minute stale reclaim
LOCK_POLL_INTERVAL = 0.05

# How long an empty or unparseable lock file must sit before it counts as
# abandoned rather than half-written. Sized between the two things it has to
# separate: the create-to-write window is microseconds, and the TTL that
# governs a properly written lock is 300s. Two seconds is six orders of
# magnitude clear of the first and two orders short of the second, so a lock
# genuinely left as garbage by a crash still clears well inside the default
# 10s wait.
#
# WHAT THIS DOES NOT COVER, and the road not taken. The grace period narrows
# the create-to-write window; it does not close it. An owner whose process
# stalled for longer than LOCK_GRACE between os.open() and the write below
# would still have its lock reclaimed. The airtight version is the technique
# registration.py already uses for the settings file: write `pid:epoch` to a
# temp name and rename it into place, so the lock is never observable empty
# and no grace period is needed at all.
#
# That was considered and not built, deliberately. Reaching the residual
# window needs a multi-second I/O stall between two adjacent statements
# writing about twenty bytes -- which is the same risk shape the 300s TTL
# above already accepts when it reclaims from an owner that is alive but
# frozen. Closing one and not the other buys nothing. If this file ever grows
# a reason to be airtight, the rename is the change to make, and LOCK_GRACE
# and its two fresh-lock tests come out with it.
LOCK_GRACE = 2.0


def _env_number(name, default):
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _lock_owner(text):
    """(pid, epoch) from lock.sh's `<pid>:<timestamp>` line, or (None, None)."""
    pid_text, _, stamp_text = text.strip().partition(':')
    if not pid_text.isdigit() or not stamp_text.isdigit():
        return None, None
    return int(pid_text), int(stamp_text)


def _pid_is_alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True   # running, just owned by another user
    except OSError:
        return True   # unknown: treat as alive, never force-remove on a guess
    return True


def _read_lock(path):
    try:
        with open(path, 'r', encoding='utf-8') as handle:
            return handle.read()
    except OSError:
        return None


def _age(path):
    """Seconds since the lock file was last written, or 0 if it is gone.

    A vanished lock reads as brand new on purpose: there is nothing left to
    reclaim, and the next poll will race-create cleanly.
    """
    try:
        return time.time() - os.stat(path).st_mtime
    except OSError:
        return 0.0


def _try_acquire_once(path, ttl):
    """One attempt. Creating the file IS the acquisition.

    O_CREAT|O_EXCL is the only Python equivalent of the precedent's `set -C`:
    an os.path.exists() test followed by a write is a race, and a race here
    means two runs editing one settings file at once.
    """
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        pass
    except OSError:
        return False
    else:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            handle.write('%d:%d\n' % (os.getpid(), int(time.time())))
        return True

    text = _read_lock(path)
    if text is None:
        return False
    pid, stamp = _lock_owner(text)
    if pid is None:
        # Empty or unparseable -- and NOT necessarily abandoned. Creating the
        # file is the acquisition, but the owner's pid line lands on the very
        # next statement, so between those two moments a live lock reads as
        # empty. Declaring that stale unlinks a lock out from under its owner;
        # the owner then holds a file that no longer exists, this process
        # race-creates a fresh one, and both runs walk into the same settings
        # file -- precisely what SDD-AC-11 forbids. So unreadable content is
        # stale only once the file has sat unwritten for longer than any
        # create-to-write window could plausibly last.
        stale = _age(path) > LOCK_GRACE
    else:
        stale = (
            int(time.time()) - stamp > ttl          # older than the TTL
            or not _pid_is_alive(pid)               # owner is gone
        )
    if stale:
        # Remove it and let the NEXT iteration race-create cleanly, exactly as
        # lock.sh:70-74 does. Acquiring in place here would let two contenders
        # that both saw the same stale lock both succeed.
        try:
            os.unlink(path)
        except OSError:
            pass
    return False


def acquire_lock(path, timeout=None, ttl=None):
    """Poll until the lock is ours or the bounded wait expires.

    The two outcomes a caller can see are the two outcomes of this one loop
    (lock.sh:78-99), not two designs: a lock released inside the window is
    followed by a normal successful run, and a lock still held at the deadline
    makes the caller report the contention and exit.
    """
    if timeout is None:
        timeout = _env_number(LOCK_TIMEOUT_ENV, DEFAULT_LOCK_TIMEOUT)
    if ttl is None:
        ttl = _env_number(LOCK_TTL_ENV, DEFAULT_LOCK_TTL)
    deadline = time.time() + timeout
    attempts = 0
    while True:
        if _try_acquire_once(path, ttl):
            return True
        attempts += 1
        # At least two attempts: reclaiming a stale lock takes one pass to
        # remove it and one to create it, so a very short timeout must not
        # turn a reclaimable lock into a spurious contention report.
        if attempts >= 2 and time.time() >= deadline:
            return False
        time.sleep(LOCK_POLL_INTERVAL)


def release_lock(path):
    """Idempotent. Never removes a lock a live foreign process holds.

    The dead-owner branch is lock.sh:108-118, and it is defensive here rather
    than load-bearing: git-setup acquires and releases in separate Bash calls,
    so its `pid == $$` check never matches, while this module does both in one
    process. What the branch still covers is a lock left behind by an earlier
    run that crashed.
    """
    text = _read_lock(path)
    if text is None:
        return
    pid, _stamp = _lock_owner(text)
    if pid is None or pid == os.getpid() or not _pid_is_alive(pid):
        try:
            os.unlink(path)
        except OSError:
            pass
