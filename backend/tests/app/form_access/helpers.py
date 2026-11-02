"""Builders shared by the form-access tests. Everything here is synthetic."""

from common.ids import RecordId
from common.records import derived_id
from common.models.standard_form import StandardForm
from common.models.user import User

from backend.app.container import container
from backend.app.schemas.form_access_grant import FormAccessGrantDocument
from backend.app.schemas.member_group import MemberGroupDocument
from backend.app.schemas.workspace_user import WorkspaceUserDocument
from backend.app.services.form_access.model import MODE_RESTRICTED
from tests.app.auth_helpers import access_token
from tests.app.controllers.data import formData


def cookies(user: User) -> dict:
    token = access_token(user)
    return {"Authorization": token, "RefreshToken": token}


def api(workspace) -> str:
    return f"/api/v1/workspaces/{workspace.id}"


async def audit_events(workspace, *events):
    """The workspace's audit rows of these kinds, oldest first."""
    rows = await container.workspace_audit_repo().page(
        workspace.id, 200, events=events or None
    )
    return list(reversed(rows))


def fail_audit(monkeypatch):
    """The audit log cannot be written."""

    async def refuse(document):
        raise RuntimeError("audit store down")

    async def refuse_many(documents):
        raise RuntimeError("audit store down")

    monkeypatch.setattr(container.workspace_audit_repo(), "record", refuse)
    monkeypatch.setattr(container.workspace_audit_repo(), "record_many", refuse_many)


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
    if mode is not None:
        # the one writer of the mode: a save keeps the stored one
        await repo.set_access_mode(workspace.id, str(form_id), mode)
    if hidden is not None:
        link = await repo.find_workspace_form(workspace.id, str(form_id))
        link.settings.hidden = hidden
        await repo.save(link)


async def restrict(workspace, form_id):
    await set_mode(workspace, form_id, MODE_RESTRICTED)


async def grant(
    workspace, form_id, subject_id, role, export=False, subject_type="user", workspace_id=None
):
    """Store a grant row as it is, without the checks ``put`` makes (the
    decision tests need rows that name a stranger, another workspace's team or
    a key). ``put`` itself is tested in ``test_write_checks.py``."""
    repo = container.form_access_grant_repo()
    document = FormAccessGrantDocument(
        workspace_id=workspace_id or workspace.id,
        form_id=str(form_id),
        subject_type=subject_type,
        subject_id=str(subject_id),
        role=role,
        export=export,
    )
    document.id = derived_id(
        "form_access_grant",
        document.workspace_id,
        document.form_id,
        document.subject_type,
        document.subject_id,
    )
    return await repo.save_document(document)


async def team_with(workspace, *users, name="Team") -> MemberGroupDocument:
    repo = container.member_group_repo()
    team = await repo.save(MemberGroupDocument(workspace_id=workspace.id, name=name))
    for user in users:
        await repo.add_member(workspace.id, team.id, user.id)
    return team
