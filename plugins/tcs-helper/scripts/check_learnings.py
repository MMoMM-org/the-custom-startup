#!/usr/bin/env python3
"""PreCompact hook — back up learnings queue before context compaction."""
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from lib.reflect_utils import load_queue, CLAUDE_DIR


def main():
    try:
        project_path = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
        queue = load_queue(project_path)
        if not queue:
            sys.exit(0)

        backup_dir = os.path.join(CLAUDE_DIR, 'learnings-backups')
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        backup_path = os.path.join(backup_dir, f'pre-compact-{timestamp}.json')
        with open(backup_path, 'w') as f:
            json.dump(queue, f, indent=2)
    except Exception:
        pass
    sys.exit(0)


if __name__ == '__main__':
    main()
