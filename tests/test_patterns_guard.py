"""T3.2/T3.2b (spec-020): the collision guard (component C4).

`check(repo_dir, intended_names, *, home_dir, own_installed)` partitions a
set of intended skill names into `approved` / `refused` / `skipped` -- it
**installs nothing**; writing is C5's job in T3.3 `[ref: docs/XDD/specs/
020-tcs-patterns-selective-install/plan/phase-3.md#T3.2]`. This file is
written against `guard.py` before that module exists, so every test below
fails for want of the module rather than passing by construction -- the RED
half of T3.2's TDD gate.

`own_installed` (T3.2b, added after T3.2 shipped) is required with no
default -- every pre-existing call below passes `own_installed=frozenset()`
to reproduce the behaviour T3.2 originally specified; the dedicated
`own_installed` section near the end of this file exercises the exemption
itself `[ref: plan/phase-3.md T3.2b]`.

The import of `guard` happens at RUNTIME, inside each test, not at module
level, for the same reason `test_patterns_install.py::_load_manifest` and
`test_patterns_detect.py::_load_detect` do this: a module-level `ImportError`
would abort collection of this whole file rather than failing only the tests
that need the module.

Four facts drive almost every fixture here, each measured on a live
installation and recorded in `solution.md`'s "Data model: the three
namespaces (C4)" section:

1. A skill's name is its frontmatter `name:`, never its directory -- so a
   malformed-input fixture always carries a `SKILL.md`, and a
   frontmatter-divergence fixture deliberately names its directory and its
   registered name differently.
2. Real skills sit at more than one depth (`synced/<uuid>/<name>/SKILL.md`),
   and a non-skill directory under a namespace root (no `SKILL.md` of its
   own) must not occupy its name.
3. `os.walk(followlinks=True)` is required to see a symlinked skill
   directory at all -- `rglob`/`glob("**")` silently miss it, and
   `glob(recurse_symlinks=True)` is a 3.13+ `TypeError` on the 3.11 floor
   `[ref: SDD/Architecture Decisions/ADR-2]`. Several fixtures below exist
   only to make that distinction observable.
4. `(st_dev, st_ino)` dedup, asserted only through `skipped`'s *count* --
   `refused` is keyed by name and cannot show a directory visited twice
   `[ref: solution.md, "the obvious form of this test is vacuous"]`.

`home_dir` is always an explicit `tmp_path` subdirectory, never the real
`$HOME` -- two of the three namespaces live outside the repository, and a
test that read the real `$HOME` would assert one thing today and the
opposite after this feature ships `[ref: solution.md, "home_dir is a
parameter, not Path.home()"]`.
"""

from __future__ import annotations

import hashlib
import importlib
import os
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
LIB_DIR = REPO_ROOT / "plugins" / "tcs-patterns" / "skills" / "patterns-setup" / "lib"


def _load_guard() -> ModuleType:
    """See `test_patterns_install.py::_load_manifest` for why this import
    happens here rather than at module level, and why `sys.path` (not
    `PYTHONPATH`) is how a mutated copy must be loaded when mutation-testing
    this file."""
    if str(LIB_DIR) not in sys.path:
        sys.path.insert(0, str(LIB_DIR))
    return importlib.import_module("guard")


# --- fixture builders ------------------------------------------------------


def _skill(parent: Path, dirname: str, *, name: str) -> Path:
    """Create `parent/dirname/SKILL.md` with frontmatter `name:` set to
    `name`. Returns the directory. `name` is deliberately a parameter
    independent of `dirname` -- most callers pass the same string for both,
    but `test_registered_name_used_instead_of_directory_name` relies on
    being able to pass different ones."""
    d = parent / dirname
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: fixture skill for T3.2\n---\n\nBody.\n",
        encoding="utf-8",
    )
    return d


def _malformed(parent: Path, dirname: str, content: str) -> Path:
    d = parent / dirname
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(content, encoding="utf-8")
    return d


def _cache_root(home: Path, marketplace: str, plugin: str, version: str) -> Path:
    """`<home>/.claude/plugins/cache/<marketplace>/<plugin>/<version>/skills`
    -- the cache's three wildcards, per `solution.md`'s interface block."""
    return home / ".claude" / "plugins" / "cache" / marketplace / plugin / version / "skills"


def _marketplace_root(home: Path, marketplace: str, segment: str, plugin: str) -> Path:
    """`<home>/.claude/plugins/marketplaces/<marketplace>/<segment>/<plugin>/skills`
    -- `segment` is a wildcard (`plugins`, `external_plugins`, ...), never a
    literal `[ref: solution.md, "The marketplace glob is */*/*/skills"]`."""
    return home / ".claude" / "plugins" / "marketplaces" / marketplace / segment / plugin / "skills"


def _digest_tree(root: Path) -> str:
    """A single sha256 over every entry under `root`: path plus content for
    a regular file, path plus link target for a symlink -- never dereferenced,
    so a symlink cycle fixture cannot hang this helper the way following it
    could. `followlinks=False` is deliberate here too: a write lands on a
    REAL filesystem entry regardless of which symlink a test walked through
    to find it, so not following symlinks still sees every write while
    staying immune to the cycle fixtures below.

    Used only by this test file, to prove the guard writes nothing -- never
    imported by `guard.py` itself, which must not need to compute anything
    like this to do its own job."""
    if not root.exists():
        return "ABSENT"
    h = hashlib.sha256()
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames.sort()
        rel_dir = os.path.relpath(dirpath, root)
        # The directory's own existence is part of the digest, not only its
        # files -- `os.walk` yields a tuple for every directory, including
        # an empty one, so a bare `mkdir()` with nothing inside it still
        # changes `rel_dir` and therefore the hash. Found missing at T3.2's
        # fix round: a mutant that only created a new empty directory
        # survived all 25 tests while a file-write mutant was caught
        # `[ref: plan/phase-3.md T3.2, "The write-nothing digest cannot see
        # a mkdir"]`.
        h.update(b"DIR:")
        h.update(Path(rel_dir).as_posix().encode())
        h.update(b"\n")
        for name in sorted(filenames):
            full = Path(dirpath) / name
            rel = (Path(rel_dir) / name).as_posix()
            h.update(rel.encode())
            if full.is_symlink():
                h.update(b"SYMLINK:")
                h.update(os.readlink(full).encode())
            else:
                try:
                    h.update(full.read_bytes())
                except OSError as e:
                    h.update(f"UNREADABLE:{e}".encode())
    return h.hexdigest()


def _digest_pair(repo: Path, home: Path) -> tuple[str, str]:
    return _digest_tree(repo), _digest_tree(home)


# --- one call, one namespace each, plus a free name (requirement 1) -------


def test_one_call_partitions_four_names_across_three_namespaces(tmp_path: Path) -> None:
    """Four names, one call: one colliding in each of the three namespaces,
    one free -- all four outcomes asserted from the SAME `check()` call, so
    an implementation that short-circuits after the first namespace yields a
    collision and never walks the others for the remaining names fails this
    `[ref: plan/phase-3.md T3.2, requirement 1]`. Also one of the three
    `write-nothing` scenarios the task requires (digest below)."""
    guard = _load_guard()
    repo = tmp_path / "repo"
    home = tmp_path / "home"

    _skill(repo / ".claude" / "skills", "taken-in-repo", name="taken-in-repo")
    _skill(home / ".claude" / "skills", "taken-in-user", name="taken-in-user")
    _skill(_cache_root(home, "mp", "some-plugin", "1.0.0"), "taken-in-plugin", name="taken-in-plugin")

    before = _digest_pair(repo, home)

    report = guard.check(
        repo,
        {"taken-in-repo", "taken-in-user", "taken-in-plugin", "totally-free"},
        home_dir=home,
        own_installed=frozenset(),
    )

    after = _digest_pair(repo, home)
    assert before == after, "the guard must write nothing"

    assert report.approved == frozenset({"totally-free"})
    assert report.refused["taken-in-repo"][0] == "repo"
    assert report.refused["taken-in-user"][0] == "user"
    assert report.refused["taken-in-plugin"][0] == "plugin"
    assert "totally-free" not in report.refused


def test_non_colliding_names_still_approved_one_refused(tmp_path: Path) -> None:
    """F5's fourth criterion: a selection with one colliding and two free
    names approves the two and refuses the third."""
    guard = _load_guard()
    repo = tmp_path / "repo"
    home = tmp_path / "home"
    _skill(repo / ".claude" / "skills", "ddd", name="ddd")

    report = guard.check(repo, {"ddd", "hexagonal", "observability"}, home_dir=home, own_installed=frozenset())

    assert report.approved == frozenset({"hexagonal", "observability"})
    assert set(report.refused) == {"ddd"}


# --- each namespace reports both locations ---------------------------------


def test_refusal_in_repo_namespace_names_the_colliding_skill_md(tmp_path: Path) -> None:
    guard = _load_guard()
    repo = tmp_path / "repo"
    home = tmp_path / "home"
    colliding_dir = _skill(repo / ".claude" / "skills", "ddd", name="ddd")

    report = guard.check(repo, {"ddd"}, home_dir=home, own_installed=frozenset())

    namespace, path = report.refused["ddd"]
    assert namespace == "repo"
    assert path == str(colliding_dir / "SKILL.md")


def test_refusal_in_user_namespace_names_the_colliding_skill_md(tmp_path: Path) -> None:
    guard = _load_guard()
    repo = tmp_path / "repo"
    home = tmp_path / "home"
    colliding_dir = _skill(home / ".claude" / "skills", "ddd", name="ddd")

    report = guard.check(repo, {"ddd"}, home_dir=home, own_installed=frozenset())

    namespace, path = report.refused["ddd"]
    assert namespace == "user"
    assert path == str(colliding_dir / "SKILL.md")


def test_refusal_in_plugin_cache_names_the_colliding_skill_md(tmp_path: Path) -> None:
    guard = _load_guard()
    repo = tmp_path / "repo"
    home = tmp_path / "home"
    colliding_dir = _skill(_cache_root(home, "claude-plugins-official", "tcs-team", "3.4.4"), "ddd", name="ddd")

    report = guard.check(repo, {"ddd"}, home_dir=home, own_installed=frozenset())

    namespace, path = report.refused["ddd"]
    assert namespace == "plugin"
    assert path == str(colliding_dir / "SKILL.md")


def test_refusal_in_plugin_marketplace_names_the_colliding_skill_md(tmp_path: Path) -> None:
    guard = _load_guard()
    repo = tmp_path / "repo"
    home = tmp_path / "home"
    colliding_dir = _skill(
        _marketplace_root(home, "claude-plugins-official", "plugins", "tcs-team"), "ddd", name="ddd"
    )

    report = guard.check(repo, {"ddd"}, home_dir=home, own_installed=frozenset())

    namespace, path = report.refused["ddd"]
    assert namespace == "plugin"
    assert path == str(colliding_dir / "SKILL.md")


# --- plugin specifics: both roots, versions, both segment names -----------


def test_cache_unions_names_across_plugin_versions(tmp_path: Path) -> None:
    """The cache holds several versions of one plugin; a name present in
    only the OLDER version must still be refused -- the union-across-
    versions rule, with a live instance: `tcs-team` holds `testing` in cached
    `3.4.2` and `test-practices` in `3.4.4` `[ref: solution.md, fact 3]`."""
    guard = _load_guard()
    repo = tmp_path / "repo"
    home = tmp_path / "home"
    _skill(_cache_root(home, "claude-plugins-official", "tcs-team", "3.4.2"), "testing", name="testing")
    _skill(_cache_root(home, "claude-plugins-official", "tcs-team", "3.4.4"), "test-practices", name="test-practices")

    report = guard.check(repo, {"testing", "test-practices", "free"}, home_dir=home, own_installed=frozenset())

    assert set(report.refused) == {"testing", "test-practices"}
    assert report.refused["testing"][0] == "plugin"
    assert report.refused["test-practices"][0] == "plugin"
    assert report.approved == frozenset({"free"})


def test_both_marketplace_segment_names_are_refused(tmp_path: Path) -> None:
    """The marketplace's second level is a wildcard SEGMENT, not the literal
    `plugins` -- a live installation has `external_plugins/` roots too
    `[ref: solution.md, "The marketplace glob is */*/*/skills"]`. Build
    both segment names and assert a name under each is refused."""
    guard = _load_guard()
    repo = tmp_path / "repo"
    home = tmp_path / "home"
    _skill(_marketplace_root(home, "claude-plugins-official", "plugins", "hexagonal-plugin"), "hexagonal", name="hexagonal")
    _skill(_marketplace_root(home, "claude-plugins-official", "external_plugins", "access-plugin"), "access", name="access")

    report = guard.check(repo, {"hexagonal", "access", "free"}, home_dir=home, own_installed=frozenset())

    assert set(report.refused) == {"hexagonal", "access"}
    assert report.approved == frozenset({"free"})


def test_both_plugin_roots_exercised_in_one_call(tmp_path: Path) -> None:
    """The dangerous direction, measured: the marketplace pattern applied to
    the cache root finds zero roots, and vice versa -- a guard that silently
    enumerated no plugin skills from one of the two roots would still pass
    every repo-and-user test. One cache name and one marketplace name, both
    refused from the same call, is what makes that failure visible
    `[ref: plan/phase-3.md T3.2, requirement 2]`."""
    guard = _load_guard()
    repo = tmp_path / "repo"
    home = tmp_path / "home"
    _skill(_cache_root(home, "claude-plugins-official", "tcs-patterns", "1.4.4"), "ddd", name="ddd")
    _skill(_marketplace_root(home, "claude-plugins-official", "plugins", "tcs-patterns"), "hexagonal", name="hexagonal")

    report = guard.check(repo, {"ddd", "hexagonal"}, home_dir=home, own_installed=frozenset())

    assert set(report.refused) == {"ddd", "hexagonal"}


def test_enabled_plugins_false_still_refused(tmp_path: Path) -> None:
    """`enabledPlugins` is ignored entirely -- over-inclusion is the safe
    direction `[ref: solution.md, "The decision: enumerate broadly and
    ignore reachability"]`. A plugin skill colliding with an intended name,
    disabled in BOTH the home and repository settings, is still refused."""
    guard = _load_guard()
    repo = tmp_path / "repo"
    home = tmp_path / "home"
    _skill(_cache_root(home, "claude-plugins-official", "plugin-dev", "517b2fcd1b60"), "ddd", name="ddd")

    (home / ".claude").mkdir(parents=True, exist_ok=True)
    (home / ".claude" / "settings.json").write_text(
        '{"enabledPlugins": {"plugin-dev@claude-plugins-official": false}}', encoding="utf-8"
    )
    (repo / ".claude").mkdir(parents=True, exist_ok=True)
    (repo / ".claude" / "settings.json").write_text(
        '{"enabledPlugins": {"plugin-dev@claude-plugins-official": false}}', encoding="utf-8"
    )

    report = guard.check(repo, {"ddd"}, home_dir=home, own_installed=frozenset())

    assert report.refused["ddd"][0] == "plugin"


# --- enumeration: depth, symlinks, non-skill directories, registered name -


def test_symlinked_skill_directory_outside_namespace_root_is_found(tmp_path: Path) -> None:
    """Measured: `~/.claude/skills/obsidian-eval` is a symlink into a shared
    config checkout, and `rglob`/`glob("**")` miss it while
    `os.walk(followlinks=True)` finds it `[ref: solution.md, "The
    enumeration is os.walk(followlinks=True)"]`. The real `SKILL.md` lives
    OUTSIDE the namespace root; a symlink inside the root points to it."""
    guard = _load_guard()
    repo = tmp_path / "repo"
    home = tmp_path / "home"

    real_dir = tmp_path / "shared-config-checkout" / "obsidian-eval"
    _skill(real_dir.parent, "obsidian-eval", name="obsidian-eval")

    skills_root = home / ".claude" / "skills"
    skills_root.mkdir(parents=True)
    (skills_root / "obsidian-eval").symlink_to(real_dir, target_is_directory=True)

    before = _digest_pair(repo, home)
    report = guard.check(repo, {"obsidian-eval"}, home_dir=home, own_installed=frozenset())
    after = _digest_pair(repo, home)

    assert before == after, "the guard must write nothing"
    assert report.refused["obsidian-eval"][0] == "user"


def test_skill_nested_three_levels_deep_is_found(tmp_path: Path) -> None:
    """The user namespace holds real skills at
    `synced/<uuid>/<name>/SKILL.md` -- a bounded `*/SKILL.md` finds 6 of 19;
    the walk must be unbounded in depth `[ref: solution.md, fact 2]`."""
    guard = _load_guard()
    repo = tmp_path / "repo"
    home = tmp_path / "home"
    nested = home / ".claude" / "skills" / "synced" / "9d604c14-uuid"
    _skill(nested, "morning", name="morning")

    report = guard.check(repo, {"morning"}, home_dir=home, own_installed=frozenset())

    assert report.refused["morning"][0] == "user"


def test_non_skill_directory_does_not_occupy_its_own_name(tmp_path: Path) -> None:
    """`synced/` itself has no `SKILL.md` of its own and must not occupy the
    name `synced` -- a one-level `iterdir()` gets this wrong in both
    directions at once `[ref: solution.md, fact 2]`."""
    guard = _load_guard()
    repo = tmp_path / "repo"
    home = tmp_path / "home"
    synced = home / ".claude" / "skills" / "synced"
    _skill(synced / "some-uuid", "morning", name="morning")

    report = guard.check(repo, {"synced"}, home_dir=home, own_installed=frozenset())

    assert report.approved == frozenset({"synced"})
    assert "synced" not in report.refused


def test_registered_name_used_instead_of_directory_name(tmp_path: Path) -> None:
    """Exactly one of 259 real files diverges: the `hookify` plugin's
    `skills/writing-rules/` directory registers as `writing-hookify-rules`
    `[ref: solution.md, fact 1]`. The guard must refuse against the
    REGISTERED name and must NOT treat the directory's name as occupied."""
    guard = _load_guard()
    repo = tmp_path / "repo"
    home = tmp_path / "home"
    _skill(
        _cache_root(home, "claude-plugins-official", "hookify", "1.0.0"),
        "writing-rules",
        name="writing-hookify-rules",
    )

    report = guard.check(repo, {"writing-hookify-rules", "writing-rules"}, home_dir=home, own_installed=frozenset())

    assert report.refused["writing-hookify-rules"][0] == "plugin"
    assert "writing-rules" not in report.refused
    assert "writing-rules" in report.approved


# --- (st_dev, st_ino) dedup, visible only through `skipped` ----------------


def test_two_symlinks_to_one_malformed_skill_directory_skipped_once(tmp_path: Path) -> None:
    """The obvious form of this test ("the name refused once, not twice")
    cannot fail, because `refused` is keyed by name
    `[ref: solution.md, "the obvious form of this test is vacuous"]`. The
    dedup is only visible through `skipped`'s COUNT: two symlinks to one
    malformed (no-frontmatter) directory must be reported once, not twice."""
    guard = _load_guard()
    repo = tmp_path / "repo"
    home = tmp_path / "home"

    real_dir = tmp_path / "elsewhere" / "broken-skill"
    _malformed(real_dir.parent, "broken-skill", "no frontmatter here at all\n")

    skills_root = home / ".claude" / "skills"
    skills_root.mkdir(parents=True)
    (skills_root / "link-a").symlink_to(real_dir, target_is_directory=True)
    (skills_root / "link-b").symlink_to(real_dir, target_is_directory=True)

    before = _digest_pair(repo, home)
    report = guard.check(repo, {"anything"}, home_dir=home, own_installed=frozenset())
    after = _digest_pair(repo, home)

    assert before == after, "the guard must write nothing"
    assert len(report.skipped) == 1


def test_self_referential_symlink_returns_normally_skipped_once(tmp_path: Path) -> None:
    """The cycle case: a malformed skill directory containing a symlink back
    to itself. `timeout` is not the instrument (absent on macOS, and
    measured, `os.walk(followlinks=True)` does not hang on this -- macOS
    raises `ELOOP` after 66 redundant visits without the dedup, which the
    dedup reduces to 3). Asserts both that the call returns a well-formed
    `GuardReport` (no unhandled `OSError`) and that the malformed file is
    reported exactly once despite the cycle `[ref: plan/phase-3.md T3.2,
    requirement 5]`."""
    guard = _load_guard()
    repo = tmp_path / "repo"
    home = tmp_path / "home"

    cyclic = home / ".claude" / "skills" / "cyclic-skill"
    _malformed(home / ".claude" / "skills", "cyclic-skill", "no frontmatter here at all\n")
    (cyclic / "self-link").symlink_to(cyclic, target_is_directory=True)

    before = _digest_pair(repo, home)
    report = guard.check(repo, {"anything"}, home_dir=home, own_installed=frozenset())
    after = _digest_pair(repo, home)

    assert before == after, "the guard must write nothing"
    assert isinstance(report, guard.GuardReport)
    assert len(report.skipped) == 1


# --- the five malformed-input cases, and their pairwise-distinct reasons --


def test_five_malformed_skill_md_cases_yield_four_distinguishable_reasons(tmp_path: Path) -> None:
    """None of the five occurs naturally -- all 259 real files parse
    `[ref: solution.md, fact 1]` -- so every one is constructed here. Five
    INPUTS, not five reasons: an unterminated frontmatter block (opens with
    `---`, never closes) is a second, untested path to the same skip as a
    file with no frontmatter block at all, so `len(skipped) == 5` alongside
    `len(reasons) == 4` is the correct assertion -- five distinct reasons
    would be wrong `[ref: plan/phase-3.md T3.2 fix round, item 4]`.

    The remaining assertion is still PAIRWISE-DISTINCT over those four
    reasons, not four separate non-empty checks: a mutation that collapses
    two of the four into one generic string survives every isolated
    non-empty check while failing only this comparison
    `[ref: plan/phase-3.md T3.2, "need a pairwise-distinct assertion"]`."""
    guard = _load_guard()
    repo = tmp_path / "repo"
    home = tmp_path / "home"
    skills_root = home / ".claude" / "skills"

    unreadable_dir = _malformed(skills_root, "unreadable", "---\nname: unreadable\n---\n")
    unreadable_path = unreadable_dir / "SKILL.md"
    os.chmod(unreadable_path, 0o000)

    _malformed(skills_root, "no-frontmatter", "just a body, no frontmatter delimiters\n")
    _malformed(skills_root, "unterminated-frontmatter", "---\nname: never-closed\ndescription: oops\n")
    _malformed(skills_root, "no-name-key", "---\ndescription: missing the name key\n---\n\nBody.\n")
    _malformed(skills_root, "empty-name", '---\nname: ""\n---\n\nBody.\n')

    try:
        before = _digest_pair(repo, home)
        report = guard.check(repo, {"anything"}, home_dir=home, own_installed=frozenset())
        after = _digest_pair(repo, home)
    finally:
        os.chmod(unreadable_path, 0o644)

    assert before == after, "the guard must write nothing"
    assert len(report.skipped) == 5
    reasons = {reason for _path, reason in report.skipped}
    assert len(reasons) == 4, f"reasons must be pairwise distinct across the 4 cases, got {reasons!r}"


# --- an unreadable directory is skipped and reported too (fix round item 1)


def test_unreadable_intermediate_directory_is_skipped_and_reported(tmp_path: Path) -> None:
    """`os.walk`'s default `onerror=None` swallows a directory-listing
    failure outright: a `chmod 000` directory holding a `SKILL.md` would
    otherwise yield NO entries and NO error at all -- `skipped` stays
    empty and the caller has no way to know the namespace was only
    partly checked. Measured `[ref: plan/phase-3.md T3.2 fix round, item
    1]`. The guard cannot refuse a name it was never able to read -- a
    directory it cannot list might hold anything, or nothing -- so the
    fix is not that `hidden` moves out of `approved` (there is nothing to
    refuse it WITH); the fix is that the omission becomes VISIBLE through
    `skipped`, which an `onerror=None` walk cannot produce at all."""
    guard = _load_guard()
    repo = tmp_path / "repo"
    home = tmp_path / "home"
    skills_root = home / ".claude" / "skills"

    blocked = skills_root / "blocked"
    hidden_dir = _skill(blocked, "hidden", name="hidden")
    os.chmod(blocked, 0o000)

    try:
        before = _digest_pair(repo, home)
        report = guard.check(repo, {"hidden"}, home_dir=home, own_installed=frozenset())
        after = _digest_pair(repo, home)
    finally:
        os.chmod(blocked, 0o755)

    assert before == after, "the guard must write nothing"
    assert len(report.skipped) == 1, "the unlistable directory must be reported, not silently swallowed"
    assert report.skipped[0][1].startswith("directory unreadable")
    # Housekeeping only: confirm the fixture actually built what this test
    # claims (a real SKILL.md exists, just unreachable while blocked).
    assert hidden_dir.name == "hidden"


def test_unreadable_namespace_root_is_skipped_and_reported(tmp_path: Path) -> None:
    """The same failure at the ROOT itself: `root.is_dir()` is still `True`
    on a `chmod 000` directory, so the missing-root clause does not catch
    it, and under the OLD `onerror=None` default the whole namespace would
    vanish with no trace at all -- `skipped` staying empty indistinguishable
    from an empty, healthy namespace `[ref: plan/phase-3.md T3.2 fix round,
    item 1]`."""
    guard = _load_guard()
    repo = tmp_path / "repo"
    home = tmp_path / "home"
    skills_root = home / ".claude" / "skills"
    _skill(skills_root, "hidden-root", name="hidden-root")
    os.chmod(skills_root, 0o000)

    try:
        report = guard.check(repo, {"hidden-root"}, home_dir=home, own_installed=frozenset())
    finally:
        os.chmod(skills_root, 0o755)

    assert len(report.skipped) == 1, "the unlistable root must be reported, not silently treated as empty"
    assert report.skipped[0][1].startswith("directory unreadable")


def test_three_unreadable_directories_across_namespaces_are_all_reported(tmp_path: Path) -> None:
    """Completeness of `skipped` is the whole point of the channel -- a
    caller that sees one unreadable directory when there were three has
    been told something false. No fixture before this one put more than
    one unreadable directory under the SAME namespace root, so a guard
    that kept only the LAST one it saw per `_walk_skills()` call
    (`unreadable_dirs[-1:]`) -- or only the FIRST
    (`unreadable_dirs[:1]`) -- passed every other test in this file: with
    at most one unreadable directory per root, slicing a one-element list
    either way is a no-op. TWO of the three here sit under the SAME root
    (`user`), which is what actually exercises that truncation; the third
    sits under a DIFFERENT namespace (`repo`), which additionally pins
    that `skipped` accumulates correctly across separate `_walk_skills()`
    calls rather than resetting."""
    guard = _load_guard()
    repo = tmp_path / "repo"
    home = tmp_path / "home"

    blocked_user_1 = home / ".claude" / "skills" / "blocked-user-1"
    blocked_user_2 = home / ".claude" / "skills" / "blocked-user-2"
    blocked_repo = repo / ".claude" / "skills" / "blocked-repo"

    for blocked in (blocked_user_1, blocked_user_2, blocked_repo):
        _skill(blocked, "irrelevant", name="irrelevant")

    try:
        for blocked in (blocked_user_1, blocked_user_2, blocked_repo):
            os.chmod(blocked, 0o000)
        report = guard.check(repo, {"anything"}, home_dir=home, own_installed=frozenset())
    finally:
        for blocked in (blocked_user_1, blocked_user_2, blocked_repo):
            os.chmod(blocked, 0o755)

    assert len(report.skipped) == 3, f"expected all three unreadable directories, got {report.skipped!r}"
    reported_paths = {path for path, _reason in report.skipped}
    assert reported_paths == {str(blocked_user_1), str(blocked_user_2), str(blocked_repo)}
    assert all(reason.startswith("directory unreadable") for _path, reason in report.skipped)


# --- write-nothing digest sees directory shape, not just files (item 3) ----


def test_digest_helper_detects_a_bare_mkdir(tmp_path: Path) -> None:
    """Regression guard on this file's own `_digest_tree` helper: a mutant
    that injects an empty `mkdir()` into `check()` survived all 25 tests
    before this helper hashed directory shape, while a file-write mutant
    was already caught `[ref: plan/phase-3.md T3.2 fix round, item 3]`.
    Asserted directly here so a future edit to `_digest_tree` cannot
    silently regress the property every other write-nothing assertion in
    this file relies on."""
    root = tmp_path / "tree"
    root.mkdir()
    (root / "existing.txt").write_text("content", encoding="utf-8")

    before = _digest_tree(root)
    (root / "newly-created-empty-dir").mkdir()
    after = _digest_tree(root)

    assert before != after, "_digest_tree must see a bare mkdir with no files inside it"


# --- "its frontmatter name:" means what YAML makes of it (fix round item 2)


def _frontmatter_skill(parent: Path, dirname: str, *, name_line: str, extra: str = "") -> Path:
    """Build `parent/dirname/SKILL.md` with a raw, literal `name_line` (and
    optional extra lines) inside the frontmatter block -- unlike `_skill`,
    which always writes a clean `name: <name>` line, this lets a test
    construct the exact YAML edge cases the differential test needs."""
    d = parent / dirname
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(f"---\n{name_line}\n{extra}---\n\nBody.\n", encoding="utf-8")
    return d


# Each case is the literal content of the frontmatter block's `name:`
# line(s) only -- built into a full SKILL.md and run through both
# `guard._skill_name` and real YAML (`yaml.safe_load`) over the SAME text,
# so the comparison has no shared ancestry with the code under test
# `[ref: solution.md, "A differential test is also the strongest shape
# available"]`. The invariant every case must satisfy: the guard's value
# either agrees with YAML's exactly, or the guard skipped (never a wrong
# value) -- plus a few cases are pinned to a specific side to prove the
# parser isn't trivially skipping everything.
_YAML_DIFFERENTIAL_CASES = {
    "plain": "name: ddd",
    "plain_trailing_comment": "name: ddd # comment",
    "double_quoted": 'name: "ddd"',
    "single_quoted": "name: 'ddd'",
    "single_quoted_escaped_quote": "name: 'd''dd'",
    "double_quoted_escaped_backslash": 'name: "d\\\\dd"',
    "empty_double_quoted": 'name: ""',
    "bare_no_value": "name:",
    "comment_only_value": "name: # just a comment",
    "block_scalar_literal": "name: |\n  ddd",
    "block_scalar_folded_strip": "name: >-\n  ddd",
    "tag": "name: !!str ddd",
    "anchor": "name: &anchor ddd",
    "duplicate_name_key": "name: ddd\nother: 1\nname: eee",
}


@pytest.mark.parametrize("case_name", sorted(_YAML_DIFFERENTIAL_CASES), ids=sorted(_YAML_DIFFERENTIAL_CASES))
def test_name_parser_agrees_with_yaml_or_skips(tmp_path: Path, case_name: str) -> None:
    """For every case: the guard's parsed value either equals what a real
    YAML parser yields for the SAME frontmatter text, or the guard skipped
    it -- never a value that disagrees with YAML, which is the exact bug
    class this test exists to close (9 of 14 measured cases disagreed, 4
    of those approving a name that was genuinely taken)
    `[ref: plan/phase-3.md T3.2 fix round, item 2]`."""
    yaml = pytest.importorskip("yaml")
    guard = _load_guard()
    name_block = _YAML_DIFFERENTIAL_CASES[case_name]

    skill_md = (_frontmatter_skill(tmp_path, f"case-{case_name}", name_line=name_block)) / "SKILL.md"

    frontmatter_text = skill_md.read_text(encoding="utf-8")
    end = frontmatter_text.index("\n---", 4)
    parsed = yaml.safe_load(frontmatter_text[4:end]) or {}
    true_name = parsed.get("name") if isinstance(parsed, dict) else None
    if not isinstance(true_name, str) or not true_name:
        true_name = None  # not a usable name either way -- null, non-string, or empty

    value, reason = guard._skill_name(skill_md)

    assert (value == true_name) or (value is None and reason is not None), (
        f"case {case_name!r}: guard returned {value!r} (reason={reason!r}), "
        f"YAML would register {true_name!r} -- must match exactly or skip"
    )


def test_plain_scalar_name_is_not_skipped() -> None:
    """Closes the trivial "always skip" implementation that would vacuously
    satisfy `test_name_parser_agrees_with_yaml_or_skips` above: a plain,
    unquoted `name:` line must actually produce a value, not a skip."""
    guard = _load_guard()
    value, ok = guard._parse_name_scalar("ddd")
    assert value == "ddd"
    assert ok is True


def test_trailing_comment_is_stripped_from_plain_scalar() -> None:
    """The single most concrete regression from the fix round: the old
    regex captured `ddd # comment` as the name; YAML -- and now this
    parser -- yield `ddd`."""
    guard = _load_guard()
    value, ok = guard._parse_name_scalar("ddd # comment")
    assert ok is True
    assert value == "ddd"


def test_duplicate_name_key_is_skipped_not_guessed(tmp_path: Path) -> None:
    guard = _load_guard()
    skill_md = (
        _frontmatter_skill(tmp_path, "dup", name_line="name: ddd", extra="other: 1\nname: eee\n") / "SKILL.md"
    )
    _name, reason = guard._skill_name(skill_md)
    assert reason == "duplicate name: key"


# --- all four namespace roots absent, parametrised --------------------------


@pytest.mark.parametrize(
    "missing_root",
    ["repo_skills", "user_skills", "plugin_cache", "plugin_marketplaces"],
)
def test_each_namespace_root_absent_is_empty_not_an_error(tmp_path: Path, missing_root: str) -> None:
    """A missing namespace directory is empty, not an error. Each of the
    four roots goes through a different glob or walk call -- parametrised so
    a crash specific to one code path does not hide behind the other three
    `[ref: plan/phase-3.md T3.2, requirement 6]`. The other three roots are
    populated with unrelated skills so only the one under test is actually
    absent."""
    guard = _load_guard()
    repo = tmp_path / "repo"
    home = tmp_path / "home"

    builders = {
        "repo_skills": lambda: _skill(repo / ".claude" / "skills", "unrelated-repo", name="unrelated-repo"),
        "user_skills": lambda: _skill(home / ".claude" / "skills", "unrelated-user", name="unrelated-user"),
        "plugin_cache": lambda: _skill(
            _cache_root(home, "claude-plugins-official", "some-plugin", "1.0.0"),
            "unrelated-cache",
            name="unrelated-cache",
        ),
        "plugin_marketplaces": lambda: _skill(
            _marketplace_root(home, "claude-plugins-official", "plugins", "some-plugin"),
            "unrelated-marketplace",
            name="unrelated-marketplace",
        ),
    }
    for key, build in builders.items():
        if key != missing_root:
            build()

    report = guard.check(repo, {"totally-free"}, home_dir=home, own_installed=frozenset())

    assert report.approved == frozenset({"totally-free"})
    assert report.refused == {}
    assert report.skipped == []


# --- precedence across more than one pairing --------------------------------


def test_repo_takes_precedence_over_user(tmp_path: Path) -> None:
    guard = _load_guard()
    repo = tmp_path / "repo"
    home = tmp_path / "home"
    _skill(repo / ".claude" / "skills", "ddd", name="ddd")
    _skill(home / ".claude" / "skills", "ddd", name="ddd")

    report = guard.check(repo, {"ddd"}, home_dir=home, own_installed=frozenset())

    assert report.refused["ddd"][0] == "repo"


def test_user_takes_precedence_over_plugin(tmp_path: Path) -> None:
    guard = _load_guard()
    repo = tmp_path / "repo"
    home = tmp_path / "home"
    _skill(home / ".claude" / "skills", "ddd", name="ddd")
    _skill(_cache_root(home, "claude-plugins-official", "tcs-patterns", "1.4.4"), "ddd", name="ddd")

    report = guard.check(repo, {"ddd"}, home_dir=home, own_installed=frozenset())

    assert report.refused["ddd"][0] == "user"


def test_all_three_colliding_at_once_reports_repo_exactly_once(tmp_path: Path) -> None:
    """Repo before user before plugin is a 3-way order; a test of repo-vs-
    user alone is passed by a mutant that swaps user and plugin
    `[ref: plan/phase-3.md T3.2, requirement 7]`."""
    guard = _load_guard()
    repo = tmp_path / "repo"
    home = tmp_path / "home"
    _skill(repo / ".claude" / "skills", "ddd", name="ddd")
    _skill(home / ".claude" / "skills", "ddd", name="ddd")
    _skill(_cache_root(home, "claude-plugins-official", "tcs-patterns", "1.4.4"), "ddd", name="ddd")

    report = guard.check(repo, {"ddd"}, home_dir=home, own_installed=frozenset())

    assert len(report.refused) == 1
    assert report.refused["ddd"][0] == "repo"


# --- GuardReport shape -------------------------------------------------------


def test_guard_report_is_frozen_with_named_channels(tmp_path: Path) -> None:
    guard = _load_guard()
    repo = tmp_path / "repo"
    home = tmp_path / "home"

    report = guard.check(repo, {"free"}, home_dir=home, own_installed=frozenset())

    assert hasattr(report, "approved")
    assert hasattr(report, "refused")
    assert hasattr(report, "skipped")
    with pytest.raises(Exception):
        report.approved = frozenset()  # frozen dataclass: attribute assignment must fail


# --- T3.2b: own_installed must not refuse our own earlier work -------------
#
# T3.2 shipped and both review gates passed, but the contract asked the
# wrong question: "is this name taken?" instead of "would installing here
# create a duplicate nobody can resolve?" `[ref: solution.md, "The root
# cause is that this section specified the wrong question"]`. An installed
# pattern registers in the REPOSITORY namespace under exactly the name C3
# intends to check next time, so without an exemption C4 refuses the very
# pattern this tool installed on a prior run -- `install()` then never
# receives an already-installed name, and "a second identical install is a
# no-op" can never be exercised through C3's flow at all.
#
# `test_own_installed_repo_hit_is_approved_not_refused` below is written
# TWICE across two commits, deliberately. `own_installed` is a *required*
# keyword-only parameter, so once it exists, every test that calls it --
# including all 25 pre-existing calls above, mechanically given
# `own_installed=frozenset()` -- fails with `TypeError` until `check()`
# grows the parameter. That failure proves only that the parameter is
# ABSENT, not that the old behaviour was WRONG; those are different claims.
# Only a test against the CURRENT (pre-fix) signature, asserting the
# approval the old behaviour fails to give, demonstrates the defect itself
# `[ref: plan/phase-3.md T3.2b, "The RED phase here cannot prove what a RED
# phase usually proves"]`. The RED commit therefore carries this test
# against the OLD signature (fails on the assertion -- the defect); the
# commit that adds the parameter rewrites it to the NEW signature (the old
# call becomes illegal once `own_installed` has no default), where it pins
# the fix instead.


def test_own_installed_repo_hit_is_approved_not_refused(tmp_path: Path) -> None:
    """The measured defect, now pinned against the NEW signature. Before
    T3.2b this test was written against the CURRENT (then pre-fix)
    signature and failed on `AssertionError` -- the shape that proves the
    OLD behaviour was wrong, not merely that a parameter was missing
    `[ref: plan/phase-3.md T3.2b, "(a) The defect, asserted against the
    CURRENT signature"]`. It is rewritten here because the old call
    (`home_dir=home` with no `own_installed`) is no longer legal now that
    `own_installed` is required. `tcs-ddd` is already installed in the
    repository namespace; checking it again alongside a genuinely new name
    must approve BOTH, not refuse the one this tool installed itself
    `[ref: solution.md, "check(repo, {\"tcs-ddd\", \"tcs-hexagonal\"}, ...)
    -> approved = ['tcs-hexagonal'], refused = {'tcs-ddd': 'repo'}"]`."""
    guard = _load_guard()
    repo = tmp_path / "repo"
    home = tmp_path / "home"
    _skill(repo / ".claude" / "skills", "tcs-ddd", name="tcs-ddd")

    report = guard.check(
        repo,
        {"tcs-ddd", "tcs-hexagonal"},
        home_dir=home,
        own_installed=frozenset({"tcs-ddd"}),
    )

    assert report.approved == frozenset({"tcs-ddd", "tcs-hexagonal"})
    assert "tcs-ddd" not in report.refused


def test_own_installed_does_not_suppress_a_user_namespace_hit(tmp_path: Path) -> None:
    """Boundary 1: `own_installed` only ever exempts the REPOSITORY
    namespace. A name sitting in the user's global skills is somebody else's
    even if `own_installed` claims it -- this tool never installs there
    `[ref: solution.md, "Only the repository namespace"]`."""
    guard = _load_guard()
    repo = tmp_path / "repo"
    home = tmp_path / "home"
    _skill(home / ".claude" / "skills", "tcs-ours", name="tcs-ours")

    report = guard.check(repo, {"tcs-ours"}, home_dir=home, own_installed=frozenset({"tcs-ours"}))

    assert report.refused["tcs-ours"][0] == "user"
    assert "tcs-ours" not in report.approved


def test_own_installed_does_not_suppress_a_plugin_namespace_hit(tmp_path: Path) -> None:
    """Boundary 1, plugin side: a plugin skill is always somebody else's,
    `own_installed` or not `[ref: solution.md, "Only the repository
    namespace"]`."""
    guard = _load_guard()
    repo = tmp_path / "repo"
    home = tmp_path / "home"
    _skill(_cache_root(home, "claude-plugins-official", "some-plugin", "1.0.0"), "tcs-ours", name="tcs-ours")

    report = guard.check(repo, {"tcs-ours"}, home_dir=home, own_installed=frozenset({"tcs-ours"}))

    assert report.refused["tcs-ours"][0] == "plugin"
    assert "tcs-ours" not in report.approved


def test_own_installed_name_not_installed_anywhere_is_simply_approved(tmp_path: Path) -> None:
    """A name `own_installed` claims but that no namespace actually holds is
    not a collision in the first place -- it is just approved, the same as
    any other free name."""
    guard = _load_guard()
    repo = tmp_path / "repo"
    home = tmp_path / "home"

    report = guard.check(repo, {"tcs-ours"}, home_dir=home, own_installed=frozenset({"tcs-ours"}))

    assert report.approved == frozenset({"tcs-ours"})
    assert report.refused == {}


def test_own_installed_omitted_entirely_raises_type_error(tmp_path: Path) -> None:
    """Boundary 2: required, with no default. A `frozenset()` default would
    silently restore the exact bug this task fixes the first time a caller
    forgot to pass it -- forgetting must be the loudest possible failure, a
    `TypeError` at the call site `[ref: solution.md, "Required, with no
    default"]`."""
    guard = _load_guard()
    repo = tmp_path / "repo"
    home = tmp_path / "home"

    with pytest.raises(TypeError):
        guard.check(repo, {"anything"}, home_dir=home)  # type: ignore[call-arg]


def test_empty_own_installed_reproduces_old_refusal_behavior(tmp_path: Path) -> None:
    """Boundary 3: an empty `own_installed` -- the safe fallback for a
    caller that could not read the manifest -- must refuse a repo-namespace
    hit exactly as the pre-T3.2b guard always did
    `[ref: solution.md, "An unreadable manifest means nothing is ours"]`."""
    guard = _load_guard()
    repo = tmp_path / "repo"
    home = tmp_path / "home"
    _skill(repo / ".claude" / "skills", "tcs-ours", name="tcs-ours")

    report = guard.check(repo, {"tcs-ours"}, home_dir=home, own_installed=frozenset())

    assert report.refused["tcs-ours"][0] == "repo"
    assert "tcs-ours" not in report.approved


def test_own_installed_suppression_keyed_on_membership_not_namespace_alone(tmp_path: Path) -> None:
    """The load-bearing boundary test. `own_installed` being non-empty must
    not make an implementation exempt EVERY repo-namespace hit regardless of
    which name is actually in it -- only a name that is ITSELF a member of
    `own_installed` is exempt. `own_installed` here names a different
    pattern (`tcs-ours`) than the one colliding (`tcs-ddd`), so a mutant that
    suppresses on `namespace == "repo"` alone (ignoring membership) passes
    every other test in this file but fails this one."""
    guard = _load_guard()
    repo = tmp_path / "repo"
    home = tmp_path / "home"
    _skill(repo / ".claude" / "skills", "tcs-ddd", name="tcs-ddd")

    report = guard.check(repo, {"tcs-ddd"}, home_dir=home, own_installed=frozenset({"tcs-ours"}))

    assert report.refused["tcs-ddd"][0] == "repo"
    assert "tcs-ddd" not in report.approved


def test_own_installed_membership_is_case_sensitive(tmp_path: Path) -> None:
    """`own_installed` values come from the manifest and are lowercase BY
    CONSTRUCTION (`manifest.py`'s `_INSTALLED_AS_RE`), while a registered
    name comes from a third party's frontmatter and can be any case. A
    repo-namespace skill registered as `TCS-OURS` is a DIFFERENT name from
    `tcs-ours` as far as the harness is concerned, so it must still be
    refused even though `own_installed` contains the lowercase variant --
    a case-insensitive comparison would exempt it and approve a name that
    is genuinely taken, which is the CON-3 duplicate this guard exists to
    prevent. Catches `name.lower() in {o.lower() for o in own_installed}`,
    which passes every other test in this file."""
    guard = _load_guard()
    repo = tmp_path / "repo"
    home = tmp_path / "home"
    _skill(repo / ".claude" / "skills", "tcs-ours-upper", name="TCS-OURS")

    report = guard.check(repo, {"TCS-OURS"}, home_dir=home, own_installed=frozenset({"tcs-ours"}))

    assert report.refused["TCS-OURS"][0] == "repo"
    assert "TCS-OURS" not in report.approved
