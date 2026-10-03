"""T1.3 (spec-020): no relative path inside the pattern catalogue breaks when the pattern
it lives in is copied out on its own.

Why this exists: C5 copies one pattern directory (`templates/patterns/<name>/`) into a
consumer repo -- never the whole catalogue, and never the rest of this repo. A relative
path that happens to resolve *today*, from inside this checkout, can point at something
that simply will not exist once the pattern is standing alone. Two distinct ways that
happens, both exercised here because they are not the same failure:

  - Escape: the path climbs above its own pattern directory (`../../REFERENCES.md` from
    `hexagonal/reference/` lands on `templates/patterns/REFERENCES.md` -- sibling-pattern
    territory that is never copied with `hexagonal/`). Broken on arrival regardless of
    whether anything sits there in this checkout.
  - Resolve: the path stays inside its own pattern directory but names a file that was
    never created (`../REFERENCES.md` from `hexagonal/reference/` lands on
    `templates/patterns/hexagonal/REFERENCES.md`, which nobody wrote).

Two checks, not one module-wide regex, because the two real shapes in this catalogue are
caught by different extraction code: a handful of sites are honest Markdown links
(`[text](href)`), spotted the same way `test_docs_links.py` spots them; the rest are bare
paths quoted inside inline code spans with no link syntax at all
(``see `../../REFERENCES.md` for sources``), which that file's `_linkable_lines` throws
away on purpose -- it blanks code spans specifically so a *quoted* link (the plan-file
checklist example in `docs/reference/xdd.md`) is not mistaken for a real one. This module
inspects what that one discards, on a different surface (`templates/patterns/`, not the
user-facing docs tree), under a different rule (escape-from-pattern, not just resolves).
That is why the rule lives here rather than being folded into `test_docs_links.py`: that
module's docstring says "every relative link in the user-facing docs resolves" -- true
today, and would stop being true if a catalogue-only escape rule were bolted on. T1.2 set
the same precedent (`test_tcs_patterns_catalogue_version.py`, separate from
`test_tcs_patterns_catalogue_relocation.py`) for the same reason: a catalogue-shape
contract that outlives one task gets its own file.

A code-span candidate is only treated as a path worth checking when it starts with `../`
-- climbing out is the one unambiguous "this is meant to be a filesystem reference" signal
in this catalogue. Everything else quoted in a span (`reference/api-patterns.md` pointing
into the writer's own `reference/` directory, `src/main.ts` illustrating a consumer's file
tree, `/orders/{id}` an HTTP route, `worked-example.md` a bare filename in a "load when"
table, `docs/about/sources.md` a provenance pointer meant to be read from the source repo)
is prose, not a link -- confirmed by scanning every pattern in the catalogue for inline
code spans containing `/` before writing this regex: every shape other than a `../` climb
or a real Markdown link was one of those five, and none of them is a navigable reference
that this rule is meant to police.

`FENCE`, `INLINE_CODE` and `LINK` are duplicated from `test_docs_links.py` rather than
imported -- three regexes and a one-line fence toggle, not worth reaching into a sibling
test module for.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CATALOGUE_DIR = REPO_ROOT / "plugins" / "tcs-patterns" / "templates" / "patterns"

FENCE = re.compile(r"^\s*(```|~~~)")
INLINE_CODE = re.compile(r"`([^`]*)`")
LINK = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")

EXTERNAL_PREFIXES = ("http://", "https://", "mailto:", "tel:")

# See the module docstring's last paragraph for why only an explicit `../` climb
# qualifies a bare code-span path as a candidate.
CODE_SPAN_PATH = re.compile(r"^(?:\.\./)+[\w\-./]*\.[A-Za-z0-9]+$")


def _display(path: Path) -> str:
    """Repo-relative where possible, so a failure names a path you can open."""
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


def _catalogue_files() -> list[Path]:
    assert CATALOGUE_DIR.is_dir(), f"{CATALOGUE_DIR} does not exist -- has the catalogue moved?"
    return sorted(CATALOGUE_DIR.rglob("*.md"))


def _pattern_root(path: Path) -> Path:
    """The pattern directory (`templates/patterns/<name>/`) a catalogue file lives under --
    the boundary the escape rule enforces, one per pattern, not one for the whole catalogue
    (C5 copies a single pattern directory, never its siblings)."""
    rel = path.relative_to(CATALOGUE_DIR)
    return CATALOGUE_DIR / rel.parts[0]


def _non_fenced_lines(text: str):
    """Yield (line number, raw line) with fenced blocks dropped -- same reason as
    `test_docs_links.py`'s version: a fenced example quoting link or path syntax literally
    must not be read as a real one."""
    in_fence = False
    for n, line in enumerate(text.splitlines(), 1):
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        yield n, line


def _violation(path: Path, target: str, n: int) -> str | None:
    """Apply both rules to one candidate relative path. Escape is checked first and
    independently of existence: a path that climbs out of its pattern directory is wrong
    on arrival even when something might exist at the far end in this checkout, because
    when C5 copies a single pattern directory to a consumer repository, the far end does
    not travel with it. Therefore escaping is defective regardless of what this repository
    contains. For example, a hypothetical `../../README.md` from a pattern's `reference/`
    directory would resolve to a file that does exist here and is still wrong once the
    pattern is installed alone. The relocation of obsidian-plugin/SKILL.md deepened the
    path by one level, breaking its four-../ link in the working tree as well."""
    pattern_root = _pattern_root(path).resolve()
    resolved = (path.parent / target).resolve()
    try:
        resolved.relative_to(pattern_root)
    except ValueError:
        return f"{_display(path)}:{n}: `{target}` escapes its pattern directory ({_display(pattern_root)}) -- resolves to {_display(resolved)}"
    if not resolved.exists():
        return f"{_display(path)}:{n}: `{target}` does not resolve to an existing file -- would be {_display(resolved)}"
    return None


def test_no_markdown_link_in_the_catalogue_escapes_or_dangles():
    """Catches links written with real Markdown syntax, `[text](href)` -- today that is
    exactly one site (`obsidian-plugin/SKILL.md`'s link to the Hooks section of the user
    docs, which escapes the pattern directory the link's own file ships inside)."""
    offenders = []
    for path in _catalogue_files():
        for n, line in _non_fenced_lines(path.read_text(encoding="utf-8")):
            blanked = INLINE_CODE.sub("``", line)  # a span quoting literal [text](href) syntax is not a link
            for _text, href in LINK.findall(blanked):
                href = href.strip()
                if href.startswith(EXTERNAL_PREFIXES) or href.startswith("#") or not href:
                    continue
                target = href.split("#", 1)[0].split("?", 1)[0]
                if not target:
                    continue  # pure anchor, e.g. (#installation)
                violation = _violation(path, target, n)
                if violation:
                    offenders.append(violation)

    assert not offenders, (
        f"{len(offenders)} catalogue Markdown link(s) escape their pattern directory or do not resolve:\n"
        + "\n".join(offenders)
    )


def test_no_code_span_path_in_the_catalogue_escapes_or_dangles():
    """Catches bare `../`-climbing paths quoted in inline code spans with no link syntax --
    today that is the three attribution sites in `hexagonal/` and `ddd/` reference files
    that point at a `REFERENCES.md` which has never existed in this repository."""
    offenders = []
    for path in _catalogue_files():
        for n, line in _non_fenced_lines(path.read_text(encoding="utf-8")):
            for content in INLINE_CODE.findall(line):
                target = content.strip()
                if not CODE_SPAN_PATH.match(target):
                    continue
                violation = _violation(path, target, n)
                if violation:
                    offenders.append(violation)

    assert not offenders, (
        f"{len(offenders)} catalogue code-span path(s) escape their pattern directory or do not resolve:\n"
        + "\n".join(offenders)
    )
