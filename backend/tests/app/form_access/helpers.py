"""Builders shared by the form-access tests. Everything here is synthetic."""

from common.ids import RecordId
from common.models.standard_form import StandardForm
from common.models.user import User

from backend.app.container import container
from backend.app.schemas.form_access_grant import FormAccessGrantDocument
from backend.app.schemas.member_group import MemberGroupDocument
from backend.app.schemas.workspace_user import WorkspaceUserDocument
from backend.app.services.form_access.model import MODE_RESTRICTED
from tests.app.controllers.data import formData


async def add_member(workspace, *roles, disabled=False) -> User:
    """A member of the workspace holding ``roles`` (stored spellings)."""
    user = User(id=str(RecordId()), sub=f"{RecordId()}@example.org")
    await container.workspace_user_repo().save(
        WorkspaceUserDocument(
            workspace_id=workspace.id,
            user_id=user.id,
            roles=list(roles),
            disabled=disabled,
        )
    )
    return user


async def create_form(workspace, creator: User):
    """A form created by ``creator`` (the workspace link's ``user_id``)."""
    return await container.workspace_form_service().create_form(
        workspace.id, StandardForm(**formData), creator
    )


async def set_mode(workspace, form_id, mode=None, hidden=None):
    """Write the link's access mode / hidden flag straight to the row."""
    repo = container.workspace_form_repo()
    link = await repo.find_workspace_form(workspace.id, str(form_id))
    if mode is not None:
        link.settings.access_mode = mode
    if hidden is not None:
        link.settings.hidden = hidden
    await repo.save(link)


async def restrict(workspace, form_id):
    await set_mode(workspace, form_id, MODE_RESTRICTED)


async def grant(
    workspace, form_id, subject_id, role, export=False, subject_type="user", workspace_id=None
):
    return await container.form_access_grant_repo().put(
        FormAccessGrantDocument(
            workspace_id=workspace_id or workspace.id,
            form_id=str(form_id),
            subject_type=subject_type,
            subject_id=str(subject_id),
            role=role,
            export=export,
        )
    )


async def team_with(workspace, *users, name="Team") -> MemberGroupDocument:
    repo = container.member_group_repo()
    team = await repo.save(MemberGroupDocument(workspace_id=workspace.id, name=name))
    for user in users:
        await repo.add_member(workspace.id, team.id, user.id)
    return team
