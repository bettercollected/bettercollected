"""How to reach page N of a sorted list without counting every row before it.

Three ways, each a seek on the sort index followed by a skip of a few rows:

- ``cursor``: from the first row of a page the client already has (its
  cursor): the next, the previous or a nearby page costs a skip of at most
  ``MAX_CURSOR_PAGES`` pages, at any depth of the list;
- ``start``: from the first row, for the first pages and for a link that has
  no cursor (a skip of at most ``MAX_OFFSET`` rows);
- ``end``: from the last row, scanning backwards, when the total is exact:
  the last page and the pages near it.

The cheapest that applies is used; when none does, the page is too deep to
reach without a cursor (the caller says so, and the client goes to the first
page).
"""

from dataclasses import dataclass
from typing import Literal, Optional

from backend.app.models.filter_queries.response_list import (
    MAX_CURSOR_PAGES,
    MAX_OFFSET,
)


@dataclass(frozen=True)
class Seek:
    source: Literal["start", "end", "cursor"]
    # scan against the sort order (the rows come back reversed)
    reverse: bool
    # rows to skip after the seek
    offset: int
    # rows to read: a page, plus one to learn that another follows
    limit: int
    # keyset condition on the anchor row: None, "inclusive" or "exclusive"
    anchor: Optional[str]
    # a page past the last row (no query is needed)
    empty: bool = False


class PageTooDeep(ValueError):
    """The page is farther than any seek reaches without a usable cursor."""


def plan(
    page: int,
    size: int,
    total: int,
    total_exact: bool,
    anchor_page: Optional[int],
) -> Seek:
    """The cheapest seek to ``page`` (1-based) of pages of ``size`` rows.

    ``total`` is the (possibly capped) row count, exact when ``total_exact``;
    ``anchor_page`` is the page number of a valid cursor, if one was sent.
    """
    candidates = []
    if anchor_page is not None and abs(page - anchor_page) <= MAX_CURSOR_PAGES:
        if page >= anchor_page:
            candidates.append(
                Seek(
                    "cursor", False, (page - anchor_page) * size, size + 1, "inclusive"
                )
            )
        else:
            # rows before the anchor, nearest first: this page's last row is
            # (anchor_page - 1 - page) pages back
            candidates.append(
                Seek("cursor", True, (anchor_page - 1 - page) * size, size, "exclusive")
            )
    start_offset = (page - 1) * size
    if start_offset <= MAX_OFFSET:
        candidates.append(Seek("start", False, start_offset, size + 1, None))
    if total_exact:
        in_page = min(page * size, total) - start_offset
        if in_page <= 0:
            # past the last row: nothing to read, whatever the other seeks cost
            return Seek("end", True, 0, 0, None, empty=True)
        end_offset = total - min(page * size, total)
        if end_offset <= MAX_OFFSET:
            candidates.append(Seek("end", True, end_offset, in_page, None))
    if not candidates:
        raise PageTooDeep()
    # cheapest skip first; on a tie the order above (cursor, start, end) stands
    return min(candidates, key=lambda seek: seek.offset)
