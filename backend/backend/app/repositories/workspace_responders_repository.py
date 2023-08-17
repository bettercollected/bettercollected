from beanie import PydanticObjectId

from backend.app.schemas.workspace_responder import (
    WorkspaceTags,
    WorkspaceResponderDocument,
)


class WorkspaceRespondersRepository:
    async def create_workspace_tag(self, workspace_id: PydanticObjectId, title: str):
        workspace_tag = await WorkspaceTags.find_one(
            {"workspace_id": workspace_id, "title": title}
        )
        if not workspace_tag:
            workspace_tag = WorkspaceTags(workspace_id=workspace_id, title=title)
        return await workspace_tag.save()

    async def get_workspace_tags(self, workspace_id: PydanticObjectId):
        return await WorkspaceTags.find({"workspace_id": workspace_id}).to_list()

    async def get_responder_by_email_and_workspace_id(
        self, workspace_id: PydanticObjectId, email: str
    ):
        workspace_responder = await WorkspaceResponderDocument.find_one(
            {"workspace_id": workspace_id, "email": email}
        )
        if not workspace_responder:
            workspace_responder = WorkspaceResponderDocument(
                workspace_id=workspace_id, email=email
            )
        return await workspace_responder.save()
