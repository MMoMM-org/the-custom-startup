"""State directory, plan records and the apply lock (spec 025, K13, ADR-2).

Layout, all owner-only and never inside the audited repository:

    ${XDG_STATE_HOME:-$HOME/.local/state}/tcs-helper/security-baseline/   0700
        plans/<plan_id>.json    0600, one approval per reviewed plan
        backups/                0700, filled by writer.py (K14)
        lock                    0600, advisory flock held by `apply`

A plan record makes an approval single-use and short-lived: `load_plan`
answers `ok` only for a record that exists, is younger than 15 minutes and
was not consumed. The record's content is not trusted beyond that -- `apply`
recomputes the plan from live files and compares identities.

Nothing here runs at import, and `audit` never calls this module. Every
function takes the state directory (and the clock, where time matters) as an
argument; only `state_dir` reads an environment mapping, and it writes nothing.

A consumed record stays in place, marked, until it expires, so that a second
`apply` is told `consumed` rather than `unknown`. Expired records are removed
by the next `save_plan` or `load_plan`.
"""

from __future__ import annotations

import contextlib
import dataclasses
import datetime
import errno
import os
import re
import stat
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, NamedTuple, Optional

import jsonio

PLAN_TTL_SECONDS = 15 * 60

STATUS_OK = "ok"
STATUS_UNKNOWN = "unknown"
STATUS_EXPIRED = "expired"
STATUS_CONSUMED = "consumed"

_SUBDIR = ("tcs-helper", "security-baseline")
_PLAN_ID_RE = re.compile(r"[0-9a-f]{64}")
_PLAN_FILE_RE = re.compile(r"[0-9a-f]{64}\.json(\.tmp)?")
_RECORD_SUFFIX = ".json"
_TEMP_SUFFIX = ".json.tmp"
_TIMESTAMP = "%Y-%m-%dT%H:%M:%SZ"
_RECORD_FORMAT = jsonio.Format(indent=2, newline="\n", trailing_newline=True)
_DIR_MODE = 0o700
_FILE_MODE = 0o600
_UTC = datetime.timezone.utc


class StateError(Exception):
    """Setup cannot use its state directory: the CLI exits 3 and writes
    nothing. `reason` is one of a fixed vocabulary."""

    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason


class LockBusy(StateError):
    """Another `apply` holds the lock."""


@dataclasses.dataclass(frozen=True)
class PlanRecord:
    """The approval for one reviewed plan. `selection` and `moves` are the
    inputs `apply` replays to recompute the plan: lists of change ids by
    name, and change id -> target scope."""

    plan_id: str
    created_at: str
    expires_at: str
    selection: Mapping[str, Any]
    moves: Mapping[str, str]
    profile: str
    profile_source: str
    sandbox_confirmed: bool
    consumed: bool = False

    def as_dict(self) -> dict:
        return dataclasses.asdict(self)


class Loaded(NamedTuple):
    """`record` is None for status `unknown`."""

    status: str
    record: Optional[PlanRecord]


_FIELDS = tuple(field.name for field in dataclasses.fields(PlanRecord))


# =============================================================================
# Where state lives
# =============================================================================


def state_dir(environ: Mapping[str, str], home, forbidden: Iterable = ()) -> Path:
    """The state directory for this user. Writes nothing.

    `forbidden` names the directories state must not live in: the audited
    repository root and the project directory. A relative `XDG_STATE_HOME`
    is ignored, as the XDG specification requires.
    """
    home = Path(home)
    if not home.is_absolute():
        raise StateError("home-not-absolute", f"home directory is not an absolute path: {home}")
    base = home / ".local" / "state"
    configured = environ.get("XDG_STATE_HOME") or ""
    if configured and Path(configured).is_absolute():
        base = Path(configured)
    root = base.joinpath(*_SUBDIR)
    resolved = Path(os.path.realpath(root))
    for directory in forbidden:
        inside = Path(os.path.realpath(directory))
        if resolved == inside or inside in resolved.parents:
            raise StateError(
                "inside-repository",
                f"state directory {root} would be inside the audited repository {directory}; "
                "set XDG_STATE_HOME to an absolute path outside it",
            )
    return root


def plans_dir(root) -> Path:
    return Path(root) / "plans"


def backups_dir(root) -> Path:
    """Where writer.py keeps backups; created 0700 by `ensure`."""
    return Path(root) / "backups"


def lock_path(root) -> Path:
    return Path(root) / "lock"


def ensure(root) -> Path:
    """Create the state directory with `plans/` and `backups/`, each 0700.

    A directory that exists is tightened to 0700 when it is ours, and
    refused when it is a symlink, not a directory or owned by another user.
    """
    root = Path(root)
    os.makedirs(root.parent, mode=_DIR_MODE, exist_ok=True)
    for directory in (root, plans_dir(root), backups_dir(root)):
        try:
            os.mkdir(directory, _DIR_MODE)
        except FileExistsError:
            pass
        _check_dir(directory)
    return root


def _check_dir(directory: Path) -> bool:
    """False when absent; raise unless it is a directory of ours."""
    try:
        info = os.lstat(directory)
    except FileNotFoundError:
        return False
    if not stat.S_ISDIR(info.st_mode):
        raise StateError("state-dir-unsafe", f"{directory} is not a directory (a symlink is refused)")
    if info.st_uid != os.geteuid():
        raise StateError("state-dir-unsafe", f"{directory} is owned by another user")
    if stat.S_IMODE(info.st_mode) != _DIR_MODE:
        os.chmod(directory, _DIR_MODE)
    return True


def _existing_plans_dir(root) -> Optional[Path]:
    """The plans directory when it is there and safe to read; creates nothing."""
    if not _check_dir(Path(root)):
        return None
    plans = plans_dir(root)
    return plans if _check_dir(plans) else None


# =============================================================================
# Plan records
# =============================================================================


def utc_now() -> datetime.datetime:
    """The clock the CLI passes in; tests pass their own."""
    return datetime.datetime.now(_UTC)


def new_record(
    plan_id: str,
    now: datetime.datetime,
    *,
    selection: Mapping[str, Any],
    moves: Mapping[str, str],
    profile: str,
    profile_source: str,
    sandbox_confirmed: bool,
) -> PlanRecord:
    """A fresh, unconsumed record created at `now`."""
    _require_plan_id(plan_id)
    created = _require_aware(now).astimezone(_UTC).replace(microsecond=0)
    expires = created + datetime.timedelta(seconds=PLAN_TTL_SECONDS)
    return PlanRecord(
        plan_id=plan_id,
        created_at=created.strftime(_TIMESTAMP),
        expires_at=expires.strftime(_TIMESTAMP),
        selection=selection,
        moves=moves,
        profile=profile,
        profile_source=profile_source,
        sandbox_confirmed=sandbox_confirmed,
    )


def save_plan(root, record: PlanRecord) -> Path:
    """Write the record (0600, exclusive, no symlink followed), then remove
    expired records. Planning the same changes again replaces the earlier
    record for that id, which renews the approval."""
    _require_plan_id(record.plan_id)
    if not _is_well_formed(record):
        raise ValueError("record would not load back: check field types (lists, not tuples)")
    created = _parse_timestamp(record.created_at)
    ensure(root)
    path = plans_dir(root) / (record.plan_id + _RECORD_SUFFIX)
    data = jsonio.dumps(record.as_dict(), _RECORD_FORMAT)
    try:
        _write_exclusive(path, data)
    except FileExistsError:
        _remove_own_regular_file(path)
        try:
            _write_exclusive(path, data)
        except FileExistsError:
            raise _record_unsafe(path) from None
    sweep(root, created)
    return path


def load_plan(root, plan_id, now: datetime.datetime) -> Loaded:
    """Status of the approval `plan_id` at `now`: `unknown`, `expired`,
    `consumed` or `ok`. Removes expired records afterwards, so an expired
    plan is `unknown` from the next call on. Creates nothing."""
    _require_aware(now)
    if not _is_plan_id(plan_id):
        return Loaded(STATUS_UNKNOWN, None)
    plans = _existing_plans_dir(root)
    if plans is None:
        return Loaded(STATUS_UNKNOWN, None)
    record = _read_record(plans / (plan_id + _RECORD_SUFFIX))
    if record is None:
        status = STATUS_UNKNOWN
    elif record.consumed:
        status = STATUS_CONSUMED
    elif _is_expired(record, now):
        status = STATUS_EXPIRED
    else:
        status = STATUS_OK
    sweep(root, now)
    return Loaded(status, record)


def consume(root, plan_id) -> bool:
    """Mark the approval used. True when the record is consumed afterwards
    (now or already), False when there is no such record."""
    if not _is_plan_id(plan_id):
        return False
    plans = _existing_plans_dir(root)
    if plans is None:
        return False
    path = plans / (plan_id + _RECORD_SUFFIX)
    record = _read_record(path)
    if record is None:
        return False
    if record.consumed:
        return True
    marked = dataclasses.replace(record, consumed=True)
    temp = plans / (plan_id + _TEMP_SUFFIX)
    with contextlib.suppress(FileNotFoundError):
        os.unlink(temp)  # left by an interrupted run; unlink never follows a link
    _write_exclusive(temp, jsonio.dumps(marked.as_dict(), _RECORD_FORMAT))
    try:
        os.replace(temp, path)
    except OSError:
        with contextlib.suppress(OSError):
            os.unlink(temp)
        raise
    return True


def sweep(root, now: datetime.datetime) -> int:
    """Remove expired plan records; return how many files went.

    A file under a record name that cannot be read as a record, and a
    leftover temp file, are removed once their modification time is older
    than the approval window -- never sooner, because a record another
    process is writing right now looks the same. Other files are left alone.
    """
    _require_aware(now)
    plans = _existing_plans_dir(root)
    if plans is None:
        return 0
    removed = 0
    for name in sorted(os.listdir(plans)):
        if not _PLAN_FILE_RE.fullmatch(name):
            continue
        path = plans / name
        record = None if name.endswith(_TEMP_SUFFIX) else _read_record(path)
        if record is not None:
            stale = _is_expired(record, now)
        else:
            stale = _is_older_than_window(path, now)
        if stale:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(path)
                removed += 1
    return removed


def _is_plan_id(plan_id) -> bool:
    return isinstance(plan_id, str) and _PLAN_ID_RE.fullmatch(plan_id) is not None


def _require_plan_id(plan_id) -> None:
    if not _is_plan_id(plan_id):
        raise ValueError("plan_id must be 64 lowercase hex characters")


def _require_aware(now: datetime.datetime) -> datetime.datetime:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("the clock must carry a time zone")
    return now


def _parse_timestamp(text) -> Optional[datetime.datetime]:
    if not isinstance(text, str):
        return None
    try:
        parsed = datetime.datetime.strptime(text, _TIMESTAMP).replace(tzinfo=_UTC)
    except ValueError:
        return None
    return parsed if parsed.strftime(_TIMESTAMP) == text else None


def _is_expired(record: PlanRecord, now: datetime.datetime) -> bool:
    """Outside the window that starts at `created_at`. The stored
    `expires_at` can shorten the window but never extend it."""
    created = _parse_timestamp(record.created_at)
    expires = _parse_timestamp(record.expires_at)
    limit = min(expires, created + datetime.timedelta(seconds=PLAN_TTL_SECONDS))
    return not created <= now < limit


def _is_older_than_window(path: Path, now: datetime.datetime) -> bool:
    try:
        modified = os.lstat(path).st_mtime
    except FileNotFoundError:
        return False
    return modified + PLAN_TTL_SECONDS <= now.timestamp()


def _read_record(path: Path) -> Optional[PlanRecord]:
    """The record at `path`, or None when it is absent or not exactly a
    record: a file that needs guessing is not an approval."""
    status, data, _fmt, _reason = jsonio.read_json(str(path), follow_symlink=False)
    if status != "ok" or tuple(sorted(data)) != tuple(sorted(_FIELDS)):
        return None
    record = PlanRecord(**data)
    if not _is_well_formed(record) or record.plan_id + _RECORD_SUFFIX != path.name:
        return None
    return record


def _is_well_formed(record: PlanRecord) -> bool:
    return (
        _is_plan_id(record.plan_id)
        and _parse_timestamp(record.created_at) is not None
        and _parse_timestamp(record.expires_at) is not None
        and isinstance(record.selection, dict)
        and all(_is_string_list(ids) for ids in record.selection.values())
        and isinstance(record.moves, dict)
        and all(isinstance(scope, str) for scope in record.moves.values())
        and isinstance(record.profile, str)
        and isinstance(record.profile_source, str)
        and isinstance(record.sandbox_confirmed, bool)
        and isinstance(record.consumed, bool)
    )


def _is_string_list(value) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _record_unsafe(path: Path) -> StateError:
    return StateError("record-unsafe", f"{path} exists and is not a plan record of this user")


def _remove_own_regular_file(path: Path) -> None:
    """Drop an earlier record for the same plan; refuse anything else."""
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid():
        raise _record_unsafe(path)
    with contextlib.suppress(FileNotFoundError):
        os.unlink(path)


def _write_exclusive(path: Path, data: bytes) -> None:
    """Create `path` 0600 and write `data`; FileExistsError when anything,
    a symlink included, is already there."""
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0)
    )
    try:
        fd = os.open(path, flags, _FILE_MODE)
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            raise FileExistsError(errno.EEXIST, "symlink", str(path)) from None
        raise
    try:
        try:
            os.fchmod(fd, _FILE_MODE)
            view = memoryview(data)
            while view:
                view = view[os.write(fd, view):]
            os.fsync(fd)
        finally:
            os.close(fd)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(path)
        raise


# =============================================================================
# Lock
# =============================================================================


@contextlib.contextmanager
def lock(root) -> Iterator[None]:
    """Hold the advisory apply lock for the body of the `with` block.

    Acquisition does not wait: when another `apply` holds the lock this
    raises `LockBusy`. The lock is released when the block ends, also on an
    exception, and by the kernel when the process dies.
    """
    import fcntl  # POSIX only; setup is refused on other platforms before this

    ensure(root)
    path = lock_path(root)
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    try:
        fd = os.open(path, flags, _FILE_MODE)
    except OSError as exc:
        if exc.errno in (errno.ELOOP, errno.EMLINK):
            raise StateError("lock-unsafe", f"{path} is a symlink") from None
        raise
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid():
            raise StateError("lock-unsafe", f"{path} is not a lock file of this user")
        os.fchmod(fd, _FILE_MODE)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            if exc.errno in (errno.EWOULDBLOCK, errno.EACCES):
                raise LockBusy(
                    "apply-running",
                    "another apply is running (the state lock is held); wait for it, then review again",
                ) from None
            raise
        try:
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)
