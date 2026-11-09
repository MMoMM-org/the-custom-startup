"""JSON configuration with defaults."""

import json

DEFAULTS = {"db_path": "tasks.db", "per_page": 20, "retries": 3}


def load_config(path):
    """Read a JSON object from `path` and merge it over DEFAULTS.

    Raises ValueError if the file is not a JSON object.
    """
    with open(path, encoding="utf-8") as fh:
        try:
            data = json.load(fh)
        except json.JSONDecodeError as exc:
            raise ValueError("invalid config {}: {}".format(path, exc))
    if not isinstance(data, dict):
        raise ValueError("config must be a JSON object")
    merged = dict(DEFAULTS)
    merged.update(data)
    return merged
