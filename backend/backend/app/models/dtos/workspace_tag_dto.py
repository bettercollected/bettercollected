from pydantic import BaseModel


class WorkspaceTagRequest(BaseModel):
    title: str
