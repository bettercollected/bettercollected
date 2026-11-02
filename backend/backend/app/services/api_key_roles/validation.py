"""What a key's role, form scope and form list may be, validated when a key is
made or edited (docs/enterprise-access-model.md, section 4). Pure: no storage.

Every refusal is a 400 with a stable ``code``, naming the scope that does not
fit and nothing a caller supplied beyond it.
"""

from http import HTTPStatus
from typing import FrozenSet, Iterable, List, Optional

from backend.app.exceptions import HTTPException
from backend.app.models.enum.permission import Permission
from backend.app.models.enum.workspace_roles import WorkspaceRoles, canonical_role
from backend.app.schemas.form_access_grant import (
    ROLE_EDITOR,
    ROLE_REVIEWER,
    ROLE_VIEWER,
)
from backend.app.services.api_key_roles.model import (
    KEY_ROLES,
    SCOPE_ALL,
    SCOPE_LISTED,
    role_ceiling,
    row_ceiling,
)

# the scopes a key limited to a list of forms never carries: a grant on a form
# never holds ``form.delete`` or ``privacy.manage``
LISTED_REFUSED_SCOPES = (
    "forms:delete",
    "deletion_requests:read",
    "deletion_requests:write",
)
FORM_SCOPES = (SCOPE_ALL, SCOPE_LISTED)

_ROW_ROLES = {
    WorkspaceRoles.EDITOR: ROLE_EDITOR,
    WorkspaceRoles.REVIEWER: ROLE_REVIEWER,
    WorkspaceRoles.VIEWER: ROLE_VIEWER,
    # no grant carries the privacy programme: a listed Privacy officer key reads
    # forms only (deletion requests are refused on a listed key)
    WorkspaceRoles.PRIVACY_OFFICER: ROLE_VIEWER,
}


def refuse(code: str, message: str, status: int = HTTPStatus.BAD_REQUEST):
    raise HTTPException(status_code=status, content={"code": code, "message": message})


def normalise_role(role: Optional[str]) -> Optional[str]:
    """The stored spelling of a key role (``None``: as its creator), or 400."""
    if role is None:
        return None
    known = canonical_role(str(role).strip().upper())
    if known not in KEY_ROLES:
        refuse(
            "invalid_key_role",
            "role must be one of "
            + ", ".join(r.value for r in KEY_ROLES)
            + ", or null for as its creator.",
        )
    return known.value


def normalise_form_scope(form_scope: Optional[str]) -> str:
    if form_scope is None:
        return SCOPE_ALL
    value = str(form_scope).strip().lower()
    if value not in FORM_SCOPES:
        refuse("invalid_form_scope", "formScope must be 'all' or 'listed'.")
    return value


def row_role_for(role: Optional[str]) -> str:
    """The role a key's rows are written with: the ceiling of a row for the key's
    role (an Editor grant for a key with no role of its own: it never holds
    ``form.delete``, and the creator and role narrow it further)."""
    known = canonical_role(role) if role is not None else WorkspaceRoles.EDITOR
    return _ROW_ROLES.get(known, ROLE_VIEWER)


def ceiling_set(role: Optional[str], scopes: Iterable[str]) -> FrozenSet[Permission]:
    """What a key of ``role`` may do at most, as a set (no role: everything)."""
    held = role_ceiling(role, scopes)
    return frozenset(Permission) if held is None else held


def check_matrix(role: Optional[str], form_scope: str, scopes: Iterable[str]) -> None:
    """400 when a scope of the key cannot be carried by its role, or by a list of
    forms. A stored combination that later stops being valid is not rewritten:
    this only ever runs on what is being set."""
    from backend.app.services.api_access import SCOPE_PERMISSIONS

    scopes = sorted(set(scopes))
    ceiling = role_ceiling(role, scopes)
    listed = form_scope == SCOPE_LISTED
    for scope in scopes:
        if listed and scope in LISTED_REFUSED_SCOPES:
            refuse(
                "scope_not_allowed_for_listed_key",
                f"A key limited to forms cannot carry the scope '{scope}'.",
            )
        needed = set(SCOPE_PERMISSIONS[scope])
        if ceiling is not None and not needed <= ceiling:
            refuse(
                "scope_not_allowed_by_role",
                f"This role cannot carry the scope '{scope}'.",
            )
        if listed and not needed <= row_ceiling(row_role_for(role), scopes):
            refuse(
                "scope_not_allowed_by_role",
                f"This role cannot carry the scope '{scope}' on a list of forms.",
            )


def widens_role(old: Optional[str], new: Optional[str], scopes: Iterable[str]) -> bool:
    """Whether ``new`` lets the key do something ``old`` did not."""
    return not ceiling_set(new, scopes) <= ceiling_set(old, scopes)


def unique_ids(form_ids: Optional[Iterable[str]]) -> List[str]:
    return sorted({str(f).strip() for f in (form_ids or ())})
