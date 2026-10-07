"""T2.4 (spec-020): the companion map, derived from the catalogue.

Why this exists: C5 copies **one** pattern directory into a consumer repo
`[ref: SDD/Runtime View]`. Pattern files cite each other's files -- installing
`ddd` alone leaves its citation of a file living in `hexagonal/` dangling in
the consumer repository. `companions.py` (spec-020 T2.4) derives, from the
catalogue itself, the map of which pattern a citation actually reaches, so
C3 can offer the companion before the user finishes deciding
`[ref: SDD/Interface Specifications/Data model: companion map; ADR-10]`.

This file asserts the derived map against a **hand-typed** table, not against
a second re-scan of the catalogue text: the point of T2.1's "fixtures before
rules" discipline applies here too -- a check that re-parses what the
production code parses agrees with it wherever the parsing is wrong. The
seven edges below were counted by hand against the catalogue before
`companions.py` was written, the same order of operations T2.1 used for the
detection fixtures
`[ref: docs/XDD/specs/020-tcs-patterns-selective-install/plan/phase-2.md#T2.4]`.

The module under test is imported at **runtime**, inside each test, not at
module level -- same reason `test_patterns_detect.py` does this for
`detect.py`: a module-level `ImportError` would collect zero cases and abort
the rest of the suite's collection besides.
"""

from __future__ import annotations

import dataclasses
import importlib
import signal
import sys
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
LIB_DIR = REPO_ROOT / "plugins" / "tcs-patterns" / "skills" / "patterns-setup" / "lib"
REAL_CATALOGUE_DIR = REPO_ROOT / "plugins" / "tcs-patterns" / "templates" / "patterns"


def _load_companions() -> ModuleType:
    """See `test_patterns_detect.py::_load_detect` for why this import happens
    here rather than at module level, and why `sys.path` (not `PYTHONPATH`)
    is how a mutated copy must be loaded when mutation-testing this file."""
    if str(LIB_DIR) not in sys.path:
        sys.path.insert(0, str(LIB_DIR))
    return importlib.import_module("companions")


# Hand-typed against the catalogue, independently of `companions.py`'s own
# extraction logic -- see module docstring. Mirrors
# `docs/XDD/specs/020-tcs-patterns-selective-install/solution.md`'s
# "Data model: companion map" table exactly.
EXPECTED_EDGES = {
    "ddd": frozenset({"hexagonal"}),
    "event-driven": frozenset({"hexagonal", "event-sourcing"}),
    "event-sourcing": frozenset({"event-driven", "hexagonal"}),
    "hexagonal": frozenset({"ddd"}),
    "observability": frozenset({"hexagonal"}),
}

# Three of the five sources gain `ddd` once expansion is the transitive
# closure rather than one hop -- the `ddd`/`hexagonal` pair does not, because
# both the selection and its one companion are already in the pair
# `[ref: SDD/Interface Specifications/Data model: companion map, "Expansion
# is the transitive closure"]`.
EXPECTED_CLOSURES = {
    "ddd": frozenset({"hexagonal"}),
    "hexagonal": frozenset({"ddd"}),
    "observability": frozenset({"hexagonal", "ddd"}),
    "event-driven": frozenset({"hexagonal", "event-sourcing", "ddd"}),
    "event-sourcing": frozenset({"event-driven", "hexagonal", "ddd"}),
}


@contextmanager
def _deadline(seconds: float):
    """Fail the test rather than hang the suite if the body does not return
    within `seconds`. An unguarded depth-first walk from either mutual pair
    (`ddd`/`hexagonal`, `event-driven`/`event-sourcing`) never terminates --
    this is only a real hazard once a transitive-closure traversal exists at
    all, which is why the cycle criterion could not have failed before T2.4
    `[ref: docs/XDD/specs/020-tcs-patterns-selective-install/plan/
    phase-2.md#T2.4]`. SIGALRM is POSIX-only, which is fine here -- this
    repo's own test suite already assumes a POSIX shell elsewhere."""

    def _on_alarm(signum, frame):
        raise TimeoutError(f"did not return within {seconds}s -- suspect an unterminated traversal")

    previous = signal.signal(signal.SIGALRM, _on_alarm)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def _write_pattern_file(root: Path, pattern: str, rel_path: str, text: str) -> None:
    path = root / pattern / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# --- The real catalogue -----------------------------------------------------


def test_companion_map_equals_the_seven_measured_edges() -> None:
    """`[ref: SDD/Acceptance Criteria/AC-18]`. Keyed on paths resolving under
    another pattern's root, not on the `tcs-patterns:<name>` marker, which
    would yield 43 -- this assertion is what would catch a derivation that
    quietly switched to the marker."""
    companions = _load_companions()
    assert companions.companion_map(REAL_CATALOGUE_DIR) == EXPECTED_EDGES


def test_companion_map_has_exactly_seven_edges() -> None:
    """Standalone and non-parametrized, same reason the corpus-size guards
    elsewhere in this suite are: a derivation that silently dropped or
    duplicated edges inside a dict comparison that happened to still match
    by coincidence is the failure mode a raw count catches independently."""
    companions = _load_companions()
    total = sum(len(targets) for targets in companions.companion_map(REAL_CATALOGUE_DIR).values())
    assert total == 7


def test_no_candidate_is_ambiguous_in_the_real_catalogue() -> None:
    """Zero are ambiguous today -- asserted so the day a citation resolves
    under two other pattern roots at once, this test says so rather than the
    map silently picking one `[ref: SDD/Interface Specifications/Data model:
    companion map]`."""
    companions = _load_companions()
    assert companions.ambiguous_citations(REAL_CATALOGUE_DIR) == ()


def test_the_relation_is_a_cycle_both_mutual_pairs_point_both_ways() -> None:
    """`ddd`/`hexagonal` and `event-driven`/`event-sourcing` are mutual, so
    the relation is a cycle and not a tree -- the reason the closure
    traversal below must carry a visited set at all."""
    companions = _load_companions()
    edges = companions.companion_map(REAL_CATALOGUE_DIR)
    assert "hexagonal" in edges["ddd"]
    assert "ddd" in edges["hexagonal"]
    assert "hexagonal" in edges["event-driven"] and "event-sourcing" in edges["event-driven"]
    assert "event-driven" in edges["event-sourcing"] and "hexagonal" in edges["event-sourcing"]


@pytest.mark.parametrize("selected,expected", sorted(EXPECTED_CLOSURES.items()))
def test_transitive_closure_matches_the_documented_table(selected: str, expected: frozenset) -> None:
    """`[ref: SDD/Interface Specifications/Data model: companion map,
    "Expansion is the transitive closure"]`. `observability`, `event-driven`
    and `event-sourcing` each gain `ddd` only once expansion walks past the
    first hop; `ddd` and `hexagonal` do not, which is the discriminating
    half of this assertion -- a closure that returned the source itself, or
    one that is secretly only one hop deep, would differ on at least one of
    these five rows."""
    companions = _load_companions()
    assert companions.expand_companions({selected}, REAL_CATALOGUE_DIR) == expected


def test_closure_terminates_on_both_mutual_pairs() -> None:
    """Only falsifiable now that a traversal exists at all -- before the
    closure was the rule, nothing recursed and this could not have failed
    `[ref: docs/XDD/specs/020-tcs-patterns-selective-install/plan/
    phase-2.md#T2.4]`. A timeout, not inspection, is what makes a missing
    visited set a failure instead of a hang."""
    companions = _load_companions()
    with _deadline(5.0):
        for pattern in ("ddd", "hexagonal", "event-driven", "event-sourcing"):
            companions.expand_companions({pattern}, REAL_CATALOGUE_DIR)


# --- Synthetic catalogues: the three properties a real-catalogue-only test
# cannot show -----------------------------------------------------------------


def test_a_new_cross_pattern_reference_is_picked_up_not_missed(tmp_path: Path) -> None:
    """A hardcoded table would pass this unchanged and go stale the first
    time a pattern's references changed; a derivation must not
    `[ref: SDD/Architecture Decisions/ADR-10, "A hardcoded companion table"]`.
    Never mutates the real catalogue -- builds a throwaway two-pattern tree
    under `tmp_path` instead
    `[ref: docs/XDD/specs/020-tcs-patterns-selective-install/plan/
    phase-2.md#T2.4]`."""
    companions = _load_companions()
    _write_pattern_file(tmp_path, "alpha", "SKILL.md", "citing pattern, nothing here resolves locally\n")
    _write_pattern_file(
        tmp_path,
        "alpha",
        "reference/notes.md",
        "See `tcs-patterns:beta` `reference/shared.md` for the rest.\n",
    )
    _write_pattern_file(tmp_path, "beta", "SKILL.md", "target pattern\n")
    _write_pattern_file(tmp_path, "beta", "reference/shared.md", "the file alpha's citation reaches\n")

    assert companions.companion_map(tmp_path) == {"alpha": frozenset({"beta"})}


def test_a_leading_climb_resolves_nothing_the_real_shape_has_no_climb(tmp_path: Path) -> None:
    """The real citation shape is not a `../` climb -- a derivation written
    for that shape finds zero edges in the real catalogue, measured
    `[ref: SDD/Interface Specifications/Data model: companion map, "How the
    citations are actually written..."]`. The shape is a generic filename
    naming no pattern, climbed to from inside a pattern -- **not** a path
    that climbs out and then explicitly re-descends into a named sibling (a
    different,
    legitimately-resolving shape this map does not need to rule out, and
    does not: resolving under a root by any path arithmetic, climb or not,
    is still "resolves under that root" by this module's own rule). The
    climbed-to file exists one level above every pattern root, sibling to
    all of them -- real estate no single pattern root's own subtree reaches
    -- so even though the target exists, it must resolve under none of
    them.

    This docstring claimed until 2026-10-04 that the fixture "mirrors the real
    escaping citations exactly -- `../../REFERENCES.md` from
    `hexagonal/reference/`". It did not, in two ways. Those citations were
    removed from the catalogue by `56ae369`, which is an ancestor of this
    task's own base commit, so they were already gone when this test was
    written -- there are zero `../` citations in the catalogue today. And the
    real ones were *dangling* (`56ae369`'s message: the target "has never
    existed in this repo"), while this fixture deliberately writes the target
    so that it exists, making it escaping-but-present -- the opposite fact
    pattern. The test is sound and discriminating either way; only the
    illustration was false. Found by T2.4's code-quality review."""
    companions = _load_companions()
    _write_pattern_file(
        tmp_path,
        "alpha",
        "reference/notes.md",
        "Climbs out: see `../REFERENCES.md`.\n",
    )
    (tmp_path / "REFERENCES.md").write_text("sibling to every pattern directory, inside none of them\n")
    _write_pattern_file(tmp_path, "beta", "SKILL.md", "an unrelated second pattern, so there is something to miss\n")

    assert companions.companion_map(tmp_path) == {}


def test_a_marker_with_no_resolving_path_is_not_an_edge(tmp_path: Path) -> None:
    """Does not derive from the `tcs-patterns:<name>` marker -- it means
    "mentions", not "breaks when installed alone". This fixture carries the
    marker with no accompanying path at all, proving the marker's presence
    alone is not what the derivation keys on
    `[ref: SDD/Interface Specifications/Data model: companion map]`."""
    companions = _load_companions()
    _write_pattern_file(
        tmp_path,
        "alpha",
        "reference/notes.md",
        "See also `tcs-patterns:beta` for background; nothing here names a file.\n",
    )
    _write_pattern_file(tmp_path, "beta", "reference/shared.md", "present, but never named by alpha\n")

    assert companions.companion_map(tmp_path) == {}


def test_an_own_pattern_match_wins_over_a_coincidental_match_elsewhere(tmp_path: Path) -> None:
    """Measured in the real catalogue: `node-service` and `observability`
    both carry a `reference/node-patterns.md`, and `node-service`'s own
    citation of its own file must not read as a companion edge to
    `observability` just because an identically-named file happens to exist
    there too. Resolving under the citing pattern's own root must win
    regardless of what else coincidentally matches
    `[ref: plugins/tcs-patterns/skills/patterns-setup/lib/companions.py]`."""
    companions = _load_companions()
    _write_pattern_file(
        tmp_path,
        "alpha",
        "SKILL.md",
        "Read `reference/shared.md` for the workflow.\n",
    )
    _write_pattern_file(tmp_path, "alpha", "reference/shared.md", "alpha's own file\n")
    _write_pattern_file(tmp_path, "zeta", "reference/shared.md", "a same-named file in an unrelated pattern\n")

    assert companions.companion_map(tmp_path) == {}


def test_a_bare_filename_with_no_directory_is_never_a_candidate(tmp_path: Path) -> None:
    """The candidate filter requires a `/` -- not a "looks like a path"
    heuristic but what keeps the existence check safe against a bare
    filename that happens to sit at the top of some unrelated pattern's
    directory `[ref: plugins/tcs-patterns/skills/patterns-setup/lib/
    companions.py, "_candidate_targets"]`. This fixture isolates that filter
    from the own-root-exclusion rule: `alpha` has no `shared.md` of its own
    (so the own-match safety net never fires here), yet `beta` genuinely
    carries one at its root. Without the slash requirement, the bare
    mention below would resolve under `beta` and misread as a companion
    edge."""
    companions = _load_companions()
    _write_pattern_file(tmp_path, "alpha", "reference/notes.md", "See `shared.md` for background.\n")
    _write_pattern_file(tmp_path, "beta", "shared.md", "coincidentally present at beta's root, not a citation target\n")

    assert companions.companion_map(tmp_path) == {}


def test_a_path_resolving_under_two_other_patterns_is_ambiguous_not_guessed(tmp_path: Path) -> None:
    """Treat a path resolving under more than one other pattern as
    ambiguous rather than picking one `[ref: SDD/Interface Specifications/
    Data model: companion map]`. `beta` and `gamma` each carry an identical
    `reference/shared.md`; `alpha`'s citation of the bare path cannot be
    resolved to either without guessing, so it must contribute no edge and
    must be reported, not silently dropped."""
    companions = _load_companions()
    _write_pattern_file(
        tmp_path,
        "alpha",
        "reference/notes.md",
        "See `reference/shared.md` for the shared concern.\n",
    )
    _write_pattern_file(tmp_path, "beta", "reference/shared.md", "beta's copy\n")
    _write_pattern_file(tmp_path, "gamma", "reference/shared.md", "gamma's copy\n")

    assert companions.companion_map(tmp_path) == {}
    ambiguous = companions.ambiguous_citations(tmp_path)
    assert len(ambiguous) == 1
    assert ambiguous[0].target == "reference/shared.md"
    assert ambiguous[0].candidate_patterns == ("beta", "gamma")


def test_a_symlink_leading_out_of_a_pattern_does_not_resolve_under_it(tmp_path: Path) -> None:
    """`beta/reference/shared.md` is a symlink to a file in `gamma`. Lexically
    `reference/shared.md` sits under beta; resolved, it lands in gamma, and
    gamma has no file at that relative path -- so alpha's citation reaches
    neither and contributes no edge. Pins that each candidate is still
    resolved after the pattern-root resolve was hoisted out of the
    per-candidate check (PR #176 M3): a prefix check on the unresolved path
    would report alpha -> beta."""
    companions = _load_companions()
    _write_pattern_file(tmp_path, "alpha", "SKILL.md", "See `reference/shared.md`.\n")
    _write_pattern_file(tmp_path, "gamma", "elsewhere/real.md", "gamma's file\n")
    (tmp_path / "beta" / "reference").mkdir(parents=True)
    (tmp_path / "beta" / "reference" / "shared.md").symlink_to(tmp_path / "gamma" / "elsewhere" / "real.md")

    assert companions.companion_map(tmp_path) == {}
    assert companions.ambiguous_citations(tmp_path) == ()


def test_a_markdown_link_citation_is_a_candidate_too(tmp_path: Path) -> None:
    """`_candidate_targets` extracts from two surfaces -- inline code spans and
    `[text](href)` markdown links -- and **only the first produces any edge in
    the real catalogue**. Measured 2026-10-04: of the 14 resolving citations,
    14 come from code spans and 0 from markdown links.

    So the link branch was dead to this suite. Deleting it entirely left all 16
    tests passing, confirmed by a code-quality review that ran the real test
    file against a mutated scratch copy, and no fixture here wrote
    `[text](path)` syntax at all. A branch no test can reach is a branch that
    silently stops working: the catalogue uses one surface today and nothing
    would notice the other breaking before a pattern author used it.
    """
    _write_pattern_file(tmp_path, "beta", "reference/shared.md", "# shared\n")
    _write_pattern_file(
        tmp_path, "alpha", "SKILL.md",
        "See [the shared note](reference/shared.md) in `tcs-patterns:beta`.\n",
    )

    companions = _load_companions()
    assert companions.companion_map(tmp_path) == {"alpha": frozenset({"beta"})}


def test_a_hidden_directory_in_the_catalogue_is_not_a_pattern(tmp_path: Path) -> None:
    """`pattern_names` filters dot-directories, and nothing exercised it: the
    real catalogue has none today, so removing the filter left all 16 tests
    green (measured 2026-10-04 in a scratch copy of the repo).

    The filter is not hypothetical. Running a single Bash call with the
    catalogue as its working directory makes the harness create
    `.claude/.cc-writes` there; it is gitignored, so `git status` shows a clean
    tree, and the same stray broke three unrelated suites the day this filter
    was written.

    This fixture plants a hidden directory holding **the same relative path**
    `beta` holds, so without the filter the citation resolves under two roots at
    once, is classified **ambiguous**, and is dropped: the map comes back
    `{}` and a **real** edge is lost. Measured, because the first version of
    this docstring said the map "gains a spurious edge", which is a different
    failure mode and not this one -- the mutant yields
    `assert {} == {'alpha': frozenset({'beta'})}`, and
    `ambiguous_citations` reports `('.claude', 'beta')`. The companion case
    below covers the spurious-edge mode, which is real but which this fixture
    cannot reach.
    """
    _write_pattern_file(tmp_path, "beta", "reference/shared.md", "# shared\n")
    _write_pattern_file(tmp_path, ".claude", "reference/shared.md", "# stray\n")
    _write_pattern_file(
        tmp_path, "alpha", "SKILL.md",
        "See `reference/shared.md` in `tcs-patterns:beta`.\n",
    )

    companions = _load_companions()
    assert companions.companion_map(tmp_path) == {"alpha": frozenset({"beta"})}
    assert companions.ambiguous_citations(tmp_path) == ()


def test_a_hidden_directory_cannot_supply_a_companion_edge(tmp_path: Path) -> None:
    """The other half of the hidden-directory filter, and the failure mode the
    test above was mistakenly documented as catching: a stray `.claude` holding
    a file that **nothing else holds**.

    The two modes are genuinely different and only one is reachable per fixture.
    Measured 2026-10-04 against a mutant with the filter removed:

        colliding fixture (above)   map == {}                  a real edge is LOST
        this fixture                map == {"alpha": {".claude"}}   a false edge is GAINED

    A lost edge means a companion the user is never offered. A gained edge means
    a companion that does not exist, named after a directory the harness created
    while someone ran a grep. The second is the worse report and was the one
    nothing asserted.
    """
    _write_pattern_file(tmp_path, "beta", "reference/other.md", "# other\n")
    _write_pattern_file(tmp_path, ".claude", "reference/only-here.md", "# stray\n")
    _write_pattern_file(
        tmp_path, "alpha", "SKILL.md",
        "See `reference/only-here.md` for the details.\n",
    )

    companions = _load_companions()
    assert companions.companion_map(tmp_path) == {}
    assert companions.ambiguous_citations(tmp_path) == ()


# --- T5.1a: companion_citations(), the citation behind each edge -------------


def test_companion_citations_outer_keys_equal_the_companion_map_edges() -> None:
    """Filled in the same `derive` pass, so its two outer key levels equal
    `companion_map()`'s edges by construction -- asserted rather than
    trusted `[ref: SDD/Process contract: the CLI the skill drives, scan,
    "companion_citations() is new"]`. Every edge carries at least one
    citation, and each `source_file` is catalogue-relative: joined to the
    catalogue it names a file inside the citing pattern."""
    companions = _load_companions()
    citations = companions.companion_citations(REAL_CATALOGUE_DIR)

    assert {source: frozenset(targets) for source, targets in citations.items()} == companions.companion_map(
        REAL_CATALOGUE_DIR
    )
    for source, targets in citations.items():
        for target, cited in targets.items():
            assert cited, f"{source} -> {target} has no citation"
            for citation in cited:
                assert not Path(citation.source_file).is_absolute(), citation
                assert (REAL_CATALOGUE_DIR / citation.source_file).is_file(), citation
                assert Path(citation.source_file).parts[0] == source, citation
                assert citation.line >= 1, citation


def test_companion_citations_names_the_citing_file_and_line(tmp_path: Path) -> None:
    """Hand-typed expectation on a two-pattern catalogue: the citing file
    (catalogue-relative), the 1-based line, and the target as written."""
    companions = _load_companions()
    _write_pattern_file(tmp_path, "alpha", "SKILL.md", "citing pattern\n")
    _write_pattern_file(
        tmp_path,
        "alpha",
        "reference/notes.md",
        "# Notes\n\nSee `tcs-patterns:beta` `reference/shared.md` for the rest.\n\n"
        "And again: [shared](reference/shared.md).\n",
    )
    _write_pattern_file(tmp_path, "beta", "SKILL.md", "target pattern\n")
    _write_pattern_file(tmp_path, "beta", "reference/shared.md", "the file alpha's citation reaches\n")

    Citation = companions.Citation
    assert companions.companion_citations(tmp_path) == {
        "alpha": {
            "beta": (
                Citation(source_file="alpha/reference/notes.md", line=3, target="reference/shared.md"),
                Citation(source_file="alpha/reference/notes.md", line=5, target="reference/shared.md"),
            )
        }
    }
    with pytest.raises(dataclasses.FrozenInstanceError):
        Citation(source_file="a", line=1, target="b").line = 2


def test_an_own_directory_citation_and_an_ambiguous_one_yield_no_citations(tmp_path: Path) -> None:
    """Hand-typed: `alpha` cites a file in its own directory (internal, never
    a companion) and one resolving under both `beta` and `gamma` (ambiguous,
    no edge). Neither may reach `companion_citations()`."""
    companions = _load_companions()
    _write_pattern_file(
        tmp_path,
        "alpha",
        "SKILL.md",
        "Own: `reference/own.md`. Ambiguous: `reference/shared.md`.\n",
    )
    _write_pattern_file(tmp_path, "alpha", "reference/own.md", "alpha's own file\n")
    _write_pattern_file(tmp_path, "beta", "reference/shared.md", "beta's copy\n")
    _write_pattern_file(tmp_path, "gamma", "reference/shared.md", "gamma's copy\n")

    assert companions.companion_citations(tmp_path) == {}
