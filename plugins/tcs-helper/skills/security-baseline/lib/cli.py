"""The one entry point the security-baseline skill runs (spec 025, K2, ADR-1).

    python3 -I -B <abs path>/lib/cli.py audit [--project <dir>]
                                              [--profile macos-host|linux-native|container]
    python3 -I -B <abs path>/lib/cli.py plan  [--project <dir>] [--profile <p>]
                                              [--sandbox-confirmed]
                                              [--select <change_id>]... [--deselect <change_id>]...
                                              [--move <change_id>=user|project|local]...

`audit` reads the settings files, the plugin inventory and the machine, and
prints one AuditReport. It writes nothing anywhere: no state, no temporary
file, and with `-B` no `__pycache__` in the skill directory.

`plan` reads the same and prints one PlanReport: per settings file the
proposed changes and a diff of what `apply` would write. It writes no
settings file. It writes one plan record (the approval `apply` asks for)
into the state directory, and only after the report is complete. The
state, planner and writer modules are loaded by `plan` alone.

**Exit codes:** 0 the verb ran, with or without gaps (the verdict is in the
JSON); 1 an uncaught exception, left as Python's own code so a crash is never
read as a verdict; 2 usage (argparse's own code, also a `--project` that is
not a directory, an unknown change id or a bad `--move`); 3 a precondition
failed (unsupported Python; for `plan` also an unsupported platform or an
unusable state directory), nothing written.

**Order of checks:** argparse, then the interpreter version (before any
sibling import), then the verb.

**Output:** one JSON document on exit 0 only, `ensure_ascii=True`, written to
`sys.stdout.buffer`. Help and messages go to stderr. The CLI never prompts.

**PlanReport:** `targets[]` holds `scope`, the labelled `path`, the hashes,
`writable`/`refuse_reason`, the `changes` (id, kind, pointer, check,
from_finding, default_selected, selected, flags, and the value under
`evidence.value`) and, under `evidence`, the `real_path` and the `diff`. A
diff is file content, so it stands under `evidence`; its first line is the
header `scope · real path · profile (DETECTED|EXPLICIT) · plan <short>`.
A report over the size limit is cut in this order, each cut named in
`truncated`: `not_proposed` entries, changes that are not selected, selected
changes down to PLAN_MIN_CHANGES per file, diff lines (the diff then ends in
a line saying how many are not shown), the remaining change entries.

**What leaves the `evidence` fields:** nothing a file or a directory name
could word. Evidence is rendered by `render`; fix texts come from templates;
file paths outside evidence are shown relative to a labelled root
(`<project>/.claude/settings.json`), and the real paths of those roots stand
under `roots.evidence`. The finished report is checked once more with
`render.untrusted_outside_evidence` before it is printed.

**`mcp_servers`:** every configured server with where it comes from (name,
origin, scope of the file, labelled path, plugin). The configuration of a
server (command, arguments, environment, headers, URL) is never read into
the report.

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
GIT_FAILED_UNAUDITED = "repository settings (git lookup failed)"
SETUP_PLATFORMS = ("darwin", "linux")
TARGET_SCOPES = ("user", "project", "local")
MOVE_USAGE = "--move takes <change_id>=user|project|local, once per change"
# What a cut plan report still shows per file before diff lines are cut.
PLAN_MIN_CHANGES = 10
PLAN_MIN_DIFF_LINES = 40
DIFF_SHORTENED = "diff shortened: %d more lines are not shown"
FIX_TEMPLATE_ERROR = "fix-template-error"
# Servers listed per origin before the rest is counted: a repository's
# `.mcp.json` cannot fill the report and push the findings out of it.
MCP_SERVERS_PER_ORIGIN = 20

_PLUGIN_MANIFEST = LIB_DIR.parents[2] / ".claude-plugin" / "plugin.json"
_PLUGIN_VERSION_RE = re.compile(r"[0-9]{1,9}(\.[0-9]{1,9}){0,3}")
_CHANGE_ID_RE = re.compile(r"(user|project|local):(/[A-Za-z]{1,64}){1,4}:[0-9a-f]{8}")
_DEFAULT: Any = object()


class _Usage(Exception):
    """Arguments rejected after parsing: exit 2."""


class _Refused(Exception):
    """A precondition of the verb failed: exit 3, nothing written."""


@dataclasses.dataclass(frozen=True)
class _Observed:
    """What one run read: the paths, the settings files, the machine and the
    context the checks run on."""

    environ: Any
    home: str
    config_dir: Optional[str]
    project_dir: str
    repo_root: Optional[str]
    system_root: Optional[str]
    git_failed: bool
    sources: list
    env: Any
    probe: Any
    inventory: Any
    context: dict


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
    plan = sub.add_parser("plan", help="propose changes as one diff per settings file "
                                       "(writes no settings file)")
    plan.add_argument("--project", default=None, metavar="DIR",
                      help="project directory (default: the current directory)")
    plan.add_argument("--profile", choices=PROFILES, default=None,
                      help="use this profile instead of the detected one")
    plan.add_argument("--sandbox-confirmed", action="store_true",
                      help="the developer confirmed that /sandbox shows the sandbox active")
    plan.add_argument("--select", action="append", default=[], metavar="CHANGE_ID",
                      help="include this change (repeatable)")
    plan.add_argument("--deselect", action="append", default=[], metavar="CHANGE_ID",
                      help="leave this change out (repeatable)")
    plan.add_argument("--move", action="append", default=[], metavar="CHANGE_ID=SCOPE",
                      help="put this addition into the user, project or local file (repeatable)")
    return p


def _emit(doc: dict) -> None:
    data = (json.dumps(doc, ensure_ascii=True) + "\n").encode("ascii")
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()


# =============================================================================
# audit
# =============================================================================


def _observe(args, world: World) -> _Observed:
    """Read the settings files, the inventory and the machine. Writes nothing."""
    import effective
    import environment
    import inventory
    import layers
    import probe
    import refdata

    platform = sys.platform if world.platform is None else world.platform
    environ = os.environ if world.environ is None else world.environ
    home = _home(environ)
    config_dir = _absolute_or_none(environ.get("CLAUDE_CONFIG_DIR"))
    project_dir = _project_dir(args.project)
    repo_root = _repo_root(project_dir, world, environ, home, environment)
    system_root = world.system_root
    if system_root is _DEFAULT:
        system_root = layers.default_system_root(platform)

    git_failed = repo_root is None and _nearest_git_marker(project_dir) is not None
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
    env = _with_unreadable_layers_named(
        env, sources, layers.SETTINGS_SCOPES, environment.CONTAINER_ENV_KEY,
    )
    probe_result = (world.probe or probe.run_probe)(env.platform)

    keys = refdata.load_keys()
    found = inventory.scan(home, repo_root)
    context = {
        "sources": sources,
        "env": env,
        "probe": probe_result,
        "keys": keys,
        "credentials": refdata.load_credentials(),
        "commands": refdata.load_commands(),
        "inventory": found,
        "home": Path(home),
        "effective_of": _memoised(
            lambda key: effective.effective(key, sources, keys.rules[key], env.claude_version)
        ),
    }
    return _Observed(
        environ=environ, home=home, config_dir=config_dir, project_dir=project_dir,
        repo_root=repo_root, system_root=system_root, git_failed=git_failed,
        sources=sources, env=env, probe=probe_result, inventory=found, context=context,
    )


def _audit(args, world: World) -> dict:
    import checks
    import layers
    import render
    import verdict

    seen = _observe(args, world)
    sources, env, probe_result, found = seen.sources, seen.env, seen.probe, seen.inventory
    names = render.NameTable()
    roots = _roots(seen.project_dir, seen.repo_root, seen.config_dir, seen.home, seen.system_root)
    raw = [
        _with_rendered_evidence(item, rendered, render, roots, names)
        for item, rendered in checks.run_all(seen.context)
    ]
    gaps, accepted, info, summary, coverage = verdict.finalise(
        raw, env.profile, verdict.profile_exceptions,
        sources=sources, settings_flag=env.settings_flag,
    )

    if seen.git_failed:
        # A repository marks the project, yet its root is unknown: repository-level settings
        # were not read, and the report says so.
        coverage["unaudited"] = [*coverage["unaudited"], GIT_FAILED_UNAUDITED]
        summary["counts"]["unaudited"] = len(coverage["unaudited"])

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
        "mcp_servers": _mcp_servers(
            layers.mcp_servers(
                sources,
                # The inventory keeps no configuration values.
                [{"name": s.name, "path": s.path, "plugin": s.plugin, "config": None}
                 for s in found.plugin_mcp],
                layers.project_keys(seen.project_dir, seen.repo_root),
            ),
            roots, names,
        ),
        "findings": [shown(item) for item in gaps],
        "accepted": [shown(item) for item in accepted],
        "info": [shown(item) for item in info],
        "summary": summary,
    }
    # The indent `_emit` prints with; one byte is left for its final newline.
    doc = render.cap_report(doc, limit=render.REPORT_LIMIT_BYTES - 1, indent=None)
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


def _unreadable_scopes(sources, settings_scopes):
    """Scopes with a settings file that exists and could not be read."""
    scopes = []
    for source in sources:
        if (source.scope in settings_scopes and source.status not in ("ok", "absent")
                and source.scope not in scopes):
            scopes.append(source.scope)
    return scopes


def _with_unreadable_layers_named(env, sources, settings_scopes, container_key):
    """`env` with its note on the ignored container variable reworded.

    `environment.detect` is told that an unreadable layer sets the variable
    (`_layer_env_keys`) and so writes "set by <scopes> settings" for all of
    them. Nothing is known about what an unreadable file sets: its scopes
    are taken out of that note and named in one of their own.
    """
    unreadable = _unreadable_scopes(sources, settings_scopes)
    ignored = f"env:{container_key} ignored"
    if not unreadable or not any(note.startswith(ignored) for note in env.profile_evidence):
        return env
    readable = [source for source in sources if source.status == "ok"]
    setters = _layer_env_keys(readable, settings_scopes, container_key).get(container_key, [])
    notes = []
    if setters:
        notes.append(f"{ignored}: set by {', '.join(setters)} settings")
    notes.append(f"{ignored}: unreadable {', '.join(unreadable)} settings may set {container_key}")
    evidence = []
    for note in env.profile_evidence:
        if note.startswith(ignored):
            evidence.extend(notes)
            notes = []
        else:
            evidence.append(note)
    return dataclasses.replace(env, profile_evidence=type(env.profile_evidence)(evidence))


def _mcp_servers(servers, roots, names):
    """The `mcp_servers` block: where each server comes from, never what it
    runs. The first MCP_SERVERS_PER_ORIGIN of an origin are listed, the rest
    of it counted in one `{origin, more}` entry."""
    listed, counts = [], {}
    for server in servers:
        counts[server.origin] = counts.get(server.origin, 0) + 1
        if counts[server.origin] > MCP_SERVERS_PER_ORIGIN:
            continue
        listed.append({
            "name": names.render(server.name),
            "origin": server.origin,
            "scope": server.scope,
            "path": _shown_path(server.path, roots, names),
            "plugin": names.render(server.plugin) if server.plugin is not None else None,
        })
    out = []
    for position, entry in enumerate(listed):
        out.append(entry)
        origin = entry["origin"]
        last_of_origin = all(later["origin"] != origin for later in listed[position + 1:])
        if last_of_origin and counts[origin] > MCP_SERVERS_PER_ORIGIN:
            out.append({"origin": origin, "more": counts[origin] - MCP_SERVERS_PER_ORIGIN})
    return out


def _memoised(function):
    cache = {}

    def cached(key):
        if key not in cache:
            cache[key] = function(key)
        return cache[key]

    return cached


def _with_rendered_evidence(item, already_rendered, render, roots, names):
    finish = render.render_strings if already_rendered else render.render_untrusted
    labelled = _label_evidence_files(item.evidence, roots, names)
    return dataclasses.replace(item, evidence=finish(labelled))


def _label_evidence_files(node, roots, names):
    """EVIDENCE with the `file` of every `{scope, file, value}` entry (the files a
    value was set in or overridden in) shown as `<label>/<tail>`, so that a long
    path is not cut in the middle of its name."""
    if isinstance(node, dict):
        labelled = {key: _label_evidence_files(item, roots, names) for key, item in node.items()}
        if isinstance(node.get("file"), str) and "scope" in node and "value" in node:
            labelled["file"] = _shown_path(node["file"], roots, names)
        return labelled
    if isinstance(node, (list, tuple)):
        return [_label_evidence_files(item, roots, names) for item in node]
    return node


# --- paths outside evidence ---------------------------------------------------


def _roots(project_dir, repo_root, config_dir, home, system_root):
    """`(label, directory)` pairs, the longest directory first, so that a
    path is shown below the closest root."""
    labelled = [("<project>", project_dir)]
    if repo_root and repo_root != project_dir:
        labelled.append(("<repo>", repo_root))
    if config_dir:
        labelled.append(("<config>", config_dir))
    labelled.append(("<plugins>", os.path.join(home, ".claude", "plugins")))  # inventory.scan
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
# plan
# =============================================================================


def _plan(args, world: World) -> dict:
    import render
    import state

    seen = _observe(args, world)
    if seen.env.platform not in SETUP_PLATFORMS or seen.env.profile not in PROFILES:
        raise _Refused("setup is not supported on this platform; audit still runs")
    selection = {"select": list(args.select), "deselect": list(args.deselect)}
    moves = _moves(args.move)
    plan = _computed_plan(seen, selection, moves, args.sandbox_confirmed)
    try:
        root = state.state_dir(
            seen.environ, seen.home,
            forbidden=[d for d in (seen.repo_root, seen.project_dir) if d],
        )
        record = state.new_record(
            plan.plan_id, state.utc_now(), selection=selection, moves=moves,
            profile=seen.env.profile, profile_source=seen.env.profile_source,
            sandbox_confirmed=bool(args.sandbox_confirmed),
        )
        doc = _plan_report(plan, record.expires_at, seen, render)
        state.save_plan(root, record)  # last: no approval exists for a report that failed
    except state.StateError as e:
        raise _Refused(str(e)) from None
    return doc


def _computed_plan(seen: _Observed, selection, moves, sandbox_confirmed):
    """The `planner.Plan` for what `seen` holds. `plan` shows it; `apply`
    calls this with the selection, moves and confirmation of the plan record
    and compares `plan_id`. Reads the three target files, writes nothing."""
    import checks
    import planner
    import writer

    allowed = writer.allowed_targets(seen.home, seen.config_dir, seen.project_dir, seen.repo_root)
    managed_roots = None
    if seen.system_root:
        managed_roots = (*writer.MANAGED_ROOTS, seen.system_root)
    snapshot = planner.Snapshot(
        sources=tuple(seen.sources),
        environment=seen.env,
        probe=seen.probe,
        keys=seen.context["keys"],
        credentials=seen.context["credentials"],
        home=seen.home,
        targets=planner.load_targets(
            seen.sources, {scope: target.path for scope, target in allowed.items()},
        ),
    )
    findings = [item for item, _rendered in checks.run_all(seen.context)]
    try:
        return planner.compute_plan(
            snapshot, findings, selection, moves, bool(sandbox_confirmed), _tool_version(),
            refusal=lambda scope, path: writer.refusal(
                scope, path, targets=allowed, managed_roots=managed_roots,
            ),
        )
    except planner.SelectionError as e:
        raise _Usage(_selection_message(e)) from None


def _moves(pairs) -> dict:
    """`["<id>=<scope>", ...]` as `{id: scope}`. The text given is never echoed."""
    moves = {}
    for pair in pairs:
        change, separator, scope = pair.rpartition("=")
        if not separator or not change or scope not in TARGET_SCOPES:
            raise _Usage(MOVE_USAGE)
        if moves.setdefault(change, scope) != scope:
            raise _Usage(MOVE_USAGE)
    return moves


def _selection_message(error) -> str:
    """Names the change ids at fault. Text that does not have the form of a
    change id is counted, not repeated: it may be anything."""
    wording = {
        "unknown-id": "unknown change id",
        "conflict": "change id both selected and deselected",
        "bad-scope": "change id moved to a file that is not user, project or local",
        "not-movable": "change id that cannot be moved (a removal stays in its own file)",
    }.get(error.reason, "unusable change id")
    named = [i for i in error.ids if isinstance(i, str) and _CHANGE_ID_RE.fullmatch(i)]
    parts = []
    if named:
        parts.append(f"{wording}: {', '.join(named)}")
    other = len(error.ids) - len(named)
    if other:
        parts.append(f"{other} change id(s) not in the form the plan prints")
    return "; ".join(parts) or wording


def _plan_report(plan, expires_at, seen: _Observed, render) -> dict:
    names = render.NameTable()
    roots = _roots(seen.project_dir, seen.repo_root, seen.config_dir, seen.home, seen.system_root)
    doc = {
        "schema_version": SCHEMA_VERSION,
        "tool_version": _tool_version(),
        "untrusted_notice": render.UNTRUSTED_NOTICE,
        "plan_id": plan.plan_id,
        "plan_short": plan.plan_short,
        "expires_at": expires_at,
        "environment": {
            "profile": seen.env.profile,
            "profile_source": seen.env.profile_source,
        },
        "consent_note": plan.consent_note,
        "self_allow_warning": plan.self_allow_warning,
        "targets": [
            {
                "scope": target.scope,
                "path": _shown_path(target.path, roots, names),
                "pre_sha256": target.pre_sha256,
                "post_sha256": target.post_sha256,
                "writable": target.writable,
                "refuse_reason": target.refuse_reason,
                "changes": [
                    {
                        "id": change.id,
                        "kind": change.kind,
                        "pointer": change.pointer,
                        "check": change.check,
                        "from_finding": change.from_finding,
                        "default_selected": change.default_selected,
                        "selected": change.selected,
                        "flags": list(change.flags),
                        "evidence": {"value": render.render_untrusted(change.value)},
                    }
                    for change in target.changes
                ],
                "evidence": {
                    "real_path": render.render_untrusted(target.real_path),
                    "diff": target.diff,
                },
            }
            for target in plan.targets
        ],
        "not_proposed": [dict(entry) for entry in plan.not_proposed],
        "requires_unsandboxed_apply": True,
    }
    # One byte is left for the final newline `_emit` adds.
    doc = _capped_plan(doc, render.REPORT_LIMIT_BYTES - 1, render)
    misplaced = render.untrusted_outside_evidence(doc)
    if misplaced:
        raise RuntimeError("file content outside evidence at: " + ", ".join(misplaced))
    return doc


def _capped_plan(doc, limit, render) -> dict:
    """DOC, cut if needed to LIMIT bytes of compact JSON, with every cut
    named in `truncated`. See the module docstring for the order. Targets,
    their hashes and the diff headers are never cut; a report that still
    does not fit is returned marked `over_limit`."""
    def size(candidate):
        return len(json.dumps(candidate, ensure_ascii=True))

    if size(doc) <= limit:
        return doc

    def count(chosen):
        return max(
            [sum(1 for c in t["changes"] if c["selected"] is chosen) for t in doc["targets"]],
            default=0,
        )

    keep = {
        "not_proposed": len(doc["not_proposed"]),
        "unselected": count(False),
        "selected": count(True),
        "diff": max([t["evidence"]["diff"].count("\n") + 1 for t in doc["targets"]], default=0),
    }

    def shaped(keep):
        marker = {
            "limit_bytes": limit,
            "not_proposed_dropped": len(doc["not_proposed"]) - keep["not_proposed"],
            "changes_hidden": {},
            "diffs_shortened": {},
        }
        targets = []
        for target in doc["targets"]:
            room = {True: keep["selected"], False: keep["unselected"]}
            changes = []
            for change in target["changes"]:
                if room[change["selected"]] > 0:
                    room[change["selected"]] -= 1
                    changes.append(change)
            if len(changes) < len(target["changes"]):
                marker["changes_hidden"][target["scope"]] = len(target["changes"]) - len(changes)
            diff = target["evidence"]["diff"]
            lines = diff.split("\n")
            if len(lines) > keep["diff"]:
                shown = lines[:keep["diff"]]
                marker["diffs_shortened"][target["scope"]] = {
                    "shown_lines": len(shown), "total_lines": len(lines),
                }
                shown.append(DIFF_SHORTENED % (len(lines) - len(shown)))
                diff = render.Untrusted("\n".join(shown))
            targets.append({
                **target, "changes": changes, "evidence": {**target["evidence"], "diff": diff},
            })
        return {
            **doc,
            "targets": targets,
            "not_proposed": doc["not_proposed"][:keep["not_proposed"]],
            "truncated": marker,
        }

    def fits(name, value):
        return size(shaped({**keep, name: value})) <= limit

    cuts = (
        ("not_proposed", 0), ("unselected", 0), ("selected", PLAN_MIN_CHANGES),
        ("diff", PLAN_MIN_DIFF_LINES), ("selected", 0), ("diff", 1),
    )
    for name, floor in cuts:
        if size(shaped(keep)) <= limit:
            break
        low, high = min(floor, keep[name]), keep[name]
        while low < high:  # the most that still fits; the floor when nothing does
            middle = (low + high + 1) // 2
            if fits(name, middle):
                low = middle
            else:
                high = middle - 1
        keep[name] = low
    out = shaped(keep)
    if size(out) > limit:
        out["truncated"]["over_limit"] = True
    return out


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

    verb = {"audit": _audit, "plan": _plan}[args.verb]
    try:
        doc = verb(args, World() if world is None else world)
    except _Usage as e:
        print(f"cli.py {args.verb}: {e}", file=sys.stderr)
        return EXIT_USAGE
    except _Refused as e:
        print(f"cli.py {args.verb}: {e}", file=sys.stderr)
        return EXIT_REFUSED

    _emit(doc)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
