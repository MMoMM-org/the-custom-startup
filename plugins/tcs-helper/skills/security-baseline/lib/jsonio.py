"""Strict JSON I/O for settings files (spec 025, K5, ADR-10).

Reading: a file is either parsed with certainty or reported with a status
and a reason from a fixed vocabulary. Nothing is repaired, and a file that
cannot be reproduced byte for byte from its parsed value is `unreadable` --
a misread layer must never read as a clean one.

Writing: `dumps` keeps key order, indent, newline style and the trailing
newline, so a rewrite changes only what the caller changed.
"""

import errno
import json
import math
import os
import re
import stat
from typing import NamedTuple, Optional, Union

MAX_BYTES = 1024 * 1024
MAX_DEPTH = 64

REASONS = frozenset({
    "bom",
    "duplicate-key",
    "invalid-json",
    "io-error",
    "non-finite-number",
    "not-object",
    "not-regular",
    "not-utf8",
    "permission-denied",
    "round-trip-mismatch",
    "symlink",
    "too-deep",
    "too-large",
})

_UTF8_BOM = b"\xef\xbb\xbf"
_FIRST_INDENT = re.compile(r"\n([ \t]+)[^ \t\r\n]")
_READ_CHUNK = 65536


class Format(NamedTuple):
    """How a file was laid out; `indent` is None for a single-line file."""

    indent: Optional[Union[int, str]]
    newline: str
    trailing_newline: bool


class _DuplicateKey(ValueError):
    pass


class _NonFinite(ValueError):
    pass


def read_json(path, follow_symlink):
    """Return `(status, data, fmt, reason)` for the JSON object at `path`.

    `data` and `fmt` are set only for status `ok`. `follow_symlink` resolves
    the path first (user scope); the resolved path is still opened with
    `O_NOFOLLOW`, as is `path` itself otherwise (project scope).
    """
    status, raw, reason = _read_bytes(path, follow_symlink)
    if status != "ok":
        return _failure(status, reason)
    return _parse(raw)


def dumps(obj, fmt):
    """Serialise `obj` to file bytes laid out as `fmt` describes."""
    text = json.dumps(obj, indent=fmt.indent, ensure_ascii=False, allow_nan=False)
    if fmt.newline != "\n":
        text = text.replace("\n", fmt.newline)
    if fmt.trailing_newline:
        text += fmt.newline
    return text.encode("utf-8")


def _failure(status, reason):
    return status, None, None, reason


def _read_bytes(path, follow_symlink):
    target = os.path.realpath(path) if follow_symlink else path
    flags = (
        os.O_RDONLY
        | getattr(os, "O_NONBLOCK", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_BINARY", 0)
    )
    try:
        fd = os.open(target, flags)
    except OSError as exc:
        return _open_failure(exc)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            return "not-regular", None, "not-regular"
        raw = _read_up_to(fd, MAX_BYTES + 1)
    except OSError:
        return "unreadable", None, "io-error"
    finally:
        os.close(fd)
    if len(raw) > MAX_BYTES:
        return "too-large", None, "too-large"
    return "ok", raw, None


def _open_failure(exc):
    if exc.errno in (errno.ENOENT, errno.ENOTDIR):
        return "absent", None, None
    if exc.errno in (errno.ELOOP, errno.EMLINK):
        return "not-regular", None, "symlink"
    if exc.errno in (errno.EACCES, errno.EPERM):
        return "denied", None, "permission-denied"
    if exc.errno in (errno.ENXIO, errno.EISDIR):
        return "not-regular", None, "not-regular"
    return "unreadable", None, "io-error"


def _read_up_to(fd, limit):
    chunks = []
    remaining = limit
    while remaining > 0:
        chunk = os.read(fd, min(_READ_CHUNK, remaining))
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _parse(raw):
    if raw.startswith(_UTF8_BOM):
        return _failure("unreadable", "bom")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return _failure("unreadable", "not-utf8")
    try:
        data = json.loads(
            text,
            object_pairs_hook=_unique_pairs,
            parse_constant=_reject_constant,
            parse_float=_finite_float,
        )
    except _DuplicateKey:
        return _failure("ambiguous", "duplicate-key")
    except _NonFinite:
        return _failure("unreadable", "non-finite-number")
    except RecursionError:
        return _failure("unreadable", "too-deep")
    except ValueError:
        return _failure("unreadable", "invalid-json")
    if _exceeds_depth(data, MAX_DEPTH):
        return _failure("unreadable", "too-deep")
    if not isinstance(data, dict):
        return _failure("unreadable", "not-object")
    fmt = _detect_format(text)
    try:
        faithful = dumps(data, fmt) == raw
    except ValueError:  # includes a lone surrogate that UTF-8 cannot encode
        faithful = False
    if not faithful:
        return _failure("unreadable", "round-trip-mismatch")
    return "ok", data, fmt, None


def _unique_pairs(pairs):
    obj = dict(pairs)
    if len(obj) != len(pairs):
        raise _DuplicateKey()
    return obj


def _reject_constant(_name):
    raise _NonFinite()


def _finite_float(literal):
    value = float(literal)
    if not math.isfinite(value):
        raise _NonFinite()
    return value


def _exceeds_depth(data, limit):
    pending = [(data, 1)]
    while pending:
        node, depth = pending.pop()
        if isinstance(node, dict):
            children = node.values()
        elif isinstance(node, list):
            children = node
        else:
            continue
        if depth > limit:
            return True
        pending.extend((child, depth + 1) for child in children)
    return False


def _detect_format(text):
    newline = "\r\n" if "\r\n" in text else "\n"
    trailing_newline = text.endswith(newline)
    body = text[: -len(newline)] if trailing_newline else text
    return Format(_detect_indent(body), newline, trailing_newline)


def _detect_indent(body):
    if "\n" not in body:
        return None
    match = _FIRST_INDENT.search(body)
    if match is None:
        return 0
    whitespace = match.group(1)
    if whitespace.strip(" ") == "":
        return len(whitespace)
    return whitespace
