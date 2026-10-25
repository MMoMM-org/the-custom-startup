"""Two shell constructs that work on one CI leg and silently break on the other.

Written for #226. Each has been hit before, and each fails without an error a
reader would notice, so they are checked rather than remembered:

  - `[[:<:]]` / `[[:>:]]` -- BSD-only word boundaries. glibc rejects them, so
    under Linux `[[ =~ ]]` returns 2, every caller reads "no match", and a
    guard built on them fails open. Use `([^[:alnum:]_]|$)` or `[[:space:]]`.
  - a bare `timeout` in bats -- GNU coreutils, absent on macOS and on the
    macos-latest runner. `run timeout 5 ...` exits 127 there, so the hang
    guard never runs. Use a `_timeout` helper that falls back when `timeout`
    is missing (see plugins/tcs-helper/tests/bats/observability-timed-wrapper.bats).

Only files git tracks are read. Comment lines and bats `@test` names are
ignored; a test name cannot carry a marker, since bats only recognises a
`@test ... {` line with nothing after the brace. Any other line that uses one
of these on purpose -- a test pinning the glibc failure, say -- carries
`# lint-ok: <name>` to say so.
"""

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SHELL_SUFFIXES = {".sh", ".bash", ".bats"}
SHEBANG = re.compile(r"^#!.*\b(ba)?sh\b")

BSD_BOUNDARY = re.compile(r"\[\[:[<>]:\]\]")
# `timeout` in command position: line start, after `run` (with an optional
# `-N`/`!`), after a separator, or opening a command substitution. `command
# timeout` is how a fallback helper calls the real binary, and is left alone.
BARE_TIMEOUT = re.compile(
    r"(?:^|\brun(?:[ \t]+(?:-[0-9]+|!))*[ \t]+|[;&|(][ \t]*|\$\([ \t]*)"
    r"[ \t]*timeout[ \t]"
)


def _is_shell(path):
    if path.suffix in SHELL_SUFFIXES:
        return True
    if path.suffix:
        return False
    try:
        with path.open(encoding="utf-8") as handle:
            return bool(SHEBANG.match(handle.readline()))
    except (UnicodeDecodeError, OSError):
        return False


def _tracked(root):
    out = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"],
        capture_output=True, text=True, check=True,
    ).stdout
    return [root / name for name in out.split("\0") if name]


def _files(paths, predicate):
    return [p for p in paths if p.is_file() and predicate(p)]


def _findings(paths, pattern, name, root):
    marker = "# lint-ok: %s" % name
    for path in paths:
        for no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.lstrip()
            if stripped.startswith(("#", "@test")) or marker in line:
                continue
            if pattern.search(line):
                yield "%s:%d: %s" % (path.relative_to(root), no, line.strip())


def _is_bats(path):
    return path.suffix == ".bats" or (path.suffix == ".bash" and "tests" in path.parts)


def _bsd_findings(paths, root):
    return list(_findings(_files(paths, _is_shell), BSD_BOUNDARY, "bsd-word-boundary", root))


def _timeout_findings(paths, root):
    return list(_findings(_files(paths, _is_bats), BARE_TIMEOUT, "bare-timeout", root))


def test_no_bsd_word_boundaries_in_shell_code():
    findings = _bsd_findings(_tracked(REPO_ROOT), REPO_ROOT)
    assert not findings, (
        "BSD-only [[:<:]]/[[:>:]] fail open under glibc; use ([^[:alnum:]_]|$):\n  "
        + "\n  ".join(findings)
    )


def test_no_bare_timeout_in_bats():
    findings = _timeout_findings(_tracked(REPO_ROOT), REPO_ROOT)
    assert not findings, (
        "`timeout` is absent on macOS; use a _timeout helper with a fallback:\n  "
        + "\n  ".join(findings)
    )


def test_the_checks_see_what_they_are_for(tmp_path):
    (tmp_path / "hook.sh").write_text(
        "# a comment naming [[:<:]] is fine\n"
        "[[ $c =~ git[[:>:]] ]]\n"
        "[[ $c =~ x[[:>:]] ]]  # lint-ok: bsd-word-boundary\n"
        "@test \"names [[:<:]] in its title\" {\n",
        encoding="utf-8",
    )
    (tmp_path / "noext").write_text("#!/usr/bin/env bash\np='a[[:<:]]'\n", encoding="utf-8")
    (tmp_path / "t.bats").write_text(
        "@test x {\n"
        "  run timeout 5 cmd\n"
        "  run -0 timeout 5 cmd\n"
        "  timeout 5 cmd\n"
        "  out=$(timeout 5 cmd)\n"
        "  true && timeout 5 cmd\n"
        "  command timeout 5 cmd\n"
        "  expect_parse 'timeout 5 git fetch'\n"
        "  # timeout 5 cmd\n"
        "  _timeout 5 cmd\n"
        "}\n",
        encoding="utf-8",
    )

    paths = sorted(tmp_path.iterdir())
    assert [f.split(":")[0:2] for f in _bsd_findings(paths, tmp_path)] == [
        ["hook.sh", "2"], ["noext", "2"],
    ]
    assert [int(f.split(":")[1]) for f in _timeout_findings(paths, tmp_path)] == [2, 3, 4, 5, 6]
