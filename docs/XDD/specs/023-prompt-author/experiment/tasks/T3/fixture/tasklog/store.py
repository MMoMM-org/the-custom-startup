"""sqlite3-backed task storage."""

import sqlite3
from datetime import date

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    due TEXT,
    done INTEGER NOT NULL DEFAULT 0
)
"""


class Task:
    def __init__(self, id, title, due=None, done=False):
        self.id = id
        self.title = title
        self.due = due
        self.done = done

    def __repr__(self):
        return "Task({!r}, {!r}, {!r}, {!r})".format(self.id, self.title, self.due, self.done)


def _row_to_task(row):
    due = date.fromisoformat(row[2]) if row[2] else None
    return Task(row[0], row[1], due, bool(row[3]))


class TaskStore:
    def __init__(self, path=":memory:"):
        self.conn = sqlite3.connect(path)
        self.conn.execute(SCHEMA)

    def close(self):
        self.conn.close()

    def add(self, title, due=None):
        if not title.strip():
            raise ValueError("title must be non-empty")
        cur = self.conn.execute(
            "INSERT INTO tasks (title, due) VALUES (?, ?)",
            (title, due.isoformat() if due else None))
        self.conn.commit()
        return cur.lastrowid

    def get(self, task_id):
        """Return the Task with `task_id`, or None if there is none."""
        row = self.conn.execute(
            "SELECT id, title, due, done FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return _row_to_task(row) if row else None

    def all(self):
        rows = self.conn.execute("SELECT id, title, due, done FROM tasks ORDER BY id").fetchall()
        return [_row_to_task(r) for r in rows]

    def mark_done(self, task_id):
        cur = self.conn.execute("UPDATE tasks SET done = 1 WHERE id = ?", (task_id,))
        self.conn.commit()
        return cur.rowcount == 1
