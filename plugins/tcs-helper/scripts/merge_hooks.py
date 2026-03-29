#!/usr/bin/env python3
"""Standalone utility to merge hook definitions into settings.json.
Called by tcs-helper:setup. Additive — never overwrites existing hooks.

Resolves template variables (e.g. ${CLAUDE_PLUGIN_ROOT}) before merging.
Target settings.json determined by --scope: g (global) or r (repo, default).
"""
import json
import os
import sys


def read_settings(settings_path: str) -> dict:
    """Read settings.json; return {} if not found or invalid."""
    try:
        with open(settings_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def write_settings(settings_path: str, settings: dict) -> None:
    """Write settings.json with formatting."""
    abs_path = os.path.abspath(settings_path)
    dir_path = os.path.dirname(abs_path)
    if dir_path:
        os.makedirs(dir_path, exist_ok=True)
    with open(abs_path, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)
        f.write('\n')


def resolve_settings_path(scope: str) -> str:
    """Determine target settings.json based on scope.

    g = global (~/.claude/settings.json)
    r = repo   (.claude/settings.json in cwd)
    """
    if scope == 'g':
        return os.path.expanduser('~/.claude/settings.json')
    return os.path.join(os.getcwd(), '.claude', 'settings.json')


def resolve_plugin_root(hooks_json_path: str) -> str:
    """Derive the plugin root from the hooks.json location.

    hooks.json lives at <plugin_root>/hooks/hooks.json, so the plugin root
    is two directories up. Returns absolute path.
    """
    return os.path.dirname(os.path.dirname(os.path.abspath(hooks_json_path)))


def resolve_command(cmd: str, plugin_root: str) -> str:
    """Replace template variables in a hook command with resolved paths.

    ${CLAUDE_PLUGIN_ROOT} → absolute plugin root path
    """
    return cmd.replace('${CLAUDE_PLUGIN_ROOT}', plugin_root)


def resolve_hook_entry(entry: dict, plugin_root: str) -> dict:
    """Deep-copy a hook entry with all commands resolved."""
    resolved = dict(entry)
    resolved['hooks'] = []
    for h in entry.get('hooks', []):
        rh = dict(h)
        if 'command' in rh:
            rh['command'] = resolve_command(rh['command'], plugin_root)
        resolved['hooks'].append(rh)
    return resolved


def hook_already_exists(existing_hooks: list, new_hook: dict) -> bool:
    """Check if a hook entry with the same command already exists."""
    new_cmd = new_hook.get('hooks', [{}])[0].get('command', '')
    for existing in existing_hooks:
        for h in existing.get('hooks', []):
            if h.get('command', '') == new_cmd:
                return True
    return False


def merge_hooks(
    settings_path: str,
    hooks_to_add: dict,
    plugin_root: str,
    set_cleanup_period: bool = False
) -> dict:
    """Merge hooks into settings.json. Returns report of what was added vs skipped.

    Template variables in hook commands are resolved using plugin_root before
    comparison and insertion.
    """
    settings = read_settings(settings_path)
    if 'hooks' not in settings:
        settings['hooks'] = {}

    report = {'added': [], 'skipped': []}

    for event, new_entries in hooks_to_add.items():
        if event not in settings['hooks']:
            settings['hooks'][event] = []
        for entry in new_entries:
            resolved = resolve_hook_entry(entry, plugin_root)
            cmd = resolved.get('hooks', [{}])[0].get('command', '')
            if hook_already_exists(settings['hooks'][event], resolved):
                report['skipped'].append(f'{event}: {cmd}')
            else:
                settings['hooks'][event].append(resolved)
                report['added'].append(f'{event}: {cmd}')

    if set_cleanup_period:
        current = settings.get('cleanupPeriodDays', 0)
        if current < 99999:
            settings['cleanupPeriodDays'] = 99999

    write_settings(settings_path, settings)
    return report


def main():
    """CLI: merge_hooks.py <hooks.json> [--scope g|r] [--set-cleanup-period]

    --scope g   → install into ~/.claude/settings.json (global)
    --scope r   → install into .claude/settings.json (repo, default)
    --set-cleanup-period → set cleanupPeriodDays to 99999

    Plugin root is derived from hooks.json location:
      <plugin_root>/hooks/hooks.json → plugin_root = <two dirs up>
    """
    if len(sys.argv) < 2:
        print(
            'Usage: merge_hooks.py <hooks.json> [--scope g|r] [--set-cleanup-period]',
            file=sys.stderr
        )
        sys.exit(1)

    hooks_path = sys.argv[1]
    set_cleanup = '--set-cleanup-period' in sys.argv

    # Parse --scope (default: r)
    scope = 'r'
    if '--scope' in sys.argv:
        idx = sys.argv.index('--scope')
        if idx + 1 < len(sys.argv):
            scope = sys.argv[idx + 1]
    if scope not in ('g', 'r'):
        print(f'Invalid scope: {scope}. Use g (global) or r (repo).', file=sys.stderr)
        sys.exit(1)

    settings_path = resolve_settings_path(scope)
    plugin_root = resolve_plugin_root(hooks_path)

    with open(hooks_path, 'r') as f:
        hooks_config = json.load(f)

    hooks_to_add = hooks_config.get('hooks', {})
    report = merge_hooks(
        settings_path, hooks_to_add, plugin_root, set_cleanup_period=set_cleanup
    )

    scope_label = 'global' if scope == 'g' else 'repo'
    print(f'  Target: {settings_path} ({scope_label})')
    print(f'  Plugin root: {plugin_root}')
    for item in report['added']:
        print(f'  ✓ Added: {item}')
    for item in report['skipped']:
        print(f'  · Skipped (exists): {item}')


if __name__ == '__main__':
    main()
