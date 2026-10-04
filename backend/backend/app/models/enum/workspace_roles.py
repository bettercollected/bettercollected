import enum
from typing import Iterable, Optional


class WorkspaceRoles(str, enum.Enum):
    """A member's role in a workspace (docs/enterprise-access-model.md §2).

    The owner is not a role: it is ``workspace.owner_id`` with an active
    membership. ``COLLABORATOR`` is the stored spelling of ``EDITOR``: it is
    what every existing editor membership holds, and what an Editor is still
    stored as (see ``stored_role``), so a rollback to code that only knows
    ``ADMIN`` and ``COLLABORATOR`` keeps reading them. The API speaks
    ``EDITOR``.
    """

    ADMIN: str = "ADMIN"
    EDITOR: str = "EDITOR"
    REVIEWER: str = "REVIEWER"
    VIEWER: str = "VIEWER"
    PRIVACY_OFFICER: str = "PRIVACY_OFFICER"
    # legacy spelling of EDITOR, read as EDITOR everywhere
    COLLABORATOR: str = "COLLABORATOR"


# What the role picker offers, highest first. The owner is never assignable:
# ownership is transferred, not granted.
ASSIGNABLE_ROLES = (
    WorkspaceRoles.ADMIN,
    WorkspaceRoles.EDITOR,
    WorkspaceRoles.REVIEWER,
    WorkspaceRoles.VIEWER,
    WorkspaceRoles.PRIVACY_OFFICER,
)

# The label a person sees (invitation mail, logs).
ROLE_LABELS = {
    WorkspaceRoles.ADMIN: "Admin",
    WorkspaceRoles.EDITOR: "Editor",
    WorkspaceRoles.REVIEWER: "Reviewer",
    WorkspaceRoles.VIEWER: "Viewer",
    WorkspaceRoles.PRIVACY_OFFICER: "Privacy officer",
}

OWNER_ROLE = "OWNER"


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


def primary_role(roles: Optional[Iterable], is_owner: bool = False) -> Optional[str]:
    """The one role the members list shows: ``OWNER`` for the owner, else the
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
