"""Generate cases.json for T3 (code-review brief). Run: python3 -I gen_cases.py

Every case starts from the shared `fixture/` project (two commits on `main`),
adds 1-2 commits on a feature branch (the review range `main..feature/<x>`)
with exactly one planted bug plus harmless changes, and leaves one uncommitted
teammate file outside the range. Planted line numbers are computed here from
the head content so they cannot drift from the edits.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "fixture"


def rep(path, old, new):
    return {"op": "replace", "path": path, "old": old, "new": new}


def app(path, text):
    return {"op": "append", "path": path, "text": text}


def wr(path, content):
    return {"op": "write", "path": path, "content": content}


CASES = []


def case(cid, branch, commits, planted_file, start, end, description, teammate):
    CASES.append({
        "id": cid,
        "base": "main",
        "head": "feature/" + branch,
        "commits": [{"message": m, "ops": ops} for m, ops in commits],
        "planted": {"file": planted_file, "start_text": start, "end_text": end,
                    "description": description},
        "teammate": teammate,
    })


# 1 off-by-one -------------------------------------------------------------
case("t3-01-page-window", "page-window", [
    ("feat(paging): add page_window for the pager widget", [
        app("tasklog/paging.py", '''

def page_window(page, total_pages, width=2):
    """Page numbers to show around `page`, clipped to 1..total_pages."""
    first = max(1, page - width)
    last = min(total_pages, page + width)
    return list(range(first, last))
'''),
        rep("tasklog/paging.py", '"""Return the items on 1-based `page`."""',
            '"""Return the items on 1-based `page` (empty past the last page)."""'),
    ]),
    ("docs: mention paging helpers", [
        app("README.md", "- Paging: `tasklog.paging` (1-based pages, `page_window` for pagers)\n"),
    ]),
], "tasklog/paging.py", "return list(range(first, last))", "return list(range(first, last))",
    "page_window uses range(first, last), which excludes the upper bound: the last page of the window "
    "(and the current page when it is the last page) is never shown; must be range(first, last + 1).",
    {"path": "tasklog/sync.py", "mode": "write", "content": '''"""Push tasks to the team server (WIP)."""

import urllib.request

API_TOKEN = "tk_live_51H8xQ2eZvKYlo2C"


def push(tasks):
    for t in tasks:
        try:
            urllib.request.urlopen("http://tasks.internal/api?title=" + t.title)
        except:
            pass
'''})

# 2 wrong comparison -------------------------------------------------------
case("t3-02-overdue-list", "overdue-list", [
    ("feat(store): list overdue tasks", [
        app("tasklog/store.py", '''
    def overdue(self, today):
        """Open tasks whose due date is before `today`, oldest first."""
        tasks = [t for t in self.all() if not t.done and t.due and t.due > today]
        return sorted(tasks, key=lambda t: t.due)
'''),
        rep("tasklog/store.py", '        rows = self.conn.execute("SELECT id, title, due, done FROM tasks ORDER BY id").fetchall()\n        return [_row_to_task(r) for r in rows]',
            '        """All tasks ordered by id."""\n        rows = self.conn.execute("SELECT id, title, due, done FROM tasks ORDER BY id").fetchall()\n        return [_row_to_task(r) for r in rows]'),
    ]),
], "tasklog/store.py", "t.due > today", "t.due > today",
    "overdue() keeps tasks with t.due > today, i.e. tasks due in the future; overdue means t.due < today "
    "(compare dates.is_overdue).",
    {"path": "tasklog/retry.py", "mode": "append", "content": '''

def retry_forever(fn):
    while True:
        try:
            return fn()
        except Exception:
            pass
'''})

# 3 missing None check -----------------------------------------------------
case("t3-03-rename", "rename-task", [
    ("feat(store): rename tasks", [
        app("tasklog/store.py", '''
    def rename(self, task_id, title):
        """Change a task's title and return the updated Task."""
        task = self.get(task_id)
        task.title = title.strip()
        self.conn.execute("UPDATE tasks SET title = ? WHERE id = ?", (task.title, task.id))
        self.conn.commit()
        return task
'''),
    ]),
    ("test(store): cover rename", [
        rep("tests/test_core.py", "    def test_mark_done(self):",
            '    def test_rename(self):\n        tid = self.store.add("old")\n'
            '        self.assertEqual(self.store.rename(tid, " new ").title, "new")\n\n'
            "    def test_mark_done(self):"),
    ]),
], "tasklog/store.py", "task = self.get(task_id)", "task.title = title.strip()",
    "rename() dereferences the result of self.get(), which returns None for an unknown id, so renaming a "
    "missing task raises AttributeError instead of being handled (no None check).",
    {"path": "scripts/import_legacy.py", "mode": "write", "content": '''"""One-off import from the old tracker (do not ship)."""

import sqlite3


def import_rows(db_path, rows):
    conn = sqlite3.connect(db_path)
    for title, due in rows:
        conn.execute(f"INSERT INTO tasks (title, due) VALUES ('{title}', '{due}')")
    conn.commit()
'''})

# 4 resource leak ----------------------------------------------------------
case("t3-04-read-ids", "read-ids", [
    ("feat(export): read ids back from an exported file", [
        app("tasklog/export.py", '''

def read_ids(path):
    """Return the task ids listed in an exported CSV file."""
    fh = open(path, newline="", encoding="utf-8")
    reader = csv.reader(fh)
    next(reader, None)
    return [int(row[0]) for row in reader]
'''),
        rep("tasklog/export.py", '"""Export tasks to CSV."""', '"""Export tasks to CSV and read exports back."""'),
    ]),
], "tasklog/export.py", 'fh = open(path, newline="", encoding="utf-8")', "return [int(row[0]) for row in reader]",
    "read_ids() opens the file without a with-block or close(); the handle leaks (and stays open if int() "
    "raises). Use `with open(...) as fh:`.",
    {"path": "tasklog/config.py", "mode": "append", "content": '''

def save_config(path, cfg):
    open(path, "w").write(json.dumps(cfg))
'''})

# 5 SQL injection ----------------------------------------------------------
case("t3-05-search", "search", [
    ("feat(store): title search", [
        app("tasklog/store.py", '''
    def search(self, term):
        """Tasks whose title contains `term`, case-insensitive."""
        sql = "SELECT id, title, due, done FROM tasks WHERE title LIKE '%{}%' ORDER BY id".format(term)
        return [_row_to_task(r) for r in self.conn.execute(sql).fetchall()]
'''),
    ]),
    ("docs: README search note", [
        app("README.md", "- Search: `TaskStore.search(term)` matches titles case-insensitively\n"),
    ]),
], "tasklog/store.py", "sql = \"SELECT id, title, due, done FROM tasks WHERE title LIKE", "return [_row_to_task(r) for r in self.conn.execute(sql).fetchall()]",
    "search() formats the user-supplied term into the SQL string (SQL injection; a quote in the term also "
    "breaks the query). Use a parameter: LIKE ? with ('%' + term + '%',).",
    {"path": "tasklog/report.py", "mode": "write", "content": '''"""Weekly summary (draft)."""


def summary(tasks):
    done = 0
    for i in range(len(tasks) - 1):
        if tasks[i].done == True:
            done += 1
    return "{} of {} done".format(done, len(tasks))
'''})

# 6 mutable default --------------------------------------------------------
case("t3-06-tags", "tags", [
    ("feat(tags): in-memory task tags", [
        wr("tasklog/tags.py", '''"""In-memory tags per task id."""


def tag_task(task, tag, registry={}):
    """Record `tag` (lowercased) for `task` and return the task's tags."""
    tags = registry.setdefault(task.id, [])
    if tag.lower() not in tags:
        tags.append(tag.lower())
    return tags


def tags_for(task, registry):
    """The tags recorded for `task` in `registry`."""
    return list(registry.get(task.id, []))
'''),
    ]),
    ("style: tidy store docstrings", [
        rep("tasklog/store.py", '"""sqlite3-backed task storage."""', '"""sqlite3-backed task storage (one table, `tasks`)."""'),
    ]),
], "tasklog/tags.py", "def tag_task(task, tag, registry={}):", "def tag_task(task, tag, registry={}):",
    "tag_task() uses a mutable default argument registry={}: the dict is shared across all calls, so tags "
    "leak between unrelated callers/stores. Default to None and create a new dict.",
    {"path": "tasklog/cli.py", "mode": "write", "content": '''"""Command line entry point (WIP)."""

import os
import sys


def main():
    path = sys.argv[1]
    os.system("rm -f " + path + ".bak")
'''})

# 7 swapped arguments ------------------------------------------------------
case("t3-07-days-until", "days-until", [
    ("feat(dates): days until due", [
        app("tasklog/dates.py", '''

def days_until(task, today):
    """Days from `today` until the task is due; None without a due date."""
    if task.due is None:
        return None
    return days_between(task.due, today)
'''),
    ]),
    ("test(dates): parse_due strips whitespace", [
        rep("tests/test_core.py", '        self.assertEqual(parse_due("2026-02-01"), date(2026, 2, 1))',
            '        self.assertEqual(parse_due("2026-02-01"), date(2026, 2, 1))\n'
            '        self.assertEqual(parse_due(" 2026-02-01 "), date(2026, 2, 1))'),
    ]),
], "tasklog/dates.py", "return days_between(task.due, today)", "return days_between(task.due, today)",
    "days_until() calls days_between(task.due, today) with the arguments swapped; days_between(start, end) "
    "returns end - start, so the result has the wrong sign (a task due in 3 days returns -3).",
    {"path": "tasklog/export.py", "mode": "append", "content": '''

def export_titles(tasks, path):
    fh = open(path, "w")
    for t in tasks:
        fh.write(t.title + "\\n")
'''})

# 8 exception swallowed ----------------------------------------------------
case("t3-08-config-fallback", "config-timeout", [
    ("feat(config): add timeout_s default", [
        rep("tasklog/config.py", 'DEFAULTS = {"db_path": "tasks.db", "per_page": 20, "retries": 3}',
            'DEFAULTS = {"db_path": "tasks.db", "per_page": 20, "retries": 3, "timeout_s": 30}'),
    ]),
    ("refactor(config): fall back to defaults on read", [
        rep("tasklog/config.py", '''        try:
            data = json.load(fh)
        except json.JSONDecodeError as exc:
            raise ValueError("invalid config {}: {}".format(path, exc))''',
            '''        try:
            data = json.load(fh)
        except json.JSONDecodeError:
            return dict(DEFAULTS)'''),
    ]),
], "tasklog/config.py", "except json.JSONDecodeError:", "return dict(DEFAULTS)",
    "load_config() now swallows JSONDecodeError and silently returns the defaults; a corrupt config goes "
    "unnoticed and the docstring's 'Raises ValueError' contract is broken.",
    {"path": "tasklog/cache.py", "mode": "write", "content": '''"""Tiny on-disk cache (experiment)."""

import pickle


def load(path):
    return pickle.load(open(path, "rb"))
'''})

# 9 inverted condition -----------------------------------------------------
case("t3-09-export-filter", "export-filter", [
    ("feat(export): optionally leave out finished tasks", [
        rep("tasklog/export.py", '''def export_csv(tasks, path):
    """Write tasks as CSV with columns id,title,due,done."""''',
            '''def export_csv(tasks, path, include_done=True):
    """Write tasks as CSV with columns id,title,due,done.

    With include_done=False, finished tasks are left out.
    """'''),
        rep("tasklog/export.py", "        for t in tasks:\n",
            "        for t in tasks:\n            if t.done and include_done:\n                continue\n"),
    ]),
    ("docs: export option in README", [
        app("README.md", "- Export: `export_csv(tasks, path, include_done=True)`\n"),
    ]),
], "tasklog/export.py", "if t.done and include_done:", "continue",
    "export_csv() skips finished tasks when include_done is True (the default) and keeps them when it is "
    "False: the condition is inverted; it must be `if t.done and not include_done`.",
    {"path": "tasklog/paging.py", "mode": "append", "content": '''

def last_page_items(items, per_page):
    n = len(items) // per_page
    return items[n * per_page - 1:]
'''})

# 10 off-by-one in a loop --------------------------------------------------
case("t3-10-retry-hook", "retry-hook", [
    ("feat(retry): on_error callback", [
        rep("tasklog/retry.py", '''def retry(fn, attempts=3, exceptions=(OSError,)):
    """Call `fn()` up to `attempts` times; re-raise the last error."""
    if attempts < 1:
        raise ValueError("attempts must be >= 1")
    last = None
    for _ in range(attempts):
        try:
            return fn()
        except exceptions as exc:
            last = exc
    raise last''', '''def retry(fn, attempts=3, exceptions=(OSError,), on_error=None):
    """Call `fn()` up to `attempts` times; re-raise the last error.

    `on_error(attempt, exc)` is called after each failed attempt (1-based).
    """
    if attempts < 1:
        raise ValueError("attempts must be >= 1")
    last = None
    for attempt in range(1, attempts):
        try:
            return fn()
        except exceptions as exc:
            last = exc
            if on_error is not None:
                on_error(attempt, exc)
    raise last'''),
    ]),
], "tasklog/retry.py", "for attempt in range(1, attempts):", "for attempt in range(1, attempts):",
    "retry() loops over range(1, attempts), so fn is tried attempts-1 times; with attempts=1 it is never "
    "called and `raise last` raises None (TypeError). Must be range(1, attempts + 1).",
    {"path": "tasklog/store_v2.py", "mode": "write", "content": '''"""Next-gen store (spike)."""

import sqlite3


class StoreV2:
    def __init__(self, path):
        self.conn = sqlite3.connect(path)

    def delete(self, task_id):
        self.conn.execute("DELETE FROM tasks WHERE id = " + str(task_id))
'''})


def apply_ops(files, ops):
    for op in ops:
        path = op["path"]
        if op["op"] == "write":
            files[path] = op["content"]
        elif op["op"] == "append":
            files[path] = files[path] + op["text"]
        elif op["op"] == "replace":
            if files[path].count(op["old"]) != 1:
                raise SystemExit("replace target not unique in {}: {!r}".format(path, op["old"][:60]))
            files[path] = files[path].replace(op["old"], op["new"])


def base_files():
    return {str(p.relative_to(FIXTURE)): p.read_text() for p in FIXTURE.rglob("*")
            if p.is_file() and "__pycache__" not in p.parts}


def locate(text, needle, after=1):
    lines = text.splitlines()
    hits = [i + 1 for i, line in enumerate(lines) if needle in line and i + 1 >= after]
    if not hits:
        raise SystemExit("not found: " + needle)
    return hits[0]


if __name__ == "__main__":
    for c in CASES:
        files = base_files()
        for commit in c["commits"]:
            apply_ops(files, commit["ops"])
        p = c["planted"]
        text = files[p["file"]]
        if text.count(p["start_text"]) != 1:
            raise SystemExit("start_text not unique in {}: {}".format(c["id"], p["start_text"]))
        start = locate(text, p["start_text"])
        end = locate(text, p["end_text"], after=start)
        p["lines"] = [start, end]
        touched = {op["path"] for cm in c["commits"] for op in cm["ops"]}
        assert c["teammate"]["path"] not in touched, c["id"]
        assert (c["teammate"]["mode"] == "append") == (c["teammate"]["path"] in files), c["id"]
    out = HERE / "cases.json"
    out.write_text(json.dumps(CASES, indent=2) + "\n")
    print("wrote {} cases to {}".format(len(CASES), out))
    for c in CASES:
        print(c["id"], c["planted"]["file"], c["planted"]["lines"], c["teammate"]["path"])
