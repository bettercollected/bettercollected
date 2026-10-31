from typing import Generic, Optional, TypeVar

from fastapi_pagination import Page
from pydantic import ConfigDict, Field

T = TypeVar("T")


class ResponseListPage(Page[T], Generic[T]):
    """A page of the form's responses list: the usual page object plus what
    the keyset engine knows. ``total`` is exact while ``totalExact`` is true;
    otherwise it is the cap (a lower bound, the list says "10,000+")."""

    model_config = ConfigDict(populate_by_name=True)

    total_exact: bool = Field(default=True, alias="totalExact")
    has_next: bool = Field(default=False, alias="hasNext")
    # signed handle on where this page begins: send it back with a request
    # for a page near this one (``cursor``); None when it cannot be issued
    cursor: Optional[str] = None
