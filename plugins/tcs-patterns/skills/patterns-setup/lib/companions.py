"""The tcs-patterns companion map (spec-020 T2.4).

C5 copies **one** pattern directory into a consumer repository
`[ref: SDD/Runtime View]`. Pattern files cite each other's files -- install
`ddd` alone and `ddd/reference/testing-by-layer.md`'s citation of
`reference/testing-hex-arch.md`, a file living in `hexagonal/`, resolves to
nothing in the consumer repo. This module derives, from the catalogue itself,
which pattern a citation like that actually reaches, so C3 can offer the
companion before the user finishes deciding
`[ref: SDD/Interface Specifications/Data model: companion map; ADR-10]`.

`companion_map()` and `expand_companions()` are the two things C3 reads: the
direct edges, and the transitive closure a selection pulls in.
`companion_citations()` (T5.1a) returns the citations behind each edge, so a
proposed companion can arrive with the citation that justified it named. Each
of the four walks the whole catalogue; a caller wanting more than one answer
(`cli.py scan` wants three) calls `derive()` once and reads the `Derivation`
-- one walk measured ~0.75s on the real catalogue (PR #176 M3). All four,
like `derive()`, take the catalogue root as a parameter,
defaulting to the real one (`paths.DEFAULT_CATALOGUE_DIR`) -- the same shape
`detect(repo_dir)` takes the repository root -- so a test can derive against
a throwaway `tmp_path` catalogue and never write into
`plugins/tcs-patterns/templates/patterns/` itself
`[ref: docs/XDD/specs/020-tcs-patterns-selective-install/plan/phase-2.md#T2.4]`.

**Reuses, from `tests/test_tcs_patterns_catalogue_links.py`:** the extraction
plumbing only -- `FENCE`, `INLINE_CODE`, `LINK` and the fenced-block skip
copied below (that module copies the same three from `test_docs_links.py` for
the same reason: three regexes and a one-line toggle are not worth reaching
into a sibling module for), and the idea of `_pattern_root`. **Does not
reuse** that module's resolution rule: it requires a leading `../` climb and
resolves relative to the *citing* file's directory, which is right for "does
this escape its own pattern" and wrong for this map -- real companion
citations never climb, and the path is relative to the **target** pattern's
root, with a `tcs-patterns:<name>` marker naming the target in prose beside
it:

    ddd/reference/testing-by-layer.md:3
      ... see `tcs-patterns:hexagonal` `reference/testing-hex-arch.md`.

A derivation built on the `../`-climb rule finds **zero** edges here,
measured. This module does not read the marker either -- a marker means
"mentions" (43 edges in this catalogue) where a resolving path means "breaks
when installed alone" (7), and the second is the defect this map exists to
prevent
`[ref: SDD/Interface Specifications/Data model: companion map, "How the
citations are actually written, and why the path rule is the right one"]`.

**The resolution rule.** A candidate (a `/`-containing inline-code-span or
markdown-link target, on a non-fenced line) is resolved against **every**
pattern's root in turn, as `pattern_root / candidate`. A candidate that
resolves under its *own* citing pattern's root is an internal cross-reference
and never a companion, regardless of what else it coincidentally matches
elsewhere (two patterns can and do carry an identically-named
`reference/*.md`; measured in this catalogue --
`node-service/reference/node-patterns.md` and
`observability/reference/node-patterns.md` both exist, and a scan that did
not check the citing pattern's own root first would misread node-service's
self-reference as a companion edge to observability). Failing that, a
candidate resolving under **exactly one** other pattern's root is a companion
edge; under **more than one**, it is ambiguous and contributes no edge --
zero are ambiguous in the real catalogue today, which `ambiguous_citations()`
exists to make audible the day one appears
`[ref: SDD/Interface Specifications/Data model: companion map]`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import paths

# Copied from `tests/test_tcs_patterns_catalogue_links.py` (plumbing only, see
# module docstring) rather than imported: a test module is not a dependency
# this production module should carry.
FENCE = re.compile(r"^\s*(```|~~~)")
INLINE_CODE = re.compile(r"`([^`]*)`")
LINK = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")

EXTERNAL_PREFIXES = ("http://", "https://", "mailto:", "tel:")


def _non_fenced_lines(text: str):
    """Yield `(line number, raw line)` with fenced code blocks dropped, so a
    fenced example quoting citation syntax literally is never read as a real
    one -- same reason the link test does this."""
    in_fence = False
    for n, line in enumerate(text.splitlines(), 1):
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        yield n, line


def pattern_names(catalogue_root: Path) -> list[str]:
    """Every pattern directory directly under `catalogue_root`, sorted -- the
    one definition of "a catalogue pattern" `install.py` and `cli.py` read
    too (PR #176 M6). Filters
    hidden entries -- a stray `.claude/.cc-writes` created by a Bash call
    that happened to `cd` into the real catalogue directory would otherwise
    be counted as a 22nd pattern, the same incident `tests/visible_dirs.py`
    documents for the detection corpus. Not imported from there: this is
    production code and must not depend on the test tree."""
    return sorted(p.name for p in Path(catalogue_root).iterdir() if p.is_dir() and not p.name.startswith("."))


def _pattern_root(path: Path, catalogue_root: Path) -> Path:
    """The pattern directory a catalogue file lives under."""
    rel = path.relative_to(catalogue_root)
    return catalogue_root / rel.parts[0]


def _candidate_targets(text: str):
    """Yield `(line number, target)` for every inline-code-span or
    markdown-link path on a non-fenced line that could plausibly name a file
    elsewhere in the catalogue.

    The one filter applied here -- the target must contain a `/` -- is not a
    "looks like a path" heuristic; it is what the existence check below
    needs to be safe. A bare filename with no directory (`SKILL.md`,
    `GLOSSARY.md`) sits at the top of *every* pattern directory or none, so
    without this filter a bare `` `SKILL.md` `` mention would resolve under
    nearly every other pattern's root at once and read as a mass-ambiguous
    citation it never was. Every real companion citation in this catalogue
    already has the `reference/...` form, so this filter drops no edge
    `[ref: SDD/Interface Specifications/Data model: companion map]`."""
    for n, line in _non_fenced_lines(text):
        for content in INLINE_CODE.findall(line):
            target = content.strip()
            if target and "/" in target and not target.startswith(EXTERNAL_PREFIXES):
                yield n, target

        blanked = INLINE_CODE.sub("``", line)  # a span quoting literal [text](href) syntax is not a link
        for _text, href in LINK.findall(blanked):
            href = href.strip()
            if not href or href.startswith(EXTERNAL_PREFIXES) or href.startswith("#"):
                continue
            target = href.split("#", 1)[0].split("?", 1)[0]
            if target and "/" in target:
                yield n, target


def _resolves_under(pattern_root: Path, target: str) -> bool:
    """Whether `target`, taken as a path relative to `pattern_root`, names an
    existing file that stays inside `pattern_root` -- a citation that climbs
    out via `../` and happens to land elsewhere does not count, which is also
    why the `../`-climb shape measures zero edges under this rule.

    `pattern_root` must already be resolved: `derive()` resolves each root
    once, not once per candidate (PR #176 M3). The candidate itself is still
    resolved here, so a symlink leading out of the root is judged by where it
    lands, never by its lexical prefix."""
    try:
        resolved = (pattern_root / target).resolve()
    except (OSError, ValueError):
        return False
    try:
        resolved.relative_to(pattern_root)
    except ValueError:
        return False
    return resolved.is_file()


@dataclass(frozen=True)
class AmbiguousCitation:
    """A candidate that resolved under more than one *other* pattern's root
    -- contributes no edge to the map `[ref: SDD/Interface Specifications/
    Data model: companion map]`."""

    source_file: str
    line: int
    target: str
    candidate_patterns: tuple[str, ...]


@dataclass(frozen=True)
class Citation:
    """One citation that produced a companion edge -- shaped like
    `AmbiguousCitation` without `candidate_patterns`. `source_file` is
    relative to the catalogue root, `line` is 1-based, and `target` is the
    path as written in the citing file `[ref: SDD/Process contract: the CLI
    the skill drives, scan, "companion_citations() is new"]`."""

    source_file: str
    line: int
    target: str


@dataclass(frozen=True)
class Derivation:
    """One walk of the catalogue: what `companion_map()`,
    `companion_citations()` and `ambiguous_citations()` each return, and the
    closure `expand_companions()` takes over `edges`."""

    edges: dict[str, frozenset[str]]
    ambiguous: tuple[AmbiguousCitation, ...]
    citations: dict[str, dict[str, tuple[Citation, ...]]]

    def expand(self, selected) -> frozenset[str]:
        """The transitive closure of `selected`'s companions, excluding the
        selections themselves -- so a caller can present "and these come
        with it" without filtering `[ref: SDD/Interface Specifications/Data
        model: companion map, "Expansion is the transitive closure"]`.

        Carries a visited set seeded with `selected` itself: `ddd`/`hexagonal`
        and `event-driven`/`event-sourcing` are mutual companions, so an
        unguarded walk from any of the four never terminates. The walk is
        iterative, not recursive, so there is no call-stack depth to exhaust
        either way `[ref: ADR-10, "Expansion is the transitive closure, not
        one hop"]`."""
        selected_set = set(selected)
        visited = set(selected_set)
        result: set[str] = set()
        stack = list(selected_set)

        while stack:
            current = stack.pop()
            for companion in self.edges.get(current, ()):
                if companion in visited:
                    continue
                visited.add(companion)
                result.add(companion)
                stack.append(companion)

        return frozenset(result)


def derive(catalogue_root: Path = paths.DEFAULT_CATALOGUE_DIR) -> Derivation:
    """Walk `catalogue_root` once and return every answer this module gives
    (PR #176 M3)."""
    catalogue_root = Path(catalogue_root)
    pattern_roots = {name: (catalogue_root / name).resolve() for name in pattern_names(catalogue_root)}

    edges: dict[str, set[str]] = {}
    ambiguous: list[AmbiguousCitation] = []
    citations: dict[str, dict[str, list[Citation]]] = {}

    for path in sorted(catalogue_root.rglob("*.md")):
        own = _pattern_root(path, catalogue_root).name
        source_file = str(path.relative_to(catalogue_root))
        text = path.read_text(encoding="utf-8")
        for line_no, target in _candidate_targets(text):
            matches = sorted(name for name, root in pattern_roots.items() if _resolves_under(root, target))

            if own in matches:
                # Resolves inside the citing pattern's own root -- an internal
                # cross-reference, never a companion, regardless of what else
                # it coincidentally matches elsewhere. See the module
                # docstring's node-service/observability example.
                continue
            if not matches:
                continue
            if len(matches) > 1:
                ambiguous.append(
                    AmbiguousCitation(
                        source_file=source_file,
                        line=line_no,
                        target=target,
                        candidate_patterns=tuple(matches),
                    )
                )
                continue
            edges.setdefault(own, set()).add(matches[0])
            citations.setdefault(own, {}).setdefault(matches[0], []).append(
                Citation(source_file=source_file, line=line_no, target=target)
            )

    return Derivation(
        edges={source: frozenset(targets) for source, targets in edges.items()},
        ambiguous=tuple(ambiguous),
        citations={
            source: {companion: tuple(cited) for companion, cited in by_companion.items()}
            for source, by_companion in citations.items()
        },
    )


def companion_map(catalogue_root: Path = paths.DEFAULT_CATALOGUE_DIR) -> dict[str, frozenset[str]]:
    """The direct companion edges, derived from `catalogue_root` -- the real
    catalogue equals the seven measured pattern-to-pattern edges
    `[ref: SDD/Interface Specifications/Data model: companion map; ADR-10]`.
    A pattern with no outgoing edge is simply absent as a key, never present
    with an empty set."""
    return derive(catalogue_root).edges


def companion_citations(
    catalogue_root: Path = paths.DEFAULT_CATALOGUE_DIR,
) -> dict[str, dict[str, tuple[Citation, ...]]]:
    """source -> companion -> the citations that produced that edge, in
    file-then-line order. Filled in the same `derive` pass as
    `companion_map()`, so its two outer key levels equal that map's edges by
    construction; `source_file` is catalogue-relative, as `derive` writes it
    for `AmbiguousCitation` `[ref: SDD/Process contract: the CLI the skill
    drives, scan, "companion_citations() is new"]`."""
    return derive(catalogue_root).citations


def ambiguous_citations(catalogue_root: Path = paths.DEFAULT_CATALOGUE_DIR) -> tuple[AmbiguousCitation, ...]:
    """Candidates excluded from `companion_map()` because they resolved under
    more than one other pattern's root. Empty against the real catalogue
    today; exists so the day one appears, the suite says so rather than
    silently picking one
    `[ref: SDD/Interface Specifications/Data model: companion map]`."""
    return derive(catalogue_root).ambiguous


def expand_companions(selected, catalogue_root: Path = paths.DEFAULT_CATALOGUE_DIR) -> frozenset[str]:
    """`derive(catalogue_root).expand(selected)` -- see `Derivation.expand`
    for the closure rule and its cycle guard."""
    return derive(catalogue_root).expand(selected)
