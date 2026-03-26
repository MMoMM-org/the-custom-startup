#!/usr/bin/env python3
"""SessionStart hook — show pending learnings count and YOLO review reminder."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from lib.reflect_utils import load_queue, get_queue_path


def main():
    try:
        if os.environ.get('CLAUDE_REFLECT_REMINDER', '').lower() == 'false':
            sys.exit(0)

        project_path = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
        messages = []

        # Check queue
        queue_override = os.environ.get('TCS_QUEUE_OVERRIDE')
        if queue_override:
            try:
                with open(queue_override, 'r') as f:
                    queue = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                queue = []
        else:
            queue = load_queue(project_path)

        if queue:
            messages.append(
                f'📋 {len(queue)} pending learning(s) in queue — run /memory-add to process'
            )

        # Check for YOLO review file
        yolo_path_override = os.environ.get('TCS_YOLO_REVIEW_PATH')
        if yolo_path_override:
            yolo_path = yolo_path_override
        else:
            yolo_path = os.path.join(project_path, 'docs', 'ai', 'memory', 'yolo-review.md')

        if os.path.exists(yolo_path):
            messages.append(
                '⚠ Unreviewed YOLO memory entries in docs/ai/memory/yolo-review.md '
                '— run /memory-add --review-yolo'
            )

        if messages:
            print('\n'.join(messages))

    except Exception:
        pass
    sys.exit(0)


if __name__ == '__main__':
    main()
