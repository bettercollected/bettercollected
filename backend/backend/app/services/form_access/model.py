"""What the form-level decision takes in and gives back, and the tables that
define it (docs/enterprise-access-model.md, "Form-level scope").

The decision itself is :func:`resolve`: a pure function, so every cell of its
table is a unit test. ``FormAccessService`` only feeds it (the member's base
access, the form's facts, their grants).
"""

from dataclasses import dataclass
from typing import FrozenSet, Iterable, Optional

from backend.app.models.enum.permission import Permission
from backend.app.schemas.form_access_grant import (
    ROLE_EDITOR,
    ROLE_REVIEWER,
    ROLE_VIEWER,
    FormAccessGrantDocument,
)

P = Permission

# where a member's permissions on a form came from
SOURCE_ROLE = "role"
SOURCE_GRANT = "grant"
SOURCE_CREATOR = "creator"
# a restricted form the member has no way into
SOURCE_NONE = "none"

# The access modes stored in ``settings.access_mode`` (no column).
MODE_WORKSPACE = "workspace"
MODE_RESTRICTED = "restricted"

# The permissions that are about one form's content: what a grant can give and
# what a restricted form withholds. Everything else (workspace.*, members.*,
# security.*, ai.*, audit.read, privacy.manage, form.create, response.import)
# is about the workspace and is never granted per form.
FORM_SCOPED: FrozenSet[Permission] = frozenset(
    {
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

# What a grant gives, by its role: the same content permissions as the
# workspace role of that name, except that a grant never deletes the form
# (deleting drops its responses; it stays with the workspace Editor, Admin and
# Owner). A Reviewer or Viewer grant exports only with its ``export`` flag
# (which only owners and admins set); an Editor grant exports.
GRANT_PERMISSIONS = {
    ROLE_EDITOR: frozenset(
        {
            P.FORM_READ,
            P.FORM_EDIT,
            P.FORM_SHARE,
            P.RESPONSE_READ,
            P.RESPONSE_ANNOTATE,
            P.RESPONSE_EXPORT,
            P.RESPONSE_DELETE,
            P.RESPONSE_EDIT,
            P.ANALYTICS_READ,
        }
    ),
    ROLE_REVIEWER: frozenset(
        {P.FORM_READ, P.RESPONSE_READ, P.RESPONSE_ANNOTATE, P.ANALYTICS_READ}
    ),
    ROLE_VIEWER: frozenset({P.FORM_READ, P.RESPONSE_READ, P.ANALYTICS_READ}),
}
EXPORT_PERMISSIONS: FrozenSet[Permission] = frozenset({P.RESPONSE_EXPORT})

# A Privacy officer keeps, on a restricted form they hold no grant for (they
# never do: grants do not apply to them), the form's structure and the privacy
# programme, and no answer, no analytics and no change.
PRIVACY_OFFICER_ON_RESTRICTED: FrozenSet[Permission] = frozenset(
    {P.FORM_READ, P.PRIVACY_MANAGE, P.AUDIT_READ}
)


@dataclass(frozen=True)
class BaseAccess:
    """A member's workspace-level access, as ``AuthorizationService`` decided
    it (membership, single sign-on, authenticator app, disabled workspace and
    roles all applied): the input of the form-level decision.

    ``permissions`` is empty for anyone who is not an active, unblocked member:
    nothing here ever turns that into access."""

    user_id: str
    workspace_id: str
    permissions: FrozenSet[Permission]
    # an Owner (billing owner or role OWNER) or an Admin: always pass
    privileged: bool = False
    privacy_officer: bool = False
    workspace_disabled: bool = False


@dataclass(frozen=True)
class FormPermissions:
    """The permissions of a member on one form.

    ``field_rules`` is reserved for field-level access: what a rule narrows in
    the answers ``response.read`` returns. Nothing sets it yet."""

    permissions: FrozenSet[Permission]
    source: str = SOURCE_ROLE
    restricted: bool = False
    # the form is one of the workspace's (found while deciding)
    form_found: bool = False
    # the member holds ``form.read`` through their role and the form is closed
    # to them (restricted, no grant): to be answered like an unknown form
    hidden: bool = False
    field_rules: Optional[object] = None


def is_restricted(access_mode: Optional[str], hidden: Optional[bool]) -> bool:
    """Whether a form is restricted. An explicit mode always wins: only
    ``workspace`` opens a form to the roles, any other value (one a newer
    release wrote) is read as restricted, never as open. With no mode chosen,
    a Private form (``hidden``) is restricted."""
    if access_mode is None:
        return bool(hidden)
    return access_mode != MODE_WORKSPACE


def grant_permissions(grants: Iterable[FormAccessGrantDocument]) -> FrozenSet[Permission]:
    """The union of what the grants give. Each grant is capped by its role (a
    role this code does not know gives nothing) and ``export`` applies per
    grant."""
    given = set()
    for grant in grants:
        role = GRANT_PERMISSIONS.get(grant.role)
        if role is None:
            continue
        given |= role
        if grant.export and grant.role in (ROLE_REVIEWER, ROLE_VIEWER):
            given |= EXPORT_PERMISSIONS
    return frozenset(given)


def resolve(
    base: BaseAccess,
    *,
    restricted: bool,
    creator: bool,
    grants: Iterable[FormAccessGrantDocument],
) -> FormPermissions:
    """The member's permissions on one form (the form is known to exist).

    * Nothing at the base (not a member, blocked, disabled) stays nothing; in a
      disabled workspace nothing is raised; Owners and Admins always keep what
      their role gives.
    * Grants never apply to a Privacy officer ("never elevated") and give only
      form-scoped permissions, capped by the grant's role.
    * An open form: the role's permissions plus what the grants give.
    * A restricted form: only Owners, Admins, the creator and holders of a
      grant keep form-scoped permissions. The creator keeps what their own role
      gives (never more); a grant gives what it gives. A Privacy officer
      without a way in keeps the structure and the privacy programme.
    """
    held = base.permissions
    if not held or base.workspace_disabled or base.privileged:
        return FormPermissions(held, SOURCE_ROLE, restricted=restricted)
    granted = (
        frozenset() if base.privacy_officer else grant_permissions(grants)
    )
    if not restricted:
        extra = granted - held
        return FormPermissions(
            held | granted, SOURCE_GRANT if extra else SOURCE_ROLE
        )
    outside = held - FORM_SCOPED - {P.PRIVACY_MANAGE}
    if creator:
        return FormPermissions(held | granted, SOURCE_CREATOR, restricted=True)
    if granted:
        return FormPermissions(outside | granted, SOURCE_GRANT, restricted=True)
    if base.privacy_officer:
        kept = held & PRIVACY_OFFICER_ON_RESTRICTED
        return FormPermissions(
            kept | outside, SOURCE_ROLE, restricted=True,
        )
    return FormPermissions(
        outside,
        SOURCE_NONE,
        restricted=True,
        hidden=P.FORM_READ in held,
    )
