"""The tcs-patterns collision guard (spec-020 T3.2/T3.2b, component C4).

`check(repo_dir, intended_names, *, home_dir, own_installed)` partitions a
set of intended skill names into what C5 (T3.3) may safely install, what it
must refuse, and what this guard could not evaluate at all. **This module
installs nothing** -- writing is C5's job in T3.3; C4 only decides
`[ref: docs/XDD/specs/020-tcs-patterns-selective-install/plan/phase-3.md#T3.2]`.

**`own_installed`, added in T3.2b.** T3.2 shipped checking the wrong
question -- "is this name taken?" instead of "would installing here create a
duplicate nobody can resolve?" `[ref: SDD/Constraints/CON-3]` -- which made
this guard refuse the very pattern this tool had itself installed on a prior
run, since an installed pattern registers in the REPOSITORY namespace under
exactly the name C3 checks next time. `own_installed` carries the
manifest's `installed_as` values for this repository; a repo-namespace hit
whose name is a member passes through to `approved` instead of being
refused. Three boundaries, all enforced only on the repo namespace: a user-
or plugin-namespace hit is always somebody else's regardless of
`own_installed`; the parameter is required, with no default, so a caller
that forgets it fails loudly rather than silently reintroducing the bug;
and an empty set -- the safe fallback when a caller cannot read the
manifest -- reproduces the pre-T3.2b behaviour exactly
`[ref: SDD/Interface Specifications/Data model: the three namespaces (C4),
"own_installed is required, and it exists because this guard otherwise
refuses our own earlier work"]`.

Four facts, measured on a live installation, decide how this is implemented
-- an implementer working from the contract's prose alone would get at
least two of them wrong without a fixture revealing it
`[ref: SDD/Interface Specifications/Data model: the three namespaces (C4)]`:

1. **A skill's name is its frontmatter `name:`, never its directory.**
   Measured over 259 real `SKILL.md` files: exactly one diverges (the
   `hookify` plugin's `writing-rules/` directory registers as
   `writing-hookify-rules`). A guard keyed on directory names would look
   for the wrong name and miss the right one.
2. **A skills directory can contain things that are not skills, and real
   skills sit at more than one depth.** `~/.claude/skills/synced/` has no
   `SKILL.md` of its own and holds real skills three levels down, at
   `synced/<uuid>/<name>/SKILL.md`. The walk has to be unbounded in depth,
   and a directory with no `SKILL.md` must not occupy its own name.
3. **The plugin cache holds several versions of one plugin; the names are
   unioned across all of them, never compared.** The marketplace tree holds
   one directory per plugin under either of two segment names
   (`plugins/`, `external_plugins/`), never a literal `plugins` segment.
4. **Reachability (`enabledPlugins`) is deliberately not consulted.** This
   guard enumerates every plugin skill it can find, enabled or not --
   over-inclusion costs one declined proposal, and under-inclusion writes a
   duplicate that goes live the moment someone enables that plugin later
   `[ref: SDD/.../"The decision: enumerate broadly and ignore reachability"]`.

```
check(repo_dir, intended_names, *, home_dir) -> GuardReport

namespace roots, in the order a refusal reports them:
    repo    <repo_dir>/.claude/skills/
    user    <home_dir>/.claude/skills/
    plugin  <home_dir>/.claude/plugins/cache/*/*/*/skills/
            <home_dir>/.claude/plugins/marketplaces/*/*/*/skills/
```

**`home_dir` is a parameter, never `Path.home()`.** Two of the three
namespaces live outside the repository, so a guard that read the real
`$HOME` internally could not be driven by a fixture at all -- the same
convention this repository already settled twice
`[ref: scripts/observability/report.py:686; scripts/observability/sources.py:349]`.

**Enumeration is `os.walk(root, followlinks=True)` with an `(st_dev,
st_ino)` dedup, deliberately not `rglob`/`glob("**")` (miss a symlinked
skill directory -- measured, 18 of 19 in the live user namespace) and not
`glob(recurse_symlinks=True)` (3.13+ only; ADR-2's floor is 3.11)
`[ref: SDD/.../"The enumeration is os.walk(followlinks=True)"]`.** The
dedup is applied while descending -- a child directory is stat'd before
`os.walk` is allowed to recurse into it, and pruned from `dirnames` if its
`(st_dev, st_ino)` was already visited. This is what keeps a
self-referential symlink from ever reaching the `ELOOP` macOS would raise
without it (measured: 66 redundant visits, reduced to 3), and what keeps
two symlinks to one real directory from reporting the same skill -- or the
same malformed file -- twice.

**No defensive `OSError` guard around the dedup's own `stat()` calls.**
Removed after T3.2's fix round, 2026-10-05: three mutations of those guards
survived every test, and no constructible fixture reaches them --
`os.walk` itself classifies a dangling symlink as a *file* (verified: it
never appears in `dirnames`, so the dedup never stats it), and a symlink
behind an unreadable intermediate directory is never discovered in the
first place, because `os.walk` cannot list that intermediate to find it
(verified empirically, both ways). What stays reachable through an
unguarded `stat()` is a genuine race -- a directory removed between
`os.walk`'s own `scandir` and this dedup's `stat` -- and letting that
surface as an exception is correct, not a regression: this component's
whole stance is that a name it could not check must be *reported*, and an
exception is the loudest report available. A silent `except OSError:
continue` was the one branch here that failed that stance
`[ref: SDD/.../"No defensive OSError guard around the dedup's own stat()"]`.

**A directory this guard cannot list is skipped and reported too, not
silently treated as empty.** `os.walk`'s default `onerror=None` swallows a
directory-listing failure outright -- a `chmod 000` directory holding a
`SKILL.md` would otherwise make the guard **approve** that name with
`skipped` left empty, and an unreadable namespace *root* would lose that
whole namespace the same way (`root.is_dir()` is still `True` on such a
directory, so the missing-root check does not catch it). `_walk_skills`
passes `onerror=` and routes every such failure into `skipped`, covering
both the root and any unreadable intermediate directory
`[ref: SDD/.../"A directory the guard cannot list is skipped and reported
too"]`.

**Stdlib only, Python 3.11 floor** `[ref: SDD/Architecture Decisions/
ADR-2]` -- a plugin ships as files with no install step, so this module
parses the frontmatter `name:` itself rather than importing PyYAML.
`_skill_name` reads only the lines between the first two `---` delimiters;
nothing below that second delimiter is ever inspected, so a `name:`-shaped
line in the skill's body cannot be mistaken for its frontmatter.

**"Its frontmatter `name:`" means what a YAML parser makes of it, because
that is what the harness registers under.** A regex that captures
everything to end-of-line disagrees with real YAML on a trailing comment
(`name: ddd # comment` registers as `ddd`, not `ddd # comment`), a block
scalar (`>-`, `|`), a tag (`!!str`), an anchor (`&a`), and a duplicate
`name:` key (YAML takes the last, never the first). `parse_name_scalar`
below implements exactly two YAML scalar forms -- plain and quoted
(single or double) -- and **skips and reports anything else** rather than
guessing: a wrong name silently frees the real one, where a skip is at
least visible through `skipped`. Pinned by a differential test against a
real YAML parser in the test suite (`guard.py` itself stays stdlib-only)
`[ref: SDD/.../"Its frontmatter `name:` means what a YAML parser makes of
it"]`.

**`skipped` is a third channel, not an afterthought.** An unreadable file
or directory, or a `SKILL.md` with no usable frontmatter, is skipped,
never fatal -- the same stance `detect.py` takes for an unparseable
manifest, and for the same reason: a third party's broken file must not
stop this repository's install. It is reported as a `(path, reason)` pair
because something this guard could not check is a name it cannot vouch
for, and a caller that cannot see the omission cannot warn about it
`[ref: SDD/Error Handling, "A SKILL.md in a scanned namespace..."]`. Five
distinct inputs reach this -- a file that cannot be read, a file with no
frontmatter block at all, a frontmatter block that opens and never closes,
a frontmatter block with no `name:` key, and a `name:` whose value is
empty -- but they are not five distinct REASON strings: an unterminated
block and a missing block share "no usable frontmatter block", since both
are the same underlying fact from this parser's point of view. None of the
five occurs naturally (all 259 real files parse), so every one is
fixture-only.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

# Namespace labels, in the order a refusal reports them -- repo before user
# before plugin `[ref: plan/phase-3.md T3.2, requirement 7]`.
_REPO = "repo"
_USER = "user"
_PLUGIN = "plugin"

_FRONTMATTER_DELIM = "---"
_NAME_LINE_RE = re.compile(r"^name:(.*)$")

# YAML "indicator characters" that begin a construct this minimal parser
# does not implement: a block scalar (`>`, `|`), a tag (`!`), an anchor or
# alias (`&`, `*`), or a directive/reserved marker (`%`, `@`, `` ` ``). Any
# of these in lead position is a skip, never a guess
# `[ref: SDD/.../"Its frontmatter name: means what a YAML parser makes of
# it"]`.
_YAML_INDICATOR_CHARS = frozenset(">|!&*%@`")


@dataclass(frozen=True)
class GuardReport:
    """The whole result of one `check()` call. Named channels, not a
    positional tuple -- three values of three different shapes (a set of
    names, a map keyed by name, a sequence of file problems) is a return
    that gets unpacked wrong once and stays wrong, since two of the three
    are falsy-when-empty containers
    `[ref: SDD/.../"Named channels rather than a 3-tuple"]`.

    approved: the names no namespace already owns.
    refused:  name -> (namespace, path of the colliding SKILL.md).
    skipped:  (path, reason) for every SKILL.md or directory that could not
              be read, in discovery order -- a sequence, not a set, because
              two genuinely distinct problem files are still two entries
              even when their reasons read the same.
    """

    approved: frozenset[str]
    refused: dict[str, tuple[str, str]] = field(default_factory=dict)
    skipped: list[tuple[str, str]] = field(default_factory=list)


def parse_name_scalar(raw: str) -> tuple[str | None, bool]:
    """Parse the text after `name:` as a YAML scalar. Returns `(value,
    ok)`: `ok=False` means "this parser recognises nothing valid here --
    skip and report", which the caller must never second-guess by
    returning a value anyway.

    Implements exactly two YAML scalar forms: **plain** (unquoted, with an
    unquoted `#` preceded by whitespace beginning a comment) and
    **quoted** (single or double, with the one escape each form actually
    has -- `''` for a literal `'` in single-quoted, `\\"`/`\\\\` for
    double-quoted). Nothing else of YAML is implemented on purpose: a block
    scalar, a tag, an anchor, an alias, or a second `name:` key is always a
    skip, never an attempt to resolve it correctly
    `[ref: SDD/.../"Its frontmatter name: means what a YAML parser makes of
    it"]`.
    """
    text = raw.strip()
    if not text or text.startswith("#"):
        return None, True  # YAML null: no value, or the whole remainder is a comment

    if text[0] == '"':
        return _parse_double_quoted(text)
    if text[0] == "'":
        return _parse_single_quoted(text)
    if text[0] in _YAML_INDICATOR_CHARS:
        return None, False

    # Plain scalar: an unquoted '#' counts as a comment only when it is
    # preceded by whitespace -- `a#b` is the literal value `a#b`, but
    # `a #b` is the value `a` with a trailing comment.
    comment = re.search(r"\s#", text)
    value = text[: comment.start()] if comment else text
    return value.rstrip(), True


def _parse_double_quoted(text: str) -> tuple[str | None, bool]:
    out: list[str] = []
    i = 1
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == "\\":
            if i + 1 >= n:
                return None, False  # dangling escape: malformed
            nxt = text[i + 1]
            if nxt == '"':
                out.append('"')
            elif nxt == "\\":
                out.append("\\")
            elif nxt == "n":
                out.append("\n")
            elif nxt == "t":
                out.append("\t")
            else:
                return None, False  # an escape this minimal parser does not implement
            i += 2
            continue
        if ch == '"':
            trailer = text[i + 1 :].strip()
            if trailer and not trailer.startswith("#"):
                return None, False  # content after the closing quote that isn't a comment
            return "".join(out), True
        out.append(ch)
        i += 1
    return None, False  # never closed


def _parse_single_quoted(text: str) -> tuple[str | None, bool]:
    out: list[str] = []
    i = 1
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == "'":
            if i + 1 < n and text[i + 1] == "'":
                out.append("'")  # YAML single-quoted's one escape: '' -> a literal '
                i += 2
                continue
            trailer = text[i + 1 :].strip()
            if trailer and not trailer.startswith("#"):
                return None, False
            return "".join(out), True
        out.append(ch)
        i += 1
    return None, False  # never closed


def frontmatter_lines(text: str) -> list[str] | None:
    """The lines strictly between the first two `---` delimiter lines, or
    None when there is no well-formed block: the first line (after
    stripping) is not `---`, or no later line closes it. The one reader of
    the block's extent, shared by `_skill_name` and the CLI's description
    reader."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != _FRONTMATTER_DELIM:
        return None
    for i in range(1, len(lines)):
        if lines[i].strip() == _FRONTMATTER_DELIM:
            return lines[1:i]
    return None


def _skill_name(skill_md: Path) -> tuple[str | None, str | None]:
    """Return `(name, None)` on success or `(None, reason)` on any of the
    five skip cases. Reads only between the first two `---` delimiter
    lines -- the frontmatter block -- never the body below it."""
    try:
        text = skill_md.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return None, f"unreadable: {e}"

    block = frontmatter_lines(text)
    if block is None:
        # No block, or one opened with '---' and never closed -- the same
        # fact, from this parser's point of view; shares one reason rather
        # than inventing a sixth string for it.
        return None, "no usable frontmatter block"

    matches = [m for m in (_NAME_LINE_RE.match(line) for line in block) if m is not None]
    if not matches:
        return None, "no name: key"
    if len(matches) > 1:
        # YAML takes the last of a duplicate key; this parser refuses to
        # guess which one the harness would actually register under.
        return None, "duplicate name: key"

    value, ok = parse_name_scalar(matches[0].group(1))
    if not ok:
        return None, "unsupported YAML construct in name: value"
    if not value:
        return None, "empty name: value"
    return value, None


def _identity(path: Path) -> tuple[int, int]:
    st = path.stat()
    return st.st_dev, st.st_ino


def _walk_skills(root: Path):
    """Yield `(name, path, skip_reason)` for every `SKILL.md` under `root`,
    to any depth, following symlinks, with the `(st_dev, st_ino)` dedup
    applied before `os.walk` ever recurses into a child directory -- see
    the module docstring. `name` and `skip_reason` are mutually exclusive:
    exactly one is `None`. A directory this guard could not list is also
    yielded here, as `(None, that_directory, reason)`.

    A missing `root` yields nothing; it is empty, not an error
    `[ref: SDD/Error Handling, "A missing namespace directory is empty"]`.
    """
    if not root.is_dir():
        return

    unreadable_dirs: list[tuple[Path, str]] = []

    def _record_unreadable_dir(err: OSError) -> None:
        # os.walk calls this -- instead of raising -- whenever a
        # directory (the root itself or any intermediate) cannot be
        # scanned. Collected here and yielded after the walk completes,
        # so the failure lands in `skipped` instead of vanishing the way
        # the default `onerror=None` does
        # `[ref: SDD/.../"A directory the guard cannot list is skipped
        # and reported too"]`.
        path = Path(err.filename) if err.filename else root
        unreadable_dirs.append((path, f"directory unreadable: {err}"))

    visited = {_identity(root)}

    for dirpath, dirnames, filenames in os.walk(root, onerror=_record_unreadable_dir, followlinks=True):
        kept = []
        for name in dirnames:
            child = Path(dirpath) / name
            # No try/except around this stat(): os.walk has already
            # confirmed `child` is a directory to populate `dirnames` in
            # the first place, so this can only fail via a genuine race --
            # see the module docstring's "No defensive OSError guard"
            # section for why that must be allowed to raise rather than
            # be swallowed.
            key = _identity(child)
            if key in visited:
                continue  # already walked this real directory -- prune
            visited.add(key)
            kept.append(name)
        dirnames[:] = kept

        if "SKILL.md" in filenames:
            skill_md = Path(dirpath) / "SKILL.md"
            name, reason = _skill_name(skill_md)
            yield name, skill_md, reason

    for path, reason in unreadable_dirs:
        yield None, path, reason


def _plugin_roots(home_dir: Path) -> list[Path]:
    """The two plugin-namespace root families, cache then marketplace, each
    sorted for determinism. Both are three wildcards deep
    `[ref: SDD/.../"The two plugin roots exercised independently"]`; the
    marketplace's middle segment is a wildcard, never the literal
    `plugins`, because a live installation also has `external_plugins/`
    roots `[ref: SDD/.../"The marketplace glob is */*/*/skills"]`."""
    plugins_dir = home_dir / ".claude" / "plugins"
    cache_roots = sorted(plugins_dir.glob("cache/*/*/*/skills"))
    marketplace_roots = sorted(plugins_dir.glob("marketplaces/*/*/*/skills"))
    return cache_roots + marketplace_roots


def check(repo_dir: Path, intended_names, *, home_dir: Path, own_installed: frozenset[str]) -> GuardReport:
    """Partition `intended_names` into `approved`/`refused`/`skipped`
    against the three namespaces. Writes nothing, under any input --
    `check()` only reads, `os.stat()`s, and lists directories.

    All three namespaces are walked in full on every call, regardless of
    how many names have already been resolved by an earlier namespace --
    required so a name only reachable through a later namespace is never
    missed, and so every malformed file or directory in every namespace is
    reported through `skipped` even when it cannot affect `intended_names`
    at all `[ref: plan/phase-3.md T3.2, requirement 1]`.

    `own_installed` is required, with no default (T3.2b) -- the names the
    manifest records as installed BY this tool INTO this repository. A hit
    in the repo namespace whose name is a member is not a collision; a hit
    in any other namespace always is, `own_installed` or not
    `[ref: solution.md, "own_installed is required, and it exists because
    this guard otherwise refuses our own earlier work"]`.
    """
    repo_dir = Path(repo_dir)
    home_dir = Path(home_dir)
    intended = set(intended_names)

    namespaces: list[tuple[str, list[Path]]] = [
        (_REPO, [repo_dir / ".claude" / "skills"]),
        (_USER, [home_dir / ".claude" / "skills"]),
        (_PLUGIN, _plugin_roots(home_dir)),
    ]

    refused: dict[str, tuple[str, str]] = {}
    skipped: list[tuple[str, str]] = []

    for namespace, roots in namespaces:
        for root in roots:
            for name, skill_md, reason in _walk_skills(root):
                if reason is not None:
                    skipped.append((str(skill_md), reason))
                    continue
                if name not in intended or name in refused:
                    continue
                if namespace == _REPO and name in own_installed:
                    continue  # ours already -- not a collision, see T3.2b above
                refused[name] = (namespace, str(skill_md))

    approved = frozenset(intended - set(refused))
    return GuardReport(approved=approved, refused=refused, skipped=skipped)
