#!/usr/bin/env python3
"""SessionStart hook — warn when observability hooks point at a bundle this $HOME lacks.

The hooks are registered in the repository's `.claude/settings.local.json`, which a host
and a dev container share through the mount, but the bundle they call lives under each
environment's own `$HOME` (#246). Registered from one environment, the other records
nothing and nothing fails visibly. Fails open: any error prints nothing.
"""
import json
import os
import sys

BUNDLE_PREFIX = '$HOME/.claude/observability/'
SETTINGS_FILES = ('settings.local.json', 'settings.json')


def _load(path):
    try:
        with open(path, encoding='utf-8') as f:
            doc = json.load(f)
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def _commands(doc):
    hooks = doc.get('hooks')
    if not isinstance(hooks, dict):
        return
    for groups in hooks.values():
        for group in groups if isinstance(groups, list) else []:
            entries = group.get('hooks') if isinstance(group, dict) else None
            for entry in entries if isinstance(entries, list) else []:
                command = entry.get('command') if isinstance(entry, dict) else None
                if isinstance(command, str):
                    yield command


def _bundle_scripts(command):
    """Script names a command calls under `$HOME/.claude/observability/`."""
    names = []
    for part in command.replace('"', ' ').replace("'", ' ').split():
        if part.startswith(BUNDLE_PREFIX):
            names.append(part[len(BUNDLE_PREFIX):])
    return names


def main():
    try:
        try:
            data = json.loads(sys.stdin.read())
        except ValueError:
            data = {}
        project_path = data.get('cwd') or os.getcwd()
        docs = [_load(os.path.join(project_path, '.claude', name)) for name in SETTINGS_FILES]

        enabled = os.environ.get('CLAUDE_OBSERVABILITY_ENABLED') == '1' or any(
            isinstance(d.get('env'), dict) and d['env'].get('CLAUDE_OBSERVABILITY_ENABLED') == '1'
            for d in docs
        )
        scripts = {name for d in docs for c in _commands(d) for name in _bundle_scripts(c)}
        if not enabled or not scripts:
            sys.exit(0)

        bundle_dir = os.path.join(os.path.expanduser('~'), '.claude', 'observability')
        missing = sorted(n for n in scripts if not os.path.isfile(os.path.join(bundle_dir, n)))
        if missing:
            print(
                f'⚠ Observability hooks are registered for this repository, but {bundle_dir} '
                f'lacks {", ".join(missing)} — nothing is recorded in this environment. '
                'Run /tcs-helper:observability-setup install here.'
            )
    except Exception:
        pass
    sys.exit(0)


if __name__ == '__main__':
    main()
