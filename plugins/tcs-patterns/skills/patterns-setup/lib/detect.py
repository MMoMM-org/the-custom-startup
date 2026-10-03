"""The tcs-patterns detector (spec-020 T2.2).

`detect(repo_dir)` is the whole contract between scanning and asking
`[ref: SDD/Interface Specifications/Data model: detection report]`: it reads a
directory and returns a report. It writes nothing, asks nothing, and never
consults the catalogue for anything but the list of pattern names -- and this
module does not even need that list, since the eight stack facts below name
their own patterns directly.

Scope of this module (T2.2): the eight stack facts, the manifest walk, the
runtime-dependency reader, `evidence`, `manifests_walked`, and
`unrecognised_stack`. The three gates (`q1_backend`, `q2_architecture`,
`q3_test_quality`) are emitted as an honest `False` placeholder -- real gate
evaluation is T2.3's job
`[ref: docs/XDD/specs/020-tcs-patterns-selective-install/plan/phase-2.md#T2.2]`.
Implementing them here would collapse the task split the plan deliberately
drew.

Every rule implemented below is cited to its clause in
`[ref: SDD/Interface Specifications/Detection rules: the eight stack facts and
the three gates]` and `[ref: SDD/Interface Specifications/Detection rules:
What counts as a test framework]`.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Optional

try:
    import tomllib  # Python 3.11+
except ImportError:  # pragma: no cover - exercised only on pre-3.11 runtimes
    tomllib = None  # type: ignore[assignment]

# Trap 5 + trap 7: excluded at every depth, for every file search, not only for
# dependency manifests `[ref: SDD/Detection rules, "The walk excludes..."]`.
SKIP_DIRS = {"node_modules", ".venv", "venv", "vendor"}

# Dependency-manifest filenames, walked at the nested, exclusion-aware depth
# `[ref: SDD/Detection rules, "The walk excludes..."]`, and reported in
# `manifests_walked` -- clarified on review: that field exists so "a missing
# signal is explicable", and `requirements.txt` / `setup.py` are exactly the
# files the mcp-server rule opens looking for `mcp`. Leaving them out would
# make "contained no `mcp`" and "never found" indistinguishable to a reader
# of the report, which is the one failure mode the field exists to prevent.
# `manifest.json` (obsidian) stays out: it is not a dependency manifest at
# all, which the SDD states as its own named exception.
DEPENDENCY_MANIFEST_NAMES = ("package.json", "pyproject.toml", "go.mod", "requirements.txt", "setup.py")

# python-project `[ref: SDD/Detection rules, row "python-project"]`: any .py
# file AND one of these.
PYTHON_PRESENCE_MANIFESTS = ("pyproject.toml", "requirements.txt", "setup.py")

# testing, Node row `[ref: SDD/Detection rules, "What counts as a test
# framework"]`.
NODE_TEST_FRAMEWORK_DEPS = {"jest", "vitest", "mocha", "jasmine", "ava"}

# react-testing `[ref: SDD/Detection rules, row "react-testing"]`.
REACT_TEST_LIB_DEPS = {"@testing-library/react", "react-test-renderer", "enzyme"}

# mcp-server `[ref: SDD/Detection rules, row "mcp-server"]`: the three
# ecosystems' SDK names.
MCP_NODE_DEP = "@modelcontextprotocol/sdk"
MCP_PY_DEP = "mcp"
MCP_GO_MODULE = "github.com/mark3labs/mcp-go"

# frontend-testing `[ref: SDD/Detection rules, row "frontend-testing"]`, trap 2:
# DOM-render evidence, never a directory name and never jsdom alone.
RENDER_EVIDENCE_MARKERS = ("render(", "screen.", "fireEvent", "userEvent")

# Tests shape: a dedicated directory, OR colocation (test files beside the
# code they cover) `[ref: SDD/Detection rules, "What counts as a test
# framework", the three preserved distinctions]`.
TESTS_DIR_NAMES = {"tests", "test", "spec", "__tests__"}


def _is_test_filename(name: str) -> bool:
    """A filename recognised as a test file across the four ecosystems. Used
    both for colocation (tests shape) and as the search set for frontend
    render evidence -- a test file is exactly where DOM-render evidence or a
    bare pytest/go convention lives."""
    if name.startswith("test_") and name.endswith(".py"):
        return True
    if name.endswith("_test.py") or name.endswith("_test.go"):
        return True
    if name.endswith(".bats"):
        return True
    for ext in (".js", ".jsx", ".ts", ".tsx"):
        if name.endswith(f".test{ext}") or name.endswith(f".spec{ext}"):
            return True
    return False


class _Tree:
    """One pruned `os.walk` over the repository, collected once. Every rule
    below reads from this instead of re-walking the filesystem, which keeps
    the scan to a single pass regardless of how many stack facts it decides
    `[ref: SDD/Quality Requirements, "Scan cost"]`."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.files: list[Path] = []
        self.dir_names: set[str] = set()
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
            self.dir_names.update(dirnames)
            for name in sorted(filenames):
                self.files.append(Path(dirpath) / name)
        self.files.sort()

    def rel(self, path: Path) -> str:
        return path.relative_to(self.root).as_posix()

    def files_named(self, name: str) -> list[Path]:
        return [p for p in self.files if p.name == name]

    def files_matching(self, predicate) -> list[Path]:
        return [p for p in self.files if predicate(p.name)]

    def has_dir_named(self, names: set[str]) -> bool:
        return bool(self.dir_names & names)


def _read_text(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _read_json(path: Path) -> Optional[dict]:
    text = _read_text(path)
    if text is None:
        return None
    try:
        data = json.loads(text)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _node_deps(path: Path) -> tuple[dict, dict]:
    """Runtime and dev dependencies of one `package.json`. An unparseable
    manifest is skipped, never fatal `[ref: plan/phase-2.md T2.2 step 3]`."""
    data = _read_json(path)
    if data is None:
        return {}, {}
    deps = data.get("dependencies")
    dev_deps = data.get("devDependencies")
    return (
        deps if isinstance(deps, dict) else {},
        dev_deps if isinstance(dev_deps, dict) else {},
    )


_REQUIREMENT_NAME_RE = re.compile(r"^\s*([A-Za-z0-9_.\-]+)")


def _requirements_txt_deps(path: Path) -> list[str]:
    text = _read_text(path)
    if text is None:
        return []
    names = []
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        match = _REQUIREMENT_NAME_RE.match(line)
        if match:
            names.append(match.group(1).lower())
    return names


_SETUP_PY_INSTALL_REQUIRES_RE = re.compile(r"install_requires\s*=\s*\[(.*?)\]", re.DOTALL)
_QUOTED_RE = re.compile(r"""["']([^"']+)["']""")


def _setup_py_deps(path: Path) -> list[str]:
    """Best-effort: `setup.py` is executable Python, not data, so this is a
    regex scan of `install_requires=[...]` rather than a real parse. A
    repository with no such literal list yields nothing, never a crash."""
    text = _read_text(path)
    if text is None:
        return []
    block = _SETUP_PY_INSTALL_REQUIRES_RE.search(text)
    if not block:
        return []
    names = []
    for quoted in _QUOTED_RE.findall(block.group(1)):
        match = _REQUIREMENT_NAME_RE.match(quoted)
        if match:
            names.append(match.group(1).lower())
    return names


_PYPROJECT_PEP621_FALLBACK_RE = re.compile(r'dependencies\s*=\s*\[(.*?)\]', re.DOTALL)
_PYPROJECT_POETRY_SECTION_RE = re.compile(
    r"\[tool\.poetry\.dependencies\]\s*(.*?)(?:\n\[|\Z)", re.DOTALL
)
_POETRY_DEP_NAME_RE = re.compile(r'^\s*([A-Za-z0-9_.\-]+)\s*=', re.MULTILINE)
_PYTEST_INI_OPTIONS_RE = re.compile(r"^\s*\[tool\.pytest\.ini_options\]", re.MULTILINE)


def _pyproject_deps_and_pytest(path: Path) -> tuple[list[str], bool]:
    """Returns (dependency names, has a `[tool.pytest.ini_options]` table).
    Tries `tomllib` first (3.11+); falls back to a regex scan on older
    runtimes so this module stays stdlib-only everywhere `[ref: plan/phase-2.md
    T2.2, "Python 3, standard library only ... macOS and Linux"]`."""
    text = _read_text(path)
    if text is None:
        return [], False

    has_pytest_table = bool(_PYTEST_INI_OPTIONS_RE.search(text))

    if tomllib is not None:
        try:
            data = tomllib.loads(text)
        except (tomllib.TOMLDecodeError, ValueError):
            data = None
        if isinstance(data, dict):
            names: list[str] = []
            project = data.get("project")
            if isinstance(project, dict):
                for dep in project.get("dependencies") or []:
                    match = _REQUIREMENT_NAME_RE.match(str(dep))
                    if match:
                        names.append(match.group(1).lower())
            tool = data.get("tool")
            if isinstance(tool, dict):
                poetry = tool.get("poetry")
                if isinstance(poetry, dict):
                    poetry_deps = poetry.get("dependencies")
                    if isinstance(poetry_deps, dict):
                        names.extend(k.lower() for k in poetry_deps if k != "python")
            return names, has_pytest_table

    # Fallback: no tomllib. Regex-scan PEP 621's `dependencies = [...]` array
    # and poetry's `[tool.poetry.dependencies]` table. Approximate, but an
    # unparseable file is skipped rather than fatal either way.
    names = []
    pep621 = _PYPROJECT_PEP621_FALLBACK_RE.search(text)
    if pep621:
        for quoted in _QUOTED_RE.findall(pep621.group(1)):
            match = _REQUIREMENT_NAME_RE.match(quoted)
            if match:
                names.append(match.group(1).lower())
    poetry_section = _PYPROJECT_POETRY_SECTION_RE.search(text)
    if poetry_section:
        for match in _POETRY_DEP_NAME_RE.finditer(poetry_section.group(1)):
            name = match.group(1).lower()
            if name != "python":
                names.append(name)
    return names, has_pytest_table


_GO_REQUIRE_LINE_RE = re.compile(r"^([A-Za-z0-9._\-/]+)\s+v\S+")


def _go_mod_requires(path: Path) -> list[str]:
    text = _read_text(path)
    if text is None:
        return []
    modules = []
    in_block = False
    for raw_line in text.splitlines():
        line = raw_line.split("//", 1)[0].strip()
        if not line:
            continue
        if line.startswith("require ("):
            in_block = True
            continue
        if in_block:
            if line == ")":
                in_block = False
                continue
            match = _GO_REQUIRE_LINE_RE.match(line)
            if match:
                modules.append(match.group(1))
            continue
        if line.startswith("require "):
            match = _GO_REQUIRE_LINE_RE.match(line[len("require "):].strip())
            if match:
                modules.append(match.group(1))
    return modules


def _fmt_dep_evidence(tree: _Tree, manifest_path: Path, key: str, name: str) -> str:
    return f"{tree.rel(manifest_path)}: {key}.{name}"


class _Proposal:
    __slots__ = ("pattern", "evidence")

    def __init__(self, pattern: str, evidence: str) -> None:
        self.pattern = pattern
        self.evidence = evidence

    def as_dict(self) -> dict:
        return {"pattern": self.pattern, "evidence": self.evidence}


def _rule_typescript_strict(tree: _Tree) -> Optional[_Proposal]:
    """Row: `typescript-strict` -- any `tsconfig.json`, presence only."""
    found = tree.files_named("tsconfig.json")
    if not found:
        return None
    return _Proposal("typescript-strict", tree.rel(found[0]))


def _rule_go_idiomatic(tree: _Tree) -> Optional[_Proposal]:
    """Row: `go-idiomatic` -- a `go.mod`."""
    found = tree.files_named("go.mod")
    if not found:
        return None
    return _Proposal("go-idiomatic", tree.rel(found[0]))


def _rule_python_project(tree: _Tree) -> Optional[_Proposal]:
    """Row: `python-project` -- any `.py` file AND one of `pyproject.toml`,
    `requirements.txt`, `setup.py`. Both conditions are presence-only and
    independent of location; neither is required to be a dependency manifest,
    which is why these three filenames do not feed `manifests_walked`."""
    has_py_file = any(p.suffix == ".py" for p in tree.files)
    if not has_py_file:
        return None
    for name in PYTHON_PRESENCE_MANIFESTS:
        found = tree.files_named(name)
        if found:
            return _Proposal("python-project", tree.rel(found[0]))
    return None


def _rule_mcp_server(tree: _Tree) -> Optional[_Proposal]:
    """Row: `mcp-server` -- `@modelcontextprotocol/sdk` (Node), `mcp`
    (Python), or `github.com/mark3labs/mcp-go` (Go): the three ecosystems'
    SDK names."""
    for pkg_path in tree.files_named("package.json"):
        deps, dev_deps = _node_deps(pkg_path)
        if MCP_NODE_DEP in deps:
            return _Proposal("mcp-server", _fmt_dep_evidence(tree, pkg_path, "dependencies", MCP_NODE_DEP))
        if MCP_NODE_DEP in dev_deps:
            return _Proposal("mcp-server", _fmt_dep_evidence(tree, pkg_path, "devDependencies", MCP_NODE_DEP))

    for req_path in tree.files_named("requirements.txt"):
        if MCP_PY_DEP in _requirements_txt_deps(req_path):
            return _Proposal("mcp-server", f"{tree.rel(req_path)}: requirements.{MCP_PY_DEP}")

    for pyproject_path in tree.files_named("pyproject.toml"):
        deps, _has_pytest = _pyproject_deps_and_pytest(pyproject_path)
        if MCP_PY_DEP in deps:
            return _Proposal("mcp-server", _fmt_dep_evidence(tree, pyproject_path, "dependencies", MCP_PY_DEP))

    for setup_path in tree.files_named("setup.py"):
        if MCP_PY_DEP in _setup_py_deps(setup_path):
            return _Proposal("mcp-server", f"{tree.rel(setup_path)}: install_requires.{MCP_PY_DEP}")

    for go_mod_path in tree.files_named("go.mod"):
        if MCP_GO_MODULE in _go_mod_requires(go_mod_path):
            return _Proposal("mcp-server", f"{tree.rel(go_mod_path)}: require.{MCP_GO_MODULE}")

    return None


def _rule_obsidian_plugin(tree: _Tree) -> Optional[_Proposal]:
    """Row: `obsidian-plugin` -- a `manifest.json` carrying `minAppVersion`,
    or an `obsidian` dependency. The manifest key matters; a bare
    `manifest.json` is not evidence. `manifest.json` is not a dependency
    manifest and does not feed `manifests_walked`."""
    for manifest_path in tree.files_named("manifest.json"):
        data = _read_json(manifest_path)
        if isinstance(data, dict) and "minAppVersion" in data:
            return _Proposal("obsidian-plugin", f"{tree.rel(manifest_path)}: minAppVersion")

    for pkg_path in tree.files_named("package.json"):
        deps, dev_deps = _node_deps(pkg_path)
        if "obsidian" in deps:
            return _Proposal("obsidian-plugin", _fmt_dep_evidence(tree, pkg_path, "dependencies", "obsidian"))
        if "obsidian" in dev_deps:
            return _Proposal("obsidian-plugin", _fmt_dep_evidence(tree, pkg_path, "devDependencies", "obsidian"))

    return None


def _rule_react_testing(tree: _Tree) -> Optional[_Proposal]:
    """Row: `react-testing` -- a `react` dependency AND one of
    `@testing-library/react`, `react-test-renderer`, `enzyme`. `react` alone
    is not evidence."""
    for pkg_path in tree.files_named("package.json"):
        deps, dev_deps = _node_deps(pkg_path)
        has_react = "react" in deps or "react" in dev_deps
        if not has_react:
            continue
        for lib in REACT_TEST_LIB_DEPS:
            if lib in deps:
                return _Proposal("react-testing", _fmt_dep_evidence(tree, pkg_path, "dependencies", lib))
            if lib in dev_deps:
                return _Proposal("react-testing", _fmt_dep_evidence(tree, pkg_path, "devDependencies", lib))
    return None


def _rule_frontend_testing(tree: _Tree) -> Optional[_Proposal]:
    """Row: `frontend-testing` -- DOM-render evidence in test files:
    `render(`, `screen.`, `fireEvent`, `userEvent`. Trap 2: never a directory
    name, never jsdom alone -- so this reads file *content*, not the
    directory a test file happens to sit in, and ignores any `jsdom`
    dependency entirely."""
    for path in tree.files_matching(_is_test_filename):
        text = _read_text(path)
        if text is None:
            continue
        if any(marker in text for marker in RENDER_EVIDENCE_MARKERS):
            return _Proposal("frontend-testing", tree.rel(path))
    return None


def _node_testing_framework_evidence(tree: _Tree) -> Optional[_Proposal]:
    """testing, Node row: a known runner in `dependencies` or
    `devDependencies` (trap 1 is about surfacing, not about which dependency
    section counts -- unlike trap 4's gate rule, this stack fact has no
    runtime-only restriction), or a `jest.config.*` / `vitest.config.*`
    file."""
    for pkg_path in tree.files_named("package.json"):
        deps, dev_deps = _node_deps(pkg_path)
        for runner in NODE_TEST_FRAMEWORK_DEPS:
            if runner in deps:
                return _Proposal("testing", _fmt_dep_evidence(tree, pkg_path, "dependencies", runner))
            if runner in dev_deps:
                return _Proposal("testing", _fmt_dep_evidence(tree, pkg_path, "devDependencies", runner))

    for path in tree.files:
        if path.name.startswith("jest.config.") or path.name.startswith("vitest.config."):
            return _Proposal("testing", tree.rel(path))
    return None


def _python_testing_framework_evidence(tree: _Tree) -> Optional[_Proposal]:
    """testing, Python row: `pytest.ini`, `tox.ini`, a
    `[tool.pytest.ini_options]` table in `pyproject.toml`, or any
    `test_*.py` / `*_test.py`."""
    for name in ("pytest.ini", "tox.ini"):
        found = tree.files_named(name)
        if found:
            return _Proposal("testing", tree.rel(found[0]))

    for pyproject_path in tree.files_named("pyproject.toml"):
        _deps, has_pytest_table = _pyproject_deps_and_pytest(pyproject_path)
        if has_pytest_table:
            return _Proposal("testing", f"{tree.rel(pyproject_path)}: [tool.pytest.ini_options]")

    for path in tree.files:
        name = path.name
        if (name.startswith("test_") and name.endswith(".py")) or name.endswith("_test.py"):
            return _Proposal("testing", tree.rel(path))
    return None


def _go_testing_framework_evidence(tree: _Tree) -> Optional[_Proposal]:
    """testing, Go row: any `*_test.go` -- Go tests declare no dependency."""
    found = tree.files_matching(lambda name: name.endswith("_test.go"))
    if not found:
        return None
    return _Proposal("testing", tree.rel(found[0]))


def _shell_testing_framework_evidence(tree: _Tree) -> Optional[_Proposal]:
    """testing, Shell row: any `*.bats`."""
    found = tree.files_matching(lambda name: name.endswith(".bats"))
    if not found:
        return None
    return _Proposal("testing", tree.rel(found[0]))


def _rule_testing(tree: _Tree) -> Optional[_Proposal]:
    """Row: `testing` -- any non-UI test framework together with a tests
    shape (trap 1: reported in `baseline` with `surface: false`, never as a
    recommendation -- enforced by the caller, not here).

    "Non-UI" is not a separate check: the framework-evidence rows above
    (react-testing, frontend-testing) are never consulted here, and the
    react/enzyme test libraries are deliberately absent from
    `NODE_TEST_FRAMEWORK_DEPS`, so a repository whose only Node testing
    dependency is `@testing-library/react` yields no framework evidence here
    and `testing` cannot fire from it -- which is exactly the "does not
    additionally yield testing" clause."""
    framework = (
        _python_testing_framework_evidence(tree)
        or _node_testing_framework_evidence(tree)
        or _go_testing_framework_evidence(tree)
        or _shell_testing_framework_evidence(tree)
    )
    if framework is None:
        return None

    has_tests_dir = tree.has_dir_named(TESTS_DIR_NAMES)
    has_colocated_test_file = any(_is_test_filename(p.name) for p in tree.files)
    if not (has_tests_dir or has_colocated_test_file):
        return None

    return framework


_AUTO_RULES = (
    _rule_typescript_strict,
    _rule_go_idiomatic,
    _rule_python_project,
    _rule_mcp_server,
    _rule_obsidian_plugin,
    _rule_react_testing,
    _rule_frontend_testing,
)


_MANIFEST_READERS = {
    "package.json": _node_deps,
    "pyproject.toml": _pyproject_deps_and_pytest,
    "go.mod": _go_mod_requires,
    "requirements.txt": _requirements_txt_deps,
    "setup.py": _setup_py_deps,
}


def _manifests_walked(tree: "_Tree") -> list[str]:
    """Every discovered instance of the five dependency-manifest filenames,
    with its content actually opened (never only discovered by name) before
    being reported -- independent of whether any individual rule's own
    early-return would have skipped it. `mcp_server`'s scan over
    `requirements.txt`, for instance, stops at the first match across
    several instances; this still opens every one, so a repository with two
    `requirements.txt` files never under-reports the one the rule never
    reached. An unparseable manifest is skipped by its reader, never fatal,
    and still appears here."""
    walked = []
    for name in DEPENDENCY_MANIFEST_NAMES:
        reader = _MANIFEST_READERS[name]
        for path in tree.files_named(name):
            reader(path)
            walked.append(tree.rel(path))
    return sorted(walked)


def detect(repo_dir) -> dict:
    """Scan `repo_dir` and return the detection report
    `[ref: SDD/Interface Specifications/Data model: detection report]`. Pure:
    reads the filesystem, writes nothing, asks nothing.

    `gates` and `gate_evidence` are an honest placeholder here -- T2.3 replaces
    them with real evaluation `[ref: plan/phase-2.md T2.2 step 4]`.
    `unrecognised_stack` is computed from `auto` alone, which this task can and
    must get right `[ref: SDD/Architecture Decisions/ADR-5]`.
    """
    root = Path(repo_dir)
    tree = _Tree(root)

    auto: list[_Proposal] = []
    for rule in _AUTO_RULES:
        proposal = rule(tree)
        if proposal is not None:
            auto.append(proposal)

    baseline: list[dict] = []
    testing_proposal = _rule_testing(tree)
    if testing_proposal is not None:
        entry = testing_proposal.as_dict()
        entry["surface"] = False
        baseline.append(entry)

    manifests_walked = _manifests_walked(tree)

    return {
        "schema": 1,
        "repo": str(repo_dir),
        "auto": [p.as_dict() for p in auto],
        "baseline": baseline,
        "gates": {"q1_backend": False, "q2_architecture": False, "q3_test_quality": False},
        "gate_evidence": {},
        "manifests_walked": manifests_walked,
        "unrecognised_stack": len(auto) == 0,
    }
