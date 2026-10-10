"""Every plugin hook must still run when the plugin root contains a space.

Written for #175. Claude Code substitutes `${CLAUDE_PLUGIN_ROOT}` (and
`${CLAUDE_PLUGIN_DATA}`) into a hook's `command` as plain text *before* the
string reaches `sh -c` (hooks reference: "path placeholders ... are
substituted into `command` and into each `args` element as plain strings").
An unquoted placeholder therefore splits on the first space in the install
path, and the hook never executes. That failure is silent: no denial, no
error in the session, just a guard that appears installed and enforces
nothing. A home directory with a space in it is ordinary on macOS.

Two properties are checked for every shell-form hook (exec-form hooks, those
with `args`, have no shell tokenisation and are exempt):

  - after substitution, the shell splits the command so that the plugin path
    stays inside one word;
  - run from a copy of the plugin under a path with a space, the command
    actually reaches its script (the shell's exit status is not 126 "not
    executable" or 127 "not found").

This file does not apply to plugin skill or command Markdown: there Claude
Code substitutes the path when it loads the content and no shell splits it
(#163, closed as not a defect).
"""

import json
import os
import shlex
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
PLACEHOLDERS = ("${CLAUDE_PLUGIN_ROOT}", "${CLAUDE_PLUGIN_DATA}")


def _command_hooks(manifest):
    """Yield every hook object of type `command` in a hooks.json document."""
    stack = [manifest]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            if node.get("type") == "command" and "command" in node:
                yield node
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)


def _shell_form_commands():
    for manifest in sorted(REPO_ROOT.glob("plugins/*/hooks/hooks.json")):
        plugin = manifest.parent.parent
        for hook in _command_hooks(json.loads(manifest.read_text(encoding="utf-8"))):
            if "args" in hook:
                continue
            if any(p in hook["command"] for p in PLACEHOLDERS):
                yield plugin, hook["command"]


COMMANDS = list(_shell_form_commands())


def _substitute(command, root, data):
    return command.replace("${CLAUDE_PLUGIN_ROOT}", str(root)).replace(
        "${CLAUDE_PLUGIN_DATA}", str(data)
    )


def path_survives_tokenisation(command, root="/tmp/has space/root", data="/tmp/has space/data"):
    """True when every substituted placeholder lands inside a single shell word."""
    words = shlex.split(_substitute(command, root, data))
    wanted = [v for p, v in zip(PLACEHOLDERS, (root, data)) if p in command]
    return all(any(v in w for w in words) for v in wanted)


def test_the_scan_finds_the_hooks_it_is_meant_to_guard():
    plugins = {plugin.name for plugin, _ in COMMANDS}
    assert {"tcs-git-helpers", "tcs-patterns", "tcs-helper"} <= plugins, plugins


@pytest.mark.parametrize(
    "plugin,command", COMMANDS, ids=["%s:%s" % (p.name, c) for p, c in COMMANDS]
)
def test_plugin_path_stays_one_shell_word(plugin, command):
    assert path_survives_tokenisation(command), (
        "unquoted plugin-path placeholder in %s/hooks/hooks.json: %s\n"
        'wrap it in double quotes: "\\"${CLAUDE_PLUGIN_ROOT}/scripts/x.sh\\""'
        % (plugin.name, command)
    )


@pytest.mark.parametrize(
    "plugin,command", COMMANDS, ids=["%s:%s" % (p.name, c) for p, c in COMMANDS]
)
def test_hook_reaches_its_script_from_a_spaced_plugin_root(plugin, command, tmp_path):
    root = tmp_path / "has space" / plugin.name
    data = tmp_path / "has space" / "data"
    home = tmp_path / "home"
    work = tmp_path / "work"
    shutil.copytree(plugin, root, ignore=shutil.ignore_patterns("tests", "__pycache__"))
    for d in (data, home, work):
        d.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, HOME=str(home), CLAUDE_PLUGIN_ROOT=str(root), CLAUDE_PLUGIN_DATA=str(data))
    env.pop("CLAUDECODE", None)

    result = subprocess.run(
        ["sh", "-c", _substitute(command, root, data)],
        input="{}", capture_output=True, text=True, cwd=work, env=env, timeout=60,
    )

    assert result.returncode not in (126, 127), (
        "hook did not execute (exit %d) from a spaced plugin root: %s\nstderr: %s"
        % (result.returncode, command, result.stderr)
    )


# --- the tokenisation check itself --------------------------------------------


def test_an_unquoted_placeholder_fails_the_check():
    assert not path_survives_tokenisation("${CLAUDE_PLUGIN_ROOT}/scripts/x.sh")


def test_a_quoted_placeholder_passes_the_check():
    assert path_survives_tokenisation('"${CLAUDE_PLUGIN_ROOT}/scripts/x.sh"')
    assert path_survives_tokenisation('python3 "${CLAUDE_PLUGIN_ROOT}/scripts/x.py"')


def test_a_quoted_variable_with_an_unquoted_suffix_passes_the_check():
    # The form the plugins manifest reference shows as its own example.
    assert path_survives_tokenisation('"${CLAUDE_PLUGIN_ROOT}"/scripts/x.sh')


def test_exec_form_hooks_are_not_scanned():
    manifest = {"hooks": {"X": [{"hooks": [
        {"type": "command", "command": "${CLAUDE_PLUGIN_ROOT}/x.sh", "args": []},
    ]}]}}
    assert ["args" in h for h in _command_hooks(manifest)] == [True]
