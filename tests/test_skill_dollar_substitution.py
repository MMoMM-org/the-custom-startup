"""No SKILL.md may contain an unescaped `$<digit>` (#270).

Claude Code substitutes skill arguments into the SKILL.md body: `$0` is the
first argument, `$1` the second. A literal `$0`/`$1` in a shell or awk example
(awk's `$0`, a function's `$1`) is therefore rewritten. The issue skill's
`_extract_project` rendered `sed ... "title"`: its `$1` had become the first
word of the request. No skill here uses `$N` on purpose (they take
`$ARGUMENTS`), so every occurrence must be escaped.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UNESCAPED = re.compile(r"(?<!\\)\$[0-9]")


def _offenders():
    for skill in sorted(ROOT.glob("plugins/*/skills/*/SKILL.md")):
        for n, line in enumerate(skill.read_text().splitlines(), 1):
            if UNESCAPED.search(line):
                yield f"{skill.relative_to(ROOT)}:{n}: {line.strip()}"


def test_no_skill_body_contains_an_unescaped_positional_argument():
    offenders = list(_offenders())
    assert not offenders, "escape as \\$N:\n" + "\n".join(offenders)


def test_the_pattern_flags_awk_and_shell_positionals():
    assert UNESCAPED.search("awk '{print length($0)}'")
    assert UNESCAPED.search('sed -n p "$1"')
    assert not UNESCAPED.search(r'sed -n p "\$1"')
    assert not UNESCAPED.search("$ARGUMENTS and ${CLAUDE_SKILL_DIR}")
