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

Corpus agreement over the 27 fixtures holds already and is nearly powerless on
its own: 26 of them are non-Obsidian and only `auto-obsidian-plugin` is. A hook
that never denies passes 26 of 27; a Python rule that never proposes passes
26 of 27 -- and the ratio gets *worse* with every non-Obsidian fixture added, so
this paragraph is a standing reason not to read a green corpus as evidence here.
The corpus is the floor, not the proof -- which is why the
constructed trees below are the substance of this task. Two are real,
measured bugs in the hook (closed 2026-10-04), each in the opposite direction,
neither reachable from any fixture in the corpus:

  - a `manifest.json` carrying `minAppVersion` nested below the repository
    root: the Python rule finds it (it walks the whole tree); the unfixed
    bash gate only looked at `${REPO_DIR}/manifest.json` and missed it.
  - a root `package.json` with `"obsidian"` as a script name (or, the same
    bug found in the same probe, under `resolutions`), `dependencies` holding
    only `react`: the Python rule reads only `dependencies`/`devDependencies`
    and stays silent; the unfixed bash gate greps `"obsidian"[[:space:]]*:`
    across the whole file and denied on the stray match.

A root `manifest.json` with `minAppVersion` is included as a further,
already-agreeing case -- both sides fire -- so the divergences are read
against a baseline rather than in isolation.

**The first fix for the nested-manifest divergence was itself wrong, found
2026-10-04 on this repository.** A whole-tree `find` for `manifest.json`
(mirroring the Python rule, which is genuinely repo-scoped by design) makes
the hook classify a repository as an Obsidian plugin if it merely CONTAINS
one anywhere -- and this repository does, in six places, all test fixtures
(`tests/fixtures/patterns-detection/auto-obsidian-plugin/repo/manifest.json`
plus five more under a vendored plugin cache). The result: the hook denied
`eslint-disable` writes to ANY non-Markdown file anywhere in the-custom-startup
itself. `detect()` has the same false positive from the other direction,
proposing `obsidian-plugin` for this repository -- so the two rules agreed,
on a wrong answer. Agreement is not correctness; it was never more than a
necessary condition.

The fix: the hook walks UPWARD from the file being written to the repository
root, not across the whole tree, answering "is the file I am about to write
inside an Obsidian plugin?" -- a file-scoped question -- rather than "does
this repository contain one anywhere?" -- a repo-scoped one. `detect()` stays
repo-scoped; that is the right question for it to answer, since it decides
what the repository as a whole should install. The two rules now legitimately
answer different questions, which means **one corpus case is a deliberate,
asserted divergence, not a bug**: a write outside a nested plugin in a
monorepo allows under bash (the file itself is not in a plugin) while
`detect()` still proposes `obsidian-plugin` (the repository contains one).
`test_nested_manifest_file_outside_plugin_diverges_deliberately` asserts
exactly that, so a later reader who "fixes" the hook back into a tree walk
breaks a test instead of reintroducing the bug silently.
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

# CLAUDE_ALLOW_ESLINT_DISABLE explicitly unset -- the bats suite's setup()
# does this too (`unset CLAUDE_ALLOW_ESLINT_DISABLE`), and this file skipped
# it. The hook's own deny message tells a developer to set exactly this
# variable for a repo that will never be submitted to the community
# directory, so it is plausibly already set in a real shell; left in a
# bare `**os.environ` splat, it makes the hook exit 0 before reading
# anything else, which fails this file's dirty-case assertions loudly
# (measured: `CLAUDE_ALLOW_ESLINT_DISABLE=1 pytest tests/test_obsidian_rule_agreement.py -q`
# -> 4 failed) rather than silently -- a hygiene gap, not a correctness
# one, but one worth closing so a developer with the variable set does not
# spend time on failures that are not theirs.
_GIT_ENV = {
    **os.environ,
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_SYSTEM": os.devnull,
    "CLAUDE_ALLOW_ESLINT_DISABLE": "0",
}

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


def _run_hook(repo_root: Path, content: str, probe_rel: str = "src/probe.ts") -> dict | None:
    """Invoke `block-eslint-disable.sh` exactly as PreToolUse does: the
    payload arrives on stdin, never as an argument. `probe_rel` need not
    exist -- the hook walks up to the nearest existing ancestor -- so every
    tree can be probed the same way regardless of what it actually contains.

    It defaults to a path at the repository root, which is correct for every
    case except the nested-plugin ones: the hook is now file-scoped (it
    walks UPWARD from the file to the repo root), so WHERE the probe file
    sits relative to a nested `manifest.json` changes the verdict, unlike
    before this round's fix when the hook walked the whole tree regardless
    of probe location."""
    payload = json.dumps(
        {
            "tool_name": "Write",
            "tool_input": {"file_path": str(repo_root / probe_rel), "content": content},
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


def _bash_verdict(repo_root: Path, content: str, probe_rel: str = "src/probe.ts") -> str:
    out = _run_hook(repo_root, content, probe_rel)
    if out is None:
        return "allow"
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    return "deny"


def _python_proposes_obsidian(repo_root: Path) -> bool:
    detect = _load_detect()
    report = detect.detect(repo_root)
    return "obsidian-plugin" in [p["pattern"] for p in report["auto"]]


def _assert_agrees(repo_root: Path, label: str, probe_rel: str = "src/probe.ts") -> None:
    clean_verdict = _bash_verdict(repo_root, CLEAN, probe_rel)
    assert clean_verdict == "allow", (
        f"{label}: DENY on clean content means the gate fired on something "
        "other than the eslint-disable violation, not a real scope-gate verdict"
    )
    dirty_verdict = _bash_verdict(repo_root, DIRTY, probe_rel)
    python_proposes = _python_proposes_obsidian(repo_root)
    assert (dirty_verdict == "deny") == python_proposes, (
        f"{label}: bash gate verdict={dirty_verdict!r}, "
        f"python proposes obsidian-plugin={python_proposes!r} -- these must agree"
    )


def _assert_diverges_by_scope(repo_root: Path, label: str, probe_rel: str) -> None:
    """Assert the ONE deliberate divergence: bash (file-scoped, walks UPWARD
    from the probe file) allows, while python (repo-scoped, walks the whole
    tree) still proposes. A later reader must not "fix" this into agreement
    -- doing so means making the hook repo-scoped again, which is exactly
    the false positive this round closed: it denied `eslint-disable` writes
    to every non-Markdown file anywhere in the-custom-startup itself, because
    this repository happens to contain six test-fixture `manifest.json`
    files with `minAppVersion`, none of them anywhere near most writes."""
    clean_verdict = _bash_verdict(repo_root, CLEAN, probe_rel)
    assert clean_verdict == "allow", (
        f"{label}: DENY on clean content means the gate fired on something "
        "other than the eslint-disable violation"
    )
    dirty_verdict = _bash_verdict(repo_root, DIRTY, probe_rel)
    python_proposes = _python_proposes_obsidian(repo_root)
    assert dirty_verdict == "allow", (
        f"{label}: expected bash to allow (the probe file is outside the plugin), "
        f"got {dirty_verdict!r}"
    )
    assert python_proposes is True, (
        f"{label}: expected python to propose obsidian-plugin (the repo contains one "
        f"somewhere), got {python_proposes!r}"
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
    `package.json` declares nothing. Used by two cases that probe different
    files in this same tree: a write INSIDE `packages/plugin/` agrees with
    python (both see the plugin), a write OUTSIDE it deliberately diverges
    (bash is file-scoped, python is repo-scoped) -- see
    `test_nested_manifest_file_outside_plugin_diverges_deliberately`."""
    plugin_dir = repo_root / "packages" / "plugin"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "manifest.json").write_text(
        json.dumps({"id": "demo", "name": "Demo", "minAppVersion": "1.5.0"}), encoding="utf-8"
    )
    (repo_root / "package.json").write_text(json.dumps({"name": "root-app"}), encoding="utf-8")


def _build_obsidian_dependency(repo_root: Path) -> None:
    """Root `package.json` with `"obsidian"` as a genuine `dependencies`
    entry, no `manifest.json` anywhere. The only agreement case that
    exercises python's `dependencies`/`devDependencies` branch of
    `_rule_obsidian_plugin` as the reason it proposes, rather than the
    `manifest.json` branch -- added 2026-10-04 after a mutation that
    disabled that whole branch passed this file's agreement tests without
    this case, because every other tree that agrees does so via
    `manifest.json` instead."""
    (repo_root / "package.json").write_text(
        json.dumps({"name": "has-obsidian-dependency", "dependencies": {"obsidian": "1.5.0"}}),
        encoding="utf-8",
    )


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


# name -> (builder, probe path relative to repo_root). Everything here is
# expected to AGREE -- the one deliberate divergence has its own test below,
# not folded into this table, so this table's whole point (asserting
# agreement) stays undiluted.
AGREEMENT_TREES = {
    "nested-manifest-inside-plugin": (_build_nested_manifest, "packages/plugin/src/probe.ts"),
    "obsidian-dependency": (_build_obsidian_dependency, "src/probe.ts"),
    "script-name-not-dependency": (_build_script_name_not_dependency, "src/probe.ts"),
    "resolutions-not-dependency": (_build_resolutions_not_dependency, "src/probe.ts"),
    "control-root-manifest": (_build_control_root_manifest, "src/probe.ts"),
}


@pytest.mark.parametrize("name", list(AGREEMENT_TREES), ids=list(AGREEMENT_TREES))
def test_constructed_tree_agreement(name, tmp_path) -> None:
    """The two measured-and-fixed divergences (`nested-manifest-inside-plugin`,
    `script-name-not-dependency`), the related `resolutions-not-dependency`
    false positive found in the same probe, and the `control-root-manifest`
    baseline both sides already agree on.

    `nested-manifest-inside-plugin` probes a file INSIDE
    `packages/plugin/` deliberately: the hook is file-scoped (walks UPWARD
    from the probe file to the repo root) and python is repo-scoped (walks
    the whole tree), so the two coincide only when the probe file is itself
    inside the plugin. The reverse case -- a probe file OUTSIDE the plugin,
    where the two legitimately diverge -- is its own test below, not here."""
    builder, probe_rel = AGREEMENT_TREES[name]
    repo_root = _materialize(tmp_path, name, builder=builder)
    _assert_agrees(repo_root, name, probe_rel)


def test_nested_manifest_file_outside_plugin_diverges_deliberately(tmp_path) -> None:
    """Same tree as `nested-manifest-inside-plugin` above, but the probe file
    sits at `tools/probe.ts` -- outside `packages/plugin/` entirely. bash
    (file-scoped) allows; python (repo-scoped) still proposes `obsidian-plugin`
    because the repository genuinely contains one. This is NOT a bug: it is
    the direct, intended consequence of making the hook answer "is this FILE
    in a plugin" rather than "does this REPO contain one anywhere" -- the
    question whose old (repo-scoped) answer produced the false positive this
    round's fix closed. See the module docstring for the measured false
    positive on this actual repository."""
    repo_root = _materialize(tmp_path, "nested-manifest-outside-plugin", builder=_build_nested_manifest)
    _assert_diverges_by_scope(repo_root, "nested-manifest-outside-plugin", "tools/probe.ts")
