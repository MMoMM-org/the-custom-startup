"""Mechanism matrix loader for the rule-enforcer skill.

Public API:
    load(path: str) -> dict[tuple[str, str], str]
    _parse_matrix(text: str) -> dict[tuple[str, str], str]  (exposed for unit tests)

The markdown format (SDD: Mechanism Matrix File Format):
    ## Q3 = <intervention point label>
    | Q4 | Mechanism |
    |----|-----------|
    | Block     | <mechanism string> |
    | Auto-fix  | <mechanism string> |
    | Nudge     | <mechanism string> |

load() returns {} (never raises) on missing, unreadable, or malformed file — CON-4.
UnicodeDecodeError handled explicitly (lesson from T1.1, commit 8a71ce7).
"""
import re
from pathlib import Path


def load(path: str) -> dict:
    """Return {(q3_label, q4_label): mechanism} parsed from the matrix markdown.

    Returns {} if the file is missing, unreadable, or contains no parseable tables.
    Never raises — CON-4 compliance.
    """
    try:
        text = Path(path).read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError):
        return {}

    return _parse_matrix(text)


def _parse_matrix(text: str) -> dict:
    """Parse mechanism matrix markdown into a lookup dict.

    Scans for ## Q3 = <label> headings, then collects pipe-table rows
    underneath each heading until the next ## heading.
    Skips the header row (| Q4 | Mechanism |) and separator rows (| --- |).
    Returns {(q3_label, q4_label): mechanism}.
    """
    if not text.strip():
        return {}

    matrix = {}
    current_q3 = None
    q3_pattern = re.compile(r'^##\s+Q3\s*=\s*(.+)$')
    row_pattern = re.compile(r'^\|([^|]+)\|([^|]+)\|')

    for line in text.splitlines():
        stripped = line.strip()

        m = q3_pattern.match(stripped)
        if m:
            current_q3 = m.group(1).strip()
            continue

        if current_q3 is None:
            continue

        row_m = row_pattern.match(stripped)
        if not row_m:
            continue

        q4_cell = row_m.group(1).strip()
        mechanism_cell = row_m.group(2).strip()

        # Skip header row and separator row
        if q4_cell in ('Q4', '') or re.match(r'^-+$', q4_cell):
            continue

        if not q4_cell or not mechanism_cell:
            continue

        matrix[(current_q3, q4_cell)] = mechanism_cell

    return matrix
