"""One rule for enumerating a real directory in a test: skip hidden entries.

Not a test module -- the name falls outside pytest's `test_*.py` discovery
pattern on purpose, like `patterns_detection_corpus_lib.py` beside it.

**Why this exists.** Running a single Bash tool call with some directory as its
working directory makes the harness create `.claude/.cc-writes` inside it. That
directory is matched by `.gitignore`, so nothing stages it and `git status`
reports a clean tree -- but `Path.iterdir()` sees it, and any test that counts or
names the subdirectories of a real directory then counts one too many.

Measured 2026-10-04: a single `cd plugins/tcs-patterns/templates/patterns` to
run a grep turned `catalogue_pattern_names()` from 21 into 22 and made
`test_catalogue_has_pattern_names_to_validate_against` fail. The same thing had
already happened once that day in `tests/fixtures/patterns-detection/`, where it
broke the corpus count guard and both existence checks. In both cases the
failure arrives looking like somebody broke the catalogue, `git status` actively
argues nothing changed, and CI -- which never cds anywhere -- stays green.

**Filter on the dot, not on content.** A filter like
`if (d / "SKILL.md").exists()` also excludes the stray, and silently destroys the
property that a MALFORMED real entry still gets enumerated and reported. That
property is usually the whole point of the count: a pattern directory missing its
`SKILL.md` must fail loudly, not vanish from the list.
"""

from __future__ import annotations

from pathlib import Path


def visible_dirs(parent: Path) -> list[Path]:
    """Immediate subdirectories of `parent`, excluding hidden ones, sorted.

    Sorted so a test's error message lists the same order every run; a set of
    names read out of `iterdir()` is otherwise filesystem-ordered.
    """
    return sorted(
        (p for p in parent.iterdir() if p.is_dir() and not p.name.startswith(".")),
        key=lambda p: p.name,
    )


def visible_dir_names(parent: Path) -> set[str]:
    """The names of `visible_dirs(parent)`, for the callers that compare sets."""
    return {p.name for p in visible_dirs(parent)}
