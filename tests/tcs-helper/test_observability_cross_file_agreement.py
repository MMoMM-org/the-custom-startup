"""Things that live in two files and must say the same thing.

spec-019. Two kinds of drift have now each been caught twice by a human
reviewer rather than by a test, which is the signal to mechanise:

  1. `SKILL.md`'s outcome table quotes message strings that are DEFINED in
     `setup.sh` and `detect.sh`. Twice in consecutive rounds a message moved
     and the table kept the old wording -- the second time, a row told the
     reader to "wait and retry" a failure where waiting is useless. A table
     that restates strings owned elsewhere will keep going stale; this file
     makes that mechanical instead of observational.

  2. Four constants are defined once in `detect.sh` (inside a python heredoc
     a shell script wraps) and again in `registration.py`. They carry
     "must change together" comments, which only work on a reader who looks.
     The failure direction is permissive: someone adding a fourth registered
     event edits `REGISTRATION` -- the natural place -- and a real collision
     under the new event would then classify CLEAN and install beside a hook
     that does fire alongside ours.

WHY A TEST RATHER THAN MAKING detect.sh IMPORT registration.py. Both are
python and an import is technically possible. It is rejected: `detect.sh` is
the read-only classifier, and importing the editor would make classification
depend on the editor's import path at run time, adding a failure mode where a
damaged `registration.py` stops a target being classified at all. The test
catches the same drift at CI time and adds no runtime coupling. The comments
stay as well -- the test says you drifted, the comment says so before you do.
"""
import ast
import os
import re
import sys

import pytest

LIB = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "../../plugins/tcs-helper/skills/observability-setup/lib",
    )
)
SKILL_MD = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "../../plugins/tcs-helper/skills/observability-setup/SKILL.md",
    )
)
DETECT_SH = os.path.join(LIB, "detect.sh")
SETUP_SH = os.path.join(LIB, "setup.sh")

sys.path.insert(0, LIB)
import registration  # noqa: E402


def _read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def _detect_constant(name):
    """Evaluate one top-level constant out of detect.sh's embedded python.

    Textual because the heredoc cannot be imported. The pattern deliberately
    anchors at column 0 and spans to the matching close, so a constant that
    changes SHAPE (a tuple becoming a call, say) fails loudly here rather
    than silently matching nothing.
    """
    source = _read(DETECT_SH)
    match = re.search(
        r"^%s = (\(.*?\)|\{.*?^\}|\".*?\")" % re.escape(name),
        source,
        re.DOTALL | re.MULTILINE,
    )
    assert match, f"{name} not found at column 0 in detect.sh -- did it move or change shape?"
    return ast.literal_eval(match.group(1))


# ---------------------------------------------------------------------------
# The four constants defined on both sides of the shell/python boundary.
# ---------------------------------------------------------------------------

def test_our_events_matches_the_events_registration_actually_registers():
    """detect.sh scopes CONFLICT to these; registration.py writes these.

    Drift here is the permissive failure: an event registered but outside
    OUR_EVENTS means a genuine collision under it classifies CLEAN.
    """
    assert set(_detect_constant("OUR_EVENTS")) == set(registration.REGISTRATION)


def test_our_namespace_matches_registrations_namespace():
    """Ownership is the namespace (ADR-5). detect.sh decides "is this ours";
    registration.py writes the commands that make it so. If the two strings
    ever differ, detection stops recognising what the editor writes."""
    assert _detect_constant("OUR_NAMESPACE") == registration.NAMESPACE


def test_legacy_scripts_matches():
    assert _detect_constant("LEGACY_SCRIPTS") == registration.LEGACY_SCRIPTS


def test_legacy_namespace_matches():
    assert _detect_constant("LEGACY_NAMESPACE") == registration.LEGACY_NAMESPACE


def test_the_legacy_shape_is_keyed_on_the_events_we_register():
    """The two sets are the same three names today, and the legacy shape is
    defined per registered event. Pinned so a fourth event added to one is
    not silently absent from the other."""
    assert set(registration.LEGACY_SCRIPTS) == set(registration.REGISTRATION)


# ---------------------------------------------------------------------------
# SKILL.md's outcome table quotes strings owned by the code.
# ---------------------------------------------------------------------------

_TABLE_CELL = re.compile(r"^\| `(STOP|ABORT|PLAN): ([^`]*)`", re.MULTILINE)


def _quoted_message_fragments():
    """Every literal fragment SKILL.md's table attributes to a real message.

    A cell is `LABEL: text`, where an ellipsis marks elision at either end.
    A cell that is nothing but an ellipsis (the catch-all row, and `PLAN: …`)
    quotes no literal and is skipped -- deliberately, because a catch-all row
    is the one shape that cannot go stale.
    """
    for label, text in _TABLE_CELL.findall(_read(SKILL_MD)):
        fragment = text.strip().strip("…").strip()
        if fragment:
            yield label, fragment


_TABLE_ROW_LOOSE = re.compile(r"^\|[^|]*\b(?:STOP|ABORT|PLAN):", re.MULTILINE)


def test_every_outcome_row_is_actually_parsed():
    """Guards the guard.

    The strict pattern below only sees a row whose first cell is a BACKTICKED
    `LABEL: text`. A row that loses its backticks stops being checked and
    nothing fails -- so the count of rows that merely look like outcome rows
    is compared against the count the strict pattern captured. A reshaped
    table then fails here instead of going quietly unchecked.
    """
    text = _read(SKILL_MD)
    loose = len(_TABLE_ROW_LOOSE.findall(text))
    strict = len(_TABLE_CELL.findall(text))
    assert loose == strict, (
        f"{loose} rows look like outcome rows but only {strict} parse as backticked "
        "`LABEL: message` cells -- the table was reshaped and part of it is no longer checked"
    )
    assert strict >= 5, f"only parsed {strict} outcome rows from the table"


@pytest.mark.parametrize("label, fragment", list(_quoted_message_fragments()))
def test_every_message_the_table_quotes_still_exists_in_the_code(label, fragment):
    corpus = _read(SETUP_SH) + _read(DETECT_SH)
    assert fragment in corpus, (
        f"SKILL.md's outcome table quotes {label}: {fragment!r}, which no longer appears in "
        "setup.sh or detect.sh. The message moved and the table did not follow."
    )
