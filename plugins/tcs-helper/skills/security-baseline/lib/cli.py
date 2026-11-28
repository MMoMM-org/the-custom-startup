"""The one entry point the security-baseline skill runs (spec 025, K2, ADR-1).

    python3 -I -B <abs path>/lib/cli.py audit [--project <dir>]
                                              [--profile macos-host|linux-native|container]

`audit` reads the settings files, the plugin inventory and the machine, and
prints one AuditReport. It writes nothing anywhere: no state, no temporary
file, and with `-B` no `__pycache__` in the skill directory.

**Exit codes:** 0 the verb ran, with or without gaps (the verdict is in the
JSON); 1 an uncaught exception, left as Python's own code so a crash is never
read as a verdict; 2 usage (argparse's own code, also a `--project` that is
not a directory); 3 a precondition failed (unsupported Python), nothing read.

**Order of checks:** argparse, then the interpreter version (before any
sibling import), then the verb.

**Output:** one JSON document on exit 0 only, `ensure_ascii=True`, written to
`sys.stdout.buffer`. Help and messages go to stderr. The CLI never prompts.

**What leaves the `evidence` fields:** nothing a file or a directory name
could word. Evidence is rendered by `render`; fix texts come from templates;
file paths outside evidence are shown relative to a labelled root
(`<project>/.claude/settings.json`), and the real paths of those roots stand
under `roots.evidence`. The finished report is checked once more with
`render.untrusted_outside_evidence` before it is printed.

**Test seam:** `main(argv, world=World(...))`. A `World` holds what `audit`
would otherwise take from the machine: platform, environment variables, the
filesystem root of the container markers, the managed-settings directory, the
sandbox probe, the process reader, the binary lookup. It is a parameter of
`main` only. No flag and no environment variable reaches it, so nothing a
repository ships can replace the probe.

Stdlib only, Python 3.11+. This file itself must still parse on an older
interpreter, so the version check can refuse cleanly.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Mapping, Optional

LIB_DIR = Path(__file__).resolve().parent

MIN_PYTHON = (3, 11)
SCHEMA_VERSION = 1
EXIT_OK = 0
EXIT_USAGE = 2
EXIT_REFUSED = 3

PROFILES = ("macos-host", "linux-native", "container")
PLUGIN_NAME = "tcs-helper"
UNKNOWN_VERSION = "unknown"
GIT_TIMEOUT_SECONDS = 5
FIX_TEMPLATE_ERROR = "fix-template-error"

_PLUGIN_MANIFEST = LIB_DIR.parents[2] / ".claude-plugin" / "plugin.json"
_PLUGIN_VERSION_RE = re.compile(r"[0-9]{1,9}(\.[0-9]{1,9}){0,3}")
_DEFAULT: Any = object()


class _Usage(Exception):
    """Arguments rejected after parsing: exit 2."""


@dataclasses.dataclass(frozen=True)
class World:
    """What `audit` takes from the machine. Every field left at its default
    is the real thing; tests pass fixtures. See the module docstring."""

    platform: Optional[str] = None  # sys.platform
    environ: Optional[Mapping[str, str]] = None  # os.environ
    filesystem: Any = "/"  # holds the container markers and /proc
    system_root: Any = _DEFAULT  # managed-settings directory; None for none
    probe: Optional[Callable] = None  # platform -> probe.ProbeResult
    proc_reader: Optional[Callable] = None  # see environment.detect
    which: Optional[Callable] = None
    runner: Optional[Callable] = None
    git_toplevel: Optional[Callable] = None  # directory -> repository root or None


class _Parser(argparse.ArgumentParser):
    """Help and usage go to stderr: stdout carries one JSON document or nothing."""

    def print_help(self, file=None):
        super().print_help(file if file is not None else sys.stderr)


def _parser() -> argparse.ArgumentParser:
    p = _Parser(prog="cli.py", description="The security-baseline skill's library entry point.")
    sub = p.add_subparsers(dest="verb", required=True, parser_class=_Parser)
    audit = sub.add_parser("audit", help="report the gaps of this machine and project (reads only)")
    audit.add_argument("--project", default=None, metavar="DIR",
                       help="project directory (default: the current directory)")
    audit.add_argument("--profile", choices=PROFILES, default=None,
                       help="use this profile instead of the detected one")
    return p


def _emit(doc: dict) -> None:
    data = (json.dumps(doc, ensure_ascii=True) + "\n").encode("ascii")
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()


# =============================================================================
# audit
# =============================================================================


def _audit(args, world: World) -> dict:
    import checks
    import effective
    import environment
    import inventory
    import layers
    import probe
    import refdata
    import render
    import verdict

    platform = sys.platform if world.platform is None else world.platform
    environ = os.environ if world.environ is None else world.environ
    home = _home(environ)
    config_dir = _absolute_or_none(environ.get("CLAUDE_CONFIG_DIR"))
    project_dir = _project_dir(args.project)
    repo_root = _repo_root(project_dir, world, environ, home, environment)
    system_root = world.system_root
    if system_root is _DEFAULT:
        system_root = layers.default_system_root(platform)

    sources = layers.discover(project_dir, repo_root, home, config_dir, system_root)
    env = environment.detect(
        platform,
        # A `claude` anywhere in the repository is untrusted, not only one
        # below the start directory.
        environment.Roots(Path(world.filesystem), Path(repo_root or project_dir)),
        environ,
        _layer_env_keys(sources, layers.SETTINGS_SCOPES, environment.CONTAINER_ENV_KEY),
        args.profile,
        world.proc_reader,
        world.which,
        runner=world.runner,
    )
    probe_result = (world.probe or probe.run_probe)(env.platform)

    keys = refdata.load_keys()
    context = {
        "sources": sources,
        "env": env,
        "probe": probe_result,
        "keys": keys,
        "credentials": refdata.load_credentials(),
        "commands": refdata.load_commands(),
        "inventory": inventory.scan(home, repo_root),
        "home": Path(home),
        "effective_of": _memoised(
            lambda key: effective.effective(key, sources, keys.rules[key], env.claude_version)
        ),
    }
    raw = [
        _with_rendered_evidence(item, rendered, render)
        for item, rendered in checks.run_all(context)
    ]
    gaps, accepted, info, summary, coverage = verdict.finalise(
        raw, env.profile, verdict.profile_exceptions,
        sources=sources, settings_flag=env.settings_flag,
    )

    names = render.NameTable()
    roots = _roots(project_dir, repo_root, config_dir, home, system_root)

    def shown(item):
        return _finding(item, roots, names, render, checks.FIX_TEMPLATES)

    doc = {
        "schema_version": SCHEMA_VERSION,
        "tool_version": _tool_version(),
        "untrusted_notice": render.UNTRUSTED_NOTICE,
        "environment": env.as_dict(),
        "roots": {"evidence": {label: render.render_untrusted(path) for label, path in roots}},
        "sources": [
            {
                "scope": source.scope,
                "path": _shown_path(source.path, roots, names),
                "status": source.status,
                "reason": source.reason,
            }
            for source in sources
        ],
        "coverage": coverage,
        "probe": {
            "result": probe_result.result,
            "reason": probe_result.reason,
            "missing": list(probe_result.missing),
            "context": dict(probe_result.context),
        },
        "findings": [shown(item) for item in gaps],
        "accepted": [shown(item) for item in accepted],
        "info": [shown(item) for item in info],
        "summary": summary,
    }
    doc = render.cap_report(doc, indent=None)  # the indent `_emit` prints with
    misplaced = render.untrusted_outside_evidence(doc)
    if misplaced:
        # Only the places are named, never the strings found there.
        raise RuntimeError("file content outside evidence at: " + ", ".join(misplaced))
    return doc


def _home(environ) -> str:
    home = environ.get("HOME") or ""
    if not os.path.isabs(home):
        home = os.path.expanduser("~")
    return os.path.abspath(home)


def _absolute_or_none(value):
    return os.path.abspath(value) if value else None


def _project_dir(given) -> str:
    directory = os.path.realpath(os.getcwd() if given is None else given)
    if not os.path.isdir(directory):
        raise _Usage("--project is not a directory")
    return directory


def _repo_root(project_dir, world, environ, home, environment):
    """The repository root containing `project_dir`, or None. An answer that
    does not contain the project is dropped."""
    if world.git_toplevel is not None:
        root = world.git_toplevel(project_dir)
    else:
        root = _git_toplevel(project_dir, environ, home, environment)
    if not isinstance(root, str) or not os.path.isabs(root) or not os.path.isdir(root):
        return None
    root = os.path.realpath(root)
    inside = project_dir == root or project_dir.startswith(root.rstrip(os.sep) + os.sep)
    return root if inside else None


def _git_toplevel(project_dir, environ, home, environment):
    """`git -C <dir> rev-parse --show-toplevel`, or None when git is missing
    or the directory is in no repository.

    git is looked up on the trusted PATH entries only, and never inside the
    repository: the nearest ancestor holding a `.git` entry marks it before
    git is asked. The command reads; it takes no lock and writes nothing.
    """
    inside = _nearest_git_marker(project_dir) or project_dir
    git = environment.path_which(environ.get("PATH"), inside)("git")
    if git is None:
        return None
    try:
        done = subprocess.run(  # noqa: S603 - fixed argv, shell=False
            [git, "-C", project_dir, "rev-parse", "--show-toplevel"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env={
                "PATH": os.path.dirname(git) + os.pathsep + "/usr/bin:/bin",
                "HOME": home,  # the user's own git config: safe.directory
                "LC_ALL": "C",
                "GIT_OPTIONAL_LOCKS": "0",
            },
            timeout=GIT_TIMEOUT_SECONDS,
            shell=False,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if done.returncode != 0:
        return None
    return os.fsdecode(done.stdout).rstrip("\n") or None


def _nearest_git_marker(directory):
    current = directory
    while True:
        if os.path.lexists(os.path.join(current, ".git")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent


def _layer_env_keys(sources, settings_scopes, container_key):
    """`{variable: [scope, ...]}` for the variables settings files set in
    `env`. A settings file that exists but could not be read may set the
    container variable, so it is listed as setting it: the variable then
    never selects the profile that accepts bypass mode."""
    names = {}
    for source in sources:
        if source.scope not in settings_scopes or source.status == "absent":
            continue
        if source.status == "ok":
            table = source.data.get("env")
            variables = list(table) if isinstance(table, dict) else []
        else:
            variables = [container_key]
        for variable in variables:
            scopes = names.setdefault(variable, [])
            if source.scope not in scopes:
                scopes.append(source.scope)
    return names


def _memoised(function):
    cache = {}

    def cached(key):
        if key not in cache:
            cache[key] = function(key)
        return cache[key]

    return cached


def _with_rendered_evidence(item, already_rendered, render):
    finish = render.render_strings if already_rendered else render.render_untrusted
    return dataclasses.replace(item, evidence=finish(item.evidence))


# --- paths outside evidence ---------------------------------------------------


def _roots(project_dir, repo_root, config_dir, home, system_root):
    """`(label, directory)` pairs, the longest directory first, so that a
    path is shown below the closest root."""
    labelled = [("<project>", project_dir)]
    if repo_root and repo_root != project_dir:
        labelled.append(("<repo>", repo_root))
    if config_dir:
        labelled.append(("<config>", config_dir))
    labelled.append(("~", home))
    if system_root:
        labelled.append(("<managed>", system_root))
    return sorted(labelled, key=lambda pair: -len(pair[1]))


def _shown_path(path, roots, names):
    """`path` as `<label>/<tail>`. A tail that is not a plain name becomes a
    numbered placeholder, and so does a path below no root: a directory or
    file name never words a field outside evidence."""
    if not path:
        return ""
    for label, directory in roots:
        if path == directory:
            return label
        prefix = directory.rstrip(os.sep) + os.sep
        if path.startswith(prefix):
            return label + "/" + names.render(path[len(prefix):])
    return names.render(path)


def _finding(item, roots, names, render, templates):
    return {
        "id": item.id,
        "check": item.check,
        "severity": item.severity,
        "status": item.status,
        "layer": item.layer,
        "scope": names.render(item.scope) if item.scope else "",
        "file": _shown_path(item.file, roots, names),
        "evidence": item.evidence,
        "fix": _fix(item.fix, render, templates),
        "accepted": item.accepted,
        "accepted_reason": item.accepted_reason,
    }


def _fix(fix, render, templates):
    """The fix as template id, parameters and text. A fix the template table
    cannot fill is replaced by the fallback, and nothing of it is shown."""
    try:
        template, params = fix["template"], dict(fix["params"])
        return {
            "template": template,
            "params": params,
            "text": render.fix_text(template, params, templates),
        }
    except (render.FixTemplateError, KeyError, TypeError, ValueError):
        return {
            "template": "no-auto-fix",
            "params": {},
            "text": render.fix_text("no-auto-fix", {}, templates),
            "error": FIX_TEMPLATE_ERROR,
        }


def _tool_version() -> str:
    """The version of the plugin this skill is installed in."""
    import jsonio

    status, data, _format, _reason = jsonio.read_json(str(_PLUGIN_MANIFEST), True)
    if status != "ok" or data.get("name") != PLUGIN_NAME:
        return UNKNOWN_VERSION
    version = data.get("version")
    if isinstance(version, str) and _PLUGIN_VERSION_RE.fullmatch(version):
        return version
    return UNKNOWN_VERSION


# =============================================================================
# main
# =============================================================================


def main(argv=None, world: Optional[World] = None) -> int:
    try:
        args = _parser().parse_args(argv)
    except SystemExit as e:  # argparse: usage already on stderr
        return e.code if isinstance(e.code, int) else EXIT_USAGE

    if sys.version_info < MIN_PYTHON:
        print(
            f"cli.py: Python {'.'.join(map(str, MIN_PYTHON))} or newer is required "
            f"(this is {sys.version_info[0]}.{sys.version_info[1]})",
            file=sys.stderr,
        )
        return EXIT_REFUSED

    if str(LIB_DIR) not in sys.path:
        sys.path.insert(0, str(LIB_DIR))

    try:
        doc = _audit(args, World() if world is None else world)
    except _Usage as e:
        print(f"cli.py {args.verb}: {e}", file=sys.stderr)
        return EXIT_USAGE

    _emit(doc)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
