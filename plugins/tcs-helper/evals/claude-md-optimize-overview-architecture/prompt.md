---
description: Optimize a CLAUDE.md that repeats the README architecture overview; the report must not reward the copy and must propose removing it.
tags: [memory-claude-md-optimize, scoring, instruction-files, spec-023]
runs: 3
max_turns: 40
timeout_seconds: 1200
allowed_tools: [Read, Glob, Grep, Write, Edit]
expected_outcome: claude-md-optimization/OPTIMIZATION-REPORT.md exists, its score gives no credit for the content CLAUDE.md copies from README.md and the code, and it proposes removing that content.
---

/tcs-helper:memory-claude-md-optimize --scope repo

Optimize the repo-level CLAUDE.md of a small project. The current working directory is empty, so
first create the project by writing each file below with exactly the content shown, at the path
shown, relative to the current working directory.

`README.md`:

````markdown
# tally

tally counts events in JSON-lines log files and prints a total per event name.

## Architecture

tally has three modules. `tally/cli.py` parses the command line and calls the parser.
`tally/parser.py` reads the log file line by line and yields one `Event` per JSON object.
`tally/store.py` adds the events up in a dict and, with `--snapshot`, writes the totals to the
SQLite file `tally.db`. Data flows cli -> parser -> store -> stdout.

## Layout

```
tally/
  __init__.py
  cli.py        command line entry point
  parser.py     JSON-lines reader
  store.py      counting and SQLite snapshot
tests/
  test_parser.py
pyproject.toml
```

## Tech stack

- Python 3.12
- click for the command line
- sqlite3 from the standard library for snapshots
- pytest for tests, ruff for linting

## Setup

1. `python3 -m venv .venv`
2. `source .venv/bin/activate`
3. `pip install -e '.[dev]'`
4. `tally count logs/app.jsonl`
````

`CLAUDE.md`:

```markdown
# tally

## Architecture overview

tally is split into three modules:

- `tally/cli.py` is the click entry point; it parses arguments and hands the file to the parser.
- `tally/parser.py` reads the JSON-lines file and yields an `Event` for each line.
- `tally/store.py` counts events per name in a dict and can write a SQLite snapshot to `tally.db`.

Data flows from the CLI through the parser into the store, and the totals go to stdout.

## Before committing

- Run `ruff check . && pytest -q` before every commit; the pre-push hook on the server rejects a push
  whose tests fail.
```

`pyproject.toml`:

```toml
[project]
name = "tally"
version = "0.3.0"
requires-python = ">=3.12"
dependencies = ["click>=8.1"]

[project.optional-dependencies]
dev = ["pytest>=8", "ruff>=0.6"]

[project.scripts]
tally = "tally.cli:main"
```

`tally/__init__.py`:

```python
"""tally: count events in JSON-lines logs."""
```

`tally/cli.py`:

```python
import click

from tally.parser import read_events
from tally.store import Store


@click.group()
def main():
    """Count events in JSON-lines log files."""


@main.command()
@click.argument("path")
@click.option("--snapshot", is_flag=True, help="Write the totals to tally.db.")
def count(path, snapshot):
    store = Store()
    for event in read_events(path):
        store.add(event)
    for name, total in sorted(store.totals.items()):
        click.echo(f"{name}\t{total}")
    if snapshot:
        store.write_snapshot("tally.db")
```

`tally/parser.py`:

```python
import json
from dataclasses import dataclass


@dataclass
class Event:
    name: str
    timestamp: str


def read_events(path):
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                record = json.loads(line)
                yield Event(record["event"], record["ts"])
```

`tally/store.py`:

```python
import sqlite3
from collections import Counter


class Store:
    def __init__(self):
        self.totals = Counter()

    def add(self, event):
        self.totals[event.name] += 1

    def write_snapshot(self, db_path):
        with sqlite3.connect(db_path) as db:
            db.execute("CREATE TABLE IF NOT EXISTS totals (event TEXT PRIMARY KEY, n INTEGER)")
            db.executemany("INSERT OR REPLACE INTO totals VALUES (?, ?)", self.totals.items())
```

`tests/test_parser.py`:

```python
from tally.parser import read_events


def test_reads_one_event_per_line(tmp_path):
    log = tmp_path / "app.jsonl"
    log.write_text('{"event": "login", "ts": "t1"}\n{"event": "logout", "ts": "t2"}\n')
    assert [e.name for e in read_events(log)] == ["login", "logout"]
```

Then run the optimization on that repository with scope `repo` only; ignore any global or project
CLAUDE.md outside the working directory. Write the proposal, not the applied change: create the
`claude-md-optimization/` proposal directory, with the report at `claude-md-optimization/OPTIMIZATION-REPORT.md`, and stop
before the apply step. Do not modify `CLAUDE.md` itself. In the report's Quality Scores section,
give the six criterion scores for `CLAUDE.md`, each with one line on what earned it.

I am not available for questions: decide anything I left open yourself and say what you decided in
your reply. Give me a short summary at the end.
