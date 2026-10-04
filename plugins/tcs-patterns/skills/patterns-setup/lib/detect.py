"""The tcs-patterns detector (spec-020 T2.2 + T2.3).

`detect(repo_dir)` is the whole contract between scanning and asking
`[ref: SDD/Interface Specifications/Data model: detection report]`: it reads a
directory and returns a report. It writes nothing, asks nothing, and never
consults the catalogue for anything but the list of pattern names -- and this
module does not even need that list, since the eight stack facts below name
their own patterns directly.

Scope: the eight stack facts, the manifest walk, the runtime-dependency
reader, `evidence`, `manifests_walked`, and `unrecognised_stack` (T2.2); the
three gates (`q1_backend`, `q2_architecture`, `q3_test_quality`) and
`gate_evidence` (T2.3, see `_evaluate_gates` and the functions above it)
`[ref: docs/XDD/specs/020-tcs-patterns-selective-install/plan/phase-2.md#T2.3]`.
A gate decides only whether to ask; no pattern is ever installed because a
gate opened.

Every rule implemented below is cited to its clause in
`[ref: SDD/Interface Specifications/Detection rules: the eight stack facts and
the three gates]` and `[ref: SDD/Interface Specifications/Detection rules:
What counts as a test framework]`.

Requires Python 3.11 or newer, standard library only
`[ref: SDD/Architecture Decisions/ADR-2, "The 3.11 floor"]`. `tomllib` only
entered the stdlib in 3.11, and a pre-3.11 regex fallback for `pyproject.toml`
used to live here; it matched a dependency array across the *whole file*
rather than scoping to `[project]`, which produced a confidently wrong
`mcp-server` proposal that the evidence invariants could not catch (the cited
path genuinely existed). Deleted rather than fixed: refusing loudly on an
unsupported interpreter is the decision, not a better regex -- see
`_require_tomllib`.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Optional

try:
    import tomllib  # Python 3.11+ -- the required floor; see _require_tomllib
except ImportError:  # pragma: no cover - this module's floor is 3.11
    tomllib = None  # type: ignore[assignment]

_MIN_PYTHON_VERSION = (3, 11)


def _require_tomllib() -> None:
    """Refuse loudly on a pre-3.11 interpreter instead of degrading to a
    weaker parser `[ref: SDD/Architecture Decisions/ADR-2, "The 3.11
    floor"]`. Called from `detect()` -- the module's one public entry point
    -- rather than at import time, so every call fails the same deterministic
    way regardless of whether the particular repository under scan happens
    to contain a `pyproject.toml`, and so a test can simulate the missing
    module by monkeypatching `tomllib` to `None` without needing to reimport
    this module under a different interpreter."""
    if tomllib is None:
        raise RuntimeError(
            "tcs-patterns cannot parse pyproject.toml: the standard-library "
            "`tomllib` module is unavailable. It entered the standard library in "
            f"Python 3.11; this interpreter reports {sys.version.split()[0]}. If that "
            "is 3.11 or newer, the standard library is incomplete -- some "
            "distributions package it in pieces -- and `tomllib` needs installing "
            "rather than Python upgrading."
        )


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
# framework"]`. A tuple, not a set: both this and REACT_TEST_LIB_DEPS below
# are iterated for first-match evidence, and a set's iteration order is
# randomised per-process, so two simultaneous matches would make the chosen
# evidence string vary run to run even though every value is individually
# defensible -- a report that changes between identical runs is a bad
# report. No fixture hits two today, but the ordering should not be left to
# hash randomisation regardless.
NODE_TEST_FRAMEWORK_DEPS = ("jest", "vitest", "mocha", "jasmine", "ava")

# react-testing `[ref: SDD/Detection rules, row "react-testing"]`. Also a
# tuple for the same determinism reason as NODE_TEST_FRAMEWORK_DEPS above.
REACT_TEST_LIB_DEPS = ("@testing-library/react", "react-test-renderer", "enzyme")

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

# q1_backend `[ref: SDD/Detection rules, row "q1_backend"]`: a server
# framework in `dependencies`, never `devDependencies` (trap 4). Three
# ecosystem-specific sets; Go is matched separately below because a Go
# module path's last segment, not the whole path, is the framework name.
NODE_SERVER_FRAMEWORK_DEPS = {"express", "fastify", "koa", "@nestjs/core", "hono"}
PYTHON_SERVER_FRAMEWORK_DEPS = {"fastapi", "flask", "django", "aiohttp"}
GO_SERVER_FRAMEWORK_MODULES = {"gin", "echo", "chi"}

# q2_architecture's broker-dependency weak signal `[ref: SDD/Detection rules,
# row "q2_architecture"]`. A gate, so dependencies only -- same restriction
# as q1_backend, for the same reason: a broker pulled in to drive a test
# harness does not mean this repository runs one.
NODE_BROKER_DEPS = {"kafkajs", "amqplib", "@aws-sdk/client-sqs"}
PYTHON_BROKER_DEPS = {"celery"}

# q2_architecture's other two weak content signals: the ports/adapters/domain
# triad (all three required, no common parent, no depth restriction) and the
# event-store directory (either spelling) `[ref: SDD/Detection rules,
# "Each weak signal's quantity is fixed, not left to taste"]`.
ARCHITECTURE_TRIAD_DIR_NAMES = {"ports", "adapters", "domain"}
EVENT_STORE_DIR_NAMES = {"event_store", "eventstore"}

# q2_architecture's per-module events signal: two or more of these filenames
# in distinct module directories -- one is a utility file, not a convention.
EVENTS_FILENAMES = {"events.py", "events.ts"}

_GO_MODULE_VERSION_SEGMENT_RE = re.compile(r"^v\d+$")


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
        # Full paths of every directory seen, post-exclusion, for gate
        # evidence that must cite *where* a content signal sits (q2's triad,
        # event_store) rather than merely that a name occurs somewhere in the
        # tree `[ref: SDD/Detection rules, "The triad's three directories
        # need no common parent"]`.
        self.dir_paths: list[Path] = []
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
            self.dir_names.update(dirnames)
            for d in dirnames:
                self.dir_paths.append(Path(dirpath) / d)
            for name in sorted(filenames):
                self.files.append(Path(dirpath) / name)
        self.files.sort()
        self.dir_paths.sort()

    def rel(self, path: Path) -> str:
        return path.relative_to(self.root).as_posix()

    def files_named(self, name: str) -> list[Path]:
        return [p for p in self.files if p.name == name]

    def files_matching(self, predicate) -> list[Path]:
        return [p for p in self.files if predicate(p.name)]

    def has_dir_named(self, names: set[str]) -> bool:
        return bool(self.dir_names & names)

    def dirs_named(self, names: set[str]) -> list[Path]:
        return [p for p in self.dir_paths if p.name in names]


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


_PYTEST_INI_OPTIONS_RE = re.compile(r"^\s*\[tool\.pytest\.ini_options\]", re.MULTILINE)


def _pyproject_deps_and_pytest(path: Path) -> tuple[list[str], bool]:
    """Returns (dependency names, has a `[tool.pytest.ini_options]` table).
    Requires `tomllib` -- `detect()` calls `_require_tomllib()` before this
    function is ever reached, so a pre-3.11 interpreter never gets here.
    There is deliberately no regex fallback any more: the one that used to
    live here matched `dependencies = [...]` across the whole file instead
    of scoping to `[project]`, so an unrelated `[tool.x] dependencies =
    [...]` array produced a false positive `[ref: SDD/Architecture
    Decisions/ADR-2, "The 3.11 floor"]`."""
    text = _read_text(path)
    if text is None:
        return [], False

    has_pytest_table = bool(_PYTEST_INI_OPTIONS_RE.search(text))

    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return [], has_pytest_table

    if not isinstance(data, dict):
        return [], has_pytest_table

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


_GO_REQUIRE_LINE_RE = re.compile(r"^([A-Za-z0-9._\-/]+)\s+v\S+")


def _go_mod_requires_detailed(path: Path) -> list[tuple[str, bool]]:
    """Every `require`d module in `path`, as `(module, is_indirect)`.

    Unlike the old single-list `_go_mod_requires`, this keeps the `//
    indirect` marker instead of discarding it with the rest of the trailing
    comment -- the marker must survive parsing for gate purposes
    `[ref: SDD/Detection rules, "_go_mod_requires strips // comments..."]`:
    a gate excludes a transitive require (q1_backend asks whether this
    repository *runs* a service), and `gate-q1-go-direct-require` pins a
    `gin` (direct) against a `chi` (`// indirect`) in the same file, where
    only the comment distinguishes them."""
    text = _read_text(path)
    if text is None:
        return []
    modules: list[tuple[str, bool]] = []
    in_block = False
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        if stripped.startswith("require ("):
            in_block = True
            continue
        if in_block:
            if stripped == ")":
                in_block = False
                continue
            is_indirect = "// indirect" in stripped
            code = stripped.split("//", 1)[0].strip()
            match = _GO_REQUIRE_LINE_RE.match(code)
            if match:
                modules.append((match.group(1), is_indirect))
            continue
        if stripped.startswith("require "):
            rest = stripped[len("require "):].strip()
            is_indirect = "// indirect" in rest
            code = rest.split("//", 1)[0].strip()
            match = _GO_REQUIRE_LINE_RE.match(code)
            if match:
                modules.append((match.group(1), is_indirect))
    return modules


def _go_mod_requires(path: Path) -> list[str]:
    """Every required module, direct or indirect. Used by the stack facts
    (`mcp-server`, via `MCP_GO_MODULE`) that do not distinguish the two --
    harmless there, per the SDD note this function's docstring in
    `_go_mod_requires_detailed` cites. Gate evaluation uses that richer
    function instead, because it must exclude indirect requires."""
    return [module for module, _is_indirect in _go_mod_requires_detailed(path)]


def _go_module_short_name(module: str) -> str:
    """The last path segment of a Go module path, with any trailing major-
    version segment (`/v5`, `/v2`, ...) stripped first -- `gin` from
    `github.com/gin-gonic/gin`, `chi` from `github.com/go-chi/chi/v5`."""
    segments = module.split("/")
    while segments and _GO_MODULE_VERSION_SEGMENT_RE.match(segments[-1]):
        segments.pop()
    return segments[-1] if segments else module


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


def _manifests_walked(tree: "_Tree") -> list[str]:
    """Every discovered instance of the five dependency-manifest filenames
    `[ref: SDD/Detection rules, "The walk excludes..."]`, named by filename
    alone -- this function does not open any of them itself. `manifests_walked`
    exists so that a stack fact's absence is explicable as "this file does
    not carry it" rather than "this file was never found"; naming every
    discovered instance is sufficient for that job regardless of whether any
    particular rule above went on to read its content (a rule may
    short-circuit once it finds a match, e.g. `_rule_mcp_server` returning
    before it reaches a later manifest type). A second, discarded read here
    to force every instance "actually opened" would only add a crash
    surface this module does not otherwise have: today's five readers
    swallow their own parse errors, but a call whose result nobody checks
    does not."""
    walked = [tree.rel(path) for name in DEPENDENCY_MANIFEST_NAMES for path in tree.files_named(name)]
    return sorted(walked)


# --- T2.3: the three gates ------------------------------------------------
#
# A gate decides only *whether to ask*; nothing below proposes a pattern
# `[ref: SDD/Interface Specifications/Data model: detection report]`. Every
# function here returns the list of `gate_evidence` strings that justify an
# open gate -- empty means closed -- and every entry lists EVERY contributing
# signal, not the first one found
# `[ref: SDD/Interface Specifications, "lists EVERY signal that contributed"]`.


def _gate_runtime_dependency_evidence(tree: _Tree, node_names: set[str], python_names: set[str]) -> list[str]:
    """Every runtime (never dev, never transitive) dependency declaration
    across the four non-Go manifests that names one of `node_names` /
    `python_names`, formatted the same way `_fmt_dep_evidence` already
    formats a stack fact's dependency evidence
    `[ref: SDD/Detection rules, "Which declaration counts as dependencies
    outside package.json"]`. Go is handled separately
    (`_gate_go_direct_require_evidence`) because its "direct vs. indirect"
    split lives in a parsed marker, not a manifest section.

    Shared between `q1_backend` (server frameworks) and `q2_architecture`'s
    broker signal -- both are gates, so both read the same restricted
    sections: `package.json` `dependencies` only (never `devDependencies`,
    trap 4); `pyproject.toml`'s `[project]`/`[tool.poetry]` dependencies
    (never `optional-dependencies` or a `group.*`); every `requirements.txt`
    line (the format has no development section); `setup.py`'s
    `install_requires` (never `extras_require`) -- exactly what the existing
    readers already parse, since every one of them already excludes the
    development-only counterpart."""
    evidence: list[str] = []
    for pkg_path in tree.files_named("package.json"):
        deps, _dev_deps = _node_deps(pkg_path)
        for name in deps:
            if name in node_names:
                evidence.append(_fmt_dep_evidence(tree, pkg_path, "dependencies", name))
    for req_path in tree.files_named("requirements.txt"):
        for name in _requirements_txt_deps(req_path):
            if name in python_names:
                evidence.append(f"{tree.rel(req_path)}: requirements.{name}")
    for pyproject_path in tree.files_named("pyproject.toml"):
        deps, _has_pytest = _pyproject_deps_and_pytest(pyproject_path)
        for name in deps:
            if name in python_names:
                evidence.append(_fmt_dep_evidence(tree, pyproject_path, "dependencies", name))
    for setup_path in tree.files_named("setup.py"):
        for name in _setup_py_deps(setup_path):
            if name in python_names:
                evidence.append(f"{tree.rel(setup_path)}: install_requires.{name}")
    return evidence


def _gate_go_direct_require_evidence(tree: _Tree) -> list[str]:
    """`go.mod` requires that are both direct (not `// indirect`) and match
    one of `GO_SERVER_FRAMEWORK_MODULES` by their module path's last segment
    `[ref: SDD/Detection rules, "gate-q1-go-direct-require"]`. An indirect
    match is skipped entirely, never merely unlabelled, so `gin` and `chi` in
    the same file resolve to one entry and not two."""
    evidence: list[str] = []
    for go_mod_path in tree.files_named("go.mod"):
        for module, is_indirect in _go_mod_requires_detailed(go_mod_path):
            if is_indirect:
                continue
            if _go_module_short_name(module) in GO_SERVER_FRAMEWORK_MODULES:
                evidence.append(f"{tree.rel(go_mod_path)}: require.{module}")
    return evidence


def _gate_q1_backend_evidence(tree: _Tree) -> list[str]:
    """Row `q1_backend`: a server framework in `dependencies`, never
    `devDependencies` (trap 4), across Node, Python and Go."""
    return (
        _gate_runtime_dependency_evidence(tree, NODE_SERVER_FRAMEWORK_DEPS, PYTHON_SERVER_FRAMEWORK_DEPS)
        + _gate_go_direct_require_evidence(tree)
    )


def _architecture_triad_evidence(tree: _Tree) -> list[str]:
    """q2's `ports/` + `adapters/` + `domain/` triad -- all three required,
    no common parent, no depth restriction
    `[ref: SDD/Detection rules, "The triad's three directories need no
    common parent"]`. Empty unless all three are present anywhere in the
    tree. Lists every matching directory for every name, not only the first
    found per name -- completeness, the same property that makes the Go
    direct/indirect split enforceable
    `[ref: SDD/Interface Specifications, "lists EVERY signal that
    contributed"]`: a repository with two `ports/` directories has two
    contributing signals, and citing only one would under-report exactly as
    crediting only the first-matched `go.mod` require would."""
    found = {name: tree.dirs_named({name}) for name in ARCHITECTURE_TRIAD_DIR_NAMES}
    if not all(found.values()):
        return []
    return sorted(f"{tree.rel(p)}/" for paths in found.values() for p in paths)


def _events_per_module_evidence(tree: _Tree) -> list[str]:
    """q2's per-module events signal: `events.py` / `events.ts` in two or
    more *distinct* module directories -- one such file is a utility, not a
    convention `[ref: SDD/Detection rules, "Each weak signal's quantity is
    fixed, not left to taste"]`."""
    found = tree.files_matching(lambda name: name in EVENTS_FILENAMES)
    distinct_parents = {p.parent for p in found}
    if len(distinct_parents) < 2:
        return []
    return sorted(tree.rel(p) for p in found)


def _event_store_dir_evidence(tree: _Tree) -> list[str]:
    """q2's event-store signal: one directory named `event_store` or
    `eventstore`, at any depth."""
    return sorted(f"{tree.rel(p)}/" for p in tree.dirs_named(EVENT_STORE_DIR_NAMES))


def _broker_dependency_evidence(tree: _Tree) -> list[str]:
    """q2's broker-dependency signal: `kafkajs`, `amqplib`,
    `@aws-sdk/client-sqs` (Node) or `celery` (Python), read the same
    restricted, runtime-only way `q1_backend` reads its server frameworks --
    this also doubles as the check that a broker is not itself credited to
    `q1_backend` `[ref: SDD/Detection rules, "gate-q2-broker-dependency"]`."""
    return _gate_runtime_dependency_evidence(tree, NODE_BROKER_DEPS, PYTHON_BROKER_DEPS)


def _gate_q2_architecture_evidence(tree: _Tree, q1_evidence: list[str]) -> list[str]:
    """Row `q2_architecture`: `q1_backend` opened, **or** any one weak
    content signal. When it opens solely because `q1_backend` opened, the
    justification for the one gate *is* the justification for the other, so
    `q1_evidence` is folded in -- the alternative, an empty `gate_evidence`
    entry for an open gate, violates the invariant this task is required to
    hold `[ref: SDD/Interface Specifications, "every gate reported open has
    a non-empty gate_evidence entry"]`. `trap-03`, `gate-q1-go-direct-require`
    and `gate-q1-node-runtime-dependency` all open q2 this way, with no
    content signal of its own present."""
    content_evidence = (
        _architecture_triad_evidence(tree)
        + _events_per_module_evidence(tree)
        + _event_store_dir_evidence(tree)
        + _broker_dependency_evidence(tree)
    )
    if q1_evidence:
        return sorted(set(q1_evidence) | set(content_evidence))
    return content_evidence


def _gate_q3_test_quality_evidence(tree: _Tree) -> list[str]:
    """Row `q3_test_quality`: any test framework present -- framework
    evidence only, no tests shape required, unlike the `testing` stack fact
    `[ref: SDD/Detection rules, "q3_test_quality needs framework evidence
    only"]`. Every ecosystem's framework evidence is included, not only the
    first found, for the same completeness reason every other gate's
    evidence is complete."""
    matches = [
        p
        for p in (
            _python_testing_framework_evidence(tree),
            _node_testing_framework_evidence(tree),
            _go_testing_framework_evidence(tree),
            _shell_testing_framework_evidence(tree),
        )
        if p is not None
    ]
    return [p.evidence for p in matches]


def _evaluate_gates(tree: _Tree) -> tuple[dict, dict]:
    """Returns `(gates, gate_evidence)`. A closed gate's key is absent from
    `gate_evidence` entirely -- "no entry", not an empty list
    `[ref: SDD/Interface Specifications, "every gate reported closed has no
    entry"]`."""
    q1_evidence = _gate_q1_backend_evidence(tree)
    q2_evidence = _gate_q2_architecture_evidence(tree, q1_evidence)
    q3_evidence = _gate_q3_test_quality_evidence(tree)

    gates = {
        "q1_backend": bool(q1_evidence),
        "q2_architecture": bool(q2_evidence),
        "q3_test_quality": bool(q3_evidence),
    }
    gate_evidence = {}
    if gates["q1_backend"]:
        gate_evidence["q1_backend"] = sorted(set(q1_evidence))
    if gates["q2_architecture"]:
        gate_evidence["q2_architecture"] = sorted(set(q2_evidence))
    if gates["q3_test_quality"]:
        gate_evidence["q3_test_quality"] = sorted(set(q3_evidence))
    return gates, gate_evidence


def detect(repo_dir) -> dict:
    """Scan `repo_dir` and return the detection report
    `[ref: SDD/Interface Specifications/Data model: detection report]`. Pure:
    reads the filesystem, writes nothing, asks nothing.

    `gates` and `gate_evidence` are evaluated by `_evaluate_gates` (T2.3) --
    a gate decides only whether to ask, never what to install
    `[ref: SDD/Interface Specifications/Detection rules: the eight stack
    facts and the three gates]`. `unrecognised_stack` is computed from `auto`
    alone, independently of the gates by construction, so an open gate never
    flips it `[ref: SDD/Architecture Decisions/ADR-5]`.

    Raises `RuntimeError` on a pre-3.11 interpreter -- checked here, the
    module's one public entry point, so every call refuses the same way
    regardless of whether `repo_dir` happens to contain a `pyproject.toml`.
    """
    _require_tomllib()

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
    gates, gate_evidence = _evaluate_gates(tree)

    return {
        "schema": 1,
        "repo": str(repo_dir),
        "auto": [p.as_dict() for p in auto],
        "baseline": baseline,
        "gates": gates,
        "gate_evidence": gate_evidence,
        "manifests_walked": manifests_walked,
        "unrecognised_stack": len(auto) == 0,
    }
