from backend.app.schemas.workspace import WorkspaceDocument
from backend.app.schemas.workspace_user import WorkspaceUserDocument
from common.models.user import User


async def create_workspace(user: User):
    workspace = await WorkspaceDocument.find_one({"ownerId": user.id, "default": True})
    if not workspace:
        workspace = WorkspaceDocument(
            title="Untitled",
            description="",
            ownerId=user.id,
            default=True,
            workspaceName=str(user.id),
            customDomain=None,
        )
        await workspace.save()
        workspace_user = WorkspaceUserDocument(workspaceId=workspace.id, userId=user.id)
        await workspace_user.save()
