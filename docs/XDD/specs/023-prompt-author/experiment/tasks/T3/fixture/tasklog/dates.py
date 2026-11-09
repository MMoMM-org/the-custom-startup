"""Date helpers for due dates."""

from datetime import date


def parse_due(text):
    """Parse 'YYYY-MM-DD'; empty or None means no due date."""
    if not text:
        return None
    return date.fromisoformat(text.strip())


def days_between(start, end):
    """Whole days from `start` to `end` (negative if `end` is earlier)."""
    return (end - start).days


def is_overdue(task, today):
    """True if the task is not done and its due date is before `today`."""
    return not task.done and task.due is not None and task.due < today
