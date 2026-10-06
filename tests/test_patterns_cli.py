"""T5.1a (spec-020): `lib/cli.py`, the one entry point the patterns-setup skill runs.

Contract `[ref: SDD/Interface Specifications/Process contract: the CLI the
skill drives (C3's seam)]` and `plan/phase-5.md` T5.1a, "The CLI".

Almost every verb runs as a **subprocess** of `python3 <abs path>/lib/cli.py` from a
cwd that is not the repository, with `HOME` at a `tmp_path` (so the guard's
user namespace is a fixture) and `--catalogue` at a fixture catalogue, unless
a test says otherwise (the in-process ones say so in their own docstrings). Fixture repositories are made with `git -C <dir> init`
and `GIT_CONFIG_GLOBAL=/dev/null`, so nothing depends on the cwd or on the
user's git config.

**Expected values are hand-typed.** The top-level key sets, the four-outcome
partition, the listing costs and the status table below come from the
contract's prose and the fixture's text, never from the library the CLI
calls -- a check whose expected value came from the code under test cannot
see what that code does wrong.

Library modules are imported inside each test, never at module level (the
loader convention of `test_patterns_installer.py`).
"""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
LIB_DIR = REPO_ROOT / "plugins" / "tcs-patterns" / "skills" / "patterns-setup" / "lib"
CLI = LIB_DIR / "cli.py"

BUNDLE = "1.0.0"

# The contract's tables, typed by hand -- `==`, so an extra key fails too.
SCAN_KEYS = {"repo", "report", "outcomes", "companions", "listing_cost"}
INSTALL_KEYS = {"repo", "installed", "unchanged", "failed", "refused", "skipped", "committed"}
UPDATE_KEYS = {"repo", "refreshed", "declined", "current", "failed", "committed"}
REMOVE_KEYS = {"repo", "removed", "refused", "failed", "committed"}
STATUS_KEYS = {"repo", "manifest", "patterns", "unlisted", "debris"}


def _load_lib(name: str) -> ModuleType:
    if str(LIB_DIR) not in sys.path:
        sys.path.insert(0, str(LIB_DIR))
    return importlib.import_module(name)


def _digest(root: Path) -> str:
    """Every entry under `root`, with its bytes; symlinks recorded, never followed."""
    h = hashlib.sha256()
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames.sort()
        for name in sorted([*dirnames, *filenames]):
            p = Path(dirpath) / name
            rel = p.relative_to(root).as_posix()
            if p.is_symlink():
                h.update(f"L {rel} -> {os.readlink(p)}\n".encode())
            elif p.is_dir():
                h.update(f"D {rel}\n".encode())
            else:
                h.update(f"F {rel}\n".encode())
                h.update(p.read_bytes())
    return h.hexdigest()


# =============================================================================
# The fixture catalogue
# =============================================================================
#
# Six patterns. Each SKILL.md is four frontmatter lines between two `---`
# delimiters (5 lines), a blank line, then one body line -- so the body's
# citation sits on line 7.
#
#   python-project  cites `reference/hex-guide.md`  -> only hexagonal has it: edge to hexagonal
#   ddd             cites `reference/hex-guide.md`  -> edge to hexagonal
#   hexagonal       cites `reference/fn-guide.md`   -> only functional has it: edge to functional
#   testing         cites `reference/shared.md`     -> api-design AND ddd have it: ambiguous
#
# Descriptions, and the listing cost each gives (len("tcs-"+p) + min(len(d), 1536)):
#   python-project  "Python projects \"done\" right" -> 28 chars (the \" is one); 18 + 28 = 46
#   hexagonal       Ports and adapters               -> 18;                      13 + 18 = 31
#   functional      2000 x "a"                       -> capped at 1536;          14 + 1536 = 1550
#   ddd             'Domain modelling — it''s DDD'   -> 27 (the '' is one);       7 + 27 = 34
#   api-design      "Design APIs — well"             -> 18;                      14 + 18 = 32
#   testing         >  (a block scalar)              -> unparseable: null
#   observability   two description: lines           -> no single line: null

FIXTURE_DESCRIPTIONS = {
    "python-project": 'description: "Python projects \\"done\\" right"',
    "hexagonal": "description: Ports and adapters",
    "functional": "description: " + "a" * 2000,
    "ddd": "description: 'Domain modelling — it''s DDD'",
    "api-design": 'description: "Design APIs — well"',
    "testing": "description: >",
    "observability": "description: one\ndescription: two",
}
FIXTURE_BODIES = {
    "python-project": "See `reference/hex-guide.md`.\n",
    "ddd": "See `reference/hex-guide.md`.\n",
    "hexagonal": "See `reference/fn-guide.md`.\n",
    "testing": "See `reference/shared.md`.\n",
    "functional": "Pure functions.\n",
    "api-design": "Resources.\n",
    "observability": "Signals.\n",
}
FIXTURE_REFERENCES = {
    "hexagonal": ["hex-guide.md"],
    "functional": ["fn-guide.md"],
    "ddd": ["shared.md"],
    "api-design": ["shared.md"],
}
EXPECTED_FIXTURE_COSTS = {
    "python-project": 46,
    "hexagonal": 31,
    "functional": 1550,
    "ddd": 34,
    "api-design": 32,
    "testing": None,
    "observability": None,
}


def _write_pattern(cat: Path, name: str, *, version: str = "1", body: str | None = None) -> None:
    d = cat / name
    (d / "reference").mkdir(parents=True, exist_ok=True)
    (d / "VERSION").write_text(f"{version}\n", encoding="utf-8")
    text = f"---\nname: {name}\n{FIXTURE_DESCRIPTIONS[name]}\nuser-invocable: true\n---\n\n"
    text += FIXTURE_BODIES[name] if body is None else body
    (d / "SKILL.md").write_text(text, encoding="utf-8")
    for ref in FIXTURE_REFERENCES.get(name, []):
        (d / "reference" / ref).write_text(f"{name} {ref}\n", encoding="utf-8")


def _git(*args: str) -> None:
    env = {**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"}
    subprocess.run(["git", *args], check=True, capture_output=True, env=env)


@dataclass
class World:
    tmp: Path
    home: Path
    cat: Path
    repo: Path  # the git toplevel, resolved -- what `repo` in every document must equal
    elsewhere: Path  # the cwd each subprocess runs from; not the repository


@pytest.fixture
def world(tmp_path: Path) -> World:
    home = tmp_path / "home"
    home.mkdir()
    cat = tmp_path / "catalogue"
    for name in FIXTURE_DESCRIPTIONS:
        _write_pattern(cat, name)
    repo = tmp_path / "repo"
    repo.mkdir()
    _git("-C", str(repo), "init", "-q")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    return World(tmp=tmp_path, home=home, cat=cat, repo=repo.resolve(), elsewhere=elsewhere)


def _run(
    w: World, *args: str, catalogue: bool = True, env: dict | None = None
) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(CLI)]
    if catalogue:
        cmd += ["--catalogue", str(w.cat)]
    cmd += list(args)
    full_env = {**os.environ, "HOME": str(w.home), "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"}
    full_env.pop("PYTHONIOENCODING", None)
    full_env.update(env or {})
    return subprocess.run(cmd, capture_output=True, cwd=w.elsewhere, env=full_env)


def _doc(r: subprocess.CompletedProcess) -> dict:
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")
    text = r.stdout.decode("utf-8")
    assert text.endswith("\n") and text.count("\n") == 1, "one JSON document, one line"
    return json.loads(text)


def _refused(r: subprocess.CompletedProcess, code: int) -> None:
    assert r.returncode == code, (r.returncode, r.stderr.decode("utf-8", "replace"))
    assert r.stdout == b""
    assert r.stderr.strip(), "a refusal says why on stderr"


def _library_install(w: World, names: list[str], repo: Path | None = None) -> None:
    report = _load_lib("install").install(repo or w.repo, names, catalogue_dir=w.cat, bundle=BUNDLE)
    assert not report.failed, report.failed


def _skills(repo: Path) -> Path:
    return repo / ".claude" / "skills"


def _manifest_path(repo: Path) -> Path:
    return _skills(repo) / ".tcs-patterns-manifest"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _scan_repo(w: World) -> None:
    """python-project fires (a .py file + pyproject.toml); fastapi is a runtime
    dependency, so q1_backend opens and q2_architecture with it; there is no
    test framework, so q3_test_quality stays closed and `testing` does not fire."""
    (w.repo / "pyproject.toml").write_text(
        '[project]\nname = "x"\ndependencies = ["fastapi"]\n', encoding="utf-8"
    )
    (w.repo / "app.py").write_text("print(1)\n", encoding="utf-8")


# =============================================================================
# Every verb: exact top-level keys, the toplevel as `repo`
# =============================================================================


def test_scan_keys_and_outcomes_null_without_answers(world: World) -> None:
    _scan_repo(world)
    doc = _doc(_run(world, "scan", str(world.repo)))
    assert set(doc) == SCAN_KEYS
    assert doc["repo"] == str(world.repo)
    assert doc["outcomes"] is None
    assert set(doc["companions"]) == {"proposed", "ambiguous"}
    report = doc["report"]
    assert report["repo"] == str(world.repo)
    assert [e["pattern"] for e in report["auto"]] == ["python-project"]
    assert report["baseline"] == []
    assert report["gates"] == {"q1_backend": True, "q2_architecture": True, "q3_test_quality": False}
    assert report["unreadable"] == []


def test_install_keys_and_nested_fields(world: World) -> None:
    doc = _doc(_run(world, "install", str(world.repo), "hexagonal"))
    assert set(doc) == INSTALL_KEYS
    assert doc["repo"] == str(world.repo)
    assert doc["committed"] is False
    assert doc["refused"] == {} and doc["failed"] == {} and doc["unchanged"] == {} and doc["skipped"] == []
    installed_skill = _skills(world.repo) / "tcs-hexagonal" / "SKILL.md"
    assert doc["installed"] == {
        "hexagonal": {"installed_as": "tcs-hexagonal", "version": "1", "sha256": _sha(installed_skill)}
    }
    again = _doc(_run(world, "install", str(world.repo), "hexagonal"))
    assert again["installed"] == {}
    assert again["unchanged"] == {
        "hexagonal": {"installed_as": "tcs-hexagonal", "version": "1", "sha256": _sha(installed_skill)}
    }


def test_update_keys(world: World) -> None:
    _library_install(world, ["hexagonal"])
    doc = _doc(_run(world, "update", str(world.repo)))
    assert set(doc) == UPDATE_KEYS
    assert doc["repo"] == str(world.repo)
    assert doc["committed"] is False
    sha = _sha(_skills(world.repo) / "tcs-hexagonal" / "SKILL.md")
    assert doc["current"] == {"hexagonal": {"installed_as": "tcs-hexagonal", "version": "1", "sha256": sha}}
    assert doc["refreshed"] == {} and doc["declined"] == {} and doc["failed"] == {}


def test_remove_keys(world: World) -> None:
    _library_install(world, ["hexagonal"])
    doc = _doc(_run(world, "remove", str(world.repo), "hexagonal"))
    assert set(doc) == REMOVE_KEYS
    assert doc["repo"] == str(world.repo)
    assert doc["committed"] is False
    assert doc["removed"] == {
        "hexagonal": {"installed_as": "tcs-hexagonal", "version": "1", "directory_existed": True}
    }
    assert doc["refused"] == {} and doc["failed"] == {}


def test_status_keys(world: World) -> None:
    doc = _doc(_run(world, "status", str(world.repo)))
    assert set(doc) == STATUS_KEYS
    assert doc["repo"] == str(world.repo)
    assert doc["manifest"] == {"state": "absent", "error": None, "bundle": None}
    assert doc["patterns"] == {} and doc["unlisted"] == [] and doc["debris"] == []


@pytest.mark.parametrize("verb", ["scan", "install", "update", "remove", "status"])
def test_a_subdirectory_resolves_to_the_toplevel(world: World, verb: str) -> None:
    _library_install(world, ["hexagonal"])
    sub = world.repo / "src" / "deep"
    sub.mkdir(parents=True)
    args = {"install": ["hexagonal"], "remove": ["hexagonal"]}.get(verb, [])
    doc = _doc(_run(world, verb, str(sub), *args))
    assert doc["repo"] == str(world.repo)
    if verb == "scan":
        assert doc["report"]["repo"] == str(world.repo)
    if verb == "remove":
        assert doc["removed"]["hexagonal"]["directory_existed"] is True
        assert not (_skills(world.repo) / "tcs-hexagonal").exists()
    if verb == "install":
        assert "hexagonal" in doc["unchanged"]
        assert not (sub / ".claude").exists()


# =============================================================================
# Outside a git repository: exit 3, before anything is read
# =============================================================================


@pytest.mark.parametrize(
    "verb,args",
    [
        ("scan", []),
        ("install", ["ddd"]),
        ("update", []),
        ("remove", ["hexagonal"]),
        ("status", []),
    ],
)
def test_outside_a_git_repository_every_verb_exits_3(world: World, verb: str, args: list[str]) -> None:
    """The target holds a valid manifest and an installed pattern, so a CLI
    that skipped the git check would succeed here (exit 0) for every verb."""
    outside = world.tmp / "outside"
    outside.mkdir()
    _library_install(world, ["hexagonal"], repo=outside)
    (outside / "app.py").write_text("print(1)\n", encoding="utf-8")
    before = _digest(outside)
    ceiling = os.pathsep.join([str(world.tmp), str(world.tmp.resolve())])
    r = _run(world, verb, str(outside), *args, env={"GIT_CEILING_DIRECTORIES": ceiling})
    _refused(r, 3)
    assert b"not inside a git repository" in r.stderr
    assert _digest(outside) == before


@pytest.mark.parametrize("verb", ["scan", "status", "update"])
def test_a_path_that_does_not_exist_exits_3(world: World, verb: str) -> None:
    _refused(_run(world, verb, str(world.tmp / "no-such-dir")), 3)


@pytest.mark.parametrize(
    "argv",
    [
        ["scan", "{outside}"],
        ["install", "{outside}", "ddd"],
        ["update", "{outside}"],
        ["remove", "{outside}", "ddd"],
        ["status", "{outside}"],
    ],
)
def test_outside_a_repository_no_library_call_is_reached(
    world: World, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture, argv: list[str]
) -> None:
    """In process, with every reading and writing library entry point made to
    raise: exit 3 proves none was reached -- the git check comes first."""
    outside = world.tmp / "outside"
    outside.mkdir()
    ceiling = os.pathsep.join([str(world.tmp), str(world.tmp.resolve())])
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", ceiling)
    monkeypatch.setenv("HOME", str(world.home))

    class Reached(Exception):
        pass

    def boom(*_a, **_k):
        raise Reached("a library call ran before the git check")

    cli = _load_lib("cli")
    for module, attr in [
        ("detect", "detect"),
        ("manifest", "read"),
        ("status", "status"),
        ("install", "install"),
        ("install", "update"),
        ("install", "remove"),
        ("guard", "check"),
    ]:
        monkeypatch.setattr(_load_lib(module), attr, boom)

    argv = [a.replace("{outside}", str(outside)) for a in argv]
    assert cli.main(["--catalogue", str(world.cat), *argv]) == 3
    assert capsys.readouterr().out == ""


def test_an_interpreter_older_than_3_11_exits_3(
    world: World, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Inside a real repository, so only the version check can refuse."""
    cli = _load_lib("cli")
    monkeypatch.setenv("HOME", str(world.home))
    monkeypatch.setattr(sys, "version_info", (3, 10, 14, "final", 0))
    code = cli.main(["--catalogue", str(world.cat), "status", str(world.repo)])
    monkeypatch.undo()
    captured = capsys.readouterr()
    assert code == 3
    assert captured.out == ""
    assert "3.11" in captured.err


# =============================================================================
# Usage errors: exit 2, stdout empty, nothing written
# =============================================================================


@pytest.mark.parametrize(
    "argv",
    [
        ["frobnicate", "{repo}"],
        ["install", "{repo}"],
        ["install", "{repo}", "not-a-pattern"],
        ["install", "{repo}", "hexagonal", "not-a-pattern"],
        ["scan", "{repo}", "--answers", '{"q3_test_quality": []}'],
        ["scan", "{repo}", "--answers", '{"q1_backend": ["ddd"]}'],
        ["scan", "{repo}", "--answers", '{"no_such_gate": []}'],
        ["scan", "{repo}", "--answers", '["q1_backend"]'],
        ["scan", "{repo}", "--answers", "{not json"],
        ["scan", "{repo}", "--answers", '{"q1_backend": "api-design"}'],
        ["remove", "{repo}", "hexagonal", "--force", "ddd"],
    ],
    ids=[
        "unknown-verb",
        "install-no-names",
        "install-non-catalogue-name",
        "install-one-bad-name-among-good",
        "answers-closed-gate",
        "answers-pattern-its-gate-does-not-settle",
        "answers-unknown-gate",
        "answers-not-an-object",
        "answers-not-json",
        "answers-value-not-an-array",
        "force-names-a-pattern-not-being-removed",
    ],
)
def test_usage_errors_exit_2_and_write_nothing(world: World, argv: list[str]) -> None:
    _scan_repo(world)
    _library_install(world, ["hexagonal", "ddd"])
    before = _digest(world.repo)
    r = _run(world, *[a.replace("{repo}", str(world.repo)) for a in argv])
    _refused(r, 2)
    assert _digest(world.repo) == before


def test_install_checks_catalogue_names_before_the_guard(
    world: World, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """A typo is a usage error before any namespace is walked: with the guard
    made to raise, a non-catalogue name still exits 2."""
    monkeypatch.setenv("HOME", str(world.home))
    cli = _load_lib("cli")

    def guard_ran(*_a, **_k):
        raise AssertionError("guard.check ran before the catalogue-name check")

    monkeypatch.setattr(_load_lib("guard"), "check", guard_ran)
    code = cli.main(["--catalogue", str(world.cat), "install", str(world.repo), "hexagonal", "typo"])
    assert code == 2
    assert capsys.readouterr().out == ""
    assert not _skills(world.repo).exists()


# =============================================================================
# --help: stdout carries one JSON document or nothing, so help goes to stderr
# =============================================================================


@pytest.mark.parametrize("argv", [["--help"], ["scan", "-h"]], ids=["top-level", "scan"])
def test_help_goes_to_stderr_and_leaves_stdout_empty(world: World, argv: list[str]) -> None:
    r = _run(world, *argv)
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")
    assert r.stdout == b""
    assert b"usage" in r.stderr.lower()


# =============================================================================
# Exit 3: the manifest cannot be read, and --accept naming an unlisted pattern
# =============================================================================


@pytest.mark.parametrize(
    "argv",
    [["install", "{repo}", "ddd"], ["update", "{repo}"], ["remove", "{repo}", "hexagonal"]],
    ids=["install", "update", "remove"],
)
def test_an_unparseable_manifest_exits_3_on_every_writing_verb(world: World, argv: list[str]) -> None:
    _library_install(world, ["hexagonal"])
    _manifest_path(world.repo).write_text("this is [not toml\n", encoding="utf-8")
    before = _digest(world.repo)
    r = _run(world, *[a.replace("{repo}", str(world.repo)) for a in argv])
    _refused(r, 3)
    assert b".tcs-patterns-manifest" in r.stderr
    assert b"status" in r.stderr
    assert _digest(world.repo) == before


@pytest.mark.parametrize(
    "argv",
    [["install", "{repo}", "ddd"], ["update", "{repo}"], ["remove", "{repo}", "hexagonal"]],
    ids=["install", "update", "remove"],
)
def test_an_unreadable_manifest_exits_3_on_every_writing_verb(world: World, argv: list[str]) -> None:
    """A PermissionError is an OSError, not a ManifestUnparseableError: the
    other half of the up-front read's refusal. (A manifest path that is a
    directory would not do: `manifest.read` treats a non-file as absent.)"""
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        pytest.skip("root ignores file permissions")
    _library_install(world, ["hexagonal"])
    path = _manifest_path(world.repo)
    before = _digest(world.repo)
    path.chmod(0)
    try:
        r = _run(world, *[a.replace("{repo}", str(world.repo)) for a in argv])
    finally:
        path.chmod(0o644)
    _refused(r, 3)
    assert b"status" in r.stderr
    assert _digest(world.repo) == before


def test_update_accept_naming_an_unlisted_pattern_exits_3(world: World) -> None:
    _library_install(world, ["hexagonal"])
    _write_pattern(world.cat, "hexagonal", version="2", body="Body v2.\n")
    before = _digest(world.repo)
    r = _run(world, "update", str(world.repo), "--accept", "hexagonl")
    _refused(r, 3)
    assert b"hexagonl" in r.stderr
    assert _digest(world.repo) == before


# =============================================================================
# scan
# =============================================================================


def test_scan_with_answers_returns_the_four_outcome_partition(world: World) -> None:
    """Hand-typed for `_scan_repo`: python-project is the one stack fact that
    fired; q1 and q2 opened and were asked; q3 stayed closed."""
    _scan_repo(world)
    answers = json.dumps({"q1_backend": ["api-design"], "q2_architecture": []})
    doc = _doc(_run(world, "scan", str(world.repo), "--answers", answers))
    assert doc["outcomes"] == {
        "installed": ["api-design", "python-project"],
        "declined_by_question": [
            "bff-entry-points",
            "ddd",
            "event-driven",
            "event-sourcing",
            "functional",
            "hexagonal",
            "node-service",
            "observability",
            "secure-oauth-oidc",
            "twelve-factor",
        ],
        "excluded_by_stack_fact": [
            "frontend-testing",
            "go-idiomatic",
            "mcp-server",
            "obsidian-plugin",
            "react-testing",
            "testing",
            "typescript-strict",
        ],
        "not_reached": ["mutation-testing", "test-design-reviewer"],
    }


def test_scan_an_open_gate_absent_from_answers_means_none_chosen(world: World) -> None:
    _scan_repo(world)
    doc = _doc(_run(world, "scan", str(world.repo), "--answers", "{}"))
    assert doc["outcomes"]["installed"] == ["python-project"]
    assert "api-design" in doc["outcomes"]["declined_by_question"]


def test_scan_companions_without_answers_start_from_the_proposal(world: World) -> None:
    """Selection = auto + baseline = {python-project}: hexagonal comes from it,
    functional from hexagonal (the closure). Each citation names its file and
    line; `source_file` is catalogue-relative."""
    _scan_repo(world)
    doc = _doc(_run(world, "scan", str(world.repo)))
    assert doc["companions"]["proposed"] == {
        "hexagonal": [
            {"from": "python-project", "source_file": "python-project/SKILL.md", "line": 7,
             "target": "reference/hex-guide.md"},
        ],
        "functional": [
            {"from": "hexagonal", "source_file": "hexagonal/SKILL.md", "line": 7,
             "target": "reference/fn-guide.md"},
        ],
    }
    for cited in doc["companions"]["proposed"].values():
        for c in cited:
            assert (world.cat / c["source_file"]).is_file()
    assert doc["companions"]["ambiguous"] == [
        {"source_file": "testing/SKILL.md", "line": 7, "target": "reference/shared.md",
         "candidate_patterns": ["api-design", "ddd"]},
    ]


def test_scan_companions_with_answers_start_from_outcomes_installed(world: World) -> None:
    """Choosing ddd adds a second citation into hexagonal -- from ddd, which
    only the answered selection contains."""
    _scan_repo(world)
    answers = json.dumps({"q2_architecture": ["ddd"]})
    doc = _doc(_run(world, "scan", str(world.repo), "--answers", answers))
    assert doc["outcomes"]["installed"] == ["ddd", "python-project"]
    assert doc["companions"]["proposed"] == {
        "hexagonal": [
            {"from": "ddd", "source_file": "ddd/SKILL.md", "line": 7, "target": "reference/hex-guide.md"},
            {"from": "python-project", "source_file": "python-project/SKILL.md", "line": 7,
             "target": "reference/hex-guide.md"},
        ],
        "functional": [
            {"from": "hexagonal", "source_file": "hexagonal/SKILL.md", "line": 7,
             "target": "reference/fn-guide.md"},
        ],
    }


def test_scan_listing_cost_against_the_fixture_catalogue(world: World) -> None:
    """Keys equal the catalogue's pattern directories (a hidden directory is
    not a pattern); values are hand-computed in the fixture comment above."""
    (world.cat / ".claude").mkdir()
    _scan_repo(world)
    doc = _doc(_run(world, "scan", str(world.repo)))
    pattern_dirs = {p.name for p in world.cat.iterdir() if p.is_dir() and not p.name.startswith(".")}
    assert set(doc["listing_cost"]) == pattern_dirs
    assert doc["listing_cost"] == EXPECTED_FIXTURE_COSTS


def test_scan_listing_cost_against_the_real_catalogue(world: World) -> None:
    """REAL CATALOGUE, no `--catalogue`. 21 patterns summing to 5990, measured
    2026-10-06 `[ref: SDD/Process contract: the CLI the skill drives, "Listing
    cost, defined"]`. This figure is EXPECTED TO CHANGE whenever any pattern's
    `description:` changes or a pattern is added or removed -- update it in
    the same commit as that change."""
    _scan_repo(world)
    doc = _doc(_run(world, "scan", str(world.repo), catalogue=False))
    costs = doc["listing_cost"]
    assert len(costs) == 21
    assert None not in costs.values()
    assert sum(costs.values()) == 5990


def test_scan_reports_what_it_could_not_read(world: World) -> None:
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        pytest.skip("root ignores file permissions")
    _scan_repo(world)
    locked = world.repo / "locked"
    locked.mkdir()
    locked.chmod(0)
    try:
        doc = _doc(_run(world, "scan", str(world.repo)))
    finally:
        locked.chmod(0o755)
    assert doc["report"]["unreadable"] == ["locked/"]


# =============================================================================
# install: guard first, only what it cleared, no companions
# =============================================================================


def test_install_a_user_namespace_collision_is_refused_with_both_locations(world: World) -> None:
    taken = world.home / ".claude" / "skills" / "tcs-ddd"
    taken.mkdir(parents=True)
    (taken / "SKILL.md").write_text("---\nname: tcs-ddd\ndescription: mine\n---\n", encoding="utf-8")
    doc = _doc(_run(world, "install", str(world.repo), "ddd", "hexagonal"))
    assert doc["refused"] == {
        "ddd": {
            "installed_as": "tcs-ddd",
            "namespace": "user",
            "path": str(taken / "SKILL.md"),
            "intended_path": str(_skills(world.repo) / "tcs-ddd"),
        }
    }
    assert set(doc["installed"]) == {"hexagonal"}
    assert not (_skills(world.repo) / "tcs-ddd").exists()
    assert (_skills(world.repo) / "tcs-hexagonal" / "SKILL.md").is_file()
    manifest = _manifest_path(world.repo).read_text(encoding="utf-8")
    assert "hexagonal" in manifest and "[patterns.ddd]" not in manifest


def test_install_with_every_name_refused_installs_nothing_and_writes_no_manifest(world: World) -> None:
    taken = world.home / ".claude" / "skills" / "tcs-ddd"
    taken.mkdir(parents=True)
    (taken / "SKILL.md").write_text("---\nname: tcs-ddd\ndescription: mine\n---\n", encoding="utf-8")
    doc = _doc(_run(world, "install", str(world.repo), "ddd"))
    assert doc["installed"] == {}
    assert list(doc["refused"]) == ["ddd"]
    assert not _manifest_path(world.repo).exists()


def test_install_reports_what_the_guard_skipped(world: World) -> None:
    broken = world.home / ".claude" / "skills" / "broken"
    broken.mkdir(parents=True)
    (broken / "SKILL.md").write_text("no frontmatter here\n", encoding="utf-8")
    doc = _doc(_run(world, "install", str(world.repo), "hexagonal"))
    assert doc["skipped"] == [{"path": str(broken / "SKILL.md"), "reason": "no usable frontmatter block"}]
    assert set(doc["installed"]) == {"hexagonal"}


def test_install_does_not_add_companions(world: World) -> None:
    """ddd cites hexagonal in the fixture catalogue; installing ddd alone
    writes ddd alone."""
    doc = _doc(_run(world, "install", str(world.repo), "ddd"))
    assert set(doc["installed"]) == {"ddd"}
    assert sorted(p.name for p in _skills(world.repo).iterdir()) == [".tcs-patterns-manifest", "tcs-ddd"]


# =============================================================================
# update: non-interactive; diverged declined unless --accept names it
# =============================================================================


def _diverged_and_behind(w: World) -> Path:
    """ddd and hexagonal installed at 1; the catalogue moves both to 2; the
    user edits installed ddd. Returns ddd's installed SKILL.md."""
    _library_install(w, ["ddd", "hexagonal"])
    _write_pattern(w.cat, "ddd", version="2", body="Body v2 — upstream.\n")
    _write_pattern(w.cat, "hexagonal", version="2", body="Body v2.\n")
    edited = _skills(w.repo) / "tcs-ddd" / "SKILL.md"
    edited.write_text(edited.read_text(encoding="utf-8") + "My own edit.\n", encoding="utf-8")
    return edited


def test_update_without_accept_declines_a_diverged_pattern_byte_identical(world: World) -> None:
    edited = _diverged_and_behind(world)
    before = edited.read_bytes()
    doc = _doc(_run(world, "update", str(world.repo)))
    assert edited.read_bytes() == before
    assert set(doc["declined"]) == {"ddd"}
    assert doc["declined"]["ddd"]["version"] == "1"
    diff = doc["declined"]["ddd"]["diff"]
    assert diff.startswith("--- installed")
    assert "-My own edit.\n" in diff
    hexagonal_skill = _skills(world.repo) / "tcs-hexagonal" / "SKILL.md"
    assert doc["refreshed"] == {
        "hexagonal": {
            "installed_as": "tcs-hexagonal",
            "version_before": "1",
            "version_after": "2",
            "sha256": _sha(hexagonal_skill),
        }
    }
    assert "Body v2." in hexagonal_skill.read_text(encoding="utf-8")


def test_update_with_accept_refreshes_only_the_named_pattern(world: World) -> None:
    edited = _diverged_and_behind(world)
    _doc(_run(world, "update", str(world.repo)))  # hexagonal refreshes; ddd declined
    doc = _doc(_run(world, "update", str(world.repo), "--accept", "ddd"))
    assert set(doc["refreshed"]) == {"ddd"}
    assert doc["refreshed"]["ddd"]["version_after"] == "2"
    assert set(doc["current"]) == {"hexagonal"}
    assert doc["declined"] == {}
    assert "My own edit." not in edited.read_text(encoding="utf-8")


def test_update_accept_on_one_of_two_diverged_leaves_the_other(world: World) -> None:
    edited_ddd = _diverged_and_behind(world)
    edited_hex = _skills(world.repo) / "tcs-hexagonal" / "SKILL.md"
    edited_hex.write_text(edited_hex.read_text(encoding="utf-8") + "Hex edit.\n", encoding="utf-8")
    hex_before = edited_hex.read_bytes()
    doc = _doc(_run(world, "update", str(world.repo), "--accept", "ddd"))
    assert set(doc["refreshed"]) == {"ddd"}
    assert set(doc["declined"]) == {"hexagonal"}
    assert edited_hex.read_bytes() == hex_before
    assert "My own edit." not in edited_ddd.read_text(encoding="utf-8")


# =============================================================================
# remove and status: the library's results, in the contract's shape
# =============================================================================


def test_remove_passes_through_removed_refused_and_force(world: World) -> None:
    _library_install(world, ["ddd", "hexagonal"])
    edited = _skills(world.repo) / "tcs-hexagonal" / "SKILL.md"
    edited.write_text(edited.read_text(encoding="utf-8") + "Edit.\n", encoding="utf-8")
    doc = _doc(_run(world, "remove", str(world.repo), "ddd", "hexagonal", "never-installed"))
    assert doc["removed"] == {"ddd": {"installed_as": "tcs-ddd", "version": "1", "directory_existed": True}}
    assert set(doc["refused"]) == {"hexagonal", "never-installed"}
    assert "--force hexagonal" in doc["refused"]["hexagonal"]
    assert "not recorded in the manifest" in doc["refused"]["never-installed"]
    assert doc["failed"] == {}
    assert edited.is_file()

    forced = _doc(_run(world, "remove", str(world.repo), "hexagonal", "--force", "hexagonal"))
    assert forced["removed"] == {
        "hexagonal": {"installed_as": "tcs-hexagonal", "version": "1", "directory_existed": True}
    }
    assert not edited.exists()


def test_remove_force_is_per_name(world: World) -> None:
    """Two diverged patterns, one named by --force: that one goes, the other
    is refused and left in place."""
    _library_install(world, ["ddd", "hexagonal"])
    for name in ("ddd", "hexagonal"):
        skill = _skills(world.repo) / f"tcs-{name}" / "SKILL.md"
        skill.write_text(skill.read_text(encoding="utf-8") + "Edit.\n", encoding="utf-8")
    doc = _doc(_run(world, "remove", str(world.repo), "ddd", "hexagonal", "--force", "ddd"))
    assert set(doc["removed"]) == {"ddd"}
    assert set(doc["refused"]) == {"hexagonal"}
    assert (_skills(world.repo) / "tcs-hexagonal" / "SKILL.md").is_file()


def test_remove_accepts_a_name_the_catalogue_does_not_carry(world: World) -> None:
    """remove takes any name: a pattern deleted upstream is exactly what
    `status` sends a user to remove. No catalogue check, so no exit 2."""
    _library_install(world, ["hexagonal"])
    doc = _doc(_run(world, "remove", str(world.repo), "gone-upstream"))
    assert set(doc["refused"]) == {"gone-upstream"}


def test_status_reports_patterns_unlisted_and_debris(world: World) -> None:
    _library_install(world, ["ddd", "hexagonal", "functional"])
    shutil.rmtree(_skills(world.repo) / "tcs-functional")
    shutil.rmtree(world.cat / "functional")
    (world.cat / "ddd" / "VERSION").write_text("2\n", encoding="utf-8")
    edited = _skills(world.repo) / "tcs-hexagonal" / "SKILL.md"
    edited.write_text(edited.read_text(encoding="utf-8") + "Edit.\n", encoding="utf-8")
    (_skills(world.repo) / "tcs-mine").mkdir()
    (_skills(world.repo) / ".tcs-ddd.tmp").mkdir()
    doc = _doc(_run(world, "status", str(world.repo)))
    assert doc["manifest"] == {"state": "present", "error": None, "bundle": BUNDLE}
    assert doc["patterns"] == {
        "ddd": {
            "installed_as": "tcs-ddd",
            "installed_version": "1",
            "catalogue_version": "2",
            "state": "DRIFT",
            "directory_present": True,
            "diverged": False,
        },
        "hexagonal": {
            "installed_as": "tcs-hexagonal",
            "installed_version": "1",
            "catalogue_version": "1",
            "state": "OK",
            "directory_present": True,
            "diverged": True,
        },
        "functional": {
            "installed_as": "tcs-functional",
            "installed_version": "1",
            "catalogue_version": None,
            "state": "UNKNOWN",
            "directory_present": False,
            "diverged": None,
        },
    }
    assert doc["unlisted"] == ["tcs-mine"]
    assert len(doc["debris"]) == 1
    debris = doc["debris"][0]
    assert set(debris) == {"name", "kind", "resolution"}
    assert (debris["name"], debris["kind"]) == (".tcs-ddd.tmp", "install-tmp")
    assert "safe to delete" in debris["resolution"]


def test_status_reports_an_unparseable_manifest_verbatim_with_exit_0(world: World) -> None:
    _library_install(world, ["hexagonal"])
    _manifest_path(world.repo).write_text("this is [not toml\n", encoding="utf-8")
    doc = _doc(_run(world, "status", str(world.repo)))
    assert doc["manifest"]["state"] == "unparseable"
    assert doc["manifest"]["error"].startswith(f"{_manifest_path(world.repo)}: TOML syntax error")
    assert doc["manifest"]["bundle"] is None
    assert doc["patterns"] == {}
    assert doc["unlisted"] == ["tcs-hexagonal"]


# =============================================================================
# Output encoding: UTF-8 bytes on stdout.buffer, never \u escapes
# =============================================================================


def test_non_ascii_round_trips_under_an_ascii_stdout(world: World) -> None:
    """PYTHONIOENCODING=ascii makes a text-stream write of "—" raise (LC_ALL=C
    would not: Python 3.7+ switches to UTF-8 mode there). The catalogue's
    "—" reaches stdout through the declined diff."""
    _diverged_and_behind(world)
    r = _run(world, "update", str(world.repo), env={"PYTHONIOENCODING": "ascii"})
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")
    text = r.stdout.decode("utf-8")
    assert "—" in text
    assert "\\u2014" not in text
    assert "+Body v2 — upstream.\n" in json.loads(text)["declined"]["ddd"]["diff"]


def test_a_non_ascii_repository_path_round_trips(tmp_path: Path) -> None:
    repo = tmp_path / "répo—x"
    repo.mkdir()
    _git("-C", str(repo), "init", "-q")
    home = tmp_path / "home"
    home.mkdir()
    env = {**os.environ, "HOME": str(home), "PYTHONIOENCODING": "ascii", "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"}
    r = subprocess.run([sys.executable, str(CLI), "status", str(repo)], capture_output=True, cwd=tmp_path, env=env)
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")
    text = r.stdout.decode("utf-8")
    assert "répo—x" in text and "\\u" not in text
    assert json.loads(text)["repo"] == str(repo.resolve())
