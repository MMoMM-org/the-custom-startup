"""Pagination helpers. Pages are 1-based."""


def page_count(n_items, per_page):
    """Number of pages needed to show `n_items` items, `per_page` at a time."""
    if per_page <= 0:
        raise ValueError("per_page must be > 0")
    return -(-n_items // per_page)


def paginate(items, page, per_page):
    """Return the items on 1-based `page`."""
    if page < 1:
        raise ValueError("page must be >= 1")
    start = (page - 1) * per_page
    return items[start:start + per_page]
