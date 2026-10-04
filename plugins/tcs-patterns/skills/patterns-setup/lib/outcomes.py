"""The decided-exactly-once partition (spec-020 T2.5).

F3's fourth acceptance criterion is that each of the 21 patterns is decided
exactly once -- by a file signal, or by one question, never both. That claim
is only a claim until something sums it. This module is the thing that sums
it: given a `detect()` report and the answers a user gave to whichever gates
opened, it partitions all 21 pattern names into four disjoint sets.

**Four sets, not three** `[ref: SDD/Runtime View/Complex Logic, "There are
four outcomes, not three"]`. The temptation is to stop at `installed`,
`declined_by_question` and `excluded_by_stack_fact` -- those three are what a
stack that opens every gate produces, which is exactly the walkthrough this
module is checked against. But a pattern behind a gate that stayed **shut**
belongs to none of the three: nobody was asked (it is not declined), no file
signal ruled it out (it is not excluded), and it was not proposed (it is not
installed). It is `not_reached`, a fourth set, because "you were not asked,
because nothing indicated the shape this pattern needs" is a statement about
the *detection*, not about the repository, and collapsing it into
`excluded_by_stack_fact` would hide that from a user who might disagree with
it.

**The two groups, and where they come from.** `detect.py` holds the constants
that decide whether a gate *opens* (`NODE_SERVER_FRAMEWORK_DEPS` and the
rest); it holds nothing mapping a gate to the patterns it *settles*, because
nothing before this module needed that mapping. `GATE_SETTLED_PATTERNS` below
is copied from the `Settles` column of the gate table
`[ref: SDD/Interface Specifications/Detection rules: the eight stack facts
and the three gates]` -- 6 + 5 + 2 = 13. `STACK_FACT_PATTERNS` is the other
eight: the patterns `detect()` decides from files alone, win or lose, and
never asks about. The two groups are disjoint and their union is exactly the
21 pattern directories under `templates/patterns/` -- asserted in
`tests/test_patterns_outcomes.py` against a hand-typed literal, not derived
from this module, so a table that swaps two names between the groups (e.g.
`testing` under a gate, `mutation-testing` under stack facts) cannot pass by
the union alone staying 21.

**This module touches no filesystem.** `decide()` takes the report `detect()`
already produced, plus the answers a caller collected, and returns the
partition -- it does not re-scan the target repository and does not read the
catalogue. The constants above are the only things it needs that a scan would
otherwise have supplied.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

# Settles column of the gate table, copied by hand
# `[ref: SDD/Interface Specifications/Detection rules: the eight stack facts
# and the three gates]`. 6 + 5 + 2 = 13.
GATE_SETTLED_PATTERNS: dict[str, frozenset[str]] = {
    "q1_backend": frozenset(
        {
            "api-design",
            "bff-entry-points",
            "secure-oauth-oidc",
            "observability",
            "twelve-factor",
            "node-service",
        }
    ),
    "q2_architecture": frozenset(
        {
            "ddd",
            "event-driven",
            "event-sourcing",
            "hexagonal",
            "functional",
        }
    ),
    "q3_test_quality": frozenset(
        {
            "mutation-testing",
            "test-design-reviewer",
        }
    ),
}

# The eight stack facts -- decided from files alone, proposed with evidence,
# never asked about `[ref: SDD/Interface Specifications/Detection rules]`.
STACK_FACT_PATTERNS: frozenset[str] = frozenset(
    {
        "obsidian-plugin",
        "mcp-server",
        "typescript-strict",
        "go-idiomatic",
        "python-project",
        "react-testing",
        "frontend-testing",
        "testing",
    }
)

# The union, for callers (and this module's own tests) that need "all 21"
# without re-deriving it from the two groups above.
ALL_PATTERN_NAMES: frozenset[str] = STACK_FACT_PATTERNS.union(
    *GATE_SETTLED_PATTERNS.values()
)


@dataclass(frozen=True)
class Outcomes:
    """The four-way partition of `ALL_PATTERN_NAMES`
    `[ref: SDD/Runtime View/Complex Logic, "installed +
    declined-by-question + excluded-by-stack-fact + not-reached = 21"]`.
    Pairwise disjoint, and the four always sum to `len(ALL_PATTERN_NAMES)`."""

    installed: frozenset[str]
    declined_by_question: frozenset[str]
    excluded_by_stack_fact: frozenset[str]
    not_reached: frozenset[str]


def decide(report: Mapping, answers: Mapping[str, Iterable[str]] | None = None) -> Outcomes:
    """Partition all 21 pattern names given a `detect()` report and the
    answers collected for whichever gates opened.

    `answers` maps an **open** gate's name to the patterns the user picked
    for it (each gate is multiSelect, so any subset of that gate's settled
    patterns, including none of them, is a valid answer). A gate that is
    closed in `report["gates"]` is never consulted here even if `answers`
    happens to carry a key for it -- a closed gate yields no question, so
    there is nothing to have answered
    `[ref: SDD/Runtime View/Complex Logic, "There are four outcomes, not
    three"]`.
    """
    answers = answers or {}

    fired = {p["pattern"] for p in report.get("auto", [])}
    fired |= {p["pattern"] for p in report.get("baseline", [])}

    installed: set[str] = set(fired & STACK_FACT_PATTERNS)
    excluded_by_stack_fact = frozenset(STACK_FACT_PATTERNS - fired)

    declined_by_question: set[str] = set()
    not_reached: set[str] = set()

    gates = report.get("gates", {})
    for gate, settled in GATE_SETTLED_PATTERNS.items():
        if gates.get(gate):
            chosen = set(answers.get(gate, ())) & settled
            installed |= chosen
            declined_by_question |= settled - chosen
        else:
            not_reached |= settled

    return Outcomes(
        installed=frozenset(installed),
        declined_by_question=frozenset(declined_by_question),
        excluded_by_stack_fact=excluded_by_stack_fact,
        not_reached=frozenset(not_reached),
    )
