"""Workspace authorization: one place that decides what a member may do.

Services name the permission an action needs and call ``authorize`` (raises)
or ``has_permission`` (bool); controllers and repositories never decide
access. The model is docs/enterprise-access-model.md: its workspace roles
(step b); form grants and restricted forms come later.

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
from backend.app.models.enum.workspace_roles import WorkspaceRoles, canonical_role
from backend.app.repositories.workspace_form_repository import WorkspaceFormRepository
from backend.app.repositories.workspace_repository import WorkspaceRepository
from backend.app.repositories.workspace_user_repository import WorkspaceUserRepository

P = Permission

# common.models.user.User.session_scope of a respondent-only session
RESPONDENT_SCOPE = "respondent"

ALL_PERMISSIONS: FrozenSet[Permission] = frozenset(Permission)

# docs/enterprise-access-model.md §2. Each role grants its own set and
# nothing else; a membership's permissions are the union over its roles.

# Editor (stored as COLLABORATOR): full access to forms and responses, no
# workspace settings and no privacy programme.
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

# Reviewer: reads and annotates answers (internal fields, respondent
# feedback), changes no form.
REVIEWER_PERMISSIONS: FrozenSet[Permission] = frozenset(
    {P.FORM_READ, P.RESPONSE_READ, P.RESPONSE_ANNOTATE, P.ANALYTICS_READ}
)

# Viewer: read-only forms and responses.
VIEWER_PERMISSIONS: FrozenSet[Permission] = frozenset(
    {P.FORM_READ, P.RESPONSE_READ, P.ANALYTICS_READ}
)

# Privacy officer: runs the privacy programme without reading answers. Form
# structure, deletion requests and data subjects, consent and retention,
# aggregates and the audit log; never response.read/annotate/export.
PRIVACY_OFFICER_PERMISSIONS: FrozenSet[Permission] = frozenset(
    {P.FORM_READ, P.PRIVACY_MANAGE, P.ANALYTICS_READ, P.AUDIT_READ}
)

ADMIN_PERMISSIONS: FrozenSet[Permission] = ALL_PERMISSIONS - {P.WORKSPACE_BILLING}

# What a Privacy officer never holds, even with another role beside it.
ANSWER_PERMISSIONS: FrozenSet[Permission] = frozenset(
    {P.RESPONSE_READ, P.RESPONSE_ANNOTATE, P.RESPONSE_EXPORT}
)

ROLE_PERMISSIONS: Dict[WorkspaceRoles, FrozenSet[Permission]] = {
    # everything but billing (plan, transfer, deleting the workspace)
    WorkspaceRoles.ADMIN: ADMIN_PERMISSIONS,
    WorkspaceRoles.EDITOR: EDITOR_PERMISSIONS,
    WorkspaceRoles.REVIEWER: REVIEWER_PERMISSIONS,
    WorkspaceRoles.VIEWER: VIEWER_PERMISSIONS,
    WorkspaceRoles.PRIVACY_OFFICER: PRIVACY_OFFICER_PERMISSIONS,
}

# The owner (``workspace.owner_id``) holds every permission.
OWNER_PERMISSIONS: FrozenSet[Permission] = ALL_PERMISSIONS

NO_PERMISSIONS: FrozenSet[Permission] = frozenset()

# A disabled workspace (the owner's plan was downgraded) is read-only for its
# owner: they still answer deletion requests and reach their respondents'
# data (GDPR), but change nothing else. Other members get nothing.
DISABLED_WORKSPACE_OWNER_PERMISSIONS: FrozenSet[Permission] = frozenset(
    {
        P.FORM_READ,
        P.RESPONSE_READ,
        P.RESPONSE_EXPORT,
        P.RESPONSE_DELETE,
        P.PRIVACY_MANAGE,
        P.ANALYTICS_READ,
    }
)


def role_permissions(role) -> FrozenSet[Permission]:
    """What one stored role grants: ``COLLABORATOR`` is the Editor, a role
    this code doesn't know grants nothing."""
    known = canonical_role(role)
    return ROLE_PERMISSIONS.get(known, NO_PERMISSIONS) if known else NO_PERMISSIONS


def permissions_for(roles: Optional[Iterable], is_owner: bool) -> FrozenSet[Permission]:
    """The permissions of an active membership with ``roles``.

    An empty role list is a membership from before roles existed (the schema
    default); it has always had full content access, so it stays an Editor.
    """
    if is_owner:
        return OWNER_PERMISSIONS
    if not roles:
        return EDITOR_PERMISSIONS
    granted = set()
    for role in roles:
        granted |= role_permissions(role)
    if WorkspaceRoles.PRIVACY_OFFICER in {
        canonical_role(role) for role in roles
    }:
        # "Never reads answers" holds whatever else the membership holds.
        granted -= ANSWER_PERMISSIONS
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
        membership (a disabled one counts as none) or in a missing workspace;
        in a disabled workspace only its owner keeps read and privacy
        permissions."""
        workspace_oid = _object_id(workspace_id)
        user_oid = _object_id(user.id) if user else None
        if workspace_oid is None or user_oid is None:
            return NO_PERMISSIONS
        if getattr(user, "session_scope", None) == RESPONDENT_SCOPE:
            # a respondent-scoped session (an email code for an address whose
            # domain requires SSO elsewhere) only answers forms: it holds no
            # workspace permission anywhere, the user's own workspaces included
            return NO_PERMISSIONS
        membership = await self._workspace_user_repo.find_workspace_user(
            workspace_oid, user_oid
        )
        if membership is None or membership.disabled:
            return NO_PERMISSIONS
        workspace = await self._workspace_repo.find_by_id(workspace_oid)
        if workspace is None:
            return NO_PERMISSIONS
        is_owner = str(workspace.owner_id) == str(user_oid)
        if workspace.disabled:
            return DISABLED_WORKSPACE_OWNER_PERMISSIONS if is_owner else NO_PERMISSIONS
        return permissions_for(membership.roles, is_owner=is_owner)

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

    async def is_owner(
        self, user: Optional[User], workspace_id: Union[PydanticObjectId, str, None]
    ) -> bool:
        """Whether ``user`` is the owner of an available workspace, with a
        full (not respondent-scoped) session and an active membership."""
        perms = await self.effective_permissions(user, workspace_id)
        if perms != OWNER_PERMISSIONS:
            return False
        workspace = await self._workspace_repo.find_by_id(_object_id(workspace_id))
        return workspace is not None and str(workspace.owner_id) == str(user.id)

    async def require_owner(
        self,
        user: Optional[User],
        workspace_id: Union[PydanticObjectId, str, None],
        message: str = MESSAGE_FORBIDDEN,
    ) -> None:
        """403 unless ``user`` owns the workspace. For decisions no role may
        take, like single sign-on configuration: it controls every account on
        the workspace's verified domains, the owner's own included."""
        if not await self.is_owner(user, workspace_id):
            raise HTTPException(status_code=HTTPStatus.FORBIDDEN, content=message)

    async def _form_in_workspace(self, workspace_id, form_id) -> bool:
        return bool(
            await self._workspace_form_repo.find_workspace_form(
                _object_id(workspace_id), str(form_id)
            )
        )
