"""Retry a flaky call a fixed number of times."""


def retry(fn, attempts=3, exceptions=(OSError,)):
    """Call `fn()` up to `attempts` times; re-raise the last error."""
    if attempts < 1:
        raise ValueError("attempts must be >= 1")
    last = None
    for _ in range(attempts):
        try:
            return fn()
        except exceptions as exc:
            last = exc
    raise last
