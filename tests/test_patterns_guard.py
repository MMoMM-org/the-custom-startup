"""T3.2 (spec-020): the collision guard (component C4).

`check(repo_dir, intended_names, *, home_dir)` partitions a set of intended
skill names into `approved` / `refused` / `skipped` -- it **installs
nothing**; writing is C5's job in T3.3 `[ref: docs/XDD/specs/
020-tcs-patterns-selective-install/plan/phase-3.md#T3.2]`. This file is
written against `guard.py` before that module exists, so every test below
fails for want of the module rather than passing by construction -- the RED
half of T3.2's TDD gate.

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

    report = guard.check(repo, {"ddd", "hexagonal", "observability"}, home_dir=home)

    assert report.approved == frozenset({"hexagonal", "observability"})
    assert set(report.refused) == {"ddd"}


# --- each namespace reports both locations ---------------------------------


def test_refusal_in_repo_namespace_names_the_colliding_skill_md(tmp_path: Path) -> None:
    guard = _load_guard()
    repo = tmp_path / "repo"
    home = tmp_path / "home"
    colliding_dir = _skill(repo / ".claude" / "skills", "ddd", name="ddd")

    report = guard.check(repo, {"ddd"}, home_dir=home)

    namespace, path = report.refused["ddd"]
    assert namespace == "repo"
    assert path == str(colliding_dir / "SKILL.md")


def test_refusal_in_user_namespace_names_the_colliding_skill_md(tmp_path: Path) -> None:
    guard = _load_guard()
    repo = tmp_path / "repo"
    home = tmp_path / "home"
    colliding_dir = _skill(home / ".claude" / "skills", "ddd", name="ddd")

    report = guard.check(repo, {"ddd"}, home_dir=home)

    namespace, path = report.refused["ddd"]
    assert namespace == "user"
    assert path == str(colliding_dir / "SKILL.md")


def test_refusal_in_plugin_cache_names_the_colliding_skill_md(tmp_path: Path) -> None:
    guard = _load_guard()
    repo = tmp_path / "repo"
    home = tmp_path / "home"
    colliding_dir = _skill(_cache_root(home, "claude-plugins-official", "tcs-team", "3.4.4"), "ddd", name="ddd")

    report = guard.check(repo, {"ddd"}, home_dir=home)

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

    report = guard.check(repo, {"ddd"}, home_dir=home)

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

    report = guard.check(repo, {"testing", "test-practices", "free"}, home_dir=home)

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

    report = guard.check(repo, {"hexagonal", "access", "free"}, home_dir=home)

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

    report = guard.check(repo, {"ddd", "hexagonal"}, home_dir=home)

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

    report = guard.check(repo, {"ddd"}, home_dir=home)

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
    report = guard.check(repo, {"obsidian-eval"}, home_dir=home)
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

    report = guard.check(repo, {"morning"}, home_dir=home)

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

    report = guard.check(repo, {"synced"}, home_dir=home)

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

    report = guard.check(repo, {"writing-hookify-rules", "writing-rules"}, home_dir=home)

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
    report = guard.check(repo, {"anything"}, home_dir=home)
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
    report = guard.check(repo, {"anything"}, home_dir=home)
    after = _digest_pair(repo, home)

    assert before == after, "the guard must write nothing"
    assert isinstance(report, guard.GuardReport)
    assert len(report.skipped) == 1


# --- the four malformed-input cases, and their pairwise-distinct reasons --


def test_four_malformed_skill_md_cases_have_distinguishable_reasons(tmp_path: Path) -> None:
    """None of the four occurs naturally -- all 259 real files parse
    `[ref: solution.md, fact 1]` -- so every one is constructed here. Asserts
    a PAIRWISE-DISTINCT set of reasons, not four separate non-empty checks:
    a mutation that collapses two of the four into one generic string
    survives every isolated non-empty check while failing only this
    comparison `[ref: plan/phase-3.md T3.2, "need a pairwise-distinct
    assertion"]`."""
    guard = _load_guard()
    repo = tmp_path / "repo"
    home = tmp_path / "home"
    skills_root = home / ".claude" / "skills"

    unreadable_dir = _malformed(skills_root, "unreadable", "---\nname: unreadable\n---\n")
    unreadable_path = unreadable_dir / "SKILL.md"
    os.chmod(unreadable_path, 0o000)

    _malformed(skills_root, "no-frontmatter", "just a body, no frontmatter delimiters\n")
    _malformed(skills_root, "no-name-key", "---\ndescription: missing the name key\n---\n\nBody.\n")
    _malformed(skills_root, "empty-name", '---\nname: ""\n---\n\nBody.\n')

    try:
        before = _digest_pair(repo, home)
        report = guard.check(repo, {"anything"}, home_dir=home)
        after = _digest_pair(repo, home)
    finally:
        os.chmod(unreadable_path, 0o644)

    assert before == after, "the guard must write nothing"
    assert len(report.skipped) == 4
    reasons = {reason for _path, reason in report.skipped}
    assert len(reasons) == 4, f"reasons must be pairwise distinct, got {reasons!r}"


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

    report = guard.check(repo, {"totally-free"}, home_dir=home)

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

    report = guard.check(repo, {"ddd"}, home_dir=home)

    assert report.refused["ddd"][0] == "repo"


def test_user_takes_precedence_over_plugin(tmp_path: Path) -> None:
    guard = _load_guard()
    repo = tmp_path / "repo"
    home = tmp_path / "home"
    _skill(home / ".claude" / "skills", "ddd", name="ddd")
    _skill(_cache_root(home, "claude-plugins-official", "tcs-patterns", "1.4.4"), "ddd", name="ddd")

    report = guard.check(repo, {"ddd"}, home_dir=home)

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

    report = guard.check(repo, {"ddd"}, home_dir=home)

    assert len(report.refused) == 1
    assert report.refused["ddd"][0] == "repo"


# --- GuardReport shape -------------------------------------------------------


def test_guard_report_is_frozen_with_named_channels(tmp_path: Path) -> None:
    guard = _load_guard()
    repo = tmp_path / "repo"
    home = tmp_path / "home"

    report = guard.check(repo, {"free"}, home_dir=home)

    assert hasattr(report, "approved")
    assert hasattr(report, "refused")
    assert hasattr(report, "skipped")
    with pytest.raises(Exception):
        report.approved = frozenset()  # frozen dataclass: attribute assignment must fail
