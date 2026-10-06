import enum
from typing import Iterable, Optional


class WorkspaceRoles(str, enum.Enum):
    """A member's role in a workspace (docs/enterprise-access-model.md §2).

    A workspace can have several owners, all with the same rights: the
    *billing owner* (``workspace.owner_id``, whose plan the workspace runs
    on) and every member holding ``OWNER`` (see ``is_owner_membership``).
    ``COLLABORATOR`` is the stored spelling of ``EDITOR``: it is
    what every existing editor membership holds, and what an Editor is still
    stored as (see ``stored_role``), so a rollback to code that only knows
    ``ADMIN`` and ``COLLABORATOR`` keeps reading them. The API speaks
    ``EDITOR``.
    """

    # an owner besides the billing owner: every permission, billing included
    OWNER: str = "OWNER"
    ADMIN: str = "ADMIN"
    EDITOR: str = "EDITOR"
    REVIEWER: str = "REVIEWER"
    VIEWER: str = "VIEWER"
    PRIVACY_OFFICER: str = "PRIVACY_OFFICER"
    # legacy spelling of EDITOR, read as EDITOR everywhere
    COLLABORATOR: str = "COLLABORATOR"


# What the role picker offers, highest first. Only an owner gives OWNER (no
# one gives a role with more permissions than their own).
ASSIGNABLE_ROLES = (
    WorkspaceRoles.OWNER,
    WorkspaceRoles.ADMIN,
    WorkspaceRoles.EDITOR,
    WorkspaceRoles.REVIEWER,
    WorkspaceRoles.VIEWER,
    WorkspaceRoles.PRIVACY_OFFICER,
)

# The label a person sees (invitation mail, logs).
ROLE_LABELS = {
    WorkspaceRoles.OWNER: "Owner",
    WorkspaceRoles.ADMIN: "Admin",
    WorkspaceRoles.EDITOR: "Editor",
    WorkspaceRoles.REVIEWER: "Reviewer",
    WorkspaceRoles.VIEWER: "Viewer",
    WorkspaceRoles.PRIVACY_OFFICER: "Privacy officer",
}

OWNER_ROLE = WorkspaceRoles.OWNER.value


def canonical_role(role) -> Optional[WorkspaceRoles]:
    """The role ``role`` (an enum member or a stored string) stands for, or
    None for a role this code doesn't know. ``COLLABORATOR`` is ``EDITOR``."""
    try:
        value = WorkspaceRoles(role)
    except ValueError:
        return None
    return WorkspaceRoles.EDITOR if value == WorkspaceRoles.COLLABORATOR else value


def stored_role(role: WorkspaceRoles) -> WorkspaceRoles:
    """How ``role`` is written to ``workspace_users.roles`` and invitations:
    an Editor stays ``COLLABORATOR`` (no rewrite of existing rows, one
    spelling in storage, readable by the previous release)."""
    role = canonical_role(role)
    return WorkspaceRoles.COLLABORATOR if role == WorkspaceRoles.EDITOR else role


def canonical_roles(roles: Optional[Iterable]) -> list:
    """A membership's stored roles as the API reports them: ``[]`` (a legacy
    membership from before roles existed) is an Editor, ``COLLABORATOR`` is
    ``EDITOR`` and a role this code doesn't know is reported as it is."""
    if not roles:
        return [WorkspaceRoles.EDITOR.value]
    reported = []
    for role in roles:
        known = canonical_role(role)
        reported.append(known.value if known else str(role))
    return reported


def has_owner_role(roles: Optional[Iterable]) -> bool:
    """Whether stored ``roles`` hold ``OWNER``."""
    return any(canonical_role(role) == WorkspaceRoles.OWNER for role in roles or ())


def is_billing_owner(workspace, user_id) -> bool:
    """Whether ``user_id`` is the workspace's billing owner (``owner_id``)."""
    return (
        workspace is not None
        and user_id is not None
        and workspace.owner_id is not None
        and str(workspace.owner_id) == str(user_id)
    )


def is_owner_membership(workspace, membership) -> bool:
    """Whether ``membership`` (a ``workspace_users`` document of
    ``workspace``) is an owner's: the billing owner's, or one holding
    ``OWNER``. It says nothing about the membership being active; access
    also needs it enabled (``authorization_service``)."""
    if membership is None or workspace is None:
        return False
    return is_billing_owner(workspace, membership.user_id) or has_owner_role(
        membership.roles
    )


def primary_role(roles: Optional[Iterable], is_owner: bool = False) -> Optional[str]:
    """The one role the members list shows: ``OWNER`` for an owner, else the
    highest known role of the membership (an empty list is an Editor), None
    when none is known."""
    if is_owner:
        return OWNER_ROLE
    known = {canonical_role(role) for role in roles} if roles else {
        WorkspaceRoles.EDITOR
    }
    for role in ASSIGNABLE_ROLES:
        if role in known:
            return role.value
    return None
