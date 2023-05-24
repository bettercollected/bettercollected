from typing import Optional, List, Dict

from beanie import PydanticObjectId
from fastapi_camelcase import CamelModel
from pydantic import BaseModel


class WorkspaceResponderPatchDto(BaseModel):
    tags: Optional[List[PydanticObjectId]]
    metadata: Optional[Dict[str, str]]


class WorkspaceTagsResponse(BaseModel):
    title: str
    id: Optional[PydanticObjectId]

    def __init__(self, _id=None, *args, **kwargs):
        super().__init__(**kwargs)
        if _id:
            self.id = PydanticObjectId(_id)


class WorkspaceResponderResponse(CamelModel):
    responses: int
    email: str
    deletion_requests: int
    tags: Optional[List[WorkspaceTagsResponse]]
    metadata: Optional[Dict[str, str]]
