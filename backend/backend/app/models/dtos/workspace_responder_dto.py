from typing import Optional, List, Dict

from common.ids import RecordId
from fastapi_camelcase import CamelModel
from pydantic import BaseModel


class WorkspaceResponderPatchDto(BaseModel):
    tags: Optional[List[RecordId]] = None
    metadata: Optional[Dict[str, str]] = None


class WorkspaceTagsResponse(BaseModel):
    title: str
    id: Optional[RecordId] = None

    def __init__(self, _id=None, *args, **kwargs):
        super().__init__(**kwargs)
        if _id:
            self.id = RecordId(_id)


class WorkspaceResponderResponse(CamelModel):
    responses: int
    email: str
    deletion_requests: int
    tags: Optional[List[WorkspaceTagsResponse]] = None
    metadata: Optional[Dict[str, str]] = None
