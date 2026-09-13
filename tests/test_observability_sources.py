"""`scripts/observability/sources.py` must turn the locations config into resolved sources.

Why this exists: spec-019 T3.2. `report.py` (T3.1/T3.2 of spec-018, unrelated
task numbers despite the shared digits -- see that file's own docstring) gets
no argument in this file; it reads its whole record from `--events`. Spec-019
gives the report several repositories to read from without an argument, and
this module is the piece that turns a TOML locations config (ADR-6) into
resolved, filesystem-classified sources for `report.py` (T3.3, not yet built)
to read from.

`homes` is a LIST because a single optional `home` cannot express a
repository worked on in both a container and the host at once -- one label,
one `repo` value, one section, but two record locations (SDD-AC-25). That is
the reason the schema exists in this shape, so the two-homes case is tested
first, before any single-home case a narrower schema would also have passed.

The module must be importable and unit-testable without a live session or a
real $HOME: every test here builds its own fixture directories under
`tmp_path` and passes them in explicitly, exactly like
`tests/test_observability_report.py` does for `report.py` itself.
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "observability"))

import report  # noqa: E402  (sys.path must be extended first) -- CON-6 cross-check only
import sources  # noqa: E402

SOURCES_PY = REPO_ROOT / "scripts" / "observability" / "sources.py"


# ---------------------------------------------------------------------------
# Fixture helpers.
# ---------------------------------------------------------------------------


def _mkdir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _events_path(repo_root: Path, home: Path) -> Path:
    """Independent reconstruction of the record-path formula.

    Deliberately NOT calling `sources._record_base_path` or
    `report._resolve_events_path` -- a fixture built from either production
    copy would pass even if that copy quietly drifted from the documented
    formula (`report.py:1603-1614`). This is a THIRD, independent copy, used
    only to place fixture files; `test_record_path_formula_matches_report_py`
    below is the one test that deliberately DOES call both production
    copies, to prove they still agree (CON-6).
    """
    return home / ".claude" / "plugins" / "data" / f"observability-{repo_root.name}" / "observability" / "events.jsonl"


def _write_record(repo_root: Path, home: Path, suffix: str = "") -> None:
    path = _events_path(repo_root, home)
    if suffix:
        path = path.with_name(path.name + suffix)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"ts": "2026-09-10T08:12:00Z", "kind": "state"}) + "\n", encoding="utf-8")


def _source_entry(label: str, repo_root: Path, homes: list[Path] | None = None, extra: str = "") -> str:
    lines = ["[[source]]", f'label = "{label}"', f'repo_root = "{repo_root}"']
    if homes is not None:
        homes_str = ", ".join(f'"{h}"' for h in homes)
        lines.append(f"homes = [{homes_str}]")
    if extra:
        lines.append(extra)
    return "\n".join(lines)


def _write_config(tmp_path: Path, *entries: str) -> Path:
    config = tmp_path / "observability-sources.toml"
    config.write_text("\n\n".join(entries) + "\n", encoding="utf-8")
    return config


# ---------------------------------------------------------------------------
# SDD-AC-25: a single source with two homes, merged into one section.
# Written first -- it is the reason `homes` is a list at all.
# ---------------------------------------------------------------------------


def test_two_homes_resolve_into_one_source_with_both_locations(tmp_path):
    repo_root = _mkdir(tmp_path / "repo3")
    container_home = _mkdir(tmp_path / "repo3-container-home")
    host_home = _mkdir(tmp_path / "repo3-host-home")
    _write_record(repo_root, container_home)
    # host_home deliberately gets no record: still resolved, still reported.

    config = _write_config(
        tmp_path,
        _source_entry("repo3", repo_root, homes=[container_home, host_home]),
    )

    result = sources.load_sources(config, default_home=tmp_path / "unused-default")

    assert len(result) == 1, "one [[source]] table must resolve to exactly one Source"
    src = result[0]
    assert src.label == "repo3"
    assert src.repo_root == repo_root
    assert [h.home for h in src.homes] == [container_home, host_home], (
        "homes must resolve in config order -- both locations, one label, one section"
    )
    assert src.homes[0].state == sources.RECORDING
    assert src.homes[1].state == sources.NOT_YET_RECORDING
    # A file present in only one home must not vanish: the verdict still
    # reports the source as live because at least one home is recording.
    assert src.verdict == sources.RECORDING


# ---------------------------------------------------------------------------
# SDD-AC-16: a container source (homes given) and a host source (none).
# ---------------------------------------------------------------------------


def test_container_source_and_host_source_both_resolve(tmp_path):
    container_repo = _mkdir(tmp_path / "repo1")
    container_home = _mkdir(tmp_path / "repo1-container-home")
    _write_record(container_repo, container_home)

    host_repo = _mkdir(tmp_path / "repo2")
    real_home = _mkdir(tmp_path / "the-real-home")
    _write_record(host_repo, real_home)

    config = _write_config(
        tmp_path,
        _source_entry("repo1", container_repo, homes=[container_home]),
        _source_entry("repo2", host_repo),  # no `homes` -- the real $HOME applies
    )

    result = sources.load_sources(config, default_home=real_home)

    by_label = {s.label: s for s in result}
    assert set(by_label) == {"repo1", "repo2"}

    repo1 = by_label["repo1"]
    assert repo1.homes == [sources.HomeStatus(home=container_home, state=sources.RECORDING)]

    repo2 = by_label["repo2"]
    assert repo2.homes == [sources.HomeStatus(home=real_home, state=sources.RECORDING)]


# ---------------------------------------------------------------------------
# SDD-AC-17: a configured source whose record does not exist yet.
# ---------------------------------------------------------------------------


def test_record_absent_is_not_yet_recording_and_others_still_reported(tmp_path):
    quiet_repo = _mkdir(tmp_path / "quiet-repo")
    quiet_home = _mkdir(tmp_path / "quiet-home")
    # No record written for the quiet source at all.

    live_repo = _mkdir(tmp_path / "live-repo")
    live_home = _mkdir(tmp_path / "live-home")
    _write_record(live_repo, live_home)

    config = _write_config(
        tmp_path,
        _source_entry("quiet", quiet_repo, homes=[quiet_home]),
        _source_entry("live", live_repo, homes=[live_home]),
    )

    result = sources.load_sources(config, default_home=tmp_path / "unused-default")

    by_label = {s.label: s for s in result}
    assert by_label["quiet"].homes[0].state == sources.NOT_YET_RECORDING
    assert by_label["quiet"].verdict == sources.NOT_YET_RECORDING
    # The other source is still reported, unaffected by the quiet one.
    assert by_label["live"].homes[0].state == sources.RECORDING
    assert by_label["live"].verdict == sources.RECORDING


# ---------------------------------------------------------------------------
# SDD-AC-18: a configured source whose path no longer exists.
# ---------------------------------------------------------------------------


def test_gone_repo_root_is_missing_never_recorded_nothing(tmp_path):
    gone_repo = tmp_path / "gone-repo"  # never created
    some_home = _mkdir(tmp_path / "some-home")

    config = _write_config(tmp_path, _source_entry("gone", gone_repo, homes=[some_home]))
    result = sources.load_sources(config, default_home=tmp_path / "unused-default")

    assert result[0].homes[0].state == sources.MISSING
    assert result[0].verdict == sources.MISSING


def test_gone_home_is_missing_even_though_repo_root_exists(tmp_path):
    repo_root = _mkdir(tmp_path / "repo-here")
    gone_home = tmp_path / "gone-home"  # never created

    config = _write_config(tmp_path, _source_entry("half-gone", repo_root, homes=[gone_home]))
    result = sources.load_sources(config, default_home=tmp_path / "unused-default")

    assert result[0].homes[0].state == sources.MISSING


def test_path_existence_checked_before_record_existence(tmp_path):
    """A stale record file must not make a dead `repo_root` look alive.

    `_resolve_events_path`'s directory name is built from `repo_root.name`
    -- a basename string, never existence-checked -- so a defunct
    `repo_root` can still resolve to a record file that happens to exist
    under a DIFFERENT, still-live repo_root sharing the same basename. R7:
    path existence is checked first, deliberately.
    """
    live_repo = _mkdir(tmp_path / "shared-name" / "live")
    home = _mkdir(tmp_path / "home")
    # A record exists for a *different* repo_root that happens to share the
    # same basename ("live") as the one this source will claim, but the
    # configured repo_root itself is never created.
    _write_record(live_repo, home)

    gone_repo = tmp_path / "elsewhere" / "live"  # same .name as live_repo, never created
    config = _write_config(tmp_path, _source_entry("ghost", gone_repo, homes=[home]))
    result = sources.load_sources(config, default_home=tmp_path / "unused-default")

    assert result[0].homes[0].state == sources.MISSING, (
        "a defunct repo_root must report missing, never recording, "
        "even if its basename's record directory happens to exist elsewhere"
    )


# ---------------------------------------------------------------------------
# Rotation: a record present only as a rotated generation still counts.
# ---------------------------------------------------------------------------


def test_rotated_generation_alone_still_counts_as_recording(tmp_path):
    repo_root = _mkdir(tmp_path / "rotated-repo")
    home = _mkdir(tmp_path / "rotated-home")
    _write_record(repo_root, home, suffix=".2")  # only the .2 generation exists

    config = _write_config(tmp_path, _source_entry("rotated", repo_root, homes=[home]))
    result = sources.load_sources(config, default_home=tmp_path / "unused-default")

    assert result[0].homes[0].state == sources.RECORDING


# ---------------------------------------------------------------------------
# An absent config file is not an error.
# ---------------------------------------------------------------------------


def test_absent_config_file_yields_no_sources_not_an_error(tmp_path):
    result = sources.load_sources(tmp_path / "does-not-exist.toml", default_home=tmp_path)
    assert result == []


# ---------------------------------------------------------------------------
# A TOML syntax error names the line.
# ---------------------------------------------------------------------------


def test_malformed_toml_names_the_line(tmp_path):
    config = tmp_path / "observability-sources.toml"
    config.write_text('[[source]]\nlabel = "x"\nrepo_root = \n', encoding="utf-8")

    with pytest.raises(sources.ConfigSyntaxError) as exc_info:
        sources.load_sources(config, default_home=tmp_path)

    message = str(exc_info.value)
    assert "line 3" in message, f"expected the offending line named in {message!r}"
    assert exc_info.value.lineno == 3


def test_malformed_toml_at_end_of_document_has_no_lineno(tmp_path):
    """The case that distinguishes the two designs (R4 correction).

    tomllib reports this shape as "Invalid value (at end of document)" --
    no line number in the message at all. Measured directly: on Python
    3.14 `TOMLDecodeError.lineno` nonetheless returns `2` here, while on
    3.11 the attribute does not exist. Reading the message text only (as
    `_syntax_error` does) gives `None` on BOTH interpreters for this input
    -- the one assertion that would catch a regression back to
    `error.lineno`, which would silently start returning `2` on 3.14 alone.
    """
    config = tmp_path / "observability-sources.toml"
    config.write_text('[[source]]\nlabel = ', encoding="utf-8")

    with pytest.raises(sources.ConfigSyntaxError) as exc_info:
        sources.load_sources(config, default_home=tmp_path)

    assert exc_info.value.lineno is None
    message = str(exc_info.value)
    assert "line None" not in message, f"None must never be formatted into the message: {message!r}"
    assert "could not determine the line" in message


# ---------------------------------------------------------------------------
# Schema errors name the source, not a line (R5): one test per class.
# ---------------------------------------------------------------------------


def test_schema_error_missing_repo_root_names_the_source(tmp_path):
    config = _write_config(tmp_path, '[[source]]\nlabel = "repo3"\n')

    with pytest.raises(sources.ConfigSchemaError, match=r"repo3.*repo_root"):
        sources.load_sources(config, default_home=tmp_path)


def test_schema_error_homes_as_string_not_list(tmp_path):
    config = _write_config(
        tmp_path, '[[source]]\nlabel = "repo3"\nrepo_root = "/abs/path"\nhomes = "not-a-list"\n'
    )

    with pytest.raises(sources.ConfigSchemaError, match=r"homes must be a list, got str"):
        sources.load_sources(config, default_home=tmp_path)


def test_schema_error_homes_as_an_empty_list_is_rejected(tmp_path):
    """Maintainer ruling (ab).

    `effective_homes = homes or [default_home]` folded an explicitly empty
    list into the same branch as an absent key, so `homes = []` -- which most
    plausibly means "none" -- silently produced "the default one". The value
    the operator wrote was not ignored so much as contradicted, with nothing
    on stdout to say so. This spec rejects ambiguous config at load time
    (duplicate labels, duplicate repo_root basenames); an empty list joins
    them rather than getting a fourth behaviour.
    """
    config = _write_config(
        tmp_path, '[[source]]\nlabel = "repo3"\nrepo_root = "/abs/path"\nhomes = []\n'
    )

    with pytest.raises(sources.ConfigSchemaError) as exc_info:
        sources.load_sources(config, default_home=tmp_path)

    message = str(exc_info.value)
    # Same vocabulary as every other schema refusal: the source is named, so a
    # config with several entries does not make the reader count brackets.
    assert "repo3" in message, f"the source must be named: {message!r}"
    assert "source #1" in message, f"the source index must be given: {message!r}"
    assert "homes" in message, f"the offending key must be named: {message!r}"


def test_omitting_homes_still_resolves_to_the_default_home(tmp_path):
    """The guard against ruling (ab) over-reaching.

    Omitting `homes` is the ordinary host-only case and most of the real
    config uses it. Rejecting the empty list must not disturb it.
    """
    repo_root = tmp_path / "repo3"
    repo_root.mkdir()
    default_home = tmp_path / "the-real-home"
    default_home.mkdir()

    config = _write_config(tmp_path, _source_entry("repo3", repo_root))

    result = sources.load_sources(config, default_home=default_home)

    assert len(result) == 1
    assert [h.home for h in result[0].homes] == [default_home]


def test_schema_error_unknown_key_names_the_source(tmp_path):
    config = _write_config(
        tmp_path, '[[source]]\nlabel = "repo3"\nrepo_root = "/abs/path"\nnickname = "nope"\n'
    )

    with pytest.raises(sources.ConfigSchemaError, match=r"repo3.*unknown key"):
        sources.load_sources(config, default_home=tmp_path)


def test_duplicate_labels_rejected(tmp_path):
    repo_a = _mkdir(tmp_path / "a")
    repo_b = _mkdir(tmp_path / "b")
    config = _write_config(
        tmp_path,
        _source_entry("dup", repo_a),
        _source_entry("dup", repo_b),
    )

    with pytest.raises(sources.ConfigSchemaError, match=r"duplicate label"):
        sources.load_sources(config, default_home=tmp_path)


def test_duplicate_repo_root_basenames_rejected(tmp_path):
    """Two different repo_root paths that share a basename collide on disk.

    `_record_base_path` derives the data directory from `repo_root.name`
    alone (sources.py:157-168), and logwrite.sh freezes the `repo` field the
    same way -- so `/work/tcs` and `/archive/tcs` would resolve to the same
    record file and be indistinguishable by `repo` in the report, even
    though the config author gave them distinct labels.
    """
    repo_work = _mkdir(tmp_path / "work" / "tcs")
    repo_archive = _mkdir(tmp_path / "archive" / "tcs")
    config = _write_config(
        tmp_path,
        _source_entry("work-copy", repo_work),
        _source_entry("archive-copy", repo_archive),
    )

    with pytest.raises(sources.ConfigSchemaError) as exc_info:
        sources.load_sources(config, default_home=tmp_path)

    message = str(exc_info.value)
    assert "work-copy" in message, f"the earlier source's label must be named: {message!r}"
    assert "archive-copy" in message, f"the offending source's own label must be named: {message!r}"
    assert "'tcs'" in message, f"the colliding basename must be named: {message!r}"


def test_different_repo_root_basenames_still_accepted(tmp_path):
    """Distinct basenames must not trip the new guard -- the common case."""
    repo_a = _mkdir(tmp_path / "repo-a")
    repo_b = _mkdir(tmp_path / "repo-b")
    config = _write_config(
        tmp_path,
        _source_entry("a", repo_a),
        _source_entry("b", repo_b),
    )

    result = sources.load_sources(config, default_home=tmp_path)

    assert {s.label for s in result} == {"a", "b"}


def test_duplicate_label_fires_before_basename_collision(tmp_path):
    """When a config violates both checks at once, the label check wins.

    Deliberate ordering (see `_parse_document`): the duplicate-label check
    runs first in the per-entry loop, so a source that repeats an earlier
    label is rejected for that reason even if its repo_root basename also
    collides.
    """
    repo_a = _mkdir(tmp_path / "work" / "tcs")
    repo_b = _mkdir(tmp_path / "archive" / "tcs")
    config = _write_config(
        tmp_path,
        _source_entry("dup", repo_a),
        _source_entry("dup", repo_b),
    )

    with pytest.raises(sources.ConfigSchemaError, match=r"duplicate label"):
        sources.load_sources(config, default_home=tmp_path)


# ---------------------------------------------------------------------------
# CON-4/ADR-6: the config path is gitignored -- a requirement, not a
# convenience, so it is a test rather than a comment (R9).
# ---------------------------------------------------------------------------


def test_config_path_is_gitignored():
    """Runs against THIS repository's own committed .gitignore, in place.

    NOT a synthetic fixture tree: the property under test is that this
    repo's real .gitignore covers the real config path, and a fixture
    directory with no ignore rules at all would test something else
    entirely. `GIT_CONFIG_GLOBAL=/dev/null` alone is not sufficient
    isolation -- it still falls back to reading `~/.config/git/ignore`,
    which has previously made a fixture report the opposite of the truth
    (docs/ai/memory/active.md) -- so `-c core.excludesFile=/dev/null` is
    passed as well.
    """
    config_path = REPO_ROOT / ".claude" / sources.CONFIG_FILENAME
    env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull}
    result = subprocess.run(
        [
            "git", "-C", str(REPO_ROOT),
            "-c", "core.excludesFile=/dev/null",
            "check-ignore", "-q", "--", str(config_path),
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f".claude/{sources.CONFIG_FILENAME} must be gitignored; "
        f"check-ignore exited {result.returncode}: {result.stderr}"
    )


# ---------------------------------------------------------------------------
# CON-3: no new runtime dependency -- sources.py imports only the stdlib.
# ---------------------------------------------------------------------------


def test_stdlib_module_names_available_this_interpreter():
    """Sanity check for R8's own foundation, not a `sources.py` behaviour.

    `sys.stdlib_module_names` was added in 3.10; CI runs 3.11 (R3). Asserted
    directly here, and separately confirmed against 3.11 itself via `uv run
    --python 3.11` (see this task's validation report) rather than assumed.
    """
    assert "tomllib" in sys.stdlib_module_names


def test_sources_py_imports_only_stdlib():
    """AST-based, not `sys.modules`-based (R8).

    A runtime check (`try: import tomli / except ImportError: import
    tomllib`) only reveals whichever branch happened to execute -- on a
    machine where `tomli` is installed, the forbidden branch would run and
    a `sys.modules`-based test would still pass. `ast.walk` sees every
    `Import`/`ImportFrom` node regardless of which branch runs, and even one
    nested inside a function body that this test never calls.
    """
    tree = ast.parse(SOURCES_PY.read_text(encoding="utf-8"), filename=str(SOURCES_PY))
    stdlib = sys.stdlib_module_names

    seen: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                seen.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:  # None only for a relative "from . import x", unused here
                seen.append(node.module)

    assert seen, "sanity: sources.py must import something (tomllib, at least)"
    for name in seen:
        top = name.split(".")[0]
        assert top in stdlib, f"sources.py imports {name!r}, which is not in sys.stdlib_module_names"


# ---------------------------------------------------------------------------
# CON-6: the record-path formula must not drift from report.py's own.
# ---------------------------------------------------------------------------


def test_record_path_formula_matches_report_py(tmp_path):
    """`sources._record_base_path` and `report._resolve_events_path` must
    agree on every input, since CON-6 requires the record's location and
    the instruction-inventory walk to stay consistently derived from
    `$HOME`. Deliberately reaching into both modules' private functions --
    the one place in this suite that does -- because this specific
    agreement has no other way to be exercised without duplicating the
    formula a third time in production code, which is exactly what R1
    forbids.
    """
    repo_root = tmp_path / "some-repo"
    home = tmp_path / "some-home"

    assert sources._record_base_path(repo_root, home) == report._resolve_events_path(None, repo_root, home)
