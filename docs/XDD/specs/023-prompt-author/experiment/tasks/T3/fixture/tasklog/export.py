"""Export tasks to CSV."""

import csv


def export_csv(tasks, path):
    """Write tasks as CSV with columns id,title,due,done."""
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["id", "title", "due", "done"])
        for t in tasks:
            writer.writerow([t.id, t.title, t.due.isoformat() if t.due else "", int(t.done)])
