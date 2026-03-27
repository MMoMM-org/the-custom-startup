#!/usr/bin/env python3
"""Standalone utility to merge hook definitions into ~/.claude/settings.json.
Called by tcs-helper:setup. Additive — never overwrites existing hooks."""
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
    if dir_path:  # Only call makedirs if dirname is not empty
        os.makedirs(dir_path, exist_ok=True)
    with open(abs_path, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)
        f.write('\n')


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
    set_cleanup_period: bool = False
) -> dict:
    """Merge hooks into settings.json. Returns report of what was added vs skipped."""
    settings = read_settings(settings_path)
    if 'hooks' not in settings:
        settings['hooks'] = {}

    report = {'added': [], 'skipped': []}

    for event, new_entries in hooks_to_add.items():
        if event not in settings['hooks']:
            settings['hooks'][event] = []
        for entry in new_entries:
            if hook_already_exists(settings['hooks'][event], entry):
                cmd = entry.get('hooks', [{}])[0].get('command', '')
                report['skipped'].append(f'{event}: {cmd}')
            else:
                settings['hooks'][event].append(entry)
                cmd = entry.get('hooks', [{}])[0].get('command', '')
                report['added'].append(f'{event}: {cmd}')

    if set_cleanup_period:
        current = settings.get('cleanupPeriodDays', 0)
        if current < 99999:
            settings['cleanupPeriodDays'] = 99999

    write_settings(settings_path, settings)
    return report


def main():
    """CLI: merge_hooks.py <hooks_json_path> <settings_json_path> [--set-cleanup-period]"""
    if len(sys.argv) < 3:
        print('Usage: merge_hooks.py <hooks.json> <settings.json> [--set-cleanup-period]',
              file=sys.stderr)
        sys.exit(1)
    hooks_path = sys.argv[1]
    settings_path = sys.argv[2]
    set_cleanup = '--set-cleanup-period' in sys.argv

    with open(hooks_path, 'r') as f:
        hooks_config = json.load(f)

    hooks_to_add = hooks_config.get('hooks', {})
    report = merge_hooks(settings_path, hooks_to_add, set_cleanup_period=set_cleanup)

    for item in report['added']:
        print(f'  ✓ Added: {item}')
    for item in report['skipped']:
        print(f'  · Skipped (exists): {item}')


if __name__ == '__main__':
    main()
