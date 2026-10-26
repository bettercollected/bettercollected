from typing import Dict, List, Optional

from common.ids import RecordId
from pydantic import BaseModel


class ResponderGroupDto(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    regex: Optional[str] = None
    emails: Optional[List[str]] = None
    forms: Optional[List] = None

    def __init__(self, _id: RecordId = None, id=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.id = str(_id) if _id else id
