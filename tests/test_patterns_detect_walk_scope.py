"""#183: the scan reads what git considers part of THIS repository.

Two structural prunes on top of `SKIP_DIRS` (spec 020 SDD, "The walk excludes..."):

- **Gitignored trees.** A tool cache under an ignored directory
  (`claude-docker-home/.bun/...` on the-custom-startup) was read as stack
  evidence. The walk now asks git which untracked paths are ignored and prunes
  them; tracked files stay, even force-added ones inside an ignored directory.
  Outside a git work tree the prune is skipped -- the walk is exactly what it
  was before (fail open).
- **Nested repositories.** A submodule (`modules/satori`) proposed
  `typescript-strict` and `mcp-server` for its parent. A directory below the
  root holding a `.git` entry -- a directory (nested clone) or a file
  (submodule, worktree) -- is not entered, and is named in `nested_repos`.

Every repository is built with a real `git init` in `tmp_path`, never inside
this worktree: a fixture under the-custom-startup would inherit its
`.gitignore` and the test would measure that file. Host git config is shut out
three ways -- `GIT_CONFIG_GLOBAL`, `GIT_CONFIG_SYSTEM` and `XDG_CONFIG_HOME` --
because the first two alone still read `~/.config/git/ignore`, and a user's
global excludes would then decide what these tests see. The variables are set
on the process, so `detect.py`'s own git call inherits the same isolation.

Expected paths are literals in each test, not computed by a walk: a second walk
would share the logic under test and agree with it whatever it did.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

LIB_DIR = Path(__file__).resolve().parent.parent / "plugins" / "tcs-patterns" / "skills" / "patterns-setup" / "lib"


def _load_detect() -> ModuleType:
    if str(LIB_DIR) not in sys.path:
        sys.path.insert(0, str(LIB_DIR))
    import detect  # noqa: PLC0415 -- per-test import, matching test_patterns_detect.py

    return detect


@pytest.fixture(autouse=True)
def _isolated_git(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    xdg = tmp_path / "xdg-empty"
    xdg.mkdir()
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", os.devnull)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _init(repo: Path) -> Path:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q", "-b", "main")
    return repo


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _auto(report: dict) -> set[str]:
    return {entry["pattern"] for entry in report["auto"]}


# --- gitignored trees --------------------------------------------------------


def test_a_gitignored_directory_is_not_evidence(tmp_path: Path) -> None:
    repo = _init(tmp_path / "repo")
    _write(repo / ".gitignore", "cache/\n")
    _write(repo / "cache" / "go.mod", "module example.com/cache\n")

    report = _load_detect().detect(repo)

    assert "go-idiomatic" not in _auto(report)
    assert "cache/go.mod" not in report["manifests_walked"]


def test_control_the_same_tree_unignored_does_fire(tmp_path: Path) -> None:
    # Proves the tree above can fire at all, so its silence is the prune's doing.
    repo = _init(tmp_path / "repo")
    _write(repo / "cache" / "go.mod", "module example.com/cache\n")

    report = _load_detect().detect(repo)

    assert "go-idiomatic" in _auto(report)
    assert "cache/go.mod" in report["manifests_walked"]


def test_a_force_added_file_inside_an_ignored_directory_is_still_walked(tmp_path: Path) -> None:
    # Tracked means part of the repository, whatever .gitignore says.
    repo = _init(tmp_path / "repo")
    _write(repo / ".gitignore", "cache/\n")
    _write(repo / "cache" / "go.mod", "module example.com/cache\n")
    _git(repo, "add", "-f", "cache/go.mod")

    report = _load_detect().detect(repo)

    assert "go-idiomatic" in _auto(report)
    assert "cache/go.mod" in report["manifests_walked"]


def test_outside_a_git_work_tree_the_walk_is_unchanged(tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    _write(plain / ".gitignore", "cache/\n")
    _write(plain / "cache" / "go.mod", "module example.com/cache\n")
    probe = subprocess.run(["git", "-C", str(plain), "rev-parse", "--is-inside-work-tree"], capture_output=True)
    if probe.returncode == 0:
        pytest.skip("tmp_path sits inside a git work tree on this machine; the fail-open path is unreachable here")

    report = _load_detect().detect(plain)

    assert "go-idiomatic" in _auto(report)
    assert report["nested_repos"] == []


# --- nested repositories -----------------------------------------------------


def test_a_nested_clone_is_not_entered_and_is_named(tmp_path: Path) -> None:
    repo = _init(tmp_path / "repo")
    nested = _init(repo / "libs" / "sub")
    _write(nested / "tsconfig.json", "{}\n")

    report = _load_detect().detect(repo)

    assert "typescript-strict" not in _auto(report)
    assert report["nested_repos"] == ["libs/sub/"]


def test_a_submodule_shaped_directory_is_not_entered_and_is_named(tmp_path: Path) -> None:
    # A submodule's `.git` is a file pointing into the parent's .git/modules/.
    repo = _init(tmp_path / "repo")
    _write(repo / "modules" / "sat" / ".git", "gitdir: ../../.git/modules/sat\n")
    _write(repo / "modules" / "sat" / "tsconfig.json", "{}\n")

    report = _load_detect().detect(repo)

    assert "typescript-strict" not in _auto(report)
    assert report["nested_repos"] == ["modules/sat/"]


def test_the_root_own_dot_git_is_not_a_nested_repo(tmp_path: Path) -> None:
    repo = _init(tmp_path / "repo")
    _write(repo / "tsconfig.json", "{}\n")

    report = _load_detect().detect(repo)

    assert "typescript-strict" in _auto(report)
    assert report["nested_repos"] == []
