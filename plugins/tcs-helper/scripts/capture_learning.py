#!/usr/bin/env python3
"""UserPromptSubmit hook — detect learnings and append to queue.
Based on claude-reflect's capture_learning.py."""
import json
import os
import sys

# Support queue path override for tests
sys.path.insert(0, os.path.dirname(__file__))
from lib.reflect_utils import detect_learning, load_queue, save_queue, create_queue_item


def main():
    try:
        project_path = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
        data = json.loads(sys.stdin.read())
        prompt = data.get('prompt', '')

        detection = detect_learning(prompt)
        if not detection:
            sys.exit(0)

        item_type, patterns, confidence = detection

        # Load queue (use override for tests)
        queue_override = os.environ.get('TCS_QUEUE_OVERRIDE')
        if queue_override:
            try:
                with open(queue_override, 'r') as f:
                    queue = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                queue = []
        else:
            queue = load_queue(project_path)

        item = create_queue_item(
            message=prompt[:500],  # truncate very long prompts
            project=project_path,
            item_type=item_type,
            patterns=patterns,
            confidence=confidence,
        )
        queue.append(item)

        if queue_override:
            with open(queue_override, 'w') as f:
                json.dump(queue, f, indent=2)
        else:
            save_queue(project_path, queue)

    except Exception:
        pass  # never block
    sys.exit(0)


if __name__ == '__main__':
    main()
