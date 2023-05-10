import enum
from typing import Optional

from pydantic import BaseModel


class SortOrder(str, enum.Enum):
    ASCENDING = "ASCENDING"
    DESCENDING = "DESCENDING"


class SortRequest(BaseModel):
    sort_by: Optional[str] = "created_at"
    sort_order: Optional[str] = SortOrder.DESCENDING
