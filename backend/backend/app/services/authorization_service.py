"""Workspace authorization: one place that decides what a member may do.

Services name the permission an action needs and call ``authorize`` (raises)
or ``has_permission`` (bool); controllers and repositories never decide
access. The model is docs/enterprise-access-model.md: its workspace roles
(step b); form grants and restricted forms (step c, behind
``FORM_ACCESS_ENABLED``) are combined with them by ``services/form_access``
wherever a form id is passed.

Respondent-facing paths (a submitter's own submission, receipts, "my
submissions", deletion requests by the submitter) authorise by the
submitter's identity, not through here. Platform admin (``get_logged_admin``)
is separate as well.
"""

from http import HTTPStatus
from typing import Callable, Dict, FrozenSet, Iterable, Optional, Union

from common.records import RecordId
from bson import ObjectId
from common.constants import MESSAGE_FORBIDDEN
from common.models.user import User

from backend.app.repositories.postgres.forms import (
    PostgresWorkspaceFormRepository,
)
from backend.app.exceptions import HTTPException
from backend.app.services.form_access.mode import form_access_enabled
from backend.app.services.form_access.model import (
    BaseAccess,
    FormPermissions,
)
from backend.app.services.form_access.service import FormAccessService
from backend.app.services.mfa.policy import (
    blocks_session as totp_blocks,
    mfa_required_error,
)
from backend.app.models.enum.permission import Permission
from backend.app.models.enum.workspace_roles import (
    WorkspaceRoles,
    canonical_role,
    has_owner_role,
    is_owner_membership,
)
from backend.app.repositories.postgres.identity import (
    PostgresWorkspaceRepository,
    PostgresWorkspaceUserRepository,
)

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
        P.RESPONSE_EDIT,
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
    {P.RESPONSE_READ, P.RESPONSE_ANNOTATE, P.RESPONSE_EXPORT, P.RESPONSE_EDIT}
)

# Every owner holds every permission: the billing owner (``owner_id``) and
# each member with role OWNER alike.
OWNER_PERMISSIONS: FrozenSet[Permission] = ALL_PERMISSIONS

ROLE_PERMISSIONS: Dict[WorkspaceRoles, FrozenSet[Permission]] = {
    WorkspaceRoles.OWNER: OWNER_PERMISSIONS,
    # everything but billing (plan, transfer, deleting the workspace)
    WorkspaceRoles.ADMIN: ADMIN_PERMISSIONS,
    WorkspaceRoles.EDITOR: EDITOR_PERMISSIONS,
    WorkspaceRoles.REVIEWER: REVIEWER_PERMISSIONS,
    WorkspaceRoles.VIEWER: VIEWER_PERMISSIONS,
    WorkspaceRoles.PRIVACY_OFFICER: PRIVACY_OFFICER_PERMISSIONS,
}

NO_PERMISSIONS: FrozenSet[Permission] = frozenset()

# A disabled workspace (the billing owner's plan was downgraded) is read-only
# for its owners: they still answer deletion requests and reach their
# respondents' data (GDPR), but change nothing else. Other members get
# nothing.
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
    if is_owner or has_owner_role(roles):
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


def _object_id(value) -> Optional[RecordId]:
    if value is None or not ObjectId.is_valid(str(value)):
        return None
    return RecordId(str(value))


class AuthorizationService:
    def __init__(
        self,
        workspace_repo: PostgresWorkspaceRepository,
        workspace_user_repo: PostgresWorkspaceUserRepository,
        workspace_form_repo: PostgresWorkspaceFormRepository,
        sso_policy: Callable[[], object],
        form_access: Optional[FormAccessService] = None,
    ):
        self._workspace_repo = workspace_repo
        self._workspace_user_repo = workspace_user_repo
        self._workspace_form_repo = workspace_form_repo
        # Form grants and restricted forms (FORM_ACCESS_ENABLED). Only read
        # while that switch is on, and then required: a service built without
        # it must not silently skip a restricted form.
        self._form_access = form_access
        # Returns the SsoPolicyService, resolved per call: the policy depends
        # on services that depend on this one (the container wires it late).
        # Required: a service built without it must not silently skip the
        # single sign-on check.
        self._sso_policy = sso_policy

    async def effective_permissions(
        self,
        user: Optional[User],
        workspace_id: Union[RecordId, str, None],
        raise_sso_required: bool = False,
        form_id: Optional[str] = None,
    ) -> FrozenSet[Permission]:
        """What ``user`` may do in the workspace. Nothing without an active
        membership (a disabled one counts as none) or in a missing workspace;
        in a disabled workspace only its owners keep read and privacy
        permissions.

        Nothing either for a session that does not meet the workspace's
        single sign-on requirement (docs/sso.md, the rule the token refresh
        applies, here on every request): with ``raise_sso_required`` the
        403 ``sso_required`` the webapp reacts to, otherwise just no
        permissions. A workspace that requires an authenticator app
        (``services/mfa/policy.py``) is the same rule with 403
        ``mfa_required``.

        With ``form_id`` and while ``FORM_ACCESS_ENABLED`` is on: what the
        user may do on that form (grants and the form's access mode applied
        to the above); otherwise the workspace-level answer, unchanged."""
        base = await self._base_access(user, workspace_id, raise_sso_required)
        if form_id is None or not form_access_enabled():
            return base.permissions
        return (await self._form_permissions(base, form_id)).permissions

    async def form_permissions(
        self,
        user: Optional[User],
        workspace_id: Union[RecordId, str, None],
        form_id: Optional[str],
        raise_sso_required: bool = False,
    ) -> FormPermissions:
        """``user``'s permissions on one form and where they come from (their
        role, a grant, being the creator), for the payloads that tell the
        webapp. With the switch off it is the workspace-level answer."""
        base = await self._base_access(user, workspace_id, raise_sso_required)
        if form_id is None or not form_access_enabled():
            return FormPermissions(base.permissions)
        return await self._form_permissions(base, form_id)

    async def visible_form_ids(
        self,
        user: Optional[User],
        workspace_id: Union[RecordId, str, None],
        permission: Permission,
        form_ids: Optional[Iterable[str]] = None,
    ) -> Optional[FrozenSet[str]]:
        """The ids of the workspace's forms (of ``form_ids`` when given) on
        which ``user`` holds ``permission``; ``None`` means every form (the
        switch is off, or an Owner or Admin holds it). For a list that must not
        name a form its reader may not open: filter before counting or
        searching."""
        base = await self._base_access(user, workspace_id)
        return await self._required_form_access().visible_ids(
            base, permission, form_ids
        )

    async def _form_permissions(self, base: BaseAccess, form_id) -> FormPermissions:
        return await self._required_form_access().permissions_on(base, str(form_id))

    def _required_form_access(self) -> FormAccessService:
        if self._form_access is None:
            # fail closed: never allow because the resolver is not wired
            raise RuntimeError("AuthorizationService: form access is not wired")
        return self._form_access

    async def _base_access(
        self,
        user: Optional[User],
        workspace_id: Union[RecordId, str, None],
        raise_sso_required: bool = False,
    ) -> BaseAccess:
        """The workspace-level decision (every rule but the form's), with what
        the form-level one needs to know about the member."""
        workspace_oid = _object_id(workspace_id)
        user_oid = _object_id(user.id) if user else None
        nobody = BaseAccess(
            user_id=str(user_oid or ""),
            workspace_id=str(workspace_oid or ""),
            permissions=NO_PERMISSIONS,
        )
        if workspace_oid is None or user_oid is None:
            return nobody
        if getattr(user, "session_scope", None) == RESPONDENT_SCOPE:
            # a respondent-scoped session (an email code for an address whose
            # domain requires SSO elsewhere) only answers forms: it holds no
            # workspace permission anywhere, the user's own workspaces included
            return nobody
        membership = await self._workspace_user_repo.find_workspace_user(
            workspace_oid, user_oid
        )
        if membership is None or membership.disabled:
            return nobody
        workspace = await self._workspace_repo.find_by_id(workspace_oid)
        if workspace is None:
            return nobody
        is_owner = is_owner_membership(workspace, membership)
        if await self._sso_blocks(user, workspace, is_owner):
            if raise_sso_required:
                raise self._sso_required(user)
            return nobody
        if totp_blocks(workspace, user):
            # the workspace requires an authenticator app and this session has
            # not presented one (docs/totp.md): the same rule on every request
            if raise_sso_required:
                raise mfa_required_error()
            return nobody
        roles = {canonical_role(role) for role in (membership.roles or [])}
        base = dict(
            user_id=str(user_oid),
            workspace_id=str(workspace_oid),
            privileged=is_owner
            or has_owner_role(membership.roles)
            or WorkspaceRoles.ADMIN in roles,
            privacy_officer=WorkspaceRoles.PRIVACY_OFFICER in roles,
        )
        if workspace.disabled:
            return BaseAccess(
                permissions=(
                    DISABLED_WORKSPACE_OWNER_PERMISSIONS if is_owner else NO_PERMISSIONS
                ),
                workspace_disabled=True,
                **base,
            )
        return BaseAccess(
            permissions=permissions_for(membership.roles, is_owner=is_owner), **base
        )

    async def has_permission(
        self,
        user: Optional[User],
        permission: Permission,
        workspace_id: Union[RecordId, str, None],
        form_id: Optional[str] = None,
    ) -> bool:
        """Whether ``user`` holds ``permission`` in the workspace (and, with
        ``form_id``, the form belongs to it; while ``FORM_ACCESS_ENABLED`` is on
        the permission is the one held on that form, and a form closed to the
        user is no form of theirs)."""
        if permission not in await self.effective_permissions(
            user, workspace_id, form_id=form_id
        ):
            return False
        if form_id is not None:
            return await self._form_in_workspace(workspace_id, form_id)
        return True

    async def authorize(
        self,
        user: Optional[User],
        permission: Permission,
        workspace_id: Union[RecordId, str, None],
        form_id: Optional[str] = None,
        message: str = MESSAGE_FORBIDDEN,
    ) -> None:
        """403 unless ``user`` holds ``permission`` in the workspace; then,
        with ``form_id``, 404 unless the form belongs to the workspace (so
        only someone allowed in learns whether a form exists). A session that
        misses the workspace's single sign-on requirement gets 403
        ``sso_required`` instead, whatever the permission.

        While ``FORM_ACCESS_ENABLED`` is on, ``form_id`` also narrows or widens
        what the user holds (grants, restricted forms): a member the form is
        closed to gets the 404 of an unknown form, whatever the permission."""
        base = await self._base_access(user, workspace_id, raise_sso_required=True)
        decided: Optional[FormPermissions] = None
        if form_id is not None and form_access_enabled():
            decided = await self._form_permissions(base, form_id)
            if decided.hidden:
                raise HTTPException(HTTPStatus.NOT_FOUND, "Form not found in workspace")
        held = base.permissions if decided is None else decided.permissions
        if permission not in held:
            raise HTTPException(status_code=HTTPStatus.FORBIDDEN, content=message)
        if form_id is not None and not (
            decided is not None and decided.form_found
        ) and not await self._form_in_workspace(workspace_id, form_id):
            raise HTTPException(HTTPStatus.NOT_FOUND, "Form not found in workspace")

    async def _sso_blocks(self, user: User, workspace, is_owner: bool) -> bool:
        policy = self._sso_policy()
        if policy is None:
            # fail closed: never allow because the policy is not wired
            raise RuntimeError("AuthorizationService: the SSO policy is not wired")
        return await policy.blocks_session(
            workspace,
            getattr(user, "sub", None),
            getattr(user, "auth_method", None),
            getattr(user, "session_scope", None),
            is_owner,
            sso_workspace_id=getattr(user, "sso_workspace_id", None),
            sso_connection_id=getattr(user, "sso_connection_id", None),
            session_id=getattr(user, "sid", None),
            user_id=getattr(user, "id", None),
        )

    @staticmethod
    def _sso_required(user: User) -> HTTPException:
        # at call time: the policy module imports services that import this one
        from backend.app.services.domains.names import domain_of
        from backend.app.services.sso.policy import sso_required_error

        return sso_required_error(domain_of(getattr(user, "sub", "") or "") or "")

    async def is_owner(
        self,
        user: Optional[User],
        workspace_id: Union[RecordId, str, None],
        raise_sso_required: bool = False,
    ) -> bool:
        """Whether ``user`` is an owner of an available workspace (the
        billing owner or a member with role OWNER, every owner alike), with
        a full (not respondent-scoped) session and an active membership.
        Only owners hold every permission. ``raise_sso_required``: as for
        ``effective_permissions``."""
        held = await self.effective_permissions(
            user, workspace_id, raise_sso_required=raise_sso_required
        )
        return held == OWNER_PERMISSIONS

    async def require_owner(
        self,
        user: Optional[User],
        workspace_id: Union[RecordId, str, None],
        message: str = MESSAGE_FORBIDDEN,
    ) -> None:
        """403 unless ``user`` is an owner of the workspace. For decisions no
        role below Owner may take, like single sign-on configuration: it
        controls every account on the workspace's verified domains, the
        owners' own included. A session that misses the workspace's single
        sign-on requirement gets 403 ``sso_required`` instead."""
        if not await self.is_owner(user, workspace_id, raise_sso_required=True):
            raise HTTPException(status_code=HTTPStatus.FORBIDDEN, content=message)

    async def _form_in_workspace(self, workspace_id, form_id) -> bool:
        return bool(
            await self._workspace_form_repo.find_workspace_form(
                _object_id(workspace_id), str(form_id)
            )
        )
