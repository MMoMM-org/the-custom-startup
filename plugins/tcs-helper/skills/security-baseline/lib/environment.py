"""Environment detection of the security-baseline skill (K3, ADR-7).

Answers four questions about the machine the audit runs on:

- **platform** — ``darwin``, ``linux`` or ``other``
- **profile** — ``macos-host``, ``linux-native`` or ``container``, with the
  evidence it was detected from. ``container`` comes from filesystem markers
  (``/.dockerenv``, ``/run/.containerenv``, a container cgroup line). The
  ``CONTAINERIZED`` variable counts only when no settings layer sets it in
  ``env``: a cloned repository's settings reach every Bash subprocess and
  could otherwise select the profile that accepts bypass mode.
- **ancestor flags** — whether one of up to eight ancestor processes carries
  ``--settings``, ``--dangerously-skip-permissions`` or ``--permission-mode``.
  Presence only: argument values are never stored, returned or logged, so
  ``--permission-mode`` leaves ``bypass_active`` at ``unknown``.
- **Claude Code version** — ``claude --version`` of a binary found on an
  absolute PATH entry outside the project that others cannot write to.

Every outside dependency is a parameter of ``detect`` (marker root, process
reader, binary lookup, subprocess runner), so tests never touch the real
machine. Evidence strings come from a fixed vocabulary and never carry file
content. Nothing is read at import.
"""

from __future__ import annotations

import os
import pathlib
import re
import stat
import subprocess
from dataclasses import dataclass
from typing import Any, Callable, Collection, Mapping, Optional, Sequence

PROFILES = ("macos-host", "linux-native", "container")
UNKNOWN_PROFILE = "unknown"
MAX_ANCESTORS = 8
VERSION_TIMEOUT_SECONDS = 5
PS_TIMEOUT_SECONDS = 5
CONTAINER_ENV_KEY = "CONTAINERIZED"

SETTINGS_FLAG = "--settings"
SKIP_PERMISSIONS_FLAG = "--dangerously-skip-permissions"
PERMISSION_MODE_FLAG = "--permission-mode"
_WATCHED_FLAGS = (SETTINGS_FLAG, SKIP_PERMISSIONS_FLAG, PERMISSION_MODE_FLAG)

_MARKER_FILES = (".dockerenv", "run/.containerenv")
_CGROUP_FILES = ("proc/1/cgroup", "proc/self/cgroup")
_CGROUP_CONTAINER_RE = re.compile(r"(?:^|/)(?:docker|libpod|lxc|crio)(?:[-/_]|$)|kubepods")
_NEGATIVE_ENV_VALUES = ("", "0", "false", "no", "off")
_SCOPE_NAME_RE = re.compile(r"[a-z][a-z-]{0,31}")
_VERSION_RE = re.compile(r"([0-9]{1,9})\.([0-9]{1,9})\.([0-9]{1,9})(?:\s.*)?", re.DOTALL)
_PS_BINARY = "/bin/ps"
_SUBPROCESS_PATH = "/usr/bin:/bin"
_READ_LIMIT_BYTES = 256 * 1024


@dataclass(frozen=True, order=True)
class Version:
    """A ``major.minor.patch`` version, ordered numerically."""

    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, text: Any) -> Optional["Version"]:
        """``2.1.332`` or ``2.1.332 (Claude Code)`` → Version; anything else → None."""
        if not isinstance(text, str):
            return None
        match = _VERSION_RE.fullmatch(text.strip())
        if match is None:
            return None
        return cls(*(int(part) for part in match.groups()))

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


@dataclass(frozen=True)
class Roots:
    """Where detection looks: ``filesystem`` holds the container markers and
    ``proc``; a PATH entry inside ``project`` is never trusted."""

    filesystem: pathlib.Path = pathlib.Path("/")
    project: Optional[pathlib.Path] = None


@dataclass(frozen=True)
class ProcessInfo:
    """One ancestor as a process reader returns it. ``args`` is inspected for
    flag presence and then dropped."""

    parent_pid: int
    args: tuple[str, ...]


@dataclass(frozen=True)
class Environment:
    platform: str  # darwin | linux | other
    profile: str  # one of PROFILES, or "unknown" on platform other
    profile_source: str  # detected | explicit
    profile_evidence: tuple[str, ...]
    bypass_active: str  # yes | no | unknown
    settings_flag: str  # present | absent | unknown
    permission_mode_flag: str  # present | absent | unknown
    claude_version: Optional[Version]

    def as_dict(self) -> dict[str, Any]:
        """The ``environment`` object of the audit report."""
        return {
            "platform": self.platform,
            "profile": self.profile,
            "profile_source": self.profile_source,
            "profile_evidence": list(self.profile_evidence),
            "bypass_active": self.bypass_active,
            "settings_flag": self.settings_flag,
            "permission_mode_flag": self.permission_mode_flag,
            "claude_version": None if self.claude_version is None else str(self.claude_version),
        }


ProcReader = Callable[[int], Optional[ProcessInfo]]
Which = Callable[[str], Optional[str]]
Runner = Callable[[Sequence[str], float], "tuple[int, str]"]


def detect(
    platform: str,
    roots: Roots,
    env: Mapping[str, str],
    layer_env_keys: Any = (),
    explicit_profile: Optional[str] = None,
    proc_reader: Optional[ProcReader] = None,
    which: Optional[Which] = None,
    *,
    runner: Optional[Runner] = None,
    start_pid: Optional[int] = None,
) -> Environment:
    """Describe the machine.

    ``platform`` is ``sys.platform``. ``layer_env_keys`` names the variables
    that readable settings layers set in ``env`` — a mapping of name to the
    scopes setting it, or a plain collection of names. ``proc_reader``,
    ``which`` and ``runner`` default to the real ``/proc`` or ``ps``, the PATH
    in ``env`` and ``subprocess``; ``start_pid`` defaults to the parent of
    this process, the first ancestor.
    """
    if explicit_profile is not None and explicit_profile not in PROFILES:
        raise ValueError("unknown profile; expected one of: " + ", ".join(PROFILES))
    runner = runner or run_subprocess
    name = _platform_name(platform)

    if explicit_profile is not None:
        profile, source, evidence = explicit_profile, "explicit", ("explicit:--profile",)
    else:
        source = "detected"
        profile, evidence = _detect_profile(name, roots, env, layer_env_keys)

    if proc_reader is None:
        proc_reader = _default_proc_reader(name, roots, runner)
    found, complete = _walk_ancestors(proc_reader, os.getppid() if start_pid is None else start_pid)

    if which is None:
        which = path_which(env.get("PATH"), roots.project)

    return Environment(
        platform=name,
        profile=profile,
        profile_source=source,
        profile_evidence=evidence,
        bypass_active=_bypass_state(found, complete),
        settings_flag=_presence(SETTINGS_FLAG, found, complete),
        permission_mode_flag=_presence(PERMISSION_MODE_FLAG, found, complete),
        claude_version=_claude_version(which, runner),
    )


# --- profile ----------------------------------------------------------------


def _platform_name(platform: str) -> str:
    lowered = platform.lower() if isinstance(platform, str) else ""
    if lowered == "darwin":
        return "darwin"
    if lowered.startswith("linux"):
        return "linux"
    return "other"


def _detect_profile(
    platform: str, roots: Roots, env: Mapping[str, str], layer_env_keys: Any
) -> tuple[str, tuple[str, ...]]:
    if platform == "darwin":
        return "macos-host", ("platform:darwin",)
    if platform != "linux":
        return UNKNOWN_PROFILE, ("platform:other",)

    markers = _container_markers(roots.filesystem)
    ignored_note = None
    if CONTAINER_ENV_KEY in env:
        if _is_set_by_a_layer(layer_env_keys):
            ignored_note = _ignored_note(layer_env_keys)
        elif env[CONTAINER_ENV_KEY].strip().lower() not in _NEGATIVE_ENV_VALUES:
            markers.append("env:" + CONTAINER_ENV_KEY)

    profile = "container" if markers else "linux-native"
    evidence = markers or ["platform:linux", "no container marker"]
    if ignored_note is not None:
        evidence.append(ignored_note)
    return profile, tuple(evidence)


def _container_markers(filesystem: pathlib.Path) -> list[str]:
    markers = [
        "marker:/" + relative
        for relative in _MARKER_FILES
        if os.path.lexists(os.path.join(filesystem, relative))
    ]
    for relative in _CGROUP_FILES:
        if _has_container_cgroup(os.path.join(filesystem, relative)):
            markers.append("cgroup:/" + relative)
            break
    return markers


def _has_container_cgroup(path: str) -> bool:
    content = _read_limited(path)
    if content is None:
        return False
    for line in content.decode("utf-8", "replace").splitlines():
        # hierarchy-ID:controller-list:cgroup-path
        cgroup_path = line.split(":", 2)[-1]
        if _CGROUP_CONTAINER_RE.search(cgroup_path):
            return True
    return False


def _is_set_by_a_layer(layer_env_keys: Any) -> bool:
    return CONTAINER_ENV_KEY in layer_env_keys


def _ignored_note(layer_env_keys: Any) -> str:
    """Name the scopes when they are plain scope names; never echo other text."""
    prefix = f"env:{CONTAINER_ENV_KEY} ignored: set by "
    scopes: Any = ()
    if isinstance(layer_env_keys, Mapping):
        scopes = layer_env_keys[CONTAINER_ENV_KEY]
        if isinstance(scopes, str):
            scopes = (scopes,)
    try:
        names = list(scopes)
    except TypeError:
        names = []
    if names and all(isinstance(n, str) and _SCOPE_NAME_RE.fullmatch(n) for n in names):
        return prefix + ", ".join(names) + " settings"
    return prefix + "a settings layer"


# --- ancestor flags ---------------------------------------------------------


def _walk_ancestors(reader: Optional[ProcReader], start_pid: int) -> tuple[frozenset[str], bool]:
    """Flags seen in up to ``MAX_ANCESTORS`` ancestors, and whether the walk
    was complete (reached the root of the process tree or the limit) rather
    than cut short by an unreadable process."""
    found: set[str] = set()
    if reader is None or start_pid <= 0:
        return frozenset(found), False
    pid = start_pid
    for _ in range(MAX_ANCESTORS):
        try:
            info = reader(pid)
        except (OSError, ValueError, subprocess.SubprocessError):
            info = None
        if info is None:
            return frozenset(found), False
        found.update(_flags_in(info.args))
        if info.parent_pid <= 0 or info.parent_pid == pid:
            break
        pid = info.parent_pid
    return frozenset(found), True


def _flags_in(args: Sequence[str]) -> set[str]:
    return {
        flag
        for flag in _WATCHED_FLAGS
        for arg in args
        if arg == flag or arg.startswith(flag + "=")
    }


def _presence(flag: str, found: Collection[str], complete: bool) -> str:
    if flag in found:
        return "present"
    return "absent" if complete else "unknown"


def _bypass_state(found: Collection[str], complete: bool) -> str:
    if SKIP_PERMISSIONS_FLAG in found:
        return "yes"
    if PERMISSION_MODE_FLAG in found:
        return "unknown"  # the mode is the flag's value, which is never read
    return "no" if complete else "unknown"


def _default_proc_reader(platform: str, roots: Roots, runner: Runner) -> Optional[ProcReader]:
    if platform == "linux":
        return procfs_reader(roots.filesystem)
    if platform == "darwin":
        return ps_reader(runner)
    return None


def procfs_reader(filesystem: Any = "/") -> ProcReader:
    """Reader over ``<filesystem>/proc/<pid>/{stat,cmdline}`` (Linux)."""

    def read(pid: int) -> Optional[ProcessInfo]:
        directory = os.path.join(filesystem, "proc", str(int(pid)))
        status = _read_limited(os.path.join(directory, "stat"))
        cmdline = _read_limited(os.path.join(directory, "cmdline"))
        if status is None or cmdline is None:
            return None
        # "pid (comm) state ppid ..." — comm may itself contain ") ".
        fields = status.decode("utf-8", "replace").rpartition(")")[2].split()
        if len(fields) < 2 or not fields[1].isdigit():
            return None
        args = tuple(part.decode("utf-8", "replace") for part in cmdline.split(b"\0") if part)
        return ProcessInfo(parent_pid=int(fields[1]), args=args)

    return read


def ps_reader(runner: Optional[Runner] = None) -> ProcReader:
    """Reader over ``ps -o ppid= -p <pid>`` and ``ps -o args= -p <pid>`` (macOS).

    ``ps`` prints the arguments as one line, so they are split on whitespace;
    that can only add a presence, never hide one."""
    run = runner or run_subprocess

    def column(name: str, pid: int) -> Optional[str]:
        argv = (_PS_BINARY, "-o", name + "=", "-p", str(int(pid)))
        try:
            code, output = run(argv, PS_TIMEOUT_SECONDS)
        except (OSError, subprocess.SubprocessError):
            return None
        return output if code == 0 else None

    def read(pid: int) -> Optional[ProcessInfo]:
        parent = column("ppid", pid)
        if parent is None or not parent.strip().isdigit():
            return None
        args = column("args", pid)
        if args is None:
            return None
        return ProcessInfo(parent_pid=int(parent.strip()), args=tuple(args.split()))

    return read


# --- Claude Code version ----------------------------------------------------


def path_which(path_value: Optional[str], project: Any = None) -> Which:
    """Lookup over the entries of ``path_value`` that can be trusted.

    Skipped: relative and empty entries (they follow the working directory),
    entries inside ``project`` (a cloned repository can ship a ``claude``),
    world-writable entries, and a binary that is world-writable or resolves
    into the project."""
    entries = path_value.split(os.pathsep) if isinstance(path_value, str) else []
    project_real = None if project is None else os.path.realpath(project)

    def which(name: str) -> Optional[str]:
        if not name or os.path.basename(name) != name:
            return None
        for entry in entries:
            if not os.path.isabs(entry):
                continue
            candidate = os.path.join(entry, name)
            if _is_trusted_binary(entry, candidate, project_real):
                return candidate
        return None

    return which


def _is_trusted_binary(entry: str, candidate: str, project_real: Optional[str]) -> bool:
    candidate_real = os.path.realpath(candidate)
    if project_real is not None and (
        _is_within(os.path.realpath(entry), project_real)
        or _is_within(candidate_real, project_real)
    ):
        return False
    try:
        entry_mode = os.stat(entry).st_mode
        binary_mode = os.stat(candidate).st_mode
        holder_mode = os.stat(os.path.dirname(candidate_real)).st_mode
    except OSError:
        return False
    if any(mode & stat.S_IWOTH for mode in (entry_mode, binary_mode, holder_mode)):
        return False
    return stat.S_ISREG(binary_mode) and os.access(candidate, os.X_OK)


def _is_within(path: str, directory: str) -> bool:
    return path == directory or path.startswith(directory.rstrip(os.sep) + os.sep)


def _claude_version(which: Which, runner: Runner) -> Optional[Version]:
    binary = which("claude")
    if not isinstance(binary, str) or not os.path.isabs(binary):
        return None
    try:
        code, output = runner((binary, "--version"), VERSION_TIMEOUT_SECONDS)
    except (OSError, subprocess.SubprocessError):
        return None
    return Version.parse(output) if code == 0 else None


# --- outside world ----------------------------------------------------------


def run_subprocess(argv: Sequence[str], timeout: float) -> tuple[int, str]:
    """Run ``argv`` without a shell and with a minimal environment; return
    exit code and stdout. The binary's own directory is on PATH so that an
    interpreter installed beside it is found."""
    completed = subprocess.run(  # noqa: S603 - fixed argv, shell=False
        list(argv),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        env={"PATH": os.path.dirname(argv[0]) + os.pathsep + _SUBPROCESS_PATH, "LC_ALL": "C"},
        timeout=timeout,
        shell=False,
        check=False,
    )
    return completed.returncode, completed.stdout.decode("utf-8", "replace")


def _read_limited(path: str) -> Optional[bytes]:
    try:
        with open(path, "rb") as handle:
            return handle.read(_READ_LIMIT_BYTES)
    except OSError:
        return None
