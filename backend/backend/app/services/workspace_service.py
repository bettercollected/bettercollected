from backend.app.schemas.workspace import WorkspaceDocument
from backend.app.schemas.workspace_user import WorkspaceUserDocument
from common.models.user import User


async def create_workspace(user: User):
    workspace = await WorkspaceDocument.find_one({"owner_id": user.id, "default": True})
    if not workspace:
        workspace = WorkspaceDocument(
            title="Untitled",
            description="",
            owner_id=user.id,
            default=True,
            workspace_name=str(user.id),
            custom_domain=None,
        )
        await workspace.save()
        workspace_user = WorkspaceUserDocument(workspace_id=workspace.id, user_id=user.id)
        await workspace_user.save()
