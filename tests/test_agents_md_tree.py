"""AGENTS.md must describe the tree that exists, in both directions.

Why this exists (#252): CLAUDE.md sends agents to AGENTS.md to locate a plugin,
skill or agent, and the file had drifted: entries for files that did not exist,
renamed skills, two plugins missing and a stale manifest version. Nothing
checked it. These tests derive the facts from the filesystem.
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
AGENTS = REPO_ROOT / "AGENTS.md"
PLUGINS = REPO_ROOT / "plugins"
TREE_ENTRY = re.compile(r"^(?P<indent>(?:[│ ]   )*)[├└]── (?P<name>[^\s#]+)")


def _text() -> str:
    return AGENTS.read_text(encoding="utf-8")


def _tree_block() -> list[str]:
    m = re.search(r"^## Repository Structure\n(?:(?!^#).)*?^```\n(.*?)^```", _text(), re.S | re.M)
    assert m, "AGENTS.md has no Repository Structure tree"
    return m.group(1).splitlines()


def _tree_paths() -> list[str]:
    """Repo-relative path of every tree entry, rebuilt from its indentation."""
    stack: list[str] = []
    paths = []
    for line in _tree_block():
        m = TREE_ENTRY.match(line)
        if not m:
            continue
        depth = len(m.group("indent")) // 4
        name = m.group("name").rstrip("/").rstrip(":")
        del stack[depth:]
        stack.append(name)
        paths.append("/".join(stack))
    assert paths, "tree parsed to no entries"
    return paths


def _dirs(path: Path) -> list[str]:
    return sorted(p.name for p in path.iterdir() if p.is_dir() and not p.name.startswith(("_", ".")))


@pytest.mark.parametrize("path", _tree_paths())
def test_every_tree_entry_exists(path):
    assert (REPO_ROOT / path).exists(), f"AGENTS.md tree lists {path}, which does not exist"


def test_every_plugin_is_in_the_tree():
    listed = {p.split("/")[1] for p in _tree_paths() if p.startswith("plugins/") and p.count("/") >= 1}
    assert set(_dirs(PLUGINS)) <= listed


@pytest.mark.parametrize("plugin", _dirs(PLUGINS))
def test_every_skill_and_agent_is_named(plugin):
    text = _text()
    names = _dirs(PLUGINS / plugin / "skills") if (PLUGINS / plugin / "skills").is_dir() else []
    agents = PLUGINS / plugin / "agents"
    if agents.is_dir():
        names += [p.stem for p in agents.rglob("*.md") if p.name != "README.md"]
    missing = [n for n in names if not re.search(rf"(?<![\w-]){re.escape(n)}(?![\w-])", text)]
    assert not missing, f"AGENTS.md does not name {plugin}: {missing}"


def test_backticked_repo_paths_exist():
    paths = re.findall(r"`((?:plugins|docs|scripts|tests|\.github)/[^`\s*\[\]<>]+)`", _text())
    missing = [p for p in paths if not (REPO_ROOT / p.rstrip("/")).exists()]
    assert not missing, f"AGENTS.md references missing paths: {missing}"


def test_states_no_plugin_version():
    # Versions move on every merge (auto-bump); the manifests are the source.
    assert not re.search(r"\bv?\d+\.\d+\.\d+\b", _text().split("## Publishing")[0])
