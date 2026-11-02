"""The decision of a key on one form, as a pure function (every cell of its
table is a unit test); ``api_access`` feeds it.

    key's permissions on a form = the creator's current permissions there
                                  & the role ceiling
                                  & (listed keys) the ceiling of the key's row

Every term only ever narrows: a key never adds to its creator, a role never
adds to a row, a row never adds to a role. A role this code does not know and a
form scope this code does not know both fail closed.
"""

import dataclasses
from typing import FrozenSet, Iterable, Optional

from backend.app.models.enum.permission import Permission
from backend.app.models.enum.workspace_roles import WorkspaceRoles, canonical_role
from backend.app.schemas.form_access_grant import FormAccessGrantDocument
from backend.app.services.authorization_service import ROLE_PERMISSIONS
from backend.app.services.form_access.model import GRANT_PERMISSIONS, FormPermissions

# a key's form scope: every form its creator and role reach, or only the forms
# it holds a row for
SCOPE_ALL = "all"
SCOPE_LISTED = "listed"

# where a key's permissions on a form came from, when the key narrowed them
SOURCE_KEY = "key"

# The roles a key can have. Never Owner or Admin: the creator is one of them by
# construction, so "no role" (as its creator) already is the full set.
KEY_ROLES = (
    WorkspaceRoles.EDITOR,
    WorkspaceRoles.REVIEWER,
    WorkspaceRoles.VIEWER,
    WorkspaceRoles.PRIVACY_OFFICER,
)

# The scope that reads answers, and the permission a bulk read of answers is
# (api_access.SCOPE_PERMISSIONS): a Reviewer or Viewer role does not carry
# ``response.export``, so a key of that role gets it when, and only when, it
# carries this scope (the admin acknowledged what it hands out at creation).
RESPONSES_READ_SCOPE = "responses:read"
_READ_ONLY_ROLES = (WorkspaceRoles.REVIEWER, WorkspaceRoles.VIEWER)
_EXPORT = frozenset({Permission.RESPONSE_EXPORT})


def role_ceiling(
    role: Optional[str], scopes: Iterable[str] = ()
) -> Optional[FrozenSet[Permission]]:
    """The most a key of ``role`` may do. ``None``: no ceiling (no role, "as its
    creator"). A role that is not one of ``KEY_ROLES`` gives the empty set."""
    if role is None:
        return None
    known = canonical_role(role)
    if known not in KEY_ROLES:
        return frozenset()
    held = ROLE_PERMISSIONS[known]
    if known in _READ_ONLY_ROLES and RESPONSES_READ_SCOPE in set(scopes or ()):
        held = held | _EXPORT
    return held


def is_listed(form_scope: Optional[str]) -> bool:
    """Whether the key is limited to the forms it holds a row for. Anything but
    ``all`` is read as limited."""
    return form_scope != SCOPE_ALL


def row_ceiling(row_role: str, scopes: Iterable[str] = ()) -> FrozenSet[Permission]:
    """The most a key's row for a form allows there: what a grant of the row's
    role gives (never ``form.delete``), plus the export of the role ceiling's
    rule. A row role this code does not know allows nothing."""
    known = canonical_role(row_role)
    held = GRANT_PERMISSIONS.get(known.value, frozenset()) if known else frozenset()
    if known in _READ_ONLY_ROLES and RESPONSES_READ_SCOPE in set(scopes or ()):
        held = held | _EXPORT
    return held


def key_decision(
    creator: FormPermissions,
    *,
    ceiling: Optional[FrozenSet[Permission]],
    listed: bool,
    row: Optional[FormAccessGrantDocument],
    scopes: Iterable[str] = (),
) -> FormPermissions:
    """The key's permissions on one form.

    ``creator`` is the creator's own decision there (role, grants, the form's
    access mode); nothing the creator lacks is ever given back. A listed key
    with no row for the form gets a ``hidden`` decision, which every caller
    answers exactly as a form that does not exist."""
    if not creator.permissions:
        return creator
    held = creator.permissions
    if ceiling is not None:
        held = held & ceiling
    if listed:
        if row is None:
            return FormPermissions(
                frozenset(),
                SOURCE_KEY,
                restricted=creator.restricted,
                form_found=creator.form_found,
                hidden=True,
            )
        held = held & row_ceiling(row.role, scopes)
    if held == creator.permissions:
        return creator
    return dataclasses.replace(creator, permissions=held, source=SOURCE_KEY)
