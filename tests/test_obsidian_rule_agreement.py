"""ADR-7's consistency test (spec-020 T2.6): the bash write-time guard
(`block-eslint-disable.sh`) and the Python detection rule (`_rule_obsidian_plugin`
in `detect.py`) each decide "is this repo an Obsidian plugin?" independently.
ADR-7's whole bet is that two independent implementations plus a test that fails
when they disagree buys the safety of a shared source without the coupling the
hook must avoid (issue #163 -- a write-time guard with a dependency outside
itself is a recorded failure mode here, twice).

Why a fixture copy, never a fixture in place: the hook's scope gate resolves
the repository with `git -C "$DIR" rev-parse --show-toplevel`. Run against a
fixture sitting inside this worktree, that resolves to the-custom-startup's own
root -- which has neither `manifest.json` nor `package.json` -- so every one of
the 26 fixtures reads `allow`, Obsidian fixture included, and the "agreement"
would be measuring the TCS repo, not the fixture. Each fixture is therefore
copied into its own `tmp_path` and `git init`-ed there
(`GIT_CONFIG_GLOBAL`/`GIT_CONFIG_SYSTEM` pointed at `os.devnull`, matching
`tests/test_observability_report.py`'s `_init_git_repo`, so no host git config
or stray identity leaks in and a failed init cannot fall back to this session's
own `.git/`).

Each fixture (and each constructed tree below) is probed twice, content held
constant across both bash and python so only the scope gate varies: once with
a real `eslint-disable` (a DENY here means the gate considered the repo an
Obsidian plugin), once with clean content (a DENY here would mean the gate
fired on something other than the violation, which is a bug in the probe or
the hook, not a disagreement worth reporting as one).

Corpus agreement over the 26 fixtures holds already and is nearly powerless on
its own: 25 of them are non-Obsidian and only `auto-obsidian-plugin` is. A hook
that never denies passes 25 of 26; a Python rule that never proposes passes
25 of 26. The corpus is the floor, not the proof -- which is why the four
constructed trees below are the substance of this task. Two are real,
measured bugs in the hook, each in the opposite direction, neither reachable
from any fixture in the corpus:

  - a `manifest.json` carrying `minAppVersion` nested below the repository
    root: the Python rule finds it (it walks the whole tree); the unfixed
    bash gate only looks at `${REPO_DIR}/manifest.json` and misses it.
  - a root `package.json` with `"obsidian"` as a script name (or, the same
    bug found in the same probe, under `resolutions`), `dependencies` holding
    only `react`: the Python rule reads only `dependencies`/`devDependencies`
    and stays silent; the unfixed bash gate greps `"obsidian"[[:space:]]*:`
    across the whole file and denies on the stray match.

A root `manifest.json` with `minAppVersion` is included as a fourth,
already-agreeing case -- both sides fire -- so the divergences are read
against a baseline rather than in isolation.
"""

from __future__ import annotations

import importlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

from patterns_detection_corpus_lib import EXPECTED_CASE_COUNT, REPO_ROOT, discover_fixtures

HOOK = REPO_ROOT / "plugins" / "tcs-patterns" / "scripts" / "block-eslint-disable.sh"
LIB_DIR = REPO_ROOT / "plugins" / "tcs-patterns" / "skills" / "patterns-setup" / "lib"

_GIT_ENV = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull}

DIRTY = "// eslint-disable-next-line\n"
CLEAN = "const x = 1;\n"


def _load_detect() -> ModuleType:
    """Imports `detect` at call time -- consistent with
    `test_patterns_detect.py::_load_detect`'s reasoning, though this module
    does not share RED/collection concerns with it: `detect.py` already
    exists by the time T2.6 runs."""
    if str(LIB_DIR) not in sys.path:
        sys.path.insert(0, str(LIB_DIR))
    return importlib.import_module("detect")


def _git_init(repo_root: Path) -> None:
    result = subprocess.run(
        ["git", "-C", str(repo_root), "init", "-q"],
        env=_GIT_ENV,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def _materialize(tmp_path: Path, name: str, source: Path | None = None, builder=None) -> Path:
    """Produce a standalone git repository under `tmp_path`: either a copy of
    a detection fixture's `repo/`, or a tree built fresh by `builder`. Exactly
    one of `source`/`builder` must be given."""
    repo_root = tmp_path / name
    if source is not None:
        shutil.copytree(source, repo_root)
    else:
        repo_root.mkdir(parents=True)
        builder(repo_root)
    _git_init(repo_root)
    return repo_root


def _run_hook(repo_root: Path, content: str) -> dict | None:
    """Invoke `block-eslint-disable.sh` exactly as PreToolUse does: the
    payload arrives on stdin, never as an argument. The probe path need not
    exist -- the hook walks up to the nearest existing ancestor -- so every
    tree can be probed the same way regardless of what it actually contains."""
    payload = json.dumps(
        {
            "tool_name": "Write",
            "tool_input": {"file_path": str(repo_root / "src" / "probe.ts"), "content": content},
        }
    )
    result = subprocess.run(
        ["bash", str(HOOK)],
        input=payload,
        env=_GIT_ENV,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, (
        f"hook must always exit 0 -- denial travels via JSON, never via exit code: {result.stderr}"
    )
    out = result.stdout.strip()
    return json.loads(out) if out else None


def _bash_verdict(repo_root: Path, content: str) -> str:
    out = _run_hook(repo_root, content)
    if out is None:
        return "allow"
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    return "deny"


def _python_proposes_obsidian(repo_root: Path) -> bool:
    detect = _load_detect()
    report = detect.detect(repo_root)
    return "obsidian-plugin" in [p["pattern"] for p in report["auto"]]


def _assert_agrees(repo_root: Path, label: str) -> None:
    clean_verdict = _bash_verdict(repo_root, CLEAN)
    assert clean_verdict == "allow", (
        f"{label}: DENY on clean content means the gate fired on something "
        "other than the eslint-disable violation, not a real scope-gate verdict"
    )
    dirty_verdict = _bash_verdict(repo_root, DIRTY)
    python_proposes = _python_proposes_obsidian(repo_root)
    assert (dirty_verdict == "deny") == python_proposes, (
        f"{label}: bash gate verdict={dirty_verdict!r}, "
        f"python proposes obsidian-plugin={python_proposes!r} -- these must agree"
    )


# --- Corpus sweep: agreement already holds, and is nearly powerless alone ---


def test_corpus_has_exactly_the_expected_number_of_cases_here_too() -> None:
    """Standalone and non-parametrized -- a `pytest.mark.parametrize` over an
    empty corpus reports `1 skipped` at exit 0, a false green this file must
    not depend on `test_patterns_detection_corpus.py` to catch for it, since
    this file is run standalone too (task's own Validate step)."""
    fixtures = discover_fixtures()
    assert len(fixtures) == EXPECTED_CASE_COUNT, (
        f"expected exactly {EXPECTED_CASE_COUNT} fixtures, found {len(fixtures)}: "
        f"{[f.name for f in fixtures]}"
    )


@pytest.mark.parametrize("fixture", discover_fixtures(), ids=[f.name for f in discover_fixtures()])
def test_corpus_agreement(fixture, tmp_path) -> None:
    """For every detection fixture, the bash gate's verdict on `repo/` equals
    the Python rule's `obsidian-plugin` proposal. Both directions matter -- a
    fixture the bash gate accepts and the detector rejects is as much a
    divergence as the reverse."""
    repo_root = _materialize(tmp_path, fixture.name, source=fixture.repo_dir)
    _assert_agrees(repo_root, fixture.name)


# --- Constructed trees: the two divergences, plus a control -----------------


def _build_nested_manifest(repo_root: Path) -> None:
    """`packages/plugin/manifest.json` carries `minAppVersion`; the root
    `package.json` declares nothing. Diverges before the fix: the Python
    rule walks the whole tree and finds it, while the unfixed bash gate only
    looks at `${REPO_DIR}/manifest.json`."""
    plugin_dir = repo_root / "packages" / "plugin"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "manifest.json").write_text(
        json.dumps({"id": "demo", "name": "Demo", "minAppVersion": "1.5.0"}), encoding="utf-8"
    )
    (repo_root / "package.json").write_text(json.dumps({"name": "root-app"}), encoding="utf-8")


def _build_script_name_not_dependency(repo_root: Path) -> None:
    """Root `package.json` with `"obsidian"` as a script name only;
    `dependencies` holds `react` alone. Diverges before the fix: the Python
    rule reads only `dependencies`/`devDependencies` and stays silent, while
    the unfixed bash gate's whole-file grep matches `"obsidian":` wherever it
    occurs, including a script name."""
    (repo_root / "package.json").write_text(
        json.dumps(
            {
                "name": "not-an-obsidian-plugin",
                "scripts": {"obsidian": "echo hi"},
                "dependencies": {"react": "^18.2.0"},
            }
        ),
        encoding="utf-8",
    )


def _build_resolutions_not_dependency(repo_root: Path) -> None:
    """Root `package.json` with `"obsidian"` under `resolutions` only --
    the same whole-file-grep bug as the script-name tree, found in the same
    probe, covered as its own tree because it is a different JSON section
    and the fix (parsing `dependencies`/`devDependencies` with `jq`) must
    reject it too."""
    (repo_root / "package.json").write_text(
        json.dumps(
            {
                "name": "not-an-obsidian-plugin-either",
                "resolutions": {"obsidian": "1.0.0"},
                "dependencies": {"react": "^18.2.0"},
            }
        ),
        encoding="utf-8",
    )


def _build_control_root_manifest(repo_root: Path) -> None:
    """Root `manifest.json` with `minAppVersion` -- both sides already agree
    here, before and after the fix. Included so the two divergences are read
    against a baseline instead of in isolation."""
    (repo_root / "manifest.json").write_text(
        json.dumps({"id": "demo", "name": "Demo", "minAppVersion": "1.5.0"}), encoding="utf-8"
    )


CONSTRUCTED_TREES = {
    "nested-manifest-at-depth": _build_nested_manifest,
    "script-name-not-dependency": _build_script_name_not_dependency,
    "resolutions-not-dependency": _build_resolutions_not_dependency,
    "control-root-manifest": _build_control_root_manifest,
}


@pytest.mark.parametrize("name", list(CONSTRUCTED_TREES), ids=list(CONSTRUCTED_TREES))
def test_constructed_tree_agreement(name, tmp_path) -> None:
    """The two measured divergences (`nested-manifest-at-depth`,
    `script-name-not-dependency`), the related `resolutions-not-dependency`
    false positive found in the same probe, and the `control-root-manifest`
    baseline both sides already agree on. Before the hook is fixed, the first
    three fail here -- that failure is this task's RED."""
    repo_root = _materialize(tmp_path, name, builder=CONSTRUCTED_TREES[name])
    _assert_agrees(repo_root, name)
