"""The tcs-patterns collision guard (spec-020 T3.2, component C4).

`check(repo_dir, intended_names, *, home_dir)` partitions a set of intended
skill names into what C5 (T3.3) may safely install, what it must refuse, and
what this guard could not evaluate at all. **This module installs nothing**
-- writing is C5's job in T3.3; C4 only decides
`[ref: docs/XDD/specs/020-tcs-patterns-selective-install/plan/phase-3.md#T3.2]`.

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

**Stdlib only, Python 3.11 floor** `[ref: SDD/Architecture Decisions/
ADR-2]` -- a plugin ships as files with no install step, so this module
parses the frontmatter `name:` itself rather than importing PyYAML.
`_skill_name` reads only the lines between the first two `---` delimiters;
nothing below that second delimiter is ever inspected, so a `name:`-shaped
line in the skill's body cannot be mistaken for its frontmatter.

**`skipped` is a third channel, not an afterthought.** An unreadable or
frontmatter-less `SKILL.md` is skipped, never fatal -- the same stance
`detect.py` takes for an unparseable manifest, and for the same reason: a
third party's broken file must not stop this repository's install. It is
reported as a `(path, reason)` pair because a file this guard could not
check is a name it cannot vouch for, and a caller that cannot see the
omission cannot warn about it
`[ref: SDD/Error Handling, "A SKILL.md in a scanned namespace..."]`. Four
distinct inputs reach this, each with its own distinguishable reason:
unreadable, no frontmatter block, no `name:` key, and an empty `name:`
value -- none occurs naturally (all 259 real files parse), so every one of
them is fixture-only.
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
_NAME_LINE_RE = re.compile(r"^name:\s*(.*?)\s*$")


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
    skipped:  (path, reason) for every SKILL.md that could not be read,
              in discovery order -- a sequence, not a set, because the same
              malformed file reached by two distinct surviving paths (after
              dedup, at most one survives per real directory) is still two
              distinct problems if they are genuinely two different files.
    """

    approved: frozenset[str]
    refused: dict[str, tuple[str, str]] = field(default_factory=dict)
    skipped: list[tuple[str, str]] = field(default_factory=list)


def _skill_name(skill_md: Path) -> tuple[str | None, str | None]:
    """Return `(name, None)` on success or `(None, reason)` on any of the
    four skip cases. Reads only between the first two `---` delimiter
    lines -- the frontmatter block -- never the body below it."""
    try:
        text = skill_md.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return None, f"unreadable: {e}"

    lines = text.splitlines()
    if not lines or lines[0].strip() != _FRONTMATTER_DELIM:
        return None, "no frontmatter block"

    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == _FRONTMATTER_DELIM:
            end = i
            break
    if end is None:
        return None, "no frontmatter block"

    raw_value = None
    for line in lines[1:end]:
        match = _NAME_LINE_RE.match(line)
        if match:
            raw_value = match.group(1)
            break
    if raw_value is None:
        return None, "no name: key"

    value = raw_value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1].strip()
    if not value:
        return None, "empty name: value"
    return value, None


def _walk_skills(root: Path):
    """Yield `(name, skill_md_path, skip_reason)` for every `SKILL.md`
    under `root`, to any depth, following symlinks, with the
    `(st_dev, st_ino)` dedup applied before `os.walk` ever recurses into a
    child directory -- see the module docstring. `name` and `skip_reason`
    are mutually exclusive: exactly one is `None`.

    A missing `root` yields nothing; it is empty, not an error
    `[ref: SDD/Error Handling, "A missing namespace directory is empty"]`.
    """
    if not root.is_dir():
        return

    try:
        root_key = _identity(root)
    except OSError:
        return
    visited = {root_key}

    for dirpath, dirnames, filenames in os.walk(root, followlinks=True):
        kept = []
        for name in dirnames:
            child = Path(dirpath) / name
            try:
                key = _identity(child)
            except OSError:
                # Let os.walk's own traversal surface whatever this is;
                # not our dedup's problem to solve.
                kept.append(name)
                continue
            if key in visited:
                continue  # already walked this real directory -- prune
            visited.add(key)
            kept.append(name)
        dirnames[:] = kept

        if "SKILL.md" in filenames:
            skill_md = Path(dirpath) / "SKILL.md"
            name, reason = _skill_name(skill_md)
            yield name, skill_md, reason


def _identity(path: Path) -> tuple[int, int]:
    st = path.stat()
    return st.st_dev, st.st_ino


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


def check(repo_dir: Path, intended_names, *, home_dir: Path) -> GuardReport:
    """Partition `intended_names` into `approved`/`refused`/`skipped`
    against the three namespaces. Writes nothing, under any input --
    `check()` only reads and `os.stat()`s.

    All three namespaces are walked in full on every call, regardless of
    how many names have already been resolved by an earlier namespace --
    required so a name only reachable through a later namespace is never
    missed, and so every malformed file in every namespace is reported
    through `skipped` even when it cannot affect `intended_names` at all
    `[ref: plan/phase-3.md T3.2, requirement 1]`.
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
                if name in intended and name not in refused:
                    refused[name] = (namespace, str(skill_md))

    approved = frozenset(intended - set(refused))
    return GuardReport(approved=approved, refused=refused, skipped=skipped)
