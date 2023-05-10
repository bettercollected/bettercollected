import enum
from typing import Optional

from pydantic import BaseModel


class SortOrder(str, enum.Enum):
    ASCENDING = "ASCENDING"
    DESCENDING = "DESCENDING"


class SortRequest(BaseModel):
    sort_by: Optional[str]
    sort_order: Optional[str] = SortOrder.ASCENDING
