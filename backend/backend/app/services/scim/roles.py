"""Which workspace roles an IdP group may map to, and which one wins.

Roles are read from ``WorkspaceRoles`` at runtime, so a role added to the
enum becomes mappable without a change here. ADMIN may be mapped (an
organisation's admin group); an owner never comes from a directory
(``OWNER`` is refused, and owners are never changed by it).
``COLLABORATOR`` is the stored spelling of EDITOR and is accepted as EDITOR.
"""

from typing import Iterable, List, Optional

from backend.app.models.enum.workspace_roles import WorkspaceRoles, canonical_role

# Highest first. A role missing here (added to the enum later) ranks below
# these, in enum order, so the outcome is always deterministic. Privacy
# officer and Viewer are not comparable (different permissions); Viewer
# ranks higher because a Privacy officer never reads answers, and a person
# in both kinds of group most likely needs to.
ROLE_ORDER = ("ADMIN", "EDITOR", "REVIEWER", "VIEWER", "PRIVACY_OFFICER")
NEVER_MAPPED = frozenset({"OWNER"})


def mappable_roles() -> List[str]:
    """Every role in the enum but the owner, in its API spelling."""
    found: List[str] = []
    for role in WorkspaceRoles:
        known = canonical_role(role)
        if known is not None and known.value not in NEVER_MAPPED:
            if known.value not in found:
                found.append(known.value)
    return sorted(found, key=_rank)


def to_mappable(role: Optional[str]) -> Optional[str]:
    """``role`` in its API spelling when a group may map to it, else None."""
    known = canonical_role(role) if role else None
    if known is None or known.value in NEVER_MAPPED:
        return None
    return known.value


def is_mappable(role: Optional[str]) -> bool:
    return to_mappable(role) is not None


def _rank(role: str):
    if role in ROLE_ORDER:
        return (0, ROLE_ORDER.index(role))
    names = [r.value for r in WorkspaceRoles]
    return (1, names.index(role) if role in names else len(names))


def highest_role(roles: Iterable[Optional[str]]) -> Optional[str]:
    """The highest mappable role among ``roles`` (API spelling), or None."""
    valid = [r for r in (to_mappable(role) for role in roles) if r]
    return min(valid, key=_rank) if valid else None
