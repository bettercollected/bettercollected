"""Which workspace roles an IdP group may map to, and which one wins.

Roles are read from ``WorkspaceRoles`` at runtime, so roles added to the enum
(Editor, Reviewer, Viewer, Privacy officer) become mappable without a change
here. ADMIN may be mapped (an organisation's admin group); the owner never
comes from a directory (``OWNER``, should it become a role, is excluded).
"""

from typing import Iterable, List, Optional

from backend.app.models.enum.workspace_roles import WorkspaceRoles

# Highest first. A role missing here (added to the enum later) ranks below
# these, in enum order, so the outcome is always deterministic. Privacy
# officer and Viewer are not comparable (different permissions); Viewer
# wins because it is the common, least surprising one.
ROLE_ORDER = (
    "ADMIN",
    "EDITOR",
    "COLLABORATOR",
    "REVIEWER",
    "VIEWER",
    "PRIVACY_OFFICER",
)
NEVER_MAPPED = frozenset({"OWNER"})


def mappable_roles() -> List[str]:
    return [role.value for role in WorkspaceRoles if role.value not in NEVER_MAPPED]


def is_mappable(role: Optional[str]) -> bool:
    return role in mappable_roles()


def _rank(role: str):
    if role in ROLE_ORDER:
        return (0, ROLE_ORDER.index(role))
    names = [r.value for r in WorkspaceRoles]
    return (1, names.index(role) if role in names else len(names))


def highest_role(roles: Iterable[Optional[str]]) -> Optional[str]:
    """The highest mappable role among ``roles``, or None."""
    valid = [r for r in roles if is_mappable(r)]
    return min(valid, key=_rank) if valid else None
