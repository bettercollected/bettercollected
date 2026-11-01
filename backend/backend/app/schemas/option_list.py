"""A workspace's option list (``services/option_lists``): a name, an order and
items, each an id the server made, a label and an optional group key. Reference
data the workspace maintains; no answer and no personal data of respondents."""

from typing import List, Literal, Optional

from common.records import Record, RecordId
from pydantic import BaseModel, Field


class OptionListItem(BaseModel):
    id: str = Field(..., min_length=1, max_length=64)
    label: str = Field(..., min_length=1, max_length=200)
    # the parent key a dependent list is filtered by; never shown to respondents
    group: Optional[str] = Field(None, max_length=200)


class OptionListDocument(Record):
    workspace_id: RecordId
    name: str
    # the folded name: a name is unique per workspace (revision 0031)
    name_key: str
    order: Literal["manual", "alphabetical"] = "manual"
    items: List[OptionListItem] = []
    # one more on every write: the cache token and the editor's concurrency check
    revision: int = 1
    created_by: Optional[str] = None
    updated_by: Optional[str] = None

    class Settings:
        name = "workspace_option_lists"
