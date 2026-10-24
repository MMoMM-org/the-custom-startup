"""Every json.dump/json.dumps in shipped code decides how non-ASCII is written.

Written for #226. `ensure_ascii` defaults to True, so a script that rewrites
one field turns every `ä` or `→` in the file into `\\uXXXX` -- silently, since
the result is still valid JSON. Each call must either pass `ensure_ascii`
explicitly or carry the marker below on its line, saying the output is only
ever read by a machine (a cache, a counter, a hook's stdout).

    json.dumps(output)  # json-ascii: machine-read

A call that passes `ensure_ascii=False` and writes to a file must open that
file with an explicit encoding: under a non-UTF-8 locale the write raises,
and most of these writers swallow exceptions, so the file is simply lost.
That half is not checked here; it is a review item.

Tests are excluded: they build fixtures, not files a person reads.
"""

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ROOTS = ("plugins", "scripts")
MARKER = "# json-ascii: machine-read"


def _is_test_file(path):
    parts = path.relative_to(REPO_ROOT).parts
    return "tests" in parts or "test" in parts or path.name.startswith("test_")


def _shipped_python_files():
    for root in ROOTS:
        for path in sorted((REPO_ROOT / root).rglob("*.py")):
            if not _is_test_file(path):
                yield path


def _is_json_dump(call):
    func = call.func
    return (
        isinstance(func, ast.Attribute)
        and func.attr in ("dump", "dumps")
        and isinstance(func.value, ast.Name)
        and func.value.id == "json"
    )


def _findings(path, root=REPO_ROOT):
    source = path.read_text(encoding="utf-8")
    lines = source.splitlines()
    for node in ast.walk(ast.parse(source, filename=str(path))):
        if not (isinstance(node, ast.Call) and _is_json_dump(node)):
            continue
        if any(kw.arg == "ensure_ascii" for kw in node.keywords):
            continue
        call_lines = lines[node.lineno - 1:node.end_lineno]
        if any(MARKER in line for line in call_lines):
            continue
        yield "%s:%d" % (path.relative_to(root), node.lineno)


def test_every_json_dump_decides_ensure_ascii():
    findings = [f for path in _shipped_python_files() for f in _findings(path)]
    assert not findings, (
        "json.dump/json.dumps without ensure_ascii and without %r:\n  %s"
        % (MARKER, "\n  ".join(findings))
    )


def test_the_check_sees_an_unmarked_call(tmp_path):
    probe = tmp_path / "probe.py"
    probe.write_text(
        "import json\n"
        "json.dumps({})\n"
        "json.dumps({}, ensure_ascii=False)\n"
        "json.dumps({})  %s\n" % MARKER,
        encoding="utf-8",
    )
    assert list(_findings(probe, root=tmp_path)) == ["probe.py:2"]
