"""Minimal style checker: line length, tabs, trailing whitespace, final newline.

Usage: python3 scripts/lint.py [--fix] PATH...
"""

import os
import sys

MAX_LINE = 99
SUFFIXES = (".py", ".sh")


def iter_files(paths):
    for path in paths:
        if os.path.isfile(path):
            yield path
            continue
        for root, dirs, files in os.walk(path):
            dirs[:] = sorted(d for d in dirs if d != "__pycache__")
            for name in sorted(files):
                if name.endswith(SUFFIXES):
                    yield os.path.join(root, name)


def check(path, fix):
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    problems = []
    lines = text.split("\n")
    for number, line in enumerate(lines, start=1):
        if len(line) > MAX_LINE:
            problems.append("{}:{}: line longer than {}".format(path, number, MAX_LINE))
        if "\t" in line:
            problems.append("{}:{}: tab character".format(path, number))
        if line != line.rstrip():
            problems.append("{}:{}: trailing whitespace".format(path, number))
    if text and not text.endswith("\n"):
        problems.append("{}: missing final newline".format(path))
    if fix:
        fixed = "\n".join(line.rstrip() for line in lines).rstrip("\n") + "\n"
        if fixed != text:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(fixed)
        problems = [p for p in problems if "line longer" in p or "tab" in p]
    return problems


def main(argv):
    fix = "--fix" in argv
    paths = [a for a in argv if a != "--fix"] or ["."]
    problems = []
    for path in iter_files(paths):
        problems.extend(check(path, fix))
    for problem in problems:
        print(problem)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
