"""Strict JSON I/O for security-baseline (spec 025, T1.1, ADR-10).

A settings file that cannot be read with certainty must never look like an
empty one, and a rewrite must not reformat what it did not change.
"""

import importlib.util
import json
import os
import threading
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
JSONIO_PATH = (
    REPO_ROOT / "plugins/tcs-helper/skills/security-baseline/lib/jsonio.py"
)
MIB = 1024 * 1024


def _load():
    spec = importlib.util.spec_from_file_location("sb_jsonio", JSONIO_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


jsonio = _load()


def _write(tmp_path, raw, name="settings.json"):
    path = tmp_path / name
    path.write_bytes(raw)
    return str(path)


def _read(tmp_path, raw, follow_symlink=False):
    return jsonio.read_json(_write(tmp_path, raw), follow_symlink)


def _nested(depth):
    """An object whose containers nest `depth` levels deep, one line."""
    return ('{"a": ' * (depth - 1) + "{}" + "}" * (depth - 1)).encode("utf-8")


# --- valid files and format detection ------------------------------------


@pytest.mark.parametrize(
    "raw, expected",
    [
        (b'{\n  "a": 1,\n  "b": [\n    "x"\n  ]\n}\n', (2, "\n", True)),
        (b'{\n    "a": 1\n}\n', (4, "\n", True)),
        (b'{\n\t"a": {\n\t\t"b": 1\n\t}\n}\n', ("\t", "\n", True)),
        (b'{\r\n  "a": 1\r\n}\r\n', (2, "\r\n", True)),
        (b'{\n  "a": 1\n}', (2, "\n", False)),
        (b'{"a": 1, "b": [1, 2]}\n', (None, "\n", True)),
        (b"{}", (None, "\n", False)),
    ],
    ids=["2-space", "4-space", "tab", "crlf", "no-trailing-newline",
         "single-line", "empty-object"],
)
def test_valid_object_parses_with_detected_format(tmp_path, raw, expected):
    status, data, fmt, reason = _read(tmp_path, raw)

    assert (status, reason) == ("ok", None)
    assert data == json.loads(raw)
    assert (fmt.indent, fmt.newline, fmt.trailing_newline) == expected


def test_non_ascii_text_is_read_as_utf8(tmp_path):
    raw = '{\n  "name": "Zürich → 東京"\n}\n'.encode("utf-8")

    status, data, _fmt, _reason = _read(tmp_path, raw)

    assert status == "ok"
    assert data == {"name": "Zürich → 東京"}


def test_nesting_of_64_levels_is_accepted(tmp_path):
    status, _data, _fmt, reason = _read(tmp_path, _nested(64))

    assert (status, reason) == ("ok", None)


# --- files that must not be trusted --------------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        b'{\n  "allow": [],\n  "allow": [\n    "Bash"\n  ]\n}\n',
        b'{\n  "p": {\n    "x": 1,\n    "x": 1\n  }\n}\n',
    ],
    ids=["top-level", "nested"],
)
def test_duplicate_key_is_ambiguous(tmp_path, raw):
    status, data, fmt, reason = _read(tmp_path, raw)

    assert (status, data, fmt, reason) == ("ambiguous", None, None, "duplicate-key")


@pytest.mark.parametrize(
    "raw, expected_reason",
    [
        (b'\xef\xbb\xbf{\n  "a": 1\n}\n', "bom"),
        (b'{\n  "a": NaN\n}\n', "non-finite-number"),
        (b'{\n  "a": Infinity\n}\n', "non-finite-number"),
        (b'{\n  "a": -Infinity\n}\n', "non-finite-number"),
        (b'{\n  "a": 1e999\n}\n', "non-finite-number"),
        (b'{\n  // why\n  "a": 1\n}\n', "invalid-json"),
        (b'{\n  "a": 1,\n}\n', "invalid-json"),
        (b'{\n  "a": [\n    1,\n  ]\n}\n', "invalid-json"),
        (b"", "invalid-json"),
        (b'{\n  "a": 1\n', "invalid-json"),
        (b'{\n  "a": "\xff"\n}\n', "not-utf8"),
        (_nested(65), "too-deep"),
        (b"[" * 100000, "too-deep"),
        (b'[\n  "a"\n]\n', "not-object"),
        (b'"text"\n', "not-object"),
        (b"null\n", "not-object"),
        (b'{"a":1}\n', "round-trip-mismatch"),
        (b'{\n  "a": [1, 2]\n}\n', "round-trip-mismatch"),
        (b'{\n  "a": 1.50\n}\n', "round-trip-mismatch"),
        (b'{\n  "a": "\\u00e9"\n}\n', "round-trip-mismatch"),
        (b'{\n  "a": "\\ud800"\n}\n', "round-trip-mismatch"),
        (b'{\n  "a": 1,\r\n  "b": 2\n}\n', "round-trip-mismatch"),
        (b'{\n  "a": 1\n}\n\n', "round-trip-mismatch"),
    ],
    ids=["bom", "nan", "infinity", "neg-infinity", "float-overflow", "comment",
         "trailing-comma-object", "trailing-comma-array", "empty-file",
         "truncated", "invalid-utf8", "depth-65", "depth-bomb", "top-level-array",
         "top-level-string", "top-level-null", "minified", "inline-array",
         "number-spelling", "escaped-non-ascii", "lone-surrogate",
         "mixed-newlines", "extra-blank-line"],
)
def test_untrustworthy_content_is_unreadable(tmp_path, raw, expected_reason):
    status, data, fmt, reason = _read(tmp_path, raw)

    assert (status, data, fmt, reason) == ("unreadable", None, None, expected_reason)


def test_every_reason_comes_from_the_fixed_vocabulary(tmp_path):
    samples = [
        b"\xef\xbb\xbf{}", b'{"a": NaN}', b"{,}", b"\xff", _nested(65), b"[]",
        b'{"a":1}', b'{"a": 1, "a": 2}', b" " * (MIB + 1),
    ]

    reasons = {_read(tmp_path, raw)[3] for raw in samples}
    reasons.add(jsonio.read_json(str(tmp_path), False)[3])
    reasons.add(jsonio.read_json(str(tmp_path / "missing.json"), False)[3])

    assert reasons - {None} <= jsonio.REASONS
    assert None in reasons  # the missing file carries no reason


def test_reason_never_carries_file_content(tmp_path):
    marker = "MARKER_FROM_FILE"
    raw = ('{\n  "' + marker + '": tru\n}\n').encode("utf-8")

    _status, _data, _fmt, reason = _read(tmp_path, raw)

    assert marker not in reason


# --- size limit ----------------------------------------------------------


def _padded_object(size):
    head, tail = b'{\n  "pad": "', b'"\n}\n'
    return head + b"x" * (size - len(head) - len(tail)) + tail


def test_file_of_exactly_one_mebibyte_is_read(tmp_path):
    raw = _padded_object(MIB)
    assert len(raw) == MIB

    status, _data, _fmt, reason = _read(tmp_path, raw)

    assert (status, reason) == ("ok", None)


def test_one_byte_over_one_mebibyte_is_too_large(tmp_path):
    raw = _padded_object(MIB + 1)
    assert len(raw) == MIB + 1

    status, data, fmt, reason = _read(tmp_path, raw)

    assert (status, data, fmt, reason) == ("too-large", None, None, "too-large")


# --- things that are not a plain file ------------------------------------


def _read_without_hanging(path, follow_symlink):
    result = []
    worker = threading.Thread(
        target=lambda: result.append(jsonio.read_json(path, follow_symlink)),
        daemon=True,
    )
    worker.start()
    worker.join(timeout=10)
    assert not worker.is_alive(), "read_json blocked on a non-regular file"
    return result[0]


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="no FIFOs on this platform")
@pytest.mark.parametrize("follow_symlink", [False, True])
def test_fifo_is_not_regular_and_does_not_hang(tmp_path, follow_symlink):
    fifo = tmp_path / "settings.json"
    os.mkfifo(fifo)

    result = _read_without_hanging(str(fifo), follow_symlink)

    assert result == ("not-regular", None, None, "not-regular")


@pytest.mark.parametrize("follow_symlink", [False, True])
def test_directory_is_not_regular(tmp_path, follow_symlink):
    directory = tmp_path / "settings.json"
    directory.mkdir()

    result = _read_without_hanging(str(directory), follow_symlink)

    assert result == ("not-regular", None, None, "not-regular")


def _symlink_to_valid_file(tmp_path):
    target = _write(tmp_path, b'{\n  "a": 1\n}\n', name="real.json")
    link = tmp_path / "settings.json"
    link.symlink_to(target)
    return str(link)


def test_symlink_is_refused_when_not_following(tmp_path):
    link = _symlink_to_valid_file(tmp_path)

    result = jsonio.read_json(link, False)

    assert result == ("not-regular", None, None, "symlink")


def test_symlink_is_resolved_when_following(tmp_path):
    link = _symlink_to_valid_file(tmp_path)

    status, data, fmt, reason = jsonio.read_json(link, True)

    assert (status, data, reason) == ("ok", {"a": 1}, None)
    assert fmt.indent == 2


def test_symlink_to_fifo_is_not_regular_when_following(tmp_path):
    if not hasattr(os, "mkfifo"):
        pytest.skip("no FIFOs on this platform")
    fifo = tmp_path / "pipe"
    os.mkfifo(fifo)
    link = tmp_path / "settings.json"
    link.symlink_to(fifo)

    result = _read_without_hanging(str(link), True)

    assert result == ("not-regular", None, None, "not-regular")


@pytest.mark.parametrize("follow_symlink", [False, True])
def test_missing_file_is_absent(tmp_path, follow_symlink):
    result = jsonio.read_json(str(tmp_path / "settings.json"), follow_symlink)

    assert result == ("absent", None, None, None)


def test_missing_parent_directory_is_absent(tmp_path):
    result = jsonio.read_json(str(tmp_path / "nope" / "settings.json"), False)

    assert result == ("absent", None, None, None)


def test_dangling_symlink_is_absent_when_following(tmp_path):
    link = tmp_path / "settings.json"
    link.symlink_to(tmp_path / "gone.json")

    assert jsonio.read_json(str(link), True) == ("absent", None, None, None)


@pytest.mark.skipif(
    not hasattr(os, "geteuid") or os.geteuid() == 0,
    reason="permission bits do not bind root",
)
def test_file_without_read_permission_is_denied(tmp_path):
    path = _write(tmp_path, b'{\n  "a": 1\n}\n')
    os.chmod(path, 0)

    result = jsonio.read_json(path, False)

    assert result == ("denied", None, None, "permission-denied")


def test_empty_object_is_not_confused_with_an_unreadable_file(tmp_path):
    """PRD F1 AC5: only a file that parsed may yield data, even empty data."""
    ok = _read(tmp_path, b"{}\n")
    broken = _read(tmp_path, b"{\n")

    assert ok[:2] == ("ok", {})
    assert broken[:2] == ("unreadable", None)


# --- byte-faithful serialisation -----------------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        b'{\n  "z": 1,\n  "a": {\n    "k": [\n      "x",\n      2.5,\n      true,\n      null\n    ]\n  },\n  "e": [],\n  "o": {}\n}\n',
        b'{\n    "z": 1,\n    "a": "b"\n}\n',
        b'{\n\t"z": [\n\t\t1\n\t]\n}\n',
        b'{\r\n  "z": 1,\r\n  "a": "line\\nbreak"\r\n}\r\n',
        b'{\n  "z": 1\n}',
        b'{"z": 1, "a": [1, 2]}\n',
        '{\n  "name": "Zürich → 東京",\n  "esc": "tab\\tquote\\"slash\\\\"\n}\n'.encode("utf-8"),
    ],
    ids=["2-space", "4-space", "tab", "crlf", "no-trailing-newline",
         "single-line", "non-ascii"],
)
def test_dumps_reproduces_original_bytes_for_unchanged_object(tmp_path, raw):
    status, data, fmt, _reason = _read(tmp_path, raw)
    assert status == "ok"

    assert jsonio.dumps(data, fmt) == raw


def test_dumps_preserves_key_order_and_format_after_an_append(tmp_path):
    raw = b'{\r\n\t"zeta": 1,\r\n\t"alpha": {\r\n\t\t"deny": [\r\n\t\t\t"a"\r\n\t\t]\r\n\t}\r\n}'
    _status, data, fmt, _reason = _read(tmp_path, raw)

    data["alpha"]["deny"].append("b")
    data["middle"] = True

    assert jsonio.dumps(data, fmt) == (
        b'{\r\n\t"zeta": 1,\r\n\t"alpha": {\r\n\t\t"deny": [\r\n\t\t\t"a",'
        b'\r\n\t\t\t"b"\r\n\t\t]\r\n\t},\r\n\t"middle": true\r\n}'
    )


def test_dumps_writes_non_ascii_as_utf8_not_escapes():
    fmt = jsonio.Format(indent=2, newline="\n", trailing_newline=True)

    out = jsonio.dumps({"name": "Zürich → 東京"}, fmt)

    assert out == '{\n  "name": "Zürich → 東京"\n}\n'.encode("utf-8")
    assert b"\\u" not in out


def test_dumps_refuses_non_finite_numbers():
    fmt = jsonio.Format(indent=2, newline="\n", trailing_newline=True)

    with pytest.raises(ValueError):
        jsonio.dumps({"a": float("nan")}, fmt)


def test_dumps_output_reads_back_as_ok(tmp_path):
    fmt = jsonio.Format(indent=4, newline="\r\n", trailing_newline=False)
    obj = {"b": [1, {"c": "d"}], "a": None}

    status, data, read_fmt, _reason = _read(tmp_path, jsonio.dumps(obj, fmt))

    assert (status, data, read_fmt) == ("ok", obj, fmt)
    assert list(data) == ["b", "a"]


# --- module hygiene ------------------------------------------------------


def test_import_performs_no_io(monkeypatch):
    def _forbidden(*_args, **_kwargs):
        raise AssertionError("jsonio touched the filesystem at import")

    source = JSONIO_PATH.read_text(encoding="utf-8")
    spec = importlib.util.spec_from_file_location("sb_jsonio_noio", JSONIO_PATH)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setattr(os, "open", _forbidden)
    monkeypatch.setattr(os, "stat", _forbidden)
    monkeypatch.setattr("builtins.open", _forbidden)

    exec(compile(source, str(JSONIO_PATH), "exec"), module.__dict__)

    assert callable(module.read_json)
