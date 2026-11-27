"""Sandbox dependency check and trial run (spec 025, K4, ADR-6).

Answers "can a sandbox start on this machine" without trusting anything the
machine's configuration says. Binaries are taken from fixed directories only
(never from `PATH`), must be owned by root or the current user and must not
be world-writable. The argv, the environment and the working directory are
constants; nothing from a settings file is executed and no file is written.

The result is a probe, not Claude Code's own check: `pass` only on a clean
exit 0, `fail` when a dependency is missing or the trial run exits non-zero,
and `inconclusive` for everything that says nothing certain -- a timeout, a
signal, a nested sandbox, an unsupported platform.
"""

import os
import signal
import stat
import subprocess
from typing import Callable, NamedTuple, Optional, Sequence

SEARCH_DIRS = ("/usr/bin", "/bin", "/usr/local/bin", "/opt/homebrew/bin")
DEFAULT_TIMEOUT = 10

PROBE_ENV = {"PATH": os.pathsep.join(SEARCH_DIRS), "LANG": "C"}
PROBE_CWD = "/"
PROBE_TARGET = "/usr/bin/true"

BWRAP_ARGS = (
    "--ro-bind", "/", "/", "--dev", "/dev", "--proc", "/proc",
    "--unshare-net", "--tmpfs", "/tmp", PROBE_TARGET,
)
# Permissive on purpose: the trial asks whether a profile can be applied at
# all, not whether /usr/bin/true survives a strict one.
DARWIN_PROFILE = "(version 1)(allow default)(deny network*)"
SANDBOX_EXEC_ARGS = ("-p", DARWIN_PROFILE, PROBE_TARGET)

INSTALL_HINT = (
    "sudo apt-get install bubblewrap socat (Debian, Ubuntu) or "
    "sudo dnf install bubblewrap socat (Fedora)"
)

# Lower-case stderr fragments of a sandbox refused by an enclosing sandbox
# or container: the trial says nothing about the machine itself.
NESTED_SYMPTOMS = (
    "operation not permitted",
    "setting up uid map",
    "sandbox_apply",
)

_STDERR_LIMIT = 4096
_REAP_SECONDS = 2
# What `_resolve` returns for a binary that exists but fails the trust check.
_UNTRUSTED = object()


class RunOutcome(NamedTuple):
    """What a runner reports; `returncode` is None when nothing exited."""

    returncode: Optional[int]
    stderr: str
    timed_out: bool


class ProbeResult(NamedTuple):
    result: str  # pass | fail | inconclusive
    reason: str  # fixed text, never output of the probed binary
    missing: list
    context: dict  # inside_sandbox: bool|None, uid: int, tool_versions: dict


Runner = Callable[[list, dict, str, float], RunOutcome]


def subprocess_runner(argv, env, cwd, timeout):
    """Run `argv` detached from the terminal and bounded by `timeout`.

    The child gets its own session, so a timeout kills the whole process
    group and not just the direct child.
    """
    try:
        process = subprocess.Popen(
            argv,
            shell=False,
            cwd=cwd,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
    except OSError:
        return RunOutcome(None, "", False)
    timed_out = False
    try:
        _, raw = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        _kill_group(process)
        try:
            _, raw = process.communicate(timeout=_REAP_SECONDS)
        except subprocess.TimeoutExpired:
            # A grandchild that left the group still holds the pipe. Its
            # output is given up; the direct child is reaped and our end of
            # the pipe closed, so neither a zombie nor a descriptor is left.
            raw = b""
            try:
                process.wait(timeout=_REAP_SECONDS)
            except subprocess.TimeoutExpired:
                pass
            if process.stderr:
                process.stderr.close()
    stderr = (raw or b"")[:_STDERR_LIMIT].decode("utf-8", errors="replace")
    return RunOutcome(process.returncode, stderr, timed_out)


def _kill_group(process):
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except OSError:
        process.kill()


def run_probe(
    platform,
    search_dirs: Sequence[str] = SEARCH_DIRS,
    runner: Optional[Runner] = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> ProbeResult:
    """Check the sandbox dependencies of `platform` and try one sandboxed run.

    `platform` is `linux` or `darwin`; anything else is inconclusive.
    """
    context = {"inside_sandbox": None, "uid": _uid(), "tool_versions": {}}
    if platform == "linux":
        launcher, args, needed, hint = "bwrap", BWRAP_ARGS, ("bwrap", "socat"), INSTALL_HINT
    elif platform == "darwin":
        launcher, args, needed, hint = "sandbox-exec", SANDBOX_EXEC_ARGS, ("sandbox-exec",), None
    else:
        return ProbeResult(
            "inconclusive", "unsupported platform: no sandbox probe", [], context
        )

    found = {name: _resolve(name, search_dirs) for name in needed}
    untrusted = [name for name in needed if found[name] is _UNTRUSTED]
    missing = [name for name in needed if found[name] is None]
    if untrusted:
        reason = "%s found but not trusted: owner or mode" % ", ".join(untrusted)
        return ProbeResult("fail", reason, missing, context)
    if missing:
        reason = "missing: %s" % ", ".join(missing)
        if hint:
            reason += "; install with: " + hint
        return ProbeResult("fail", reason, missing, context)

    argv = [found[launcher], *args]
    outcome = (runner or subprocess_runner)(argv, dict(PROBE_ENV), PROBE_CWD, timeout)
    return _judge(outcome, context)


def _judge(outcome, context):
    code = outcome.returncode
    if outcome.timed_out:
        verdict, reason = "inconclusive", "probe timed out"
    elif code is None:
        verdict, reason = "inconclusive", "probe could not start"
    elif code < 0:
        verdict, reason = "inconclusive", "probe ended by a signal"
    elif code == 0:
        verdict, reason = "pass", "sandbox started (probe, not Claude Code's own check)"
    elif _looks_nested(outcome.stderr):
        context["inside_sandbox"] = True
        verdict, reason = "inconclusive", "nested sandbox: probe ran inside a sandbox or container"
    else:
        verdict, reason = "fail", "sandbox cannot run here"
    return ProbeResult(verdict, reason, [], context)


def _looks_nested(stderr):
    text = stderr.lower()
    return any(symptom in text for symptom in NESTED_SYMPTOMS)


def _resolve(name, search_dirs):
    """Path of `name`, `_UNTRUSTED`, or None when no directory has it.

    The first directory holding an executable file of that name decides: an
    untrusted one is refused rather than skipped, so a tampered binary is
    reported instead of silently replaced by a later one.
    """
    # Out of scope, because the directories are fixed system ones (ADR-6):
    # the window between this stat and the exec, a writable parent directory
    # and group-writable bits.
    for directory in search_dirs:
        path = os.path.join(directory, name)
        try:
            info = os.stat(path)
        except (OSError, ValueError):
            continue
        if not stat.S_ISREG(info.st_mode) or not info.st_mode & 0o111:
            continue
        if info.st_uid not in (0, _uid()) or info.st_mode & stat.S_IWOTH:
            return _UNTRUSTED
        return path
    return None


def _uid():
    geteuid = getattr(os, "geteuid", None)
    return geteuid() if geteuid else -1
