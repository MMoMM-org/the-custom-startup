"""Runtime configuration read from the environment."""

import os

ENV_VAR = "LEDGERLITE_HOME"


def home():
    value = os.environ.get(ENV_VAR)
    if not value:
        raise RuntimeError(ENV_VAR + " is not set")
    return value


def default_ledger():
    return os.path.join(home(), "ledger.csv")
