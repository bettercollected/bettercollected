"""Workspace authorization: one place that decides what a member may do.

Services name the permission an action needs and call ``authorize`` (raises)
or ``has_permission`` (bool); controllers and repositories never decide
access. The model is docs/enterprise-access-model.md. This is its first step:
the roles that exist today, with today's semantics.

Respondent-facing paths (a submitter's own submission, receipts, "my
submissions", deletion requests by the submitter) authorise by the
submitter's identity, not through here. Platform admin (``get_logged_admin``)
is separate as well.
"""

from http import HTTPStatus
from typing import Dict, FrozenSet, Iterable, Optional, Union

from beanie import PydanticObjectId
from bson import ObjectId
from common.constants import MESSAGE_FORBIDDEN
from common.models.user import User

from backend.app.exceptions import HTTPException
from backend.app.models.enum.permission import Permission
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.app.repositories.workspace_form_repository import WorkspaceFormRepository
from backend.app.repositories.workspace_repository import WorkspaceRepository
from backend.app.repositories.workspace_user_repository import WorkspaceUserRepository

P = Permission

ALL_PERMISSIONS: FrozenSet[Permission] = frozenset(Permission)

# The doc's Editor (today's COLLABORATOR): full access to forms and responses.
EDITOR_PERMISSIONS: FrozenSet[Permission] = frozenset(
    {
        P.FORM_CREATE,
        P.FORM_READ,
        P.FORM_EDIT,
        P.FORM_DELETE,
        P.FORM_SHARE,
        P.RESPONSE_READ,
        P.RESPONSE_ANNOTATE,
        P.RESPONSE_EXPORT,
        P.RESPONSE_DELETE,
        P.ANALYTICS_READ,
    }
)

# What every active membership grants today, whatever its roles (including
# none): the Editor's permissions plus privacy.manage. Collaborators handle
# deletion requests, the responders list and the consent catalog today; the
# doc's Editor does not. Dropping it is a behaviour change that belongs with
# the new roles (step b), not to this step.
MEMBER_PERMISSIONS: FrozenSet[Permission] = EDITOR_PERMISSIONS | {P.PRIVACY_MANAGE}

ROLE_PERMISSIONS: Dict[WorkspaceRoles, FrozenSet[Permission]] = {
    # everything but billing (plan, transfer, deleting the workspace)
    WorkspaceRoles.ADMIN: ALL_PERMISSIONS - {P.WORKSPACE_BILLING},
    WorkspaceRoles.COLLABORATOR: MEMBER_PERMISSIONS,
}

# The owner (``workspace.owner_id``) holds every permission.
OWNER_PERMISSIONS: FrozenSet[Permission] = ALL_PERMISSIONS

NO_PERMISSIONS: FrozenSet[Permission] = frozenset()


def permissions_for(roles: Iterable, is_owner: bool) -> FrozenSet[Permission]:
    """The permissions of an active membership with ``roles``."""
    if is_owner:
        return OWNER_PERMISSIONS
    granted = set(MEMBER_PERMISSIONS)
    for role in roles or []:
        try:
            granted |= ROLE_PERMISSIONS.get(WorkspaceRoles(role), NO_PERMISSIONS)
        except ValueError:  # a role this code doesn't know grants nothing more
            continue
    return frozenset(granted)


def _object_id(value) -> Optional[PydanticObjectId]:
    if value is None or not ObjectId.is_valid(str(value)):
        return None
    return PydanticObjectId(str(value))


class AuthorizationService:
    def __init__(
        self,
        workspace_repo: WorkspaceRepository,
        workspace_user_repo: WorkspaceUserRepository,
        workspace_form_repo: WorkspaceFormRepository,
    ):
        self._workspace_repo = workspace_repo
        self._workspace_user_repo = workspace_user_repo
        self._workspace_form_repo = workspace_form_repo

    async def effective_permissions(
        self, user: Optional[User], workspace_id: Union[PydanticObjectId, str, None]
    ) -> FrozenSet[Permission]:
        """What ``user`` may do in the workspace. Nothing without an active
        membership (a disabled one counts as none) or in a disabled or
        missing workspace."""
        workspace_oid = _object_id(workspace_id)
        user_oid = _object_id(user.id) if user else None
        if workspace_oid is None or user_oid is None:
            return NO_PERMISSIONS
        membership = await self._workspace_user_repo.find_workspace_user(
            workspace_oid, user_oid
        )
        if membership is None or membership.disabled:
            return NO_PERMISSIONS
        workspace = await self._workspace_repo.find_by_id(workspace_oid)
        if workspace is None or workspace.disabled:
            return NO_PERMISSIONS
        return permissions_for(
            membership.roles, is_owner=str(workspace.owner_id) == str(user_oid)
        )

    async def has_permission(
        self,
        user: Optional[User],
        permission: Permission,
        workspace_id: Union[PydanticObjectId, str, None],
        form_id: Optional[str] = None,
    ) -> bool:
        """Whether ``user`` holds ``permission`` in the workspace (and, with
        ``form_id``, the form belongs to it)."""
        if permission not in await self.effective_permissions(user, workspace_id):
            return False
        if form_id is not None:
            return await self._form_in_workspace(workspace_id, form_id)
        return True

    async def authorize(
        self,
        user: Optional[User],
        permission: Permission,
        workspace_id: Union[PydanticObjectId, str, None],
        form_id: Optional[str] = None,
        message: str = MESSAGE_FORBIDDEN,
    ) -> None:
        """403 unless ``user`` holds ``permission`` in the workspace; then,
        with ``form_id``, 404 unless the form belongs to the workspace (so
        only someone allowed in learns whether a form exists)."""
        if permission not in await self.effective_permissions(user, workspace_id):
            raise HTTPException(status_code=HTTPStatus.FORBIDDEN, content=message)
        if form_id is not None and not await self._form_in_workspace(
            workspace_id, form_id
        ):
            raise HTTPException(HTTPStatus.NOT_FOUND, "Form not found in workspace")

    async def _form_in_workspace(self, workspace_id, form_id) -> bool:
        return bool(
            await self._workspace_form_repo.find_workspace_form(
                _object_id(workspace_id), str(form_id)
            )
        )
